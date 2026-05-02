"""Tests for :mod:`vrcpilot.cli.keyboard`.

The CLI calls into :mod:`vrcpilot.controls.keyboard` via the
``keyboard_api`` re-export. Patching :func:`vrcpilot.controls.keyboard._get`
to return an :class:`~tests.helpers.ImplKeyboard` lets the real public
``keyboard.press`` function run end-to-end (focus guard included) while
keeping the backend out of the test. The guard itself is stubbed to a
no-op so tests do not need a live VRChat process; the guard-failure
tests deliberately re-arm the stub to raise.

Only ``press`` is exposed by the CLI: ``up`` / ``down`` cannot work
across separate ``vrcpilot`` invocations because each process opens
and closes its own backend, and the kernel auto-releases on close.
"""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from tests.helpers import ImplKeyboard
from vrcpilot.cli import main
from vrcpilot.controls import VRChatNotFocusedError, VRChatNotRunningError
from vrcpilot.controls.keyboard import Key


@pytest.fixture
def fake_keyboard(mocker: MockerFixture) -> ImplKeyboard:
    """Wire the public ``keyboard`` module to a recording
    :class:`ImplKeyboard`.

    Also stubs :func:`vrcpilot.controls.guard.ensure_target` to a no-op
    so the success-path tests do not need a real VRChat process.
    """
    impl = ImplKeyboard()
    mocker.patch("vrcpilot.controls.keyboard._get", return_value=impl)
    mocker.patch("vrcpilot.controls.keyboard.ensure_target", return_value=None)
    return impl


class TestKeyboardPress:
    @pytest.mark.parametrize(
        ("key_arg", "expected_key"),
        [
            ("a", Key.A),
            ("enter", Key.ENTER),
            ("escape", Key.ESCAPE),
        ],
    )
    def test_dispatches_single_key_with_default_duration(
        self,
        fake_keyboard: ImplKeyboard,
        key_arg: str,
        expected_key: Key,
    ):
        exit_code = main(["keyboard", "press", key_arg])

        assert exit_code == 0
        assert fake_keyboard.calls == [
            ("_do_press", {"key": expected_key, "duration": 0.1})
        ]

    def test_default_duration_is_0_1(self, fake_keyboard: ImplKeyboard):
        # Match the API default in vrcpilot.controls.keyboard.Keyboard.press
        # (Unity / VRChat drops shorter holds - see
        # .claude/memory/project_keyboard_press_duration.md).
        exit_code = main(["keyboard", "press", "a"])

        assert exit_code == 0
        assert len(fake_keyboard.calls) == 1
        name, kwargs = fake_keyboard.calls[0]
        assert name == "_do_press"
        assert kwargs["duration"] == 0.1

    def test_custom_duration_propagates(self, fake_keyboard: ImplKeyboard):
        exit_code = main(["keyboard", "press", "a", "--duration", "0.5"])

        assert exit_code == 0
        assert fake_keyboard.calls == [("_do_press", {"key": Key.A, "duration": 0.5})]

    def test_silent_on_success(
        self, fake_keyboard: ImplKeyboard, capsys: pytest.CaptureFixture[str]
    ):
        del fake_keyboard
        exit_code = main(["keyboard", "press", "a"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_processes_keys_in_order_with_shared_duration(
        self, fake_keyboard: ImplKeyboard
    ):
        exit_code = main(["keyboard", "press", "a", "b", "c", "--duration", "0.2"])

        assert exit_code == 0
        assert fake_keyboard.calls == [
            ("_do_press", {"key": Key.A, "duration": 0.2}),
            ("_do_press", {"key": Key.B, "duration": 0.2}),
            ("_do_press", {"key": Key.C, "duration": 0.2}),
        ]


class TestKeyboardArgparseValidation:
    def test_press_requires_at_least_one_key(self, capsys: pytest.CaptureFixture[str]):
        # ``nargs="+"`` rejects zero arguments.
        with pytest.raises(SystemExit) as excinfo:
            main(["keyboard", "press"])

        assert excinfo.value.code != 0
        captured = capsys.readouterr()
        assert captured.err != ""

    def test_argparse_rejects_unknown_key(self, capsys: pytest.CaptureFixture[str]):
        with pytest.raises(SystemExit) as excinfo:
            main(["keyboard", "press", "not_a_real_key"])

        assert excinfo.value.code != 0
        # argparse writes its error to stderr; just ensure something landed.
        captured = capsys.readouterr()
        assert captured.err != ""

    @pytest.mark.parametrize("removed", ["up", "down"])
    def test_up_and_down_subcommands_are_not_exposed(
        self, removed: str, capsys: pytest.CaptureFixture[str]
    ):
        # The CLI deliberately drops up / down: each invocation opens and
        # closes its own backend so a held key would auto-release as the
        # process exits.
        with pytest.raises(SystemExit) as excinfo:
            main(["keyboard", removed, "a"])

        assert excinfo.value.code != 0
        captured = capsys.readouterr()
        assert captured.err != ""


class TestKeyboardGuardErrors:
    def test_not_running_error_returns_exit_1(
        self,
        fake_keyboard: ImplKeyboard,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
    ):
        del fake_keyboard  # fixture wires the impl, but the guard fires first
        mocker.patch(
            "vrcpilot.controls.keyboard.ensure_target",
            side_effect=VRChatNotRunningError("VRChat is not running"),
        )

        exit_code = main(["keyboard", "press", "a"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "vrcpilot:" in captured.err
        assert "VRChat is not running" in captured.err

    def test_not_focused_error_returns_exit_1(
        self,
        fake_keyboard: ImplKeyboard,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
    ):
        del fake_keyboard
        mocker.patch(
            "vrcpilot.controls.keyboard.ensure_target",
            side_effect=VRChatNotFocusedError("VRChat is not focused"),
        )

        exit_code = main(["keyboard", "press", "a"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "vrcpilot:" in captured.err
        assert "VRChat is not focused" in captured.err

    def test_first_key_guard_error_aborts_remaining_keys(
        self,
        fake_keyboard: ImplKeyboard,
        mocker: MockerFixture,
    ):
        # ``ensure_target`` raises on the very first call -> the second
        # key must not be processed (no second ``_do_press`` recorded).
        mocker.patch(
            "vrcpilot.controls.keyboard.ensure_target",
            side_effect=VRChatNotRunningError("VRChat is not running"),
        )

        exit_code = main(["keyboard", "press", "a", "b"])

        assert exit_code == 1
        assert fake_keyboard.calls == []


class TestKeyboardDispatch:
    def test_no_action_exits_non_zero(self, capsys: pytest.CaptureFixture[str]):
        # ``add_subparsers(required=True)`` makes argparse error out
        # when ``vrcpilot keyboard`` is invoked without a sub-action.
        with pytest.raises(SystemExit) as excinfo:
            main(["keyboard"])

        assert excinfo.value.code != 0
        captured = capsys.readouterr()
        assert captured.err != ""
