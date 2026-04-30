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
        from vrcpilot._backends.window_win32 import focus_window as _impl

        return _impl()
    if sys.platform == "linux":
        from vrcpilot._backends.window_x11 import focus_window as _impl

        return _impl()
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
        from vrcpilot._backends.window_win32 import unfocus_window as _impl

        return _impl()
    if sys.platform == "linux":
        from vrcpilot._backends.window_x11 import unfocus_window as _impl

        return _impl()
    raise NotImplementedError(f"unfocus() is not supported on {sys.platform}")
