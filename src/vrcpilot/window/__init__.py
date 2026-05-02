"""VRChat window z-order control (focus / unfocus / is_foreground).

Windows and Linux (X11 / XWayland). Native Wayland is unsupported -
``focus()`` / ``unfocus()`` / ``is_foreground()`` warn and return
``False``.
"""

from __future__ import annotations

import sys


def focus() -> bool:
    """Bring the running VRChat window to the foreground.

    Restored if minimized (Win32 ``ShowWindow(SW_RESTORE)``; on X11 an
    EWMH window manager typically deminimizes in response to
    ``_NET_ACTIVE_WINDOW``). Only meaningful in Desktop mode — VR
    exclusive mode has no desktop window to surface.

    Raises:
        NotImplementedError: Platform other than Windows or Linux.

    Returns:
        ``True`` on success. ``False`` when VRChat is not running, the
        window cannot be located, the platform call fails, or the
        session is native Wayland (also emits :class:`RuntimeWarning`).
    """
    if sys.platform == "win32":
        from .win32 import focus_window as _impl

        return _impl()
    if sys.platform == "linux":
        from .x11 import focus_window as _impl

        return _impl()
    raise NotImplementedError(f"focus() is not supported on {sys.platform}")


def is_foreground() -> bool:
    """Return ``True`` when the running VRChat window is foreground.

    Compares the OS-reported active window against the one owned by the
    running VRChat process.

    Raises:
        NotImplementedError: Platform other than Linux. The Win32
            backend is not wired in this iteration.

    Returns:
        ``True`` when VRChat is the active window. ``False`` when
        VRChat is not running, the window cannot be located, the
        platform call fails, or the session is native Wayland (also
        emits :class:`RuntimeWarning`).
    """
    if sys.platform == "linux":
        from .x11 import is_window_foreground as _impl

        return _impl()
    raise NotImplementedError(f"is_foreground() is not supported on {sys.platform}")


def unfocus() -> bool:
    """Send the running VRChat window to the bottom of the z-order.

    Unlike minimizing, no other window is activated, so input focus
    stays where the caller had it.

    Raises:
        NotImplementedError: Platform other than Windows or Linux.

    Returns:
        ``True`` on success. ``False`` when VRChat is not running, the
        window cannot be located, the platform call fails, or the
        session is native Wayland (also emits :class:`RuntimeWarning`).
    """
    if sys.platform == "win32":
        from .win32 import unfocus_window as _impl

        return _impl()
    if sys.platform == "linux":
        from .x11 import unfocus_window as _impl

        return _impl()
    raise NotImplementedError(f"unfocus() is not supported on {sys.platform}")
