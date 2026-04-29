"""Win32 helpers shared between window control and screen capture.

Both :mod:`vrcpilot.window` (focus / unfocus) and
:mod:`vrcpilot.capture` (take_screenshot) need to locate the VRChat
top-level window by PID. Centralising that primitive here keeps the
two modules from duplicating the ``EnumWindows`` boilerplate.
"""

from __future__ import annotations

import sys

if sys.platform == "win32":
    import pywintypes
    import win32gui
    import win32process


def find_vrchat_hwnd(pid: int) -> int | None:
    """Return the visible top-level HWND owned by *pid*.

    Walks every top-level window via :func:`win32gui.EnumWindows` and
    returns the first one whose owning process id matches *pid* and
    which is currently visible (``IsWindowVisible``). Returns ``None``
    when no matching visible window is found — for example, when the
    process has been spawned but its main window has not yet been
    created, or when the window is hidden.

    Args:
        pid: Process id to match against the window's owning process.

    Returns:
        The HWND of the first matching visible top-level window, or
        ``None`` if no such window exists.
    """
    if sys.platform != "win32":
        # Defensive: callers gate on ``sys.platform`` before invoking. This
        # branch also narrows the win32* names for pyright on POSIX runs.
        raise RuntimeError("unreachable")

    result: list[int] = []

    def _callback(hwnd: int, _lparam: int) -> bool:
        # Always continue enumeration. Returning False to stop early
        # makes pywin32 raise a spurious ``EnumWindows`` access-denied
        # error (Win32 interprets False as a callback failure and
        # surfaces GetLastError); enumerating fully is cheap enough.
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid == pid and win32gui.IsWindowVisible(hwnd):
            result.append(hwnd)
        return True

    win32gui.EnumWindows(_callback, 0)
    return result[0] if result else None


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return ``(x, y, width, height)`` of *hwnd* in physical screen pixels.

    Wraps :func:`win32gui.GetWindowRect`, which yields ``(left, top,
    right, bottom)`` for the outer window frame. The result is converted
    to origin + size form for parity with :func:`vrcpilot._x11.get_window_rect`.

    VRChat (Unity) is per-monitor DPI aware, so the rect is already in
    physical pixels and matches what :mod:`mss` grabs without any scaling
    correction.

    Args:
        hwnd: Window handle to query.

    Returns:
        ``(x, y, width, height)`` on success, or ``None`` when the HWND
        has been destroyed (``pywintypes.error``) or the rectangle is
        degenerate (non-positive width or height).
    """
    if sys.platform != "win32":
        # Defensive narrow for pyright on POSIX runs.
        raise RuntimeError("unreachable")

    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    except pywintypes.error:
        return None
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    return (int(left), int(top), int(width), int(height))
