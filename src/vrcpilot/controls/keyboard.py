"""Synthetic keyboard input for VRChat.

Keys are passed as :class:`Key` (a :class:`enum.StrEnum`) so pyright
and IDE completion catch typos. Combos are explicit ``down`` /
``press`` / ``up`` triples; there is no ``"ctrl+c"`` string parsing.
"""

from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, override

from .guard import ensure_target


class Key(StrEnum):
    """Normalized key identifiers.

    Values follow the pydirectinput naming convention so a future Win32
    backend can pass ``key.value`` straight through; the Linux backend
    maps each member via :data:`_INPUTTINO_CODES`.
    """

    # Letters
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"
    I = "i"  # noqa: E741
    J = "j"
    K = "k"
    L = "l"
    M = "m"
    N = "n"
    O = "o"  # noqa: E741
    P = "p"
    Q = "q"
    R = "r"
    S = "s"
    T = "t"
    U = "u"
    V = "v"
    W = "w"
    X = "x"
    Y = "y"
    Z = "z"

    # Digits (identifier cannot start with a digit, so prefix NUM_)
    NUM_0 = "0"
    NUM_1 = "1"
    NUM_2 = "2"
    NUM_3 = "3"
    NUM_4 = "4"
    NUM_5 = "5"
    NUM_6 = "6"
    NUM_7 = "7"
    NUM_8 = "8"
    NUM_9 = "9"

    # Function keys (F1..F12 — F13..F24 omitted from the public surface
    # for now; add when a concrete need arises)
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"

    # Modifiers (generic + L/R)
    SHIFT = "shift"
    SHIFT_LEFT = "shiftleft"
    SHIFT_RIGHT = "shiftright"
    CTRL = "ctrl"
    CTRL_LEFT = "ctrlleft"
    CTRL_RIGHT = "ctrlright"
    ALT = "alt"
    ALT_LEFT = "altleft"
    ALT_RIGHT = "altright"
    WIN = "win"
    WIN_LEFT = "winleft"
    WIN_RIGHT = "winright"

    # Navigation / arrows
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    HOME = "home"
    END = "end"
    PAGE_UP = "pageup"
    PAGE_DOWN = "pagedown"

    # Editing
    BACKSPACE = "backspace"
    DELETE = "delete"
    INSERT = "insert"
    TAB = "tab"
    ENTER = "enter"
    ESCAPE = "escape"
    SPACE = "space"

    # Symbols
    MINUS = "-"
    EQUALS = "="
    LBRACKET = "["
    RBRACKET = "]"
    BACKSLASH = "\\"
    SEMICOLON = ";"
    QUOTE = "'"
    COMMA = ","
    PERIOD = "."
    SLASH = "/"
    BACKTICK = "`"


class Keyboard(ABC):
    """Keyboard ABC: runs :func:`ensure_target`, then delegates to ``_do_*``."""

    def press(self, key: Key, *, duration: float = 0.1, focus: bool = True) -> None:
        """Tap ``key`` (down then up).

        ``duration`` is the down-to-up hold in seconds. The default of
        0.1 is tuned to be reliably picked up by Unity / VRChat --
        shorter holds (including ``0.0``) get dropped in practice.
        """
        if focus:
            ensure_target()
        self._do_press(key, duration=duration)

    def down(self, key: Key, *, focus: bool = True) -> None:
        """Press and hold ``key`` until a matching :meth:`up`.

        Pair with :meth:`up` to express modifier combos -- e.g.
        ``down(Key.CTRL); press(Key.C); up(Key.CTRL)`` for ``Ctrl+C``.
        """
        if focus:
            ensure_target()
        self._do_down(key)

    def up(self, key: Key, *, focus: bool = True) -> None:
        """Release ``key`` previously pressed with :meth:`down`."""
        if focus:
            ensure_target()
        self._do_up(key)

    @abstractmethod
    def _do_press(self, key: Key, *, duration: float) -> None: ...

    @abstractmethod
    def _do_down(self, key: Key) -> None: ...

    @abstractmethod
    def _do_up(self, key: Key) -> None: ...


# Linux backend ------------------------------------------------------------

