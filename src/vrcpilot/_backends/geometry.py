"""Platform-agnostic VRChat window geometry lookup.

Wraps the Win32 (:mod:`vrcpilot._win32`) and X11 (:mod:`vrcpilot._x11`)
helpers behind a single :func:`get_vrchat_window_rect` entry point so
callers (e.g. :mod:`vrcpilot.screenshot`) do not have to branch on
``sys.platform`` themselves.

The function is intentionally narrow: it returns the VRChat window's
``(x, y, width, height)`` rectangle on success, or ``None`` for any
recoverable failure (VRChat not running, window not yet mapped, X11
display unavailable). Wayland detection is **not** performed here -
that is a screenshot/capture-level concern, since Wayland still allows
process and window discovery; it just blocks pixel grabs.
"""

from __future__ import annotations

import sys

from vrcpilot._x11 import (
    find_vrchat_window,
    get_window_rect as _x11_get_window_rect,
    open_x11_display,
)
from vrcpilot.process import find_pid

if sys.platform == "win32":
    from vrcpilot._win32 import (
        find_vrchat_hwnd,
        get_window_rect as _win32_get_window_rect,
    )


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
    function leaves no X resources behind - callers that need a single
    geometry lookup pay only for the connection's lifetime.
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


def get_vrchat_window_rect() -> tuple[int, int, int, int] | None:
    """Return the VRChat window rectangle for the current platform.

    Dispatches to the Win32 helper on Windows and the X11 helper on
    Linux, returning ``(x, y, width, height)`` in absolute desktop
    pixels. Returns ``None`` when VRChat is not running, the window
    cannot be located, or the platform-specific geometry query fails.

    Raises:
        NotImplementedError: When invoked on a platform other than
            Windows or Linux. Callers that already perform their own
            platform guard (e.g. :func:`vrcpilot.take_screenshot`) will
            never reach this branch, but the exception is still raised
            here so direct callers fail loudly instead of silently
            returning ``None``.
    """
    if sys.platform == "win32":
        return _get_vrchat_rect_win32()
    if sys.platform == "linux":
        return _get_vrchat_rect_x11()
    raise NotImplementedError(
        f"get_vrchat_window_rect() is not supported on {sys.platform}"
    )
