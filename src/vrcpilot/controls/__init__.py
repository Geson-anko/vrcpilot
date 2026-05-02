"""VRChat-targeted synthetic mouse and keyboard input.

Every public input call runs :func:`ensure_target` first by default;
pass ``focus=False`` inside hot loops that have already verified focus.
Linux backend only (inputtino over uinput); Windows / macOS raise
:class:`NotImplementedError`. Native Wayland is rejected up front
(XWayland is fine).

Usage::

    from vrcpilot.controls import mouse, keyboard, Key
    mouse.click()
    keyboard.down(Key.CTRL)
    keyboard.press(Key.C)
    keyboard.up(Key.CTRL)
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
