"""Tests for :mod:`vrcpilot.cli.unfocus`."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from vrcpilot.cli import main


class TestUnfocusCommand:
    def test_silent_on_success(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        # Patch the re-exported window function on ``vrcpilot.cli`` --
        # ``unfocus.run`` resolves the call through ``_cli.unfocus`` so
        # this is the right boundary to swap.
        mocker.patch("vrcpilot.cli.unfocus", return_value=True)

        exit_code = main(["unfocus"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_stderr_on_failure(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.unfocus", return_value=False)

        exit_code = main(["unfocus"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "vrcpilot: could not unfocus VRChat\n"
