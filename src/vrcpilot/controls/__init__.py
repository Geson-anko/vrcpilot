"""VRChat-targeted synthetic mouse and keyboard input.

Every public input call runs :func:`ensure_target` first by default,
so VRChat must be running and foregrounded before events are
delivered. Pass ``focus=False`` to skip the guard inside hot loops
that already verified focus. The guard raises
:class:`VRChatNotRunningError` / :class:`VRChatNotFocusedError`
(both :class:`RuntimeError` subclasses) and :class:`NotImplementedError`
on native Wayland sessions (XWayland is fine).

The :class:`Key` enum (a :class:`enum.StrEnum`) is the only accepted
key identifier so pyright and IDE completion catch typos. Modifier
combos are spelled as explicit ``down`` / ``press`` / ``up`` triples
(no ``"ctrl+c"`` string parsing).

This iteration ships the Linux backend only (inputtino over uinput);
calling the module functions on Windows or macOS raises
:class:`NotImplementedError`.

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
