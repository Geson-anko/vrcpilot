"""Exceptions raised by the :mod:`vrcpilot.controls` safety guard."""

from __future__ import annotations


class VRChatNotRunningError(RuntimeError):
    """No VRChat process is running when an input was requested."""


class VRChatNotFocusedError(RuntimeError):
    """VRChat is running but could not be brought to the foreground."""
