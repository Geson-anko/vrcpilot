"""VRChat window control API.

Public entry points for focusing and unfocusing the running VRChat
client window. Companion to :mod:`vrcpilot.process` — once VRChat is
launched and observed (via :func:`vrcpilot.find_pid`), use
:func:`focus` / :func:`unfocus` to drive its z-order from automation.
Capturing the window's contents is handled separately in
:mod:`vrcpilot.capture`.

Supports Windows and Linux (X11 / XWayland). Wayland native sessions
are not supported (``focus()`` / ``unfocus()`` warn and return
``False``).
"""

from __future__ import annotations

import sys
import warnings

from vrcpilot._x11 import find_vrchat_window, is_wayland_native, x11_display
from vrcpilot.process import find_pid

if sys.platform == "win32":
    import pywintypes
    import win32api
    import win32con
    import win32gui
    import win32process

if sys.platform == "linux":
    import Xlib.error
    import Xlib.protocol.event
    from Xlib import X


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


def _focus_x11() -> bool:
    """X11/XWayland implementation of :func:`focus`."""
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")

    if is_wayland_native():
        warnings.warn(
            "Wayland native session detected; "
            "focus()/unfocus() require X11 or XWayland.",
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    pid = find_pid()
    if pid is None:
        return False

    with x11_display() as display:
        if display is None:
            return False
        window = find_vrchat_window(display, pid)
        if window is None:
            return False
        try:
            net_active = display.intern_atom("_NET_ACTIVE_WINDOW")
            root = display.screen().root
            event = Xlib.protocol.event.ClientMessage(
                window=window,
                client_type=net_active,
                # 32-bit format payload per EWMH: source=2 (pager /
                # automation tool), timestamp=CurrentTime, currently
                # active window=0 (unknown), remaining slots=0.
                data=(32, [2, X.CurrentTime, 0, 0, 0]),
            )
            mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
            root.send_event(event, event_mask=mask)
            display.flush()
        except Xlib.error.XError:
            return False
        return True


def _unfocus_x11() -> bool:
    """X11/XWayland implementation of :func:`unfocus`."""
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")

    if is_wayland_native():
        warnings.warn(
            "Wayland native session detected; "
            "focus()/unfocus() require X11 or XWayland.",
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    pid = find_pid()
    if pid is None:
        return False

    with x11_display() as display:
        if display is None:
            return False
        window = find_vrchat_window(display, pid)
        if window is None:
            return False
        try:
            # ConfigureWindow with stack_mode=Below lowers the window in
            # the z-order without changing input focus — the X11
            # equivalent of SetWindowPos(HWND_BOTTOM, SWP_NOACTIVATE).
            window.configure(stack_mode=X.Below)
            display.flush()
        except Xlib.error.XError:
            return False
        return True


def focus() -> bool:
    """Bring the running VRChat window to the foreground.

    Use this when an automation step needs the VRChat window to be the
    active, visible window — for example, before sending input.
    Restored if minimized (Win32 calls ``ShowWindow(SW_RESTORE)``
    explicitly; on X11 an EWMH-compliant window manager typically
    deminimizes in response to ``_NET_ACTIVE_WINDOW``).

    Only meaningful in Desktop mode. When VRChat is running in VR
    exclusive mode there is no desktop window to surface, so the call
    has no visible effect even though it may still report success.

    Supported on Windows and Linux (X11 / XWayland). Native Wayland
    sessions are not supported because the X11 activation path cannot
    reach the compositor.

    Raises:
        NotImplementedError: When called on a platform other than
            Windows or Linux.

    Returns:
        ``True`` on success. ``False`` when VRChat is not running, its
        top-level window cannot be located (e.g. still starting up),
        the underlying platform call fails, or the session is native
        Wayland (a ``RuntimeWarning`` is also emitted in that case).
    """
    if sys.platform == "win32":
        return _focus_win32()
    if sys.platform == "linux":
        return _focus_x11()
    raise NotImplementedError(f"focus() is not supported on {sys.platform}")


def unfocus() -> bool:
    """Send the running VRChat window to the bottom of the z-order.

    Use this to step VRChat out of the way without disturbing it: the
    window stays open and keeps rendering, but other applications cover
    it. Unlike minimizing, no other window is activated, so input focus
    is left wherever the caller had it.

    Pairs with :func:`focus` for automation that briefly surfaces VRChat
    and then returns to a background workflow.

    Supported on Windows and Linux (X11 / XWayland). Native Wayland
    sessions are not supported because the X11 stacking request cannot
    reach the compositor.

    Raises:
        NotImplementedError: When called on a platform other than
            Windows or Linux.

    Returns:
        ``True`` on success. ``False`` when VRChat is not running, its
        top-level window cannot be located (e.g. still starting up),
        the underlying platform call fails, or the session is native
        Wayland (a ``RuntimeWarning`` is also emitted in that case).
    """
    if sys.platform == "win32":
        return _unfocus_win32()
    if sys.platform == "linux":
        return _unfocus_x11()
    raise NotImplementedError(f"unfocus() is not supported on {sys.platform}")
