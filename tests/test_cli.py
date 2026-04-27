"""Tests for :mod:`vrcpilot.cli`."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from vrcpilot.cli import main
from vrcpilot.launcher import VRCHAT_STEAM_APP_ID


def _patch_launch_vrchat(mocker: MockerFixture, pid: int = 1234):
    process = mocker.MagicMock()
    process.pid = pid
    return mocker.patch("vrcpilot.cli.launch_vrchat", return_value=process)


def test_launch_uses_defaults(mocker: MockerFixture):
    launch_mock = _patch_launch_vrchat(mocker)

    exit_code = main(["launch"])

    assert exit_code == 0
    launch_mock.assert_called_once_with(app_id=VRCHAT_STEAM_APP_ID, steam_path=None)


def test_launch_app_id_override(mocker: MockerFixture):
    launch_mock = _patch_launch_vrchat(mocker)

    exit_code = main(["launch", "--app-id", "12345"])

    assert exit_code == 0
    launch_mock.assert_called_once_with(app_id=12345, steam_path=None)


def test_launch_steam_path_override(mocker: MockerFixture):
    launch_mock = _patch_launch_vrchat(mocker)

    exit_code = main(["launch", "--steam-path", "/foo/Steam.exe"])

    assert exit_code == 0
    launch_mock.assert_called_once_with(
        app_id=VRCHAT_STEAM_APP_ID, steam_path=Path("/foo/Steam.exe")
    )


def test_launch_reports_steam_not_found(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
):
    from vrcpilot._steam import SteamNotFoundError

    mocker.patch(
        "vrcpilot.cli.launch_vrchat",
        side_effect=SteamNotFoundError("nope"),
    )

    exit_code = main(["launch"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "nope" in captured.err


def test_missing_subcommand_exits():
    with pytest.raises(SystemExit):
        main([])