if sys.platform == "linux":
    import inputtino

    # Exhaustive Key -> inputtino.KeyCode map; tests assert
    # set(_INPUTTINO_CODES) == set(Key) so a missing entry surfaces
    # at test time rather than as a production KeyError.
    _INPUTTINO_CODES: dict[Key, inputtino.KeyCode] = {
        # Letters
        Key.A: inputtino.KeyCode.A,
        Key.B: inputtino.KeyCode.B,
        Key.C: inputtino.KeyCode.C,
        Key.D: inputtino.KeyCode.D,
        Key.E: inputtino.KeyCode.E,
        Key.F: inputtino.KeyCode.F,
        Key.G: inputtino.KeyCode.G,
        Key.H: inputtino.KeyCode.H,
        Key.I: inputtino.KeyCode.I,
        Key.J: inputtino.KeyCode.J,
        Key.K: inputtino.KeyCode.K,
        Key.L: inputtino.KeyCode.L,
        Key.M: inputtino.KeyCode.M,
        Key.N: inputtino.KeyCode.N,
        Key.O: inputtino.KeyCode.O,
        Key.P: inputtino.KeyCode.P,
        Key.Q: inputtino.KeyCode.Q,
        Key.R: inputtino.KeyCode.R,
        Key.S: inputtino.KeyCode.S,
        Key.T: inputtino.KeyCode.T,
        Key.U: inputtino.KeyCode.U,
        Key.V: inputtino.KeyCode.V,
        Key.W: inputtino.KeyCode.W,
        Key.X: inputtino.KeyCode.X,
        Key.Y: inputtino.KeyCode.Y,
        Key.Z: inputtino.KeyCode.Z,
        # Digits
        Key.NUM_0: inputtino.KeyCode.KEY_0,
        Key.NUM_1: inputtino.KeyCode.KEY_1,
        Key.NUM_2: inputtino.KeyCode.KEY_2,
        Key.NUM_3: inputtino.KeyCode.KEY_3,
        Key.NUM_4: inputtino.KeyCode.KEY_4,
        Key.NUM_5: inputtino.KeyCode.KEY_5,
        Key.NUM_6: inputtino.KeyCode.KEY_6,
        Key.NUM_7: inputtino.KeyCode.KEY_7,
        Key.NUM_8: inputtino.KeyCode.KEY_8,
        Key.NUM_9: inputtino.KeyCode.KEY_9,
        # Function keys
        Key.F1: inputtino.KeyCode.F1,
        Key.F2: inputtino.KeyCode.F2,
        Key.F3: inputtino.KeyCode.F3,
        Key.F4: inputtino.KeyCode.F4,
        Key.F5: inputtino.KeyCode.F5,
        Key.F6: inputtino.KeyCode.F6,
        Key.F7: inputtino.KeyCode.F7,
        Key.F8: inputtino.KeyCode.F8,
        Key.F9: inputtino.KeyCode.F9,
        Key.F10: inputtino.KeyCode.F10,
        Key.F11: inputtino.KeyCode.F11,
        Key.F12: inputtino.KeyCode.F12,
        # Modifiers
        Key.SHIFT: inputtino.KeyCode.SHIFT,
        Key.SHIFT_LEFT: inputtino.KeyCode.LEFT_SHIFT,
        Key.SHIFT_RIGHT: inputtino.KeyCode.RIGHT_SHIFT,
        Key.CTRL: inputtino.KeyCode.CTRL,
        Key.CTRL_LEFT: inputtino.KeyCode.LEFT_CONTROL,
        Key.CTRL_RIGHT: inputtino.KeyCode.RIGHT_CONTROL,
        Key.ALT: inputtino.KeyCode.ALT,
        Key.ALT_LEFT: inputtino.KeyCode.LEFT_ALT,
        Key.ALT_RIGHT: inputtino.KeyCode.RIGHT_ALT,
        # Generic WIN has no inputtino equivalent — map to LEFT_WIN
        # (the spec already treats generic modifiers as left-mapped).
        Key.WIN: inputtino.KeyCode.LEFT_WIN,
        Key.WIN_LEFT: inputtino.KeyCode.LEFT_WIN,
        Key.WIN_RIGHT: inputtino.KeyCode.RIGHT_WIN,
        # Navigation / arrows
        Key.UP: inputtino.KeyCode.UP,
        Key.DOWN: inputtino.KeyCode.DOWN,
        Key.LEFT: inputtino.KeyCode.LEFT,
        Key.RIGHT: inputtino.KeyCode.RIGHT,
        Key.HOME: inputtino.KeyCode.HOME,
        Key.END: inputtino.KeyCode.END,
        Key.PAGE_UP: inputtino.KeyCode.PAGE_UP,
        Key.PAGE_DOWN: inputtino.KeyCode.PAGE_DOWN,
        # Editing
        Key.BACKSPACE: inputtino.KeyCode.BACKSPACE,
        Key.DELETE: inputtino.KeyCode.DELETE,
        Key.INSERT: inputtino.KeyCode.INSERT,
        Key.TAB: inputtino.KeyCode.TAB,
        Key.ENTER: inputtino.KeyCode.ENTER,
        Key.ESCAPE: inputtino.KeyCode.ESC,
        Key.SPACE: inputtino.KeyCode.SPACE,
        # Symbols
        Key.MINUS: inputtino.KeyCode.MINUS,
        Key.EQUALS: inputtino.KeyCode.PLUS,
        Key.LBRACKET: inputtino.KeyCode.OPEN_BRACKET,
        Key.RBRACKET: inputtino.KeyCode.CLOSE_BRACKET,
        Key.BACKSLASH: inputtino.KeyCode.BACKSLASH,
        Key.SEMICOLON: inputtino.KeyCode.SEMICOLON,
        Key.QUOTE: inputtino.KeyCode.QUOTE,
        Key.COMMA: inputtino.KeyCode.COMMA,
        Key.PERIOD: inputtino.KeyCode.PERIOD,
        Key.SLASH: inputtino.KeyCode.SLASH,
        Key.BACKTICK: inputtino.KeyCode.TILDE,
    }

    class LinuxKeyboard(Keyboard):
        """``inputtino``-backed :class:`Keyboard`.

        Opens ``/dev/uinput`` at construction; inputtino raises
        :class:`RuntimeError` if the caller lacks permission.
        """

        def __init__(self) -> None:
            self._imp = inputtino.Keyboard()

        @override
        def _do_press(self, key: Key, *, duration: float) -> None:
            self._imp.type(_INPUTTINO_CODES[key], duration=duration)

        @override
        def _do_down(self, key: Key) -> None:
            self._imp.press(_INPUTTINO_CODES[key])

        @override
        def _do_up(self, key: Key) -> None:
            self._imp.release(_INPUTTINO_CODES[key])


