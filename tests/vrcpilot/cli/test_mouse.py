"""Tests for :mod:`vrcpilot.cli.mouse`.

The CLI calls into :mod:`vrcpilot.controls.mouse` via the ``mouse_api``
re-export. Patching :func:`vrcpilot.controls.mouse._get` to return an
:class:`~tests.helpers.ImplMouse` lets the real public ``mouse.click``
function run end-to-end (focus guard included) while keeping the
backend out of the test. The guard itself is stubbed to a no-op so
tests do not need a live VRChat process; the guard-failure tests
deliberately re-arm the stub to raise.

Only ``click`` is exposed by the CLI: ``move`` / ``press`` / ``release``
/ ``scroll`` cannot work meaningfully across separate ``vrcpilot``
invocations because each process opens and closes its own backend, and
the kernel auto-releases on close.
"""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from tests.helpers import ImplMouse
from vrcpilot.cli import main
from vrcpilot.controls import VRChatNotFocusedError, VRChatNotRunningError
from vrcpilot.controls.mouse import MouseButton


@pytest.fixture
def fake_mouse(mocker: MockerFixture) -> ImplMouse:
    """Wire the public ``mouse`` module to a recording :class:`ImplMouse`.

    Also stubs :func:`vrcpilot.controls.guard.ensure_target` to a no-op
    so the success-path tests do not need a real VRChat process.
    """
    impl = ImplMouse()
    mocker.patch("vrcpilot.controls.mouse._get", return_value=impl)
    mocker.patch("vrcpilot.controls.mouse.ensure_target", return_value=None)
    return impl


class TestMouseClick:
    def test_default_button_is_left(self, fake_mouse: ImplMouse):
        exit_code = main(["mouse", "click"])

        assert exit_code == 0
        assert fake_mouse.calls == [
            (
                "_do_click",
                {"button": MouseButton.LEFT, "count": 1, "duration": 0.0},
            )
        ]

    @pytest.mark.parametrize(
        ("button_arg", "expected_button"),
        [
            ("left", MouseButton.LEFT),
            ("right", MouseButton.RIGHT),
            ("middle", MouseButton.MIDDLE),
        ],
    )
    def test_button_override(
        self,
        fake_mouse: ImplMouse,
        button_arg: str,
        expected_button: MouseButton,
    ):
        exit_code = main(["mouse", "click", button_arg])

        assert exit_code == 0
        assert fake_mouse.calls == [
            (
                "_do_click",
                {"button": expected_button, "count": 1, "duration": 0.0},
            )
        ]

    def test_count_and_duration_propagation(self, fake_mouse: ImplMouse):
        exit_code = main(
            ["mouse", "click", "right", "--count", "3", "--duration", "0.05"]
        )

        assert exit_code == 0
        assert fake_mouse.calls == [
            (
                "_do_click",
                {"button": MouseButton.RIGHT, "count": 3, "duration": 0.05},
            )
        ]

    def test_silent_on_success(
        self, fake_mouse: ImplMouse, capsys: pytest.CaptureFixture[str]
    ):
        del fake_mouse
        exit_code = main(["mouse", "click"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_argparse_rejects_unknown_button(self, capsys: pytest.CaptureFixture[str]):
        with pytest.raises(SystemExit) as excinfo:
            main(["mouse", "click", "foobar"])

        assert excinfo.value.code != 0
        # argparse writes its error to stderr; just ensure something landed.
        captured = capsys.readouterr()
        assert captured.err != ""


class TestMouseRemovedActions:
    @pytest.mark.parametrize(
        "argv",
        [
            ["mouse", "move", "0", "0"],
            ["mouse", "press"],
            ["mouse", "release"],
            ["mouse", "scroll", "1"],
        ],
    )
    def test_removed_actions_are_not_exposed(
        self, argv: list[str], capsys: pytest.CaptureFixture[str]
    ):
        # The CLI deliberately drops move / press / release / scroll:
        # each invocation opens and closes its own backend, so any
        # held-state action would auto-release as the process exits.
        with pytest.raises(SystemExit) as excinfo:
            main(argv)

        assert excinfo.value.code != 0
        captured = capsys.readouterr()
        assert captured.err != ""


class TestMouseGuardErrors:
    def test_not_running_error_returns_exit_1(
        self,
        fake_mouse: ImplMouse,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
    ):
        del fake_mouse  # fixture wires the impl, but the guard fires first
        mocker.patch(
            "vrcpilot.controls.mouse.ensure_target",
            side_effect=VRChatNotRunningError("VRChat is not running"),
        )

        exit_code = main(["mouse", "click"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "vrcpilot:" in captured.err
        assert "VRChat is not running" in captured.err

    def test_not_focused_error_returns_exit_1(
        self,
        fake_mouse: ImplMouse,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
    ):
        del fake_mouse
        mocker.patch(
            "vrcpilot.controls.mouse.ensure_target",
            side_effect=VRChatNotFocusedError("VRChat is not focused"),
        )

        exit_code = main(["mouse", "click"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "vrcpilot:" in captured.err
        assert "VRChat is not focused" in captured.err


class TestMouseDispatch:
    def test_no_action_exits_non_zero(self, capsys: pytest.CaptureFixture[str]):
        # ``add_subparsers(required=True)`` makes argparse error out
        # when ``vrcpilot mouse`` is invoked without a sub-action.
        with pytest.raises(SystemExit) as excinfo:
            main(["mouse"])

        assert excinfo.value.code != 0
        captured = capsys.readouterr()
        assert captured.err != ""
