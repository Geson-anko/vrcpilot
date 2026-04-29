"""VRChat window control API.

Public entry points for focusing and unfocusing the running VRChat
client window. Companion to :mod:`vrcpilot.process` — once VRChat is
launched and observed (via :func:`vrcpilot.find_pid`), use
:func:`focus` / :func:`unfocus` to drive its z-order from automation.

Currently Windows-only; calling on other platforms raises
:class:`NotImplementedError`.
"""

from __future__ import annotations

import sys

from vrcpilot.process import find_pid

if sys.platform == "win32":
    import pywintypes
    import win32api
    import win32con
    import win32gui
    import win32process


def _find_vrchat_hwnd(pid: int) -> int | None:
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
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid == pid and win32gui.IsWindowVisible(hwnd):
            result.append(hwnd)
            return False
        return True

    win32gui.EnumWindows(_callback, 0)
    return result[0] if result else None


def focus() -> bool:
    """Bring the running VRChat window to the foreground.

    Restores the window if it is currently minimized. Assumes Desktop
    mode — has no visible effect when VRChat is in VR exclusive mode.

    Raises:
        NotImplementedError: When called on a non-Windows platform.

    Returns:
        ``True`` on success, ``False`` when VRChat is not running, no
        matching window can be located, or the underlying Win32 call
        fails.
    """
    if sys.platform != "win32":
        # TODO: Linux 対応 (X11/Wayland)
        raise NotImplementedError("focus() is only supported on Windows")

    pid = find_pid()
    if pid is None:
        return False

    hwnd = _find_vrchat_hwnd(pid)
    if hwnd is None:
        return False

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Press/release Alt to defeat Windows' SetForegroundWindow lock —
        # without an active input event from this process the OS may refuse
        # to change the foreground window. types-pywin32 stubs leave the
        # first two positional args untyped, so silence the unknown-arg
        # warning rather than weakening the rest of the module.
        win32api.keybd_event(  # pyright: ignore[reportUnknownMemberType]
            win32con.VK_MENU, 0, 0, 0
        )
        try:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
        finally:
            win32api.keybd_event(  # pyright: ignore[reportUnknownMemberType]
                win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0
            )
    except pywintypes.error:
        return False
    return True


def unfocus() -> bool:
    """Send the running VRChat window to the bottom of the z-order.

    Removes the window from the foreground without minimizing it or
    activating another window. Useful for hiding VRChat behind other
    applications while keeping it running and rendering.

    Raises:
        NotImplementedError: When called on a non-Windows platform.

    Returns:
        ``True`` on success, ``False`` when VRChat is not running, no
        matching window can be located, or the underlying Win32 call
        fails.
    """
    if sys.platform != "win32":
        # TODO: Linux 対応 (X11/Wayland)
        raise NotImplementedError("unfocus() is only supported on Windows")

    pid = find_pid()
    if pid is None:
        return False

    hwnd = _find_vrchat_hwnd(pid)
    if hwnd is None:
        return False

    flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    try:
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0, flags)
    except pywintypes.error:
        return False
    return True
