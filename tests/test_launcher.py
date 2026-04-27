"""Tests for :mod:`vrcpilot.launcher`."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from vrcpilot.launcher import (
    VRCHAT_STEAM_APP_ID,
    build_launch_command,
    launch_vrchat,
)


def test_build_launch_command_basic():
    steam = Path("/usr/bin/steam")

    result = build_launch_command(steam, 438100)

    assert result == [str(steam), "-applaunch", "438100"]


@pytest.mark.parametrize("app_id", [438100, 440, 1])
def test_build_launch_command_app_id_stringified(app_id: int):
    result = build_launch_command(Path("/usr/bin/steam"), app_id)

    assert result[2] == str(app_id)


def test_build_launch_command_default_app_id():
    result = build_launch_command(Path("/usr/bin/steam"))

    assert result[2] == str(VRCHAT_STEAM_APP_ID)


def test_launch_vrchat_invokes_popen_with_default_argv(mocker: MockerFixture):
    steam = Path("/usr/bin/steam")
    mocker.patch(
        "vrcpilot.launcher.find_steam_executable",
        return_value=steam,
    )
    popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

    launch_vrchat()

    popen_mock.assert_called_once()
    argv = popen_mock.call_args.args[0]
    assert argv == [str(steam), "-applaunch", "438100"]


def test_launch_vrchat_propagates_steam_path_override(mocker: MockerFixture):
    override = Path("/custom/steam")
    find_mock = mocker.patch(
        "vrcpilot.launcher.find_steam_executable",
        return_value=override,
    )
    mocker.patch("vrcpilot.launcher.subprocess.Popen")

    launch_vrchat(steam_path=override)

    find_mock.assert_called_once_with(override)


def test_launch_vrchat_app_id_override(mocker: MockerFixture):
    steam = Path("/usr/bin/steam")
    mocker.patch(
        "vrcpilot.launcher.find_steam_executable",
        return_value=steam,
    )
    popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

    launch_vrchat(app_id=440)

    argv = popen_mock.call_args.args[0]
    assert argv == [str(steam), "-applaunch", "440"]


def test_launch_vrchat_uses_new_process_group_on_windows(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    monkeypatch.setattr("sys.platform", "win32")
    mocker.patch(
        "vrcpilot.launcher.find_steam_executable",
        return_value=Path("C:/Steam/Steam.exe"),
    )
    popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

    launch_vrchat()

    assert "creationflags" in popen_mock.call_args.kwargs
    assert "start_new_session" not in popen_mock.call_args.kwargs


def test_launch_vrchat_uses_new_session_on_posix(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    monkeypatch.setattr("sys.platform", "linux")
    mocker.patch(
        "vrcpilot.launcher.find_steam_executable",
        return_value=Path("/usr/bin/steam"),
    )
    popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

    launch_vrchat()

    assert popen_mock.call_args.kwargs.get("start_new_session") is True
    assert "creationflags" not in popen_mock.call_args.kwargs
