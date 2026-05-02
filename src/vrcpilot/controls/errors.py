"""Exceptions raised by the :mod:`vrcpilot.controls` safety guard.

Both are :class:`RuntimeError` subclasses so callers may catch them
generically when the distinction does not matter.
"""

from __future__ import annotations


class VRChatNotRunningError(RuntimeError):
    """No VRChat process is running when a control input was requested.

    Raised by :func:`vrcpilot.controls.ensure_target` (and therefore by
    every guarded ``mouse`` / ``keyboard`` call) when
    :func:`vrcpilot.process.find_pid` returns ``None``.
    """


class VRChatNotFocusedError(RuntimeError):
    """VRChat is running but could not be brought to the foreground.

    Raised by :func:`vrcpilot.controls.ensure_target` when either the
    underlying :func:`vrcpilot.window.focus` call fails outright, or
    succeeds but VRChat is still not the active window on the
    follow-up :func:`vrcpilot.window.is_foreground` check (e.g. another
    full-screen app is blocking the focus change).
    """