# Win32 backend ------------------------------------------------------------

if sys.platform == "win32":
    # pydirectinput ships no stubs; alias to Any once so call sites stay
    # clean instead of needing reportUnknownMemberType ignores per call.
    import pydirectinput as _pydirectinput_module  # pyright: ignore[reportMissingTypeStubs]

    pydirectinput: Any = _pydirectinput_module

    # Disable pydirectinput's "cursor at (0, 0) panic" — VRChat workflows
    # legitimately move the cursor to corners and we do not want a hard
    # exit from a synthetic input call. Idempotent with mouse.py setting
    # the same flag (they share the same module reference).
    pydirectinput.FAILSAFE = False

    class Win32Keyboard(Keyboard):
        """``pydirectinput``-backed :class:`Keyboard`.

        :class:`Key` values follow pydirectinput's naming convention so
        ``key.value`` is forwarded straight through. If a key turns out
        to be unsupported by the real ``pydirectinput.KEYBOARD_MAPPING``
        (caught by manual / e2e smoke), follow up per spec §11 with a
        translation table here.
        """

        @override
        def _do_press(self, key: Key, *, duration: float) -> None:
            if duration > 0:
                # Older pydirectinput versions inject MINIMUM_DURATION
                # sleeps when press() is called with duration kwarg, so
                # split the down/up path manually instead of passing
                # duration through.
                pydirectinput.keyDown(key.value)
                time.sleep(duration)
                pydirectinput.keyUp(key.value)
            else:
                pydirectinput.press(key.value)

        @override
        def _do_down(self, key: Key) -> None:
            pydirectinput.keyDown(key.value)

        @override
        def _do_up(self, key: Key) -> None:
            pydirectinput.keyUp(key.value)


# Lazy singleton -----------------------------------------------------------

_instance: Keyboard | None = None


def _get() -> Keyboard:
    """Return the lazily-built platform backend (deferred uinput open)."""
    global _instance
    if _instance is None:
        if sys.platform == "win32":
            _instance = Win32Keyboard()
        elif sys.platform == "linux":
            _instance = LinuxKeyboard()
        else:
            raise NotImplementedError(
                f"controls.keyboard is not supported on {sys.platform}"
            )
    return _instance


# Module functions ---------------------------------------------------------


def press(key: Key, *, duration: float = 0.1, focus: bool = True) -> None:
    """See :meth:`Keyboard.press`."""
    _get().press(key, duration=duration, focus=focus)


def down(key: Key, *, focus: bool = True) -> None:
    """See :meth:`Keyboard.down`."""
    _get().down(key, focus=focus)


def up(key: Key, *, focus: bool = True) -> None:
    """See :meth:`Keyboard.up`."""
    _get().up(key, focus=focus)
