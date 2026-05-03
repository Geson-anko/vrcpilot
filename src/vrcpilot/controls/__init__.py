"""VRChat-targeted synthetic mouse and keyboard input.

Every public input call runs :func:`ensure_target` first by default;
pass ``focus=False`` inside hot loops that have already verified focus.
Linux backend only (inputtino over uinput); Windows / macOS raise
:class:`NotImplementedError`. Native Wayland is rejected up front
(XWayland is fine).

``press`` / ``down`` / ``up`` (keyboard) and ``click`` / ``press`` /
``release`` (mouse) accept multiple targets via ``*args`` and drive
them as a single simultaneous combo: targets go down left-to-right,
the duration sleeps once for the whole combo, then targets are
released in reverse order so modifiers come off last (the standard
Ctrl+C convention).

Usage::

    import vrcpilot
    vrcpilot.mouse.click()
    # held-state combo (down / up explicit)
    vrcpilot.keyboard.down(vrcpilot.Key.CTRL)
    vrcpilot.keyboard.press(vrcpilot.Key.C)
    vrcpilot.keyboard.up(vrcpilot.Key.CTRL)
    # one-shot combo (equivalent to the held-state form above)
    vrcpilot.keyboard.press(vrcpilot.Key.CTRL, vrcpilot.Key.C)
    vrcpilot.mouse.click(vrcpilot.MouseButton.LEFT, vrcpilot.MouseButton.RIGHT)
"""

from . import keyboard, mouse
from .errors import VRChatNotFocusedError, VRChatNotRunningError
from .guard import ensure_target
from .keyboard import Key
from .mouse import MouseButton

__all__ = [
    "ensure_target",
    "Key",
    "keyboard",
    "mouse",
    "MouseButton",
    "VRChatNotFocusedError",
    "VRChatNotRunningError",
]
