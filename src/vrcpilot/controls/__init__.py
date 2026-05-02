"""VRChat-targeted synthetic mouse and keyboard input.

This iteration provides only the safety guard
(:func:`ensure_target`) and its error types. The ``mouse`` and
``keyboard`` submodules are added in subsequent steps.
"""

from .errors import VRChatNotFocusedError, VRChatNotRunningError
from .guard import ensure_target

__all__ = [
    "ensure_target",
    "VRChatNotFocusedError",
    "VRChatNotRunningError",
]
