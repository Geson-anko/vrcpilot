"""Tests for :mod:`vrcpilot.cli.focus`."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from vrcpilot.cli import main


class TestFocusCommand:
    def test_silent_on_success(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        # ``focus.run`` calls the locally imported ``focus`` window
        # function, so the right patch boundary is the binding inside
        # the submodule.
        mocker.patch("vrcpilot.cli.focus.focus", return_value=True)

        exit_code = main(["focus"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_stderr_on_failure(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.focus.focus", return_value=False)

        exit_code = main(["focus"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "vrcpilot: could not focus VRChat\n"
