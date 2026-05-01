"""Single-shot VRChat window screenshot for GUI automation.

For continuous frames use :mod:`vrcpilot.capture`. This module focuses
VRChat first to guarantee captured pixels match what the user sees,
accepting the latency cost in exchange for accurate click coordinates.
Recoverable failures return ``None`` so polling callers can retry.
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

from vrcpilot.geometry import get_vrchat_window_rect
from vrcpilot.session import is_wayland_native
from vrcpilot.window import focus


@dataclass(frozen=True, eq=False)
class Screenshot:
    """VRChat window pixel data plus its on-screen geometry.

    ``eq=False`` because numpy element-wise ``__eq__`` does not return a
    bool and so cannot back a dataclass-synthesised ``__eq__``. Frozen;
    use :func:`dataclasses.replace` for derived copies.

    Attributes:
        image: ``(H, W, 3)`` ``uint8`` ndarray in RGB. Detached copy.
        x, y: Window-frame top-left in absolute desktop pixels. May be
            negative on multi-monitor layouts.
        width, height: Window-frame size in physical pixels.
        monitor_index: Index into ``mss.MSS().monitors`` (``0`` is the
            composite, ``1..N`` are individual monitors). Falls back to
            ``0`` when the window centre lies outside every monitor.
        captured_at: UTC timestamp of the grab.
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
    """Return the mss-monitor index containing *rect*'s centre, or ``0``."""
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
    """Focus VRChat, wait, then grab one window-only screenshot.

    Args:
        settle_seconds: Sleep between focus and grab, giving the
            compositor time to finish raising the window. Must be
            ``>= 0``. Default 50 ms is a generous margin for typical
            desktops.

    Raises:
        NotImplementedError: Platform other than Windows or Linux.
        ValueError: ``settle_seconds`` is negative.

    Returns:
        :class:`Screenshot` on success, ``None`` on recoverable failure
        (Wayland native, focus refused, window unmapped, ``mss``
        error). Wayland native also emits :class:`RuntimeWarning`; this
        asymmetry with :class:`Capture` (which raises) lets polling
        callers retry while streaming sessions fail loudly.
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
