"""Win32 implementation of focus/unfocus for the VRChat window."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

# ``TYPE_CHECKING`` is False at runtime — the raise fires on non-Windows hosts.
# Under pyright (which treats ``TYPE_CHECKING`` as True) the raise is skipped,
# letting the type checker see the win32 symbols below.
if not TYPE_CHECKING and sys.platform != "win32":
    raise ImportError

from typing import Any, cast

import pywintypes
import win32api
import win32con
import win32gui

from vrcpilot._win32 import find_vrchat_hwnd
from vrcpilot.process import find_pid


def focus_window() -> bool:
    """Win32 implementation of :func:`vrcpilot.window.focus`."""
    pid = find_pid()
    if pid is None:
        return False

    hwnd = find_vrchat_hwnd(pid)
    if hwnd is None:
        return False

    # Press/release Alt to defeat Windows' SetForegroundWindow lock --
    # without an active input event from this process the OS may refuse
    # to change the foreground window. types-pywin32 stubs leave
    # ``keybd_event``'s positional args partially typed
    # (``reportUnknownMemberType``), so we widen to ``Any`` once here
    # instead of suppressing each of the two call sites.
    keybd_event = cast(Any, win32api).keybd_event
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        keybd_event(win32con.VK_MENU, 0, 0, 0)
        try:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
        finally:
            keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    except pywintypes.error:
        return False
    return True


def unfocus_window() -> bool:
    """Win32 implementation of :func:`vrcpilot.window.unfocus`."""
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
