"""Win32 helpers shared between window control and screen capture.

Both :mod:`vrcpilot.window` (focus / unfocus) and
:mod:`vrcpilot.capture` (take_screenshot) need to locate the VRChat
top-level window by PID. Centralising that primitive here keeps the
two modules from duplicating the ``EnumWindows`` boilerplate.
"""

from __future__ import annotations

import ctypes
import sys

if sys.platform == "win32":
    import pywintypes
    import win32gui
    import win32process

    # Configure ``SetThreadDpiAwarenessContext`` once at import time so we do
    # not repeat the assignment on every ``get_window_rect`` call. Explicit
    # argtypes / restype are required so that the 64-bit
    # ``DPI_AWARENESS_CONTEXT`` handle is not truncated to 32 bits when
    # ctypes marshals the Python int via the default ``c_int`` rule.
    ctypes.windll.user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    ctypes.windll.user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p


# DPI awareness context handle for ``SetThreadDpiAwarenessContext``.
#
# ``-4`` is the documented pseudo-handle for ``PER_MONITOR_AWARE_V2``.
# See: https://learn.microsoft.com/en-us/windows/win32/api/windef/ne-windef-dpi_awareness_context
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


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

    The current thread is switched to per-monitor DPI aware (V2) for the
    duration of the call via ``SetThreadDpiAwarenessContext`` so that
    ``GetWindowRect`` returns physical pixel coordinates that match what
    :mod:`mss` grabs. The previous context is restored in ``finally`` to
    keep the change scoped to this call. A thread-local toggle is used
    rather than process-wide DPI awareness so that no other code in the
    process is affected.

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

    set_thread_dpi = ctypes.windll.user32.SetThreadDpiAwarenessContext
    old_ctx = set_thread_dpi(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    try:
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except pywintypes.error:
            return None
    finally:
        set_thread_dpi(old_ctx)

    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    return (int(left), int(top), int(width), int(height))
