"""Tests for :mod:`vrcpilot.cli`."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from argcomplete.completers import FilesCompleter
from pytest_mock import MockerFixture

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.cli import _build_parser, main
from vrcpilot.launcher import VRCHAT_STEAM_APP_ID, OscConfig


def _patch_launch_vrchat(mocker: MockerFixture, pid: int = 1234):
    process = mocker.MagicMock()
    process.pid = pid
    return mocker.patch("vrcpilot.cli.launch_vrchat", return_value=process)


class TestLaunchCommand:
    def test_uses_defaults(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(["launch"])

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=VRCHAT_STEAM_APP_ID,
            steam_path=None,
            no_vr=False,
            screen_width=None,
            screen_height=None,
            osc=None,
        )

    def test_app_id_override(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(["launch", "--app-id", "12345"])

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=12345,
            steam_path=None,
            no_vr=False,
            screen_width=None,
            screen_height=None,
            osc=None,
        )

    def test_steam_path_override(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(["launch", "--steam-path", "/foo/Steam.exe"])

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=VRCHAT_STEAM_APP_ID,
            steam_path=Path("/foo/Steam.exe"),
            no_vr=False,
            screen_width=None,
            screen_height=None,
            osc=None,
        )

    def test_reports_steam_not_found(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch(
            "vrcpilot.cli.launch_vrchat",
            side_effect=SteamNotFoundError("nope"),
        )

        exit_code = main(["launch"])

        assert exit_code == 2
        captured = capsys.readouterr()
        assert "nope" in captured.err

    def test_no_vr_flag_propagates(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(["launch", "--no-vr"])

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=VRCHAT_STEAM_APP_ID,
            steam_path=None,
            no_vr=True,
            screen_width=None,
            screen_height=None,
            osc=None,
        )

    def test_screen_dimensions_propagate(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(["launch", "--screen-width", "1280", "--screen-height", "720"])

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=VRCHAT_STEAM_APP_ID,
            steam_path=None,
            no_vr=False,
            screen_width=1280,
            screen_height=720,
            osc=None,
        )

    def test_osc_in_port_creates_config(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(["launch", "--osc-in-port", "9000"])

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=VRCHAT_STEAM_APP_ID,
            steam_path=None,
            no_vr=False,
            screen_width=None,
            screen_height=None,
            osc=OscConfig(in_port=9000, out_ip="127.0.0.1", out_port=9001),
        )

    def test_osc_full_override(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(
            [
                "launch",
                "--osc-in-port",
                "10000",
                "--osc-out-ip",
                "192.168.1.10",
                "--osc-out-port",
                "10001",
            ]
        )

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=VRCHAT_STEAM_APP_ID,
            steam_path=None,
            no_vr=False,
            screen_width=None,
            screen_height=None,
            osc=OscConfig(in_port=10000, out_ip="192.168.1.10", out_port=10001),
        )

    def test_osc_out_options_ignored_without_in_port(self, mocker: MockerFixture):
        launch_mock = _patch_launch_vrchat(mocker)

        exit_code = main(["launch", "--osc-out-ip", "192.168.1.10"])

        assert exit_code == 0
        launch_mock.assert_called_once_with(
            app_id=VRCHAT_STEAM_APP_ID,
            steam_path=None,
            no_vr=False,
            screen_width=None,
            screen_height=None,
            osc=None,
        )


class TestStatusCommand:
    def test_reports_running(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.find_vrchat_pid", return_value=12345)

        exit_code = main(["status"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "VRChat is running" in captured.out
        assert "12345" in captured.out

    def test_reports_not_running(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.find_vrchat_pid", return_value=None)

        exit_code = main(["status"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "VRChat is not running" in captured.out


class TestTerminateCommand:
    def test_reports_killed(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.terminate_vrchat", return_value=True)

        exit_code = main(["terminate"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Terminated" in captured.out

    def test_reports_not_running(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.terminate_vrchat", return_value=False)

        exit_code = main(["terminate"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "not running" in captured.out


class TestMain:
    def test_missing_subcommand_exits(self):
        with pytest.raises(SystemExit):
            main([])


class TestArgcompleteIntegration:
    def test_autocomplete_invoked_with_parser(self, mocker: MockerFixture):
        autocomplete_mock = mocker.patch("vrcpilot.cli.argcomplete.autocomplete")
        _patch_launch_vrchat(mocker)

        exit_code = main(["launch"])

        assert exit_code == 0
        autocomplete_mock.assert_called_once()
        call_args = autocomplete_mock.call_args
        assert isinstance(call_args.args[0], argparse.ArgumentParser)

    def test_steam_path_has_files_completer(self):
        parser = _build_parser()

        subparsers_action = parser._subparsers._group_actions[0]  # type: ignore[union-attr]
        launch_parser = subparsers_action.choices["launch"]
        steam_path_action = next(
            action
            for action in launch_parser._actions
            if "--steam-path" in action.option_strings
        )

        completer = steam_path_action.completer  # type: ignore[attr-defined]
        assert isinstance(completer, FilesCompleter)
        # argcomplete normalizes allowednames; "exe" should appear in some form.
        allowednames = completer.allowednames
        assert any("exe" in name for name in allowednames)

    def test_autocomplete_does_not_block_normal_run(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("_ARGCOMPLETE", raising=False)
        _patch_launch_vrchat(mocker)

        exit_code = main(["launch"])

        assert exit_code == 0
