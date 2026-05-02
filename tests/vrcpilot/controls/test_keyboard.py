"""Tests for :mod:`vrcpilot.controls.keyboard`.

Mirrors the layout of :mod:`tests.vrcpilot.controls.test_mouse`:

* :class:`Key` enum coverage (cross-platform).
* :class:`Keyboard` ABC template-method wiring -- runs on every
  platform via :class:`tests.helpers.ImplKeyboard` so the guard
  plumbing is verified independently of any backend.
* ``_INPUTTINO_CODES`` exhaustiveness -- Linux-only because the
  mapping table is only populated under ``sys.platform == "linux"``.
* :class:`vrcpilot.controls.keyboard.LinuxKeyboard` -- the
  inputtino-backed concrete class. Linux-only, with the real
  ``inputtino.Keyboard`` swapped out via ``mocker.patch`` so no
  uinput device is ever opened during testing.
* The lazy-singleton ``_get`` and the ``press`` / ``down`` / ``up``
  module functions, which simply forward to the backend.

The autouse ``_reset_keyboard_singleton`` fixture clears
``vrcpilot.controls.keyboard._instance`` between tests so backend
construction order does not leak between cases.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import override

import pytest
from pytest_mock import MockerFixture

from tests.fakes import FakeInputtinoKeyboard
from tests.helpers import ImplKeyboard, only_linux
from vrcpilot.controls import keyboard as keyboard_mod
from vrcpilot.controls.keyboard import Key, Keyboard


@pytest.fixture(autouse=True)
def _reset_keyboard_singleton() -> Iterator[None]:
    """Clear the module-level lazy backend before and after each test."""
    keyboard_mod._instance = None
    yield
    keyboard_mod._instance = None


# --- Key enum tests (cross-platform) --------------------------------------


class TestKeyEnum:
    """``Key`` values must follow the pydirectinput naming convention.

    These tests anchor the spec §4.2 surface so a typo in any single
    member is caught here rather than as a downstream KeyError.
    """

    @pytest.mark.parametrize(
        "member,value",
        [
            (Key.A, "a"),
            (Key.Z, "z"),
            (Key.NUM_0, "0"),
            (Key.NUM_9, "9"),
            (Key.F1, "f1"),
            (Key.F12, "f12"),
            (Key.SHIFT, "shift"),
            (Key.SHIFT_LEFT, "shiftleft"),
            (Key.SHIFT_RIGHT, "shiftright"),
            (Key.CTRL_LEFT, "ctrlleft"),
            (Key.ALT_RIGHT, "altright"),
            (Key.WIN_LEFT, "winleft"),
            (Key.UP, "up"),
            (Key.PAGE_UP, "pageup"),
            (Key.ESCAPE, "escape"),
            (Key.SPACE, "space"),
            (Key.MINUS, "-"),
            (Key.EQUALS, "="),
            (Key.LBRACKET, "["),
            (Key.RBRACKET, "]"),
            (Key.BACKSLASH, "\\"),
            (Key.BACKTICK, "`"),
        ],
    )
    def test_member_value(self, member: Key, value: str):
        assert member.value == value

    def test_str_enum_equals_string(self):
        # StrEnum members compare equal to their string values, so
        # downstream consumers can treat them as plain strings.
        assert Key.A == "a"
        assert Key.ESCAPE == "escape"

    def test_letters_are_complete(self):
        letters = {chr(c) for c in range(ord("a"), ord("z") + 1)}
        members = {member.value for member in Key if len(member.value) == 1}
        assert letters <= members

    def test_digits_are_complete(self):
        digits = {str(d) for d in range(10)}
        members = {member.value for member in Key}
        assert digits <= members

    def test_function_keys_f1_to_f12(self):
        for n in range(1, 13):
            assert Key(f"f{n}") is getattr(Key, f"F{n}")


# --- _INPUTTINO_CODES exhaustiveness (Linux-only) -------------------------


@only_linux
class TestInputtinoCodes:
    """Every :class:`Key` member must appear in the inputtino mapping.

    A missing entry would surface as a ``KeyError`` at the first
    runtime call -- this test pulls the failure forward to test
    discovery time so it can never escape into production.
    """

    def test_mapping_covers_all_keys(self):
        from vrcpilot.controls.keyboard import _INPUTTINO_CODES

        assert set(_INPUTTINO_CODES.keys()) == set(Key)

    def test_mapping_values_are_inputtino_keycodes(self):
        import inputtino

        from vrcpilot.controls.keyboard import _INPUTTINO_CODES

        for member, code in _INPUTTINO_CODES.items():
            assert isinstance(
                code, inputtino.KeyCode
            ), f"{member!r} maps to non-KeyCode value {code!r}"

    @pytest.mark.parametrize(
        "key_name,code_name",
        [
            ("ESCAPE", "ESC"),
            ("EQUALS", "PLUS"),
            ("BACKTICK", "TILDE"),
            ("LBRACKET", "OPEN_BRACKET"),
            ("RBRACKET", "CLOSE_BRACKET"),
            ("SHIFT_LEFT", "LEFT_SHIFT"),
            ("SHIFT_RIGHT", "RIGHT_SHIFT"),
            ("CTRL_LEFT", "LEFT_CONTROL"),
            ("CTRL_RIGHT", "RIGHT_CONTROL"),
            ("ALT_LEFT", "LEFT_ALT"),
            ("ALT_RIGHT", "RIGHT_ALT"),
            ("WIN_LEFT", "LEFT_WIN"),
            ("WIN_RIGHT", "RIGHT_WIN"),
            ("NUM_0", "KEY_0"),
            ("NUM_9", "KEY_9"),
        ],
    )
    def test_known_name_translations(self, key_name: str, code_name: str):
        import inputtino

        from vrcpilot.controls.keyboard import _INPUTTINO_CODES

        key = getattr(Key, key_name)
        expected = getattr(inputtino.KeyCode, code_name)
        assert _INPUTTINO_CODES[key] is expected


# --- ABC template-method tests (cross-platform) ---------------------------


class TestKeyboardGuardWiring:
    """Verify the ABC runs ``ensure_target`` exactly when ``focus`` allows.

    Uses the real :class:`ImplKeyboard` (not a mock) so the abstract
    method dispatch and kwarg forwarding are exercised; only
    ``ensure_target`` is patched.
    """

    def test_focus_true_calls_ensure_target_for_every_method(
        self, mocker: MockerFixture
    ):
        guard = mocker.patch("vrcpilot.controls.keyboard.ensure_target")
        impl = ImplKeyboard()

        impl.press(Key.A)
        impl.down(Key.SHIFT_LEFT)
        impl.up(Key.SHIFT_LEFT)

        assert guard.call_count == 3

    def test_focus_false_skips_ensure_target(self, mocker: MockerFixture):
        guard = mocker.patch("vrcpilot.controls.keyboard.ensure_target")
        impl = ImplKeyboard()

        impl.press(Key.A, focus=False)
        impl.down(Key.SHIFT_LEFT, focus=False)
        impl.up(Key.SHIFT_LEFT, focus=False)

        guard.assert_not_called()

    def test_press_forwards_arguments(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.controls.keyboard.ensure_target")
        impl = ImplKeyboard()

        impl.press(Key.A, duration=0.05)
        impl.press(Key.SPACE)  # default duration=0.0

        assert impl.calls == [
            ("_do_press", {"key": Key.A, "duration": 0.05}),
            ("_do_press", {"key": Key.SPACE, "duration": 0.0}),
        ]

    def test_down_up_forward_key(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.controls.keyboard.ensure_target")
        impl = ImplKeyboard()

        impl.down(Key.CTRL_LEFT)
        impl.up(Key.CTRL_LEFT)

        assert impl.calls == [
            ("_do_down", {"key": Key.CTRL_LEFT}),
            ("_do_up", {"key": Key.CTRL_LEFT}),
        ]


# --- LinuxKeyboard tests (Linux-only) -------------------------------------


@pytest.fixture
def fake_inputtino_keyboard(mocker: MockerFixture) -> FakeInputtinoKeyboard:
    """Patch ``inputtino.Keyboard`` with a recording fake.

    Linux-only fixture: imports ``inputtino`` to satisfy pyright at
    test discovery time but is gated by the ``only_linux`` mark on
    test classes that use it. The fake instance is also returned so
    tests can read ``.calls`` directly.
    """
    fake = FakeInputtinoKeyboard()
    mocker.patch("vrcpilot.controls.keyboard.inputtino.Keyboard", return_value=fake)
    return fake


@only_linux
class TestLinuxKeyboard:
    """Exercise the inputtino backend without touching ``/dev/uinput``.

    The Linux-only mark prevents collection on Windows; the
    ``fake_inputtino_keyboard`` fixture replaces ``inputtino.Keyboard``
    so the production code runs end-to-end against a fake.
    """

    def test_do_press_forwards_to_type(
        self, fake_inputtino_keyboard: FakeInputtinoKeyboard
    ):
        import inputtino

        from vrcpilot.controls.keyboard import LinuxKeyboard

        kb = LinuxKeyboard()
        kb._do_press(Key.A, duration=0.05)

        assert fake_inputtino_keyboard.type_calls == [
            {"key_code": inputtino.KeyCode.A, "duration": 0.05}
        ]

    def test_do_press_zero_duration_still_calls_type(
        self, fake_inputtino_keyboard: FakeInputtinoKeyboard
    ):
        import inputtino

        from vrcpilot.controls.keyboard import LinuxKeyboard

        kb = LinuxKeyboard()
        kb._do_press(Key.A, duration=0.0)

        # inputtino.Keyboard.type still produces a paired down/up at
        # duration=0.0, so production code forwards the value as-is.
        assert fake_inputtino_keyboard.type_calls == [
            {"key_code": inputtino.KeyCode.A, "duration": 0.0}
        ]

    def test_do_press_escape_uses_inputtino_esc(
        self, fake_inputtino_keyboard: FakeInputtinoKeyboard
    ):
        # Spec name `Key.ESCAPE` -> inputtino name `KeyCode.ESC`. The
        # mapping must bridge that gap, otherwise the manual ESC
        # toggle scenario would silently send the wrong code.
        import inputtino

        from vrcpilot.controls.keyboard import LinuxKeyboard

        kb = LinuxKeyboard()
        kb._do_press(Key.ESCAPE, duration=0.0)

        assert fake_inputtino_keyboard.type_calls == [
            {"key_code": inputtino.KeyCode.ESC, "duration": 0.0}
        ]

    def test_do_down_forwards_to_press(
        self, fake_inputtino_keyboard: FakeInputtinoKeyboard
    ):
        import inputtino

        from vrcpilot.controls.keyboard import LinuxKeyboard

        kb = LinuxKeyboard()
        kb._do_down(Key.SHIFT_LEFT)

        assert fake_inputtino_keyboard.press_calls == [
            {"key_code": inputtino.KeyCode.LEFT_SHIFT}
        ]

    def test_do_up_forwards_to_release(
        self, fake_inputtino_keyboard: FakeInputtinoKeyboard
    ):
        import inputtino

        from vrcpilot.controls.keyboard import LinuxKeyboard

        kb = LinuxKeyboard()
        kb._do_up(Key.CTRL_RIGHT)

        assert fake_inputtino_keyboard.release_calls == [
            {"key_code": inputtino.KeyCode.RIGHT_CONTROL}
        ]

    def test_modifier_combo_sequence(
        self, fake_inputtino_keyboard: FakeInputtinoKeyboard, mocker: MockerFixture
    ):
        # Drive the public methods so the guard is invoked, but stub
        # it out so the test does not need a running VRChat.
        import inputtino

        from vrcpilot.controls.keyboard import LinuxKeyboard

        mocker.patch("vrcpilot.controls.keyboard.ensure_target")
        kb = LinuxKeyboard()

        kb.down(Key.SHIFT_LEFT)
        kb.press(Key.A)
        kb.up(Key.SHIFT_LEFT)

        assert fake_inputtino_keyboard.calls == [
            ("press", {"key_code": inputtino.KeyCode.LEFT_SHIFT}),
            ("type", {"key_code": inputtino.KeyCode.A, "duration": 0.0}),
            ("release", {"key_code": inputtino.KeyCode.LEFT_SHIFT}),
        ]


# --- _get() lazy-init tests ----------------------------------------------


class TestGetLazyInit:
    """The backend should be created on first access and reused after."""

    def test_returns_same_instance_on_repeated_calls(self):
        # Replace the backend with a recording impl so the test runs
        # on every platform without needing inputtino.
        instance = ImplKeyboard()
        keyboard_mod._instance = instance

        assert keyboard_mod._get() is instance
        assert keyboard_mod._get() is instance

    def test_unsupported_platform_raises_not_implemented(self, mocker: MockerFixture):
        # Force the "neither linux nor win32" branch by patching the
        # module-level sys.platform reference. Singleton has been
        # cleared by the autouse fixture, so the branch is reached.
        mocker.patch.object(sys, "platform", "darwin")

        with pytest.raises(NotImplementedError, match="darwin"):
            keyboard_mod._get()


# --- Module function delegation tests -------------------------------------


class _SpyKeyboard(Keyboard):
    """Backend that records the public-API call it received.

    Distinct from :class:`ImplKeyboard` because we want to assert
    which *public* method on the backend was called -- the module
    functions forward through the public method (which then runs the
    guard and delegates to ``_do_*``), not directly to ``_do_*``.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    @override
    def press(self, key: Key, *, duration: float = 0.0, focus: bool = True) -> None:
        self.calls.append(
            (
                "press",
                {"key": key, "duration": duration, "focus": focus},
            )
        )

    @override
    def down(self, key: Key, *, focus: bool = True) -> None:
        self.calls.append(("down", {"key": key, "focus": focus}))

    @override
    def up(self, key: Key, *, focus: bool = True) -> None:
        self.calls.append(("up", {"key": key, "focus": focus}))

    @override
    def _do_press(self, key: Key, *, duration: float) -> None:
        # Not exercised; the spy overrides the public methods directly.
        ...

    @override
    def _do_down(self, key: Key) -> None: ...

    @override
    def _do_up(self, key: Key) -> None: ...


class TestModuleFunctions:
    """``press`` / ``down`` / ``up`` must forward through ``_get()``."""

    def test_press_forwards(self):
        spy = _SpyKeyboard()
        keyboard_mod._instance = spy

        keyboard_mod.press(Key.A, duration=0.05, focus=False)

        assert spy.calls == [
            ("press", {"key": Key.A, "duration": 0.05, "focus": False})
        ]

    def test_down_forwards(self):
        spy = _SpyKeyboard()
        keyboard_mod._instance = spy

        keyboard_mod.down(Key.CTRL_LEFT)

        assert spy.calls == [("down", {"key": Key.CTRL_LEFT, "focus": True})]

    def test_up_forwards(self):
        spy = _SpyKeyboard()
        keyboard_mod._instance = spy

        keyboard_mod.up(Key.CTRL_LEFT, focus=False)

        assert spy.calls == [("up", {"key": Key.CTRL_LEFT, "focus": False})]
