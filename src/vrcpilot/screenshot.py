"""Single-shot VRChat screenshot API for GUI automation.

Companion to :mod:`vrcpilot.capture` (continuous frames for video).
Where :class:`vrcpilot.capture.Capture` is built for streaming frames at
high rate and tolerates occluded windows, :func:`take_screenshot` is the
right tool when an automation step needs **one** snapshot together with
the on-screen geometry — for instance, to compute click coordinates,
hand a region to OCR, or diff a static UI state across runs.

The implementation deliberately differs from the streaming path: it
calls :func:`vrcpilot.window.focus`, waits a short settle interval for
the compositor to finish raising the window, then grabs the pixels via
:mod:`mss`. The same code path is used on Windows and Linux for parity.

Failures along the way (VRChat not running, focus refused by the OS,
window not yet mapped, transient ``mss`` errors) are surfaced as
``None`` rather than raised, so polling callers — for example, a loop
waiting for VRChat to finish loading — can simply retry without having
to special-case every failure mode. Programming errors such as
unsupported platforms or invalid arguments still raise.

Native Wayland sessions are also returned as ``None`` (with a
``RuntimeWarning``). This is asymmetric with :class:`Capture`, which
raises on Wayland: a one-shot polling caller is happy to retry until
the user moves to an X11 session, but a streaming session has no
useful behaviour to fall back to.
"""

from __future__ import annotations

import sys
import time
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import mss
import numpy as np
from numpy.typing import NDArray

from vrcpilot._backends.geometry import get_vrchat_window_rect
from vrcpilot._x11 import is_wayland_native
from vrcpilot.window import focus


@dataclass(frozen=True, eq=False)
class Screenshot:
    """A single VRChat screenshot together with its on-screen geometry.

    Returned by :func:`take_screenshot`. The ``image`` field is the raw
    pixel data; the geometry fields describe **where** on the user's
    desktop those pixels live, which is what lets callers translate
    in-image coordinates to absolute desktop coordinates — for clicking
    a button found via template matching, for example, or to feed
    consistent crops to OCR across calls.

    A typical click-coordinate calculation looks like::

        shot = vrcpilot.take_screenshot()
        # ``cx_in_image, cy_in_image`` come from CV / template matching
        screen_x = shot.x + cx_in_image
        screen_y = shot.y + cy_in_image

    The instance is frozen (use :func:`dataclasses.replace` to derive a
    modified copy). Equality is disabled (``eq=False``) because numpy's
    element-wise ``__eq__`` does not return a bool and so cannot back
    a dataclass-synthesised ``__eq__``; identity comparison still works.

    Attributes:
        image: ``(H, W, 3)`` ``uint8`` ndarray in RGB order. Detached
            from any internal mss buffer — safe to retain, mutate in
            place, or hand to ``PIL.Image.fromarray``.
        x: Window-frame left edge in absolute desktop pixels. May be
            negative on multi-monitor layouts where VRChat lives on a
            monitor placed left of (or above) the primary.
        y: Window-frame top edge in absolute desktop pixels. May be
            negative for the same reason.
        width: Window-frame width in physical pixels. Matches
            ``image.shape[1]`` under normal conditions.
        height: Window-frame height in physical pixels. Matches
            ``image.shape[0]`` under normal conditions.
        monitor_index: Index into ``mss.MSS().monitors`` of the monitor
            whose rectangle contains the window's centre point. ``0``
            is the synthetic "all monitors" composite; ``1..N`` are the
            individual monitors in mss enumeration order. Falls back
            to ``0`` only if the centre point lies outside every
            individual monitor (defensive — should not occur in
            practice once the window is focused).
        captured_at: UTC timestamp recorded immediately after the
            ``mss`` grab returned. Use ``.astimezone()`` to convert
            to local time.
    """

    image: NDArray[np.uint8]
    x: int
    y: int
    width: int
    height: int
    monitor_index: int
    captured_at: datetime


def _resolve_monitor_index(
    rect: tuple[int, int, int, int],
    monitors: Sequence[Mapping[str, Any]],
) -> int:
    """Return the index of the monitor containing *rect*'s center.

    Iterates ``monitors[1:]`` (the per-monitor entries; index 0 is the
    synthetic "all monitors" composite) and returns the first whose
    rectangle contains the center point ``(x + w//2, y + h//2)``.

    Falls back to ``0`` (the composite) when the center point lies
    outside every individual monitor — defensive only, since a focused
    VRChat window normally has its center on some monitor.
    """
    x, y, width, height = rect
    cx = x + width // 2
    cy = y + height // 2
    for i, mon in enumerate(monitors[1:], start=1):
        left = int(mon["left"])
        top = int(mon["top"])
        right = left + int(mon["width"])
        bottom = top + int(mon["height"])
        if left <= cx < right and top <= cy < bottom:
            return i
    return 0


