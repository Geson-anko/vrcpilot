"""Single-shot VRChat screenshot API for GUI automation.

Companion to :mod:`vrcpilot.capture` (continuous frames for video
recording). Where ``Capture`` is built for streaming frames at high rate
and tolerates occluded windows, ``take_screenshot`` is the right tool
when an automation step needs **one** accurate snapshot together with
the on-screen geometry — for instance, to compute click coordinates or
diff a UI region across frames.

The implementation deliberately differs from the streaming path: it
calls :func:`vrcpilot.window.focus`, waits a short settle interval for
the compositor to finish raising the window, then grabs the pixels via
:mod:`mss`. The same code path is used on Windows and Linux for parity.

Native Wayland sessions are not supported (a ``RuntimeWarning`` is
emitted and ``None`` is returned).
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
import mss.base
import mss.exception
import mss.models
import mss.screenshot
import numpy as np
from numpy.typing import NDArray

from vrcpilot._x11 import (
    find_vrchat_window,
    get_window_rect as _x11_get_window_rect,
    is_wayland_native,
    open_x11_display,
)
from vrcpilot.process import find_pid
from vrcpilot.window import focus

if sys.platform == "win32":
    from vrcpilot._win32 import (
        find_vrchat_hwnd,
        get_window_rect as _win32_get_window_rect,
    )


@dataclass(frozen=True, eq=False)
class Screenshot:
    """A single VRChat screenshot together with its on-screen geometry.

    Returned by :func:`take_screenshot`. The ``image`` field is the raw
    pixel data; the rest describe **where** on the user's desktop those
    pixels were captured from, which is what makes this API useful for
    GUI automation (click-coordinate calculation, region diffing, etc.).

    Equality is disabled (``eq=False``) because numpy arrays use
    element-wise ``__eq__`` semantics that interact poorly with frozen
    dataclasses' synthesized ``__hash__``. Identity comparison still
    works.

    Attributes:
        image: ``(H, W, 3)`` ``uint8`` ndarray in RGB order. Independent
            of any internal mss buffer — safe to keep, mutate, or pass
            to PIL via ``Image.fromarray``.
        x: Window-frame left edge in physical screen pixels. May be
            negative on multi-monitor layouts where VRChat lives on a
            monitor placed left of (or above) the primary.
        y: Window-frame top edge in physical screen pixels. May be
            negative for the same reason.
        width: Window-frame width in physical pixels.
        height: Window-frame height in physical pixels.
        monitor_index: Index into ``mss.MSS().monitors`` of the monitor
            whose region contains the window's center point. ``0`` is
            the synthetic "all monitors" entry; ``1..N`` are the
            individual monitors. Falls back to ``0`` if the center
            point lies outside every individual monitor.
        captured_at: UTC timestamp recorded immediately after the
            ``mss`` grab returned. Use ``.astimezone()`` to convert.
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


def _get_vrchat_rect_win32() -> tuple[int, int, int, int] | None:
    """Win32 path: ``find_pid`` -> ``find_vrchat_hwnd`` -> ``get_window_rect``."""
    if sys.platform != "win32":
        # Defensive narrow for pyright on POSIX runs.
        raise RuntimeError("unreachable")
    pid = find_pid()
    if pid is None:
        return None
    hwnd = find_vrchat_hwnd(pid)
    if hwnd is None:
        return None
    return _win32_get_window_rect(hwnd)


def _get_vrchat_rect_x11() -> tuple[int, int, int, int] | None:
    """X11 path: open display, locate the VRChat window, query geometry.

    The display is opened locally and closed before returning so the
    function leaves no X resources behind — Screenshot is a single-shot
    API, unlike :class:`vrcpilot.capture.Capture` which keeps a long-
    lived display connection.
    """
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")
    pid = find_pid()
    if pid is None:
        return None
    display = open_x11_display()
    if display is None:
        return None
    try:
        window = find_vrchat_window(display, pid)
        if window is None:
            return None
        return _x11_get_window_rect(display, window)
    finally:
        display.close()


def take_screenshot(*, settle_seconds: float = 0.05) -> Screenshot | None:
    """Focus VRChat, wait briefly, then grab a single window-only screenshot.

    The call performs five steps in order:

    1. Validate the platform (Windows or Linux only; native Wayland is
       rejected).
    2. Call :func:`vrcpilot.window.focus` to raise the VRChat window.
    3. Sleep ``settle_seconds`` so the compositor has time to draw.
    4. Read the window's current screen rectangle via the platform
       helper in :mod:`vrcpilot._win32` / :mod:`vrcpilot._x11`.
    5. Grab the pixels with :mod:`mss`, time-stamp the capture, and
       resolve which monitor the window is on.

    Failures along the way are reported as ``None`` rather than raised
    so polling automation (waiting for VRChat to finish loading, for
    instance) can simply retry.

    Args:
        settle_seconds: Seconds to wait between focusing and grabbing.
            The default (50 ms) covers typical compositor redraw
            latency. Pass ``0`` to skip the wait when you know the
            window is already on top. Must be ``>= 0``.

    Raises:
        NotImplementedError: When called on a platform other than
            Windows or Linux.
        ValueError: When ``settle_seconds`` is negative.

    Returns:
        A :class:`Screenshot` on success. ``None`` on Wayland native
        (a ``RuntimeWarning`` is also emitted), when ``focus()``
        returns ``False``, when the window rectangle cannot be
        resolved, or when ``mss`` raises
        :class:`mss.exception.ScreenShotError` during the grab.
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
    if sys.platform == "win32":
        rect = _get_vrchat_rect_win32()
    else:
        rect = _get_vrchat_rect_x11()
    if rect is None:
        return None
    x, y, width, height = rect

    # 5. mss grab + metadata
    sct: mss.base.MSS = mss.MSS()
    try:
        region = {"left": x, "top": y, "width": width, "height": height}
        try:
            shot: mss.screenshot.ScreenShot = sct.grab(region)
        except mss.exception.ScreenShotError:
            return None
        captured_at = datetime.now(timezone.utc)
        # ``shot.rgb`` is a freshly-allocated bytes object derived from the
        # raw BGRA buffer; reshape via numpy and ``.copy()`` to detach from
        # any internal mss state before the context manager closes.
        rgb_bytes: bytes = shot.rgb
        image: NDArray[np.uint8] = (
            np.frombuffer(rgb_bytes, dtype=np.uint8)
            .reshape(shot.size.height, shot.size.width, 3)
            .copy()
        )
        monitors: list[mss.models.Monitor] = sct.monitors
        monitor_index = _resolve_monitor_index((x, y, width, height), monitors)
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
