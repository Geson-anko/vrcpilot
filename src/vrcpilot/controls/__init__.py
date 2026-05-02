"""VRChat-targeted synthetic mouse and keyboard input.

Every public input call runs :func:`ensure_target` first by default;
pass ``focus=False`` inside hot loops that have already verified focus.
Linux backend only (inputtino over uinput); Windows / macOS raise
:class:`NotImplementedError`. Native Wayland is rejected up front
(XWayland is fine).

Usage::

    import vrcpilot
    vrcpilot.mouse.click()
    vrcpilot.keyboard.down(vrcpilot.Key.CTRL)
    vrcpilot.keyboard.press(vrcpilot.Key.C)
    vrcpilot.keyboard.up(vrcpilot.Key.CTRL)
"""

from . import keyboard, mouse
from .errors import VRChatNotFocusedError, VRChatNotRunningError
from .guard import ensure_target
from .keyboard import Key

__all__ = [
    "ensure_target",
    "Key",
    "keyboard",
    "mouse",
    "VRChatNotFocusedError",
    "VRChatNotRunningError",
]
