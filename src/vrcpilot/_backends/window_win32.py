"""Win32 implementation of focus/unfocus for the VRChat window."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from vrcpilot._win32 import find_vrchat_hwnd
from vrcpilot.process import find_pid

if TYPE_CHECKING or sys.platform == "win32":
    import pywintypes
    import win32api
    import win32con
    import win32gui


def focus_window() -> bool:
    """Win32 implementation of :func:`vrcpilot.window.focus`."""
    if sys.platform != "win32":
        # Defensive narrow for pyright on POSIX runs.
        raise RuntimeError("unreachable")

    pid = find_pid()
    if pid is None:
        return False

    hwnd = find_vrchat_hwnd(pid)
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


def unfocus_window() -> bool:
    """Win32 implementation of :func:`vrcpilot.window.unfocus`."""
    if sys.platform != "win32":
        # Defensive narrow for pyright on POSIX runs.
        raise RuntimeError("unreachable")

    pid = find_pid()
    if pid is None:
        return False

    hwnd = find_vrchat_hwnd(pid)
    if hwnd is None:
        return False

    flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    try:
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0, flags)
    except pywintypes.error:
        return False
    return True
