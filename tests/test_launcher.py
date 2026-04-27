"""Tests for :mod:`vrcpilot.launcher`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import psutil
import pytest
from pytest_mock import MockerFixture

from vrcpilot.launcher import (
    VRCHAT_PROCESS_NAME,
    VRCHAT_STEAM_APP_ID,
    build_launch_command,
    launch_vrchat,
    terminate_vrchat,
)


def _make_proc_mock(mocker: MockerFixture, name: str) -> MagicMock:
    proc = mocker.MagicMock()
    proc.info = {"name": name}
    return proc


class TestBuildLaunchCommand:
    def test_basic(self):
        steam = Path("/usr/bin/steam")

        result = build_launch_command(steam, 438100)

        assert result == [str(steam), "-applaunch", "438100"]

    @pytest.mark.parametrize("app_id", [438100, 440, 1])
    def test_app_id_stringified(self, app_id: int):
        result = build_launch_command(Path("/usr/bin/steam"), app_id)

        assert result[2] == str(app_id)

    def test_default_app_id(self):
        result = build_launch_command(Path("/usr/bin/steam"))

        assert result[2] == str(VRCHAT_STEAM_APP_ID)


class TestLaunchVrchat:
    def test_invokes_popen_with_default_argv(self, mocker: MockerFixture):
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

    def test_propagates_steam_path_override(self, mocker: MockerFixture):
        override = Path("/custom/steam")
        find_mock = mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=override,
        )
        mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch_vrchat(steam_path=override)

        find_mock.assert_called_once_with(override)

    def test_app_id_override(self, mocker: MockerFixture):
        steam = Path("/usr/bin/steam")
        mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=steam,
        )
        popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch_vrchat(app_id=440)

        argv = popen_mock.call_args.args[0]
        assert argv == [str(steam), "-applaunch", "440"]

    def test_uses_new_process_group_on_windows(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
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

    def test_uses_new_session_on_posix(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
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


class TestTerminateVrchat:
    def test_kills_matching_process(self, mocker: MockerFixture):
        proc = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME)
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[proc],
        )
        wait_mock = mocker.patch("vrcpilot.launcher.psutil.wait_procs")

        result = terminate_vrchat()

        assert result is True
        proc.kill.assert_called_once()
        wait_mock.assert_called_once()

    def test_returns_false_when_not_running(self, mocker: MockerFixture):
        other = _make_proc_mock(mocker, "explorer.exe")
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[other],
        )
        wait_mock = mocker.patch("vrcpilot.launcher.psutil.wait_procs")

        result = terminate_vrchat()

        assert result is False
        other.kill.assert_not_called()
        wait_mock.assert_not_called()

    def test_kills_all_matching(self, mocker: MockerFixture):
        p1 = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME)
        p2 = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME)
        other = _make_proc_mock(mocker, "explorer.exe")
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[p1, other, p2],
        )
        mocker.patch("vrcpilot.launcher.psutil.wait_procs")

        result = terminate_vrchat()

        assert result is True
        p1.kill.assert_called_once()
        p2.kill.assert_called_once()
        other.kill.assert_not_called()

    def test_swallows_no_such_process(self, mocker: MockerFixture):
        proc = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME)
        proc.kill.side_effect = psutil.NoSuchProcess(pid=9999)
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[proc],
        )
        mocker.patch("vrcpilot.launcher.psutil.wait_procs")

        result = terminate_vrchat()

        assert result is True
        proc.kill.assert_called_once()
