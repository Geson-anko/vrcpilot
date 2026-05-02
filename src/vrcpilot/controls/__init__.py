"""VRChat-targeted synthetic mouse and keyboard input.

This iteration exposes the safety guard (:func:`ensure_target`) and
the :mod:`vrcpilot.controls.mouse` submodule (Linux backend only).
The ``keyboard`` submodule is added in a subsequent step.
"""

from .errors import VRChatNotFocusedError, VRChatNotRunningError
from .guard import ensure_target

__all__ = [
    "ensure_target",
    "VRChatNotFocusedError",
    "VRChatNotRunningError",
]
