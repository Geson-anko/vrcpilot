"""Tests for :mod:`vrcpilot.launcher`."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import psutil
import pytest
from pytest_mock import MockerFixture

from tests.helpers import only_linux, only_windows
from vrcpilot.launcher import (
    VRCHAT_PROCESS_NAME,
    VRCHAT_STEAM_APP_ID,
    OscConfig,
    build_launch_command,
    build_vrchat_launch_args,
    find_pid,
    launch,
    terminate,
)


def _make_proc_mock(mocker: MockerFixture, name: str, pid: int = 12345) -> MagicMock:
    proc = mocker.MagicMock()
    proc.info = {"name": name}
    proc.pid = pid
    return proc


class TestOscConfig:
    def test_to_launch_arg_default(self):
        assert OscConfig().to_launch_arg() == "--osc=9000:127.0.0.1:9001"

    @pytest.mark.parametrize(
        ("in_port", "out_ip", "out_port", "expected"),
        [
            (9000, "127.0.0.1", 9001, "--osc=9000:127.0.0.1:9001"),
            (10000, "192.168.1.10", 10001, "--osc=10000:192.168.1.10:10001"),
            (1234, "0.0.0.0", 5678, "--osc=1234:0.0.0.0:5678"),
        ],
    )
    def test_to_launch_arg_custom(
        self, in_port: int, out_ip: str, out_port: int, expected: str
    ):
        cfg = OscConfig(in_port=in_port, out_ip=out_ip, out_port=out_port)

        assert cfg.to_launch_arg() == expected

    def test_is_frozen(self):
        cfg = OscConfig()

        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.in_port = 1234  # type: ignore[misc]


class TestBuildVrchatLaunchArgs:
    def test_no_args_returns_empty(self):
        assert build_vrchat_launch_args() == []

    def test_no_vr(self):
        assert build_vrchat_launch_args(no_vr=True) == ["--no-vr"]

    @pytest.mark.parametrize(
        ("width", "height", "expected"),
        [
            (1280, None, ["-screen-width", "1280"]),
            (None, 720, ["-screen-height", "720"]),
            (
                1280,
                720,
                ["-screen-width", "1280", "-screen-height", "720"],
            ),
        ],
    )
    def test_screen_dimensions(
        self, width: int | None, height: int | None, expected: list[str]
    ):
        result = build_vrchat_launch_args(screen_width=width, screen_height=height)

        assert result == expected

    def test_osc(self):
        result = build_vrchat_launch_args(osc=OscConfig(in_port=9000))

        assert result == ["--osc=9000:127.0.0.1:9001"]

    def test_extra_args_appended(self):
        result = build_vrchat_launch_args(extra_args=["--enable-debug-gui"])

        assert result == ["--enable-debug-gui"]

    def test_combined_order(self):
        result = build_vrchat_launch_args(
            no_vr=True,
            screen_width=1280,
            screen_height=720,
            osc=OscConfig(),
            extra_args=["--enable-debug-gui", "--profile=2"],
        )

        assert result == [
            "--no-vr",
            "-screen-width",
            "1280",
            "-screen-height",
            "720",
            "--osc=9000:127.0.0.1:9001",
            "--enable-debug-gui",
            "--profile=2",
        ]


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

    def test_appends_vrchat_args(self):
        steam = Path("/usr/bin/steam")

        result = build_launch_command(
            steam, 438100, vrchat_args=["--no-vr", "-screen-width", "1280"]
        )

        assert result == [
            str(steam),
            "-applaunch",
            "438100",
            "--no-vr",
            "-screen-width",
            "1280",
        ]

    def test_no_vrchat_args_returns_legacy_shape(self):
        steam = Path("/usr/bin/steam")

        result = build_launch_command(steam, 438100, vrchat_args=None)

        assert result == [str(steam), "-applaunch", "438100"]


class TestLaunch:
    def test_invokes_popen_with_default_argv(self, mocker: MockerFixture):
        steam = Path("/usr/bin/steam")
        mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=steam,
        )
        popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch()

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

        launch(steam_path=override)

        find_mock.assert_called_once_with(override)

    def test_app_id_override(self, mocker: MockerFixture):
        steam = Path("/usr/bin/steam")
        mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=steam,
        )
        popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch(app_id=440)

        argv = popen_mock.call_args.args[0]
        assert argv == [str(steam), "-applaunch", "440"]

    @only_windows
    def test_uses_new_process_group_on_windows(self, mocker: MockerFixture):
        mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=Path("C:/Steam/Steam.exe"),
        )
        popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch()

        assert "creationflags" in popen_mock.call_args.kwargs
        assert "start_new_session" not in popen_mock.call_args.kwargs

    @only_linux
    def test_uses_new_session_on_linux(self, mocker: MockerFixture):
        mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=Path("/usr/bin/steam"),
        )
        popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch()

        assert popen_mock.call_args.kwargs.get("start_new_session") is True
        assert "creationflags" not in popen_mock.call_args.kwargs

    def test_passes_no_vr_to_argv(self, mocker: MockerFixture):
        steam = Path("/usr/bin/steam")
        mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=steam,
        )
        popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch(no_vr=True)

        argv = popen_mock.call_args.args[0]
        assert "--no-vr" in argv

    def test_passes_osc_to_argv(self, mocker: MockerFixture):
        steam = Path("/usr/bin/steam")
        mocker.patch(
            "vrcpilot.launcher.find_steam_executable",
            return_value=steam,
        )
        popen_mock = mocker.patch("vrcpilot.launcher.subprocess.Popen")

        launch(osc=OscConfig(in_port=9000))

        argv = popen_mock.call_args.args[0]
        assert "--osc=9000:127.0.0.1:9001" in argv


class TestFindPid:
    def test_returns_pid_when_running(self, mocker: MockerFixture):
        proc = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME, pid=4242)
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[proc],
        )

        assert find_pid() == 4242

    def test_returns_none_when_not_running(self, mocker: MockerFixture):
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[],
        )

        assert find_pid() is None

    def test_ignores_other_processes(self, mocker: MockerFixture):
        other = _make_proc_mock(mocker, "explorer.exe", pid=1)
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[other],
        )

        assert find_pid() is None

    def test_returns_first_when_multiple_match(self, mocker: MockerFixture):
        p1 = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME, pid=111)
        p2 = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME, pid=222)
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[p1, p2],
        )

        assert find_pid() == 111


class TestTerminate:
    def test_kills_matching_process(self, mocker: MockerFixture):
        proc = _make_proc_mock(mocker, VRCHAT_PROCESS_NAME)
        mocker.patch(
            "vrcpilot.launcher.psutil.process_iter",
            return_value=[proc],
        )
        wait_mock = mocker.patch("vrcpilot.launcher.psutil.wait_procs")

        result = terminate()

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

        result = terminate()

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

        result = terminate()

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

        result = terminate()

        assert result is True
        proc.kill.assert_called_once()
