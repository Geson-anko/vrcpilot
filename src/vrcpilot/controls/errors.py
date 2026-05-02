"""Exceptions raised by :mod:`vrcpilot.controls`."""

from __future__ import annotations


class VRChatNotRunningError(RuntimeError):
    """Raised when a control input is requested while VRChat is not running."""


class VRChatNotFocusedError(RuntimeError):
    """Raised when VRChat could not be brought to the foreground."""
