"""Tests for :mod:`vrcpilot.cli`.

Tests favour real integration over mock surfaces:

* ``launch`` flows go through :func:`vrcpilot.cli.main` ->
  :func:`vrcpilot.process.launch` -> :class:`subprocess.Popen`, with
  ``Popen`` swapped for :class:`tests._fakes.FakePopen` so the actual
  argv is recorded and asserted on. ``find_steam_executable`` is the
  only stub — it would otherwise hit the real registry / ``$PATH``.
* ``screenshot`` flows construct a real :class:`PIL.Image.Image` from
  a real numpy array and write a real PNG to ``tmp_path``. Only the
  capture boundary (:func:`vrcpilot.cli.take_screenshot`) is mocked.
* ``capture`` flows use the canonical :class:`tests._fakes.FakeCaptureLoop`
  / :class:`tests._fakes.FakeMp4Sink` so the CLI is wired through the
  real :func:`vrcpilot.cli._run_capture` orchestration.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from argcomplete.completers import FilesCompleter
from PIL import Image
from pytest_mock import MockerFixture, MockType

from tests._fakes import FakeCaptureLoop, FakeMp4Sink, FakePopen, FakeProcess
from vrcpilot.cli import _build_parser, main
from vrcpilot.process import VRCHAT_PROCESS_NAME, VRCHAT_STEAM_APP_ID


@pytest.fixture
def fake_popen(mocker: MockerFixture, tmp_path: Path) -> type[FakePopen]:
    """Patch ``subprocess.Popen`` so launch tests can record argv.

    Also stubs :func:`vrcpilot.process.find_steam_executable` to
    honour any ``--steam-path`` override, falling back to a real
    file under ``tmp_path``. That single mock is unavoidable — the
    real lookup would touch the Windows registry or ``$PATH`` — but
    every other byte of the launch chain runs unmodified, including
    the dispatch on ``override is not None``.

    Class-level state is reset every test so ``last_argv`` reflects
    only this test's invocation.
    """
    FakePopen.reset()
    mocker.patch("vrcpilot.process.subprocess.Popen", FakePopen)
    steam_stub = tmp_path / "Steam.exe"
    steam_stub.write_bytes(b"")

    def _find(override: Path | None = None) -> Path:
        return override if override is not None else steam_stub

    mocker.patch("vrcpilot.process.find_steam_executable", side_effect=_find)
    return FakePopen


class TestLaunchCommand:
    def test_uses_defaults(self, fake_popen: type[FakePopen]):
        exit_code = main(["launch"])

        assert exit_code == 0
        assert fake_popen.last_argv is not None
        assert fake_popen.last_argv[1:] == ["-applaunch", str(VRCHAT_STEAM_APP_ID)]

    def test_reports_launched_message(
        self, fake_popen: type[FakePopen], capsys: pytest.CaptureFixture[str]
    ):
        del fake_popen
        exit_code = main(["launch"])

        assert exit_code == 0
        assert "Launched VRChat." in capsys.readouterr().out

    def test_app_id_override(self, fake_popen: type[FakePopen]):
        exit_code = main(["launch", "--app-id", "12345"])

        assert exit_code == 0
        assert fake_popen.last_argv is not None
        assert "-applaunch" in fake_popen.last_argv
        assert "12345" in fake_popen.last_argv

    def test_steam_path_override(self, fake_popen: type[FakePopen], tmp_path: Path):
        # ``fake_popen`` mocks ``find_steam_executable`` with a
        # pass-through ``side_effect`` that honours the ``override``
        # arg, so the user-supplied path flows all the way through
        # to ``Popen``.
        override = tmp_path / "custom_steam.exe"

        exit_code = main(["launch", "--steam-path", str(override)])

        assert exit_code == 0
        assert fake_popen.last_argv is not None
        assert fake_popen.last_argv[0] == str(override)

    def test_reports_steam_not_found(self, capsys: pytest.CaptureFixture[str]):
        # Pass a path that does not exist — ``find_steam_executable``
        # raises ``SteamNotFoundError`` for real, no patching needed.
        exit_code = main(["launch", "--steam-path", "/does/not/exist/Steam.exe"])

        assert exit_code == 2
        assert "/does/not/exist/Steam.exe" in capsys.readouterr().err

    def test_no_vr_flag_propagates(self, fake_popen: type[FakePopen]):
        exit_code = main(["launch", "--no-vr"])

        assert exit_code == 0
        assert fake_popen.last_argv is not None
        assert "--no-vr" in fake_popen.last_argv

    def test_screen_dimensions_propagate(self, fake_popen: type[FakePopen]):
        exit_code = main(["launch", "--screen-width", "1280", "--screen-height", "720"])

        assert exit_code == 0
        assert fake_popen.last_argv is not None
        assert "-screen-width" in fake_popen.last_argv
        assert "1280" in fake_popen.last_argv
        assert "-screen-height" in fake_popen.last_argv
        assert "720" in fake_popen.last_argv

    def test_osc_in_port_creates_config(self, fake_popen: type[FakePopen]):
        exit_code = main(["launch", "--osc-in-port", "9000"])

        assert exit_code == 0
        assert fake_popen.last_argv is not None
        assert "--osc=9000:127.0.0.1:9001" in fake_popen.last_argv

    def test_osc_full_override(self, fake_popen: type[FakePopen]):
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
        assert fake_popen.last_argv is not None
        assert "--osc=10000:192.168.1.10:10001" in fake_popen.last_argv

    def test_osc_out_options_ignored_without_in_port(self, fake_popen: type[FakePopen]):
        exit_code = main(["launch", "--osc-out-ip", "192.168.1.10"])

        assert exit_code == 0
        assert fake_popen.last_argv is not None
        # No --osc=... token because --osc-in-port was not given.
        assert not any(token.startswith("--osc=") for token in fake_popen.last_argv)


class TestStatusCommand:
    def test_reports_running(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        # Override the autouse empty default with a real ``FakeProcess``
        # so the live ``find_pid`` -> ``psutil.process_iter`` path runs
        # for real.
        mocker.patch(
            "vrcpilot.process.psutil.process_iter",
            return_value=[FakeProcess(name=VRCHAT_PROCESS_NAME, pid=12345)],
        )

        exit_code = main(["status"])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "VRChat is running" in out
        assert "12345" in out

    def test_reports_not_running(self, capsys: pytest.CaptureFixture[str]):
        # The conftest autouse fixture already empties ``process_iter``,
        # so no patch is needed for the negative path.
        exit_code = main(["status"])

        assert exit_code == 1
        assert "VRChat is not running" in capsys.readouterr().out


class TestTerminateCommand:
    def test_reports_killed(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ):
        # Drive the real ``terminate()`` end-to-end by handing it a
        # ``FakeProcess`` whose ``.kill()`` is a recorded no-op. The
        # ``wait_procs`` short-circuits to empty because nothing is a
        # real ``psutil.Process``; stub it to avoid the type check
        # raising.
        mocker.patch(
            "vrcpilot.process.psutil.process_iter",
            return_value=[FakeProcess(name=VRCHAT_PROCESS_NAME)],
        )
        mocker.patch("vrcpilot.process.psutil.wait_procs", return_value=([], []))

        exit_code = main(["terminate"])

        assert exit_code == 0
        assert "Terminated" in capsys.readouterr().out

    def test_reports_not_running(self, capsys: pytest.CaptureFixture[str]):
        # Autouse empty default makes this a real, mock-free run of the
        # negative path.
        exit_code = main(["terminate"])

        assert exit_code == 0
        assert "not running" in capsys.readouterr().out


class TestFocusUnfocusCommands:
    @pytest.mark.parametrize(
        ("command", "result", "expected_exit", "expected_word"),
        [
            ("focus", True, 0, "Focused"),
            ("focus", False, 1, "Could not"),
            ("unfocus", True, 0, "Unfocused"),
            ("unfocus", False, 1, "Could not"),
        ],
    )
    def test_focus_unfocus(
        self,
        command: str,
        result: bool,
        expected_exit: int,
        expected_word: str,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
    ):
        mocker.patch(f"vrcpilot.cli.{command}", return_value=result)

        exit_code = main([command])

        assert exit_code == expected_exit
        assert expected_word in capsys.readouterr().out


def _make_screenshot(
    *,
    width: int = 8,
    height: int = 4,
) -> object:
    """Build a real-shaped ``Screenshot`` stand-in.

    The CLI only reads ``shot.image``; building a full
    :class:`vrcpilot.Screenshot` requires importing the dataclass and
    fabricating geometry/timestamps that the CLI ignores. A simple
    duck-typed object keeps the test focused on what the CLI actually
    consumes — the RGB ndarray.
    """

    @dataclass
    class _Shot:
        image: np.ndarray

    return _Shot(image=np.zeros((height, width, 3), dtype=np.uint8))


@pytest.fixture
def patched_take_screenshot(mocker: MockerFixture) -> object:
    """Patch the screenshot capture boundary with a real ndarray-backed fake.

    Capturing the real desktop is platform-specific and out of scope
    for CLI tests; everything below the ``take_screenshot`` call —
    PIL conversion, PNG encoding, file write — runs end-to-end.
    """
    return mocker.patch("vrcpilot.cli.take_screenshot", return_value=_make_screenshot())


class TestScreenshotCommand:
    def test_reports_saved_on_success(
        self,
        patched_take_screenshot: object,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        del patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        assert "Saved screenshot to" in capsys.readouterr().out
        assert output.is_file()
        # Round-trip the PNG to confirm the bytes are a valid image
        # of the expected shape.
        with Image.open(output) as img:
            assert img.size == (8, 4)

    def test_reports_failure(
        self,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        mocker.patch("vrcpilot.cli.take_screenshot", return_value=None)
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 1
        assert "Could not" in capsys.readouterr().err
        assert not output.exists()

    def test_short_output_flag(
        self,
        patched_take_screenshot: object,
        tmp_path: Path,
    ):
        del patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "-o", str(output)])

        assert exit_code == 0
        assert output.is_file()

    def test_default_output_is_cwd_with_timestamp(
        self,
        patched_take_screenshot: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        del patched_take_screenshot
        monkeypatch.chdir(tmp_path)

        exit_code = main(["screenshot"])

        assert exit_code == 0
        # vrcpilot_screenshot_YYYYMMDD_HHMMSS.png in the current dir.
        produced = list(tmp_path.glob("vrcpilot_screenshot_*.png"))
        assert len(produced) == 1
        assert produced[0].suffix == ".png"


@dataclass
class _CaptureFakes:
    loop: type[FakeCaptureLoop]
    sink: type[FakeMp4Sink]
    sleep: MockType


@pytest.fixture
def capture_fakes(mocker: MockerFixture) -> _CaptureFakes:
    """Wire the canonical capture fakes into :mod:`vrcpilot.cli`.

    ``time.sleep`` is patched to raise ``KeyboardInterrupt`` so the
    production ``while True: time.sleep(3600)`` idiom exits on the
    first call. Without this, ``Mock.call_args_list`` accumulates
    forever and starves the runner of memory.
    """
    sleep_mock = mocker.patch("vrcpilot.cli.time.sleep", side_effect=KeyboardInterrupt)
    mocker.patch("vrcpilot.cli.CaptureLoop", FakeCaptureLoop)
    mocker.patch("vrcpilot.cli.Mp4FrameSink", FakeMp4Sink)
    FakeCaptureLoop.instances = []
    FakeCaptureLoop.frames_per_start = 3
    FakeCaptureLoop.init_side_effect = None
    FakeMp4Sink.instances = []
    return _CaptureFakes(loop=FakeCaptureLoop, sink=FakeMp4Sink, sleep=sleep_mock)


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
        # Override the fixture's KeyboardInterrupt sleep with a
        # well-behaved one so the ``--duration`` branch can complete
        # naturally.
        sleep_mock = mocker.patch("vrcpilot.cli.time.sleep", return_value=None)

        exit_code = main(["capture", "-o", str(tmp_path / "d.mp4"), "--duration", "5"])

        assert exit_code == 0
        sleep_mock.assert_called_once_with(5.0)
        assert capture_fakes.sink.instances[0].closed

    def test_no_duration_waits_until_keyboard_interrupt(
        self, capture_fakes: _CaptureFakes, tmp_path: Path
    ):
        # Default fixture sleep raises KeyboardInterrupt -> the
        # ``while True: time.sleep(3600)`` idiom exits on the first
        # call. The assertion locks in the call_count to guard the
        # memory-pressure trap (feedback_just_run_memory_pressure).
        exit_code = main(["capture", "-o", str(tmp_path / "ki.mp4")])

        assert exit_code == 0
        assert capture_fakes.sleep.call_count == 1

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
        # Use the ``status`` subcommand since the autouse conftest
        # makes it an honest, mock-free run all the way through.
        autocomplete_mock = mocker.patch("vrcpilot.cli.argcomplete.autocomplete")

        exit_code = main(["status"])

        assert exit_code == 1
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
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ``status`` against the autouse empty ``process_iter`` is the
        # cheapest fully-real path through ``main`` — it confirms the
        # ``argcomplete`` hook does not abort regular (non-completion)
        # invocations without needing a Steam launch fake.
        monkeypatch.delenv("_ARGCOMPLETE", raising=False)

        exit_code = main(["status"])

        assert exit_code == 1

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
