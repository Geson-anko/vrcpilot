"""Pre-input safety check: VRChat must be running and foreground."""

from __future__ import annotations

from vrcpilot import window
from vrcpilot.process import find_pid
from vrcpilot.session import is_wayland_native

from .errors import VRChatNotFocusedError, VRChatNotRunningError


def ensure_target() -> None:
    """Verify VRChat is running and the foreground window.

    If VRChat is not foreground, attempts :func:`vrcpilot.window.focus`
    once and re-checks. Native Wayland sessions are rejected up front
    because :func:`vrcpilot.window.is_foreground` cannot succeed without
    XWayland and the focus loop would never converge.

    Raises:
        NotImplementedError: Native Wayland session detected; controls
            require X11 or XWayland.
        VRChatNotRunningError: VRChat process was not found.
        VRChatNotFocusedError: Window cannot be brought to the
            foreground (focus call failed, or VRChat still is not
            foreground after a successful focus).
    """
    if is_wayland_native():
        raise NotImplementedError(
            "controls.ensure_target requires X11 or XWayland; "
            "native Wayland is not supported"
        )
    if find_pid() is None:
        raise VRChatNotRunningError("VRChat is not running")
    if not window.is_foreground():
        if not window.focus():
            raise VRChatNotFocusedError(
                "VRChat is not the foreground window and focus() failed"
            )
        if not window.is_foreground():
            raise VRChatNotFocusedError(
                "VRChat is not the foreground window after focus()"
            )
