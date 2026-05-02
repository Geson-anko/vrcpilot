"""Pre-input safety check: VRChat must be running and foreground.

Used by every guarded ``mouse`` / ``keyboard`` call (the
``focus=True`` default) and exported as
:func:`vrcpilot.controls.ensure_target` so callers can also invoke it
explicitly once before a hot loop and then pass ``focus=False`` on
the inner calls.
"""

from __future__ import annotations

import time

from vrcpilot import window
from vrcpilot.process import find_pid
from vrcpilot.session import is_wayland_native

from .errors import VRChatNotFocusedError, VRChatNotRunningError

# The window manager applies ``_NET_ACTIVE_WINDOW`` asynchronously, so a
# bare re-check right after ``window.focus()`` can race the WM update
# and report False even when the focus request will succeed a moment
# later. Poll for up to ``_FOCUS_RECHECK_TIMEOUT`` seconds at
# ``_FOCUS_RECHECK_INTERVAL`` granularity before giving up.
_FOCUS_RECHECK_TIMEOUT: float = 0.5
_FOCUS_RECHECK_INTERVAL: float = 0.05


def ensure_target() -> None:
    """Verify VRChat is running and the foreground window.

    If VRChat is not foreground, attempts :func:`vrcpilot.window.focus`
    once and re-checks (with a short poll loop to absorb WM latency).
    Idempotent: returns silently when the target is already correct,
    so it is safe to call before every input event or once before a
    tight loop. Native Wayland is rejected up front rather than
    warning-and-returning, because
    :func:`vrcpilot.window.is_foreground` always returns ``False``
    under native Wayland and the focus retry would never converge --
    failing fast surfaces the misconfiguration to the caller instead
    of silently dropping every input event.

    Raises:
        NotImplementedError: Native Wayland session detected; controls
            require X11 or XWayland.
        VRChatNotRunningError: VRChat process was not found.
        VRChatNotFocusedError: Window cannot be brought to the
            foreground (focus call failed, or VRChat still is not
            foreground after a successful focus and a short retry
            window).
    """
    if is_wayland_native():
        raise NotImplementedError(
            "controls.ensure_target requires X11 or XWayland; "
            "native Wayland is not supported"
        )
    if find_pid() is None:
        raise VRChatNotRunningError("VRChat is not running")
    if window.is_foreground():
        return
    if not window.focus():
        raise VRChatNotFocusedError(
            "VRChat is not the foreground window and focus() failed"
        )
    deadline = time.monotonic() + _FOCUS_RECHECK_TIMEOUT
    while not window.is_foreground():
        if time.monotonic() >= deadline:
            raise VRChatNotFocusedError(
                "VRChat is not the foreground window after focus()"
            )
        time.sleep(_FOCUS_RECHECK_INTERVAL)