def take_screenshot(*, settle_seconds: float = 0.05) -> Screenshot | None:
    """Focus VRChat, wait briefly, then grab a single window-only screenshot.

    Use this when a workflow needs **one** snapshot together with the
    window's on-screen position — most GUI automation falls into this
    category. For continuous frame streaming use
    :class:`vrcpilot.capture.Capture` instead, which avoids the focus
    step entirely.

    The call performs five steps in order: platform check, focus
    (raising VRChat), short settle sleep, window-rectangle lookup, and
    finally an :mod:`mss` grab over that rectangle. The focus step is
    what makes this API distinct from ``Capture`` — bringing the window
    to the foreground guarantees that the captured pixels match what
    the user sees, which is the right trade-off for click-coordinate
    workflows but the wrong one for long-running observation.

    Args:
        settle_seconds: Seconds to wait between focusing and grabbing,
            giving the compositor time to finish drawing the raised
            window. The 50 ms default is a generous margin for typical
            desktops; pass ``0`` to skip the wait when the window is
            already known to be on top, or raise it for sluggish remote
            sessions. Must be ``>= 0``.

    Raises:
        NotImplementedError: When called on a platform other than
            Windows or Linux.
        ValueError: When ``settle_seconds`` is negative.

    Returns:
        A :class:`Screenshot` on success, or ``None`` on any of the
        recoverable failure modes below — ``None`` rather than an
        exception so that polling callers (e.g. waiting for VRChat to
        finish loading) can retry without catching.

        ``None`` is returned when:

        - The session is native Wayland (a ``RuntimeWarning`` is also
          emitted; see the module docstring for why this asymmetry
          with :class:`Capture` exists).
        - :func:`vrcpilot.window.focus` returns ``False`` (VRChat not
          running, window not yet mapped, or OS refused the focus
          request).
        - The window rectangle cannot be resolved (the window
          disappeared between focus and the geometry query).
        - :mod:`mss` raises :class:`mss.ScreenShotError` during the
          grab (transient X / GDI failure).
    """
    if settle_seconds < 0:
        raise ValueError("settle_seconds must be >= 0")

    # 1. Platform check
    if sys.platform == "linux":
        if is_wayland_native():
            warnings.warn(
                "Wayland native session detected; "
                "take_screenshot() requires X11 or XWayland.",
                RuntimeWarning,
                stacklevel=2,
            )
            return None
    elif sys.platform != "win32":
        raise NotImplementedError(
            f"take_screenshot() is not supported on {sys.platform}"
        )

    # 2. Focus
    if not focus():
        return None

    # 3. Settle
    time.sleep(settle_seconds)

    # 4. Window rectangle
    rect = get_vrchat_window_rect()
    if rect is None:
        return None
    x, y, width, height = rect

    # 5. mss grab + metadata.
    #
    # We hold the ``MSS`` instance in a local and call ``close()`` explicitly
    # (rather than ``with mss.MSS() as sct:``) so test fakes can be plain
    # ``mocker.Mock`` objects without having to also implement the context
    # manager protocol.
    sct = mss.MSS()
    try:
        region = {"left": x, "top": y, "width": width, "height": height}
        try:
            shot = sct.grab(region)
        except mss.ScreenShotError:
            return None
        captured_at = datetime.now(timezone.utc)
        # ``shot.rgb`` is a freshly-allocated bytes object derived from the
        # raw BGRA buffer; reshape via numpy and ``.copy()`` to detach from
        # the mss-owned buffer before ``sct.close()`` runs.
        image: NDArray[np.uint8] = (
            np.frombuffer(shot.rgb, dtype=np.uint8)
            .reshape(shot.size.height, shot.size.width, 3)
            .copy()
        )
        monitor_index = _resolve_monitor_index((x, y, width, height), sct.monitors)
    finally:
        sct.close()

    return Screenshot(
        image=image,
        x=x,
        y=y,
        width=width,
        height=height,
        monitor_index=monitor_index,
        captured_at=captured_at,
    )
