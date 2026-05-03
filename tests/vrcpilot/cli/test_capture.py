"""Tests for :mod:`vrcpilot.cli.capture`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from pytest_mock import MockerFixture, MockType

from tests.fakes import FakeCaptureLoop, FakeMp4Sink
from vrcpilot.cli import main


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
        # stdout is now the resolved absolute path of the mp4.
        captured = capsys.readouterr()
        assert captured.out.strip() == str(sink.output_path.resolve())

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
        captured = capsys.readouterr()
        assert "no frames captured" in captured.err
        assert capture_fakes.sink.instances[0].frame_count == 0
        # No path emitted to stdout on failure.
        assert captured.out == ""

    def test_runtime_error_returns_error(
        self,
        capture_fakes: _CaptureFakes,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        capture_fakes.loop.init_side_effect = RuntimeError("VRChat is not running")

        exit_code = main(["capture", "-o", str(tmp_path / "err.mp4")])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "VRChat is not running" in captured.err
        assert captured.out == ""

    def test_callback_writes_frames_to_sink(
        self, capture_fakes: _CaptureFakes, tmp_path: Path
    ):
        capture_fakes.loop.frames_per_start = 5

        exit_code = main(["capture", "-o", str(tmp_path / "cb.mp4")])

        assert exit_code == 0
        sink = capture_fakes.sink.instances[0]
        assert sink.frame_count == 5
        assert sink.closed

    def test_progress_message_is_on_stderr_not_stdout(
        self,
        capture_fakes: _CaptureFakes,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        del capture_fakes
        out = tmp_path / "progress.mp4"

        exit_code = main(["capture", "-o", str(out)])

        assert exit_code == 0
        captured = capsys.readouterr()
        # Progress chatter must not pollute stdout; only the absolute
        # path is emitted there.
        assert "Recording to" not in captured.out
        assert "Press Ctrl+C" not in captured.out
        # ...and it must be present on stderr instead.
        assert "Recording to" in captured.err
        assert "Press Ctrl+C" in captured.err

    def test_stdout_is_absolute_path(
        self,
        capture_fakes: _CaptureFakes,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        del capture_fakes
        out = tmp_path / "abs.mp4"

        exit_code = main(["capture", "-o", str(out)])

        assert exit_code == 0
        stdout = capsys.readouterr().out.strip()
        assert Path(stdout).is_absolute()
        assert Path(stdout) == out.resolve()
