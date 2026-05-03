"""Tests for :class:`vrcpilot.capture.sinks.Mp4FrameSink` and
:class:`vrcpilot.capture.sinks.Y4mStdoutFrameSink`.

cv2 is exercised against the real filesystem (``tmp_path``) rather than
mocked: the sink's job is to emit a valid mp4, and the only useful
assertion is that ``cv2.VideoCapture`` can read the result back. Pixel
fidelity is not asserted (mp4 is lossy); only structural properties
(file existence, frame size in the container header, frame count
counter) are checked.

The y4m sink writes deterministic bytes, so its tests inject an
``io.BytesIO`` and assert directly against the byte stream.
"""

from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pytest

from vrcpilot.capture.sinks import Mp4FrameSink, Y4mStdoutFrameSink


def _frame(h: int = 16, w: int = 16) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestMp4FrameSink:
    def test_writes_video_file(self, tmp_path: Path):
        out = tmp_path / "out.mp4"
        sink = Mp4FrameSink(out, fps=30.0)
        for _ in range(5):
            sink.write(_frame())
        sink.close()

        assert out.exists()
        assert out.stat().st_size > 0

    def test_frame_count_matches_writes(self, tmp_path: Path):
        sink = Mp4FrameSink(tmp_path / "out.mp4", fps=30.0)
        assert sink.frame_count == 0
        for i in range(1, 4):
            sink.write(_frame())
            assert sink.frame_count == i
        sink.close()

    def test_frame_size_locked_by_first_frame(self, tmp_path: Path):
        out = tmp_path / "out.mp4"
        with Mp4FrameSink(out, fps=30.0) as sink:
            sink.write(_frame(h=10, w=20))
            sink.write(_frame(h=10, w=20))

        cap = cv2.VideoCapture(str(out))
        try:
            assert cap.isOpened()
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            cap.release()
        assert width == 20
        assert height == 10

    def test_close_is_idempotent(self, tmp_path: Path):
        sink = Mp4FrameSink(tmp_path / "out.mp4", fps=30.0)
        sink.write(_frame())
        sink.close()
        # Second close must be a safe no-op.
        sink.close()

    def test_close_without_writes_is_noop(self, tmp_path: Path):
        out = tmp_path / "out.mp4"
        sink = Mp4FrameSink(out, fps=30.0)
        sink.close()
        # Writer was never opened, so no file should be on disk.
        assert not out.exists()

    def test_context_manager_closes(self, tmp_path: Path):
        out = tmp_path / "out.mp4"
        with Mp4FrameSink(out, fps=30.0) as sink:
            sink.write(_frame())

        # After __exit__ the file is finalised: VideoCapture can open it
        # and report at least one frame in the header.
        cap = cv2.VideoCapture(str(out))
        try:
            assert cap.isOpened()
            ok, _ = cap.read()
            assert ok
        finally:
            cap.release()

    def test_open_failure_raises(self, tmp_path: Path):
        bad_dir = tmp_path / "does_not_exist"
        sink = Mp4FrameSink(bad_dir / "out.mp4", fps=30.0)
        with pytest.raises(RuntimeError, match="cv2.VideoWriter failed to open"):
            sink.write(_frame())


class TestY4mStdoutFrameSink:
    def test_first_write_emits_y4m_header_with_locked_dims(self):
        stream = io.BytesIO()
        sink = Y4mStdoutFrameSink(fps=30.0, stream=stream)

        sink.write(_frame(h=4, w=4))

        assert stream.getvalue().startswith(
            b"YUV4MPEG2 W4 H4 F30:1 Ip A1:1 C444 XCOLORRANGE=FULL\n"
        )

    def test_each_frame_starts_with_frame_marker(self):
        stream = io.BytesIO()
        sink = Y4mStdoutFrameSink(fps=30.0, stream=stream)

        sink.write(_frame(h=4, w=4))
        sink.write(_frame(h=4, w=4))

        assert stream.getvalue().count(b"FRAME\n") == 2

    def test_payload_size_per_frame_is_3_planes(self):
        stream = io.BytesIO()
        sink = Y4mStdoutFrameSink(fps=30.0, stream=stream)
        h, w = 4, 5

        sink.write(_frame(h=h, w=w))

        payload = stream.getvalue()
        header_end = payload.index(b"\n") + 1
        frame_marker = b"FRAME\n"
        marker_pos = payload.index(frame_marker, header_end)
        body = payload[marker_pos + len(frame_marker) :]
        assert len(body) == 3 * h * w

    def test_frame_count_matches_writes(self):
        stream = io.BytesIO()
        sink = Y4mStdoutFrameSink(fps=30.0, stream=stream)

        assert sink.frame_count == 0
        for i in range(1, 4):
            sink.write(_frame(h=4, w=4))
            assert sink.frame_count == i

    def test_close_flushes_but_does_not_close_stream(self):
        stream = io.BytesIO()
        sink = Y4mStdoutFrameSink(fps=30.0, stream=stream)
        sink.write(_frame(h=4, w=4))

        sink.close()

        assert stream.closed is False
        # Idempotent: a second close must not raise.
        sink.close()
        assert stream.closed is False

    def test_dimension_change_raises(self):
        stream = io.BytesIO()
        sink = Y4mStdoutFrameSink(fps=30.0, stream=stream)
        sink.write(_frame(h=4, w=4))

        with pytest.raises(RuntimeError, match="frame size changed"):
            sink.write(_frame(h=5, w=5))

    def test_fps_rational_for_ntsc_29_97(self):
        stream = io.BytesIO()
        sink = Y4mStdoutFrameSink(fps=29.97, stream=stream)

        sink.write(_frame(h=4, w=4))

        assert b"F2997:100" in stream.getvalue()

    def test_context_manager_flushes_on_exit(self):
        stream = io.BytesIO()
        with Y4mStdoutFrameSink(fps=30.0, stream=stream) as sink:
            sink.write(_frame(h=4, w=4))

        # __exit__ must have flushed without closing the stream.
        assert stream.closed is False
        assert stream.getvalue().startswith(b"YUV4MPEG2 ")
