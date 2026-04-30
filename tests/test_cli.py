"""Tests for :mod:`vrcpilot.cli`."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Self

import numpy as np
import pytest
from argcomplete.completers import FilesCompleter
from pytest_mock import MockerFixture

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.cli import _build_parser, main
from vrcpilot.process import VRCHAT_STEAM_APP_ID, OscConfig


def _patch_launch(mocker: MockerFixture):
    return mocker.patch("vrcpilot.cli.launch", return_value=None)


class TestLaunchCommand:
    def test_uses_defaults(self, mocker: MockerFixture):
        launch_mock = _patch_launch(mocker)

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

    def test_reports_launched_message(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        _patch_launch(mocker)

        exit_code = main(["launch"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Launched VRChat." in captured.out

    def test_app_id_override(self, mocker: MockerFixture):
        launch_mock = _patch_launch(mocker)

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
        launch_mock = _patch_launch(mocker)

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
            "vrcpilot.cli.launch",
            side_effect=SteamNotFoundError("nope"),
        )

        exit_code = main(["launch"])

        assert exit_code == 2
        captured = capsys.readouterr()
        assert "nope" in captured.err

    def test_no_vr_flag_propagates(self, mocker: MockerFixture):
        launch_mock = _patch_launch(mocker)

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
        launch_mock = _patch_launch(mocker)

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
        launch_mock = _patch_launch(mocker)

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
        launch_mock = _patch_launch(mocker)

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
        launch_mock = _patch_launch(mocker)

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
        mocker.patch("vrcpilot.cli.find_pid", return_value=12345)

        exit_code = main(["status"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "VRChat is running" in captured.out
        assert "12345" in captured.out

    def test_reports_not_running(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.find_pid", return_value=None)

        exit_code = main(["status"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "VRChat is not running" in captured.out


class TestTerminateCommand:
    def test_reports_killed(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.terminate", return_value=True)

        exit_code = main(["terminate"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Terminated" in captured.out

    def test_reports_not_running(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.terminate", return_value=False)

        exit_code = main(["terminate"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "not running" in captured.out


class TestFocusCommand:
    def test_reports_focused(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.focus", return_value=True)

        exit_code = main(["focus"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Focused" in captured.out

    def test_reports_failure(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.focus", return_value=False)

        exit_code = main(["focus"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Could not" in captured.out


class TestUnfocusCommand:
    def test_reports_unfocused(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.unfocus", return_value=True)

        exit_code = main(["unfocus"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Unfocused" in captured.out

    def test_reports_failure(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        mocker.patch("vrcpilot.cli.unfocus", return_value=False)

        exit_code = main(["unfocus"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Could not" in captured.out


class TestScreenshotCommand:
    def test_reports_saved_on_success(
        self,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        # ``take_screenshot`` now returns a ``Screenshot`` whose
        # ``image`` ndarray is converted via ``Image.fromarray`` before
        # being saved. Patch ``Image.fromarray`` so we can intercept the
        # save call without producing a real PNG on disk.
        fake_pil = mocker.Mock()
        mocker.patch("vrcpilot.cli.Image.fromarray", return_value=fake_pil)
        fake_shot = mocker.Mock()
        mocker.patch("vrcpilot.cli.take_screenshot", return_value=fake_shot)
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Saved screenshot to" in captured.out
        fake_pil.save.assert_called_once_with(output)

    def test_reports_failure(
        self,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        mocker.patch("vrcpilot.cli.take_screenshot", return_value=None)

        exit_code = main(["screenshot", "--output", str(tmp_path / "shot.png")])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Could not" in captured.err

    def test_short_output_flag(
        self,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        fake_pil = mocker.Mock()
        mocker.patch("vrcpilot.cli.Image.fromarray", return_value=fake_pil)
        mocker.patch("vrcpilot.cli.take_screenshot", return_value=mocker.Mock())
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "-o", str(output)])

        assert exit_code == 0
        fake_pil.save.assert_called_once_with(output)

    def test_default_output_is_cwd_with_timestamp(
        self,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        fake_pil = mocker.Mock()
        mocker.patch("vrcpilot.cli.Image.fromarray", return_value=fake_pil)
        mocker.patch("vrcpilot.cli.take_screenshot", return_value=mocker.Mock())
        monkeypatch.chdir(tmp_path)

        exit_code = main(["screenshot"])

        assert exit_code == 0
        fake_pil.save.assert_called_once()
        saved_path = fake_pil.save.call_args.args[0]
        assert isinstance(saved_path, Path)
        assert saved_path.parent == tmp_path
        # vrcpilot_screenshot_YYYYMMDD_HHMMSS.png
        assert saved_path.name.startswith("vrcpilot_screenshot_")
        assert saved_path.suffix == ".png"


class _FakeCaptureLoop:
    instances: list[_FakeCaptureLoop] = []
    frames_per_start: int = 3
    init_side_effect: BaseException | None = None

    def __init__(
        self,
        callback: Callable[[np.ndarray], None],
        *,
        fps: float,
        frame_timeout: float = 2.0,
    ) -> None:
        if _FakeCaptureLoop.init_side_effect is not None:
            raise _FakeCaptureLoop.init_side_effect
        self.callback = callback
        self.fps = fps
        self.frame_timeout = frame_timeout
        self.start_calls = 0
        _FakeCaptureLoop.instances.append(self)

    def start(self) -> None:
        self.start_calls += 1
        for _ in range(_FakeCaptureLoop.frames_per_start):
            self.callback(np.zeros((4, 4, 3), dtype=np.uint8))

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        del exc_type, exc_val, exc_tb


class _FakeMp4FrameSink:
    instances: list[_FakeMp4FrameSink] = []

    def __init__(self, output_path: Path, fps: float) -> None:
        self.output_path = output_path
        self.fps = fps
        self.writes: list[np.ndarray] = []
        self.closed = False
        _FakeMp4FrameSink.instances.append(self)

    @property
    def frame_count(self) -> int:
        return len(self.writes)

    def write(self, frame_rgb: np.ndarray) -> None:
        self.writes.append(frame_rgb)

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        self.close()


@dataclass
class _CaptureFakes:
    loop: type[_FakeCaptureLoop]
    sink: type[_FakeMp4FrameSink]
    sleep: object = field(default=None)


@pytest.fixture
def capture_fakes(mocker: MockerFixture) -> _CaptureFakes:
    # KeyboardInterrupt 既定: production の `while True: time.sleep(3600)`
    # idiom に入っても 1 回目で抜ける。これを忘れると Mock.call_args_list が
    # 無限蓄積してメモリが爆発する（feedback_just_run_memory_pressure 参照）。
    sleep_mock = mocker.patch("vrcpilot.cli.time.sleep", side_effect=KeyboardInterrupt)
    mocker.patch("vrcpilot.cli.CaptureLoop", _FakeCaptureLoop)
    mocker.patch("vrcpilot.cli.Mp4FrameSink", _FakeMp4FrameSink)
    _FakeCaptureLoop.instances = []
    _FakeCaptureLoop.frames_per_start = 3
    _FakeCaptureLoop.init_side_effect = None
    _FakeMp4FrameSink.instances = []
    return _CaptureFakes(
        loop=_FakeCaptureLoop, sink=_FakeMp4FrameSink, sleep=sleep_mock
    )


class TestCaptureCommand:
    def test_default_output_uses_cwd_with_timestamp(
        self,
        capture_fakes: _CaptureFakes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        monkeypatch.chdir(tmp_path)

        exit_code = main(["capture"])

        assert exit_code == 0
        assert len(capture_fakes.sink.instances) == 1
        sink = capture_fakes.sink.instances[0]
        assert sink.output_path.parent == tmp_path
        assert sink.output_path.name.startswith("vrcpilot_capture_")
        assert sink.output_path.suffix == ".mp4"
        assert "Saved capture to" in capsys.readouterr().out

    def test_explicit_output_path(self, capture_fakes: _CaptureFakes, tmp_path: Path):
        out = tmp_path / "foo.mp4"

        exit_code = main(["capture", "--output", str(out)])

        assert exit_code == 0
        assert capture_fakes.sink.instances[0].output_path == out

    def test_short_output_flag(self, capture_fakes: _CaptureFakes, tmp_path: Path):
        out = tmp_path / "bar.mp4"

        exit_code = main(["capture", "-o", str(out)])

        assert exit_code == 0
        assert capture_fakes.sink.instances[0].output_path == out

    def test_default_fps_is_30(self, capture_fakes: _CaptureFakes, tmp_path: Path):
        exit_code = main(["capture", "-o", str(tmp_path / "fps.mp4")])

        assert exit_code == 0
        assert capture_fakes.loop.instances[0].fps == 30.0
        assert capture_fakes.sink.instances[0].fps == 30.0

    def test_fps_argument_propagates(
        self, capture_fakes: _CaptureFakes, tmp_path: Path
    ):
        exit_code = main(["capture", "-o", str(tmp_path / "fps.mp4"), "--fps", "60"])

        assert exit_code == 0
        assert capture_fakes.loop.instances[0].fps == 60.0
        assert capture_fakes.sink.instances[0].fps == 60.0

    def test_duration_argument_propagates(
        self,
        capture_fakes: _CaptureFakes,
        tmp_path: Path,
        mocker: MockerFixture,
    ):
        # duration ありの正常完了パスを確認するため、sleep を return_value=None
        # で上書き。--duration を指定しているので 1 回の sleep で抜ける。
        sleep_mock = mocker.patch("vrcpilot.cli.time.sleep", return_value=None)

        exit_code = main(["capture", "-o", str(tmp_path / "d.mp4"), "--duration", "5"])

        assert exit_code == 0
        sleep_mock.assert_called_once_with(5.0)
        assert capture_fakes.sink.instances[0].closed

    def test_no_duration_waits_until_keyboard_interrupt(
        self, capture_fakes: _CaptureFakes, tmp_path: Path
    ):
        # 既定 fixture の sleep は side_effect=KeyboardInterrupt なので
        # `while True: time.sleep(3600)` の最初の呼び出しで抜ける。exit 0。
        exit_code = main(["capture", "-o", str(tmp_path / "ki.mp4")])

        assert exit_code == 0
        # `else` 分岐に入って sleep が 1 度だけ呼ばれて抜けたことを確認。
        # ここを忘れると Mock.call_args_list が無限蓄積する罠を踏むため
        # その契約をテストでロックしておく。
        assert capture_fakes.sleep.call_count == 1  # type: ignore[attr-defined]

    def test_zero_frames_returns_error(
        self,
        capture_fakes: _CaptureFakes,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        capture_fakes.loop.frames_per_start = 0

        exit_code = main(["capture", "-o", str(tmp_path / "zero.mp4")])

        assert exit_code == 1
        assert "no frames captured" in capsys.readouterr().err
        assert capture_fakes.sink.instances[0].frame_count == 0

    def test_runtime_error_returns_error(
        self,
        capture_fakes: _CaptureFakes,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        capture_fakes.loop.init_side_effect = RuntimeError("VRChat is not running")

        exit_code = main(["capture", "-o", str(tmp_path / "err.mp4")])

        assert exit_code == 1
        assert "VRChat is not running" in capsys.readouterr().err

    def test_callback_writes_frames_to_sink(
        self, capture_fakes: _CaptureFakes, tmp_path: Path
    ):
        capture_fakes.loop.frames_per_start = 5

        exit_code = main(["capture", "-o", str(tmp_path / "cb.mp4")])

        assert exit_code == 0
        sink = capture_fakes.sink.instances[0]
        assert sink.frame_count == 5
        assert sink.closed


class TestMain:
    def test_missing_subcommand_exits(self):
        with pytest.raises(SystemExit):
            main([])


class TestArgcompleteIntegration:
    def test_autocomplete_invoked_with_parser(self, mocker: MockerFixture):
        autocomplete_mock = mocker.patch("vrcpilot.cli.argcomplete.autocomplete")
        _patch_launch(mocker)

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
        _patch_launch(mocker)

        exit_code = main(["launch"])

        assert exit_code == 0

    def test_capture_output_has_files_completer(self):
        parser = _build_parser()

        subparsers_action = parser._subparsers._group_actions[0]  # type: ignore[union-attr]
        capture_parser = subparsers_action.choices["capture"]
        output_action = next(
            action
            for action in capture_parser._actions
            if "--output" in action.option_strings
        )

        completer = output_action.completer  # type: ignore[attr-defined]
        assert isinstance(completer, FilesCompleter)
        allowednames = completer.allowednames
        assert any("mp4" in name for name in allowednames)
