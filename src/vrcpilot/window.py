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


def _find_vrchat_hwnd_win32(pid: int) -> int | None:
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


def _focus_win32() -> bool:
    """Win32 implementation of :func:`focus`."""
    if sys.platform != "win32":
        # Defensive narrow for pyright on POSIX runs.
        raise RuntimeError("unreachable")

    pid = find_pid()
    if pid is None:
        return False

    hwnd = _find_vrchat_hwnd_win32(pid)
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


def _unfocus_win32() -> bool:
    """Win32 implementation of :func:`unfocus`."""
    if sys.platform != "win32":
        # Defensive narrow for pyright on POSIX runs.
        raise RuntimeError("unreachable")

    pid = find_pid()
    if pid is None:
        return False

    hwnd = _find_vrchat_hwnd_win32(pid)
    if hwnd is None:
        return False

    flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    try:
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0, flags)
    except pywintypes.error:
        return False
    return True


def focus() -> bool:
    """Bring the running VRChat window to the foreground.

    Use this when an automation step needs the VRChat window to be the
    active, visible window — for example, before sending input. The
    window is restored first if it is currently minimized.

    Only meaningful in Desktop mode. When VRChat is running in VR
    exclusive mode there is no desktop window to surface, so the call
    has no visible effect even though it may still report success.

    Raises:
        NotImplementedError: When called on a non-Windows platform.

    Returns:
        ``True`` on success. ``False`` when VRChat is not running, its
        top-level window cannot be located (e.g. still starting up), or
        the underlying Win32 call fails.
    """
    if sys.platform == "win32":
        return _focus_win32()
    raise NotImplementedError(f"focus() is not supported on {sys.platform}")


def unfocus() -> bool:
    """Send the running VRChat window to the bottom of the z-order.

    Use this to step VRChat out of the way without disturbing it: the
    window stays open and keeps rendering, but other applications cover
    it. Unlike minimizing, no other window is activated, so input focus
    is left wherever the caller had it.

    Pairs with :func:`focus` for automation that briefly surfaces VRChat
    and then returns to a background workflow.

    Raises:
        NotImplementedError: When called on a non-Windows platform.

    Returns:
        ``True`` on success. ``False`` when VRChat is not running, its
        top-level window cannot be located (e.g. still starting up), or
        the underlying Win32 call fails.
    """
    if sys.platform == "win32":
        return _unfocus_win32()
    raise NotImplementedError(f"unfocus() is not supported on {sys.platform}")
