"""VRChat-targeted synthetic mouse and keyboard input.

Exposes the safety guard (:func:`ensure_target`), the two error types
raised by it, and the :class:`Key` enum used by the
:mod:`vrcpilot.controls.keyboard` submodule. The ``mouse`` and
``keyboard`` submodules are imported via ``from vrcpilot.controls
import mouse, keyboard`` (Linux backend only for this iteration).
"""

from .errors import VRChatNotFocusedError, VRChatNotRunningError
from .guard import ensure_target
from .keyboard import Key

__all__ = [
    "ensure_target",
    "Key",
    "VRChatNotFocusedError",
    "VRChatNotRunningError",
]
