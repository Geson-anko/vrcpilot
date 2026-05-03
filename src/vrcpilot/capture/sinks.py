"""Frame sinks shared by the CLI ``capture`` command and e2e scenarios.

Package-private (underscore-prefixed module) and intentionally absent
from :mod:`vrcpilot.capture`'s ``__all__``: the writer machinery is an
implementation detail of the bundled CLI / e2e scripts, not a public
API. External users should compose :class:`vrcpilot.CaptureLoop` with
their own sink.
"""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self

import cv2
import numpy as np


class Mp4FrameSink:
    """Lazy ``cv2.VideoWriter`` wrapper that writes RGB ndarrays as mp4.

    The first :meth:`write` locks the output frame size from the input
    array's shape and opens the underlying writer. Subsequent writes
    convert RGB to BGR (which OpenCV's writer expects) and append. The
    writer uses ``mp4v`` fourcc; ``opencv-python`` ships an ffmpeg build
    that supports it on both Windows and Linux.

    Args:
        output_path: Destination ``.mp4`` path. Parent directory must
            already exist; otherwise the writer fails to open and the
            first :meth:`write` raises :class:`RuntimeError`.
        fps: Playback frame rate stored in the mp4 container. Should
            match the cadence of the producer (e.g.
            :class:`vrcpilot.CaptureLoop`'s configured ``fps``).
    """

    _output_path: Path
    _fps: float
    _writer: cv2.VideoWriter | None
    _frame_count: int

    def __init__(self, output_path: Path, fps: float) -> None:
        self._output_path = output_path
        self._fps = fps
        self._writer = None
        self._frame_count = 0

    @property
    def frame_count(self) -> int:
        """Number of frames written so far."""
        return self._frame_count

    def write(self, frame_rgb: np.ndarray) -> None:
        """Append a frame to the mp4.

        Args:
            frame_rgb: ``(H, W, 3)`` uint8 RGB ndarray. The first call
                locks ``(W, H)`` for the lifetime of the sink.

        Raises:
            RuntimeError: ``cv2.VideoWriter`` could not be opened on
                the first write (typically a missing parent directory
                or codec issue).
        """
        if self._writer is None:
            h, w = frame_rgb.shape[:2]
            fourcc = cv2.VideoWriter.fourcc(*"mp4v")
            writer = cv2.VideoWriter(
                str(self._output_path),
                fourcc,
                self._fps,
                (w, h),
            )
            if not writer.isOpened():
                raise RuntimeError(
                    f"cv2.VideoWriter failed to open: {self._output_path} "
                    f"(fourcc=mp4v, fps={self._fps}, size=({w}, {h}))"
                )
            self._writer = writer

        bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        self._writer.write(bgr)
        self._frame_count += 1

    def close(self) -> None:
        """Release the underlying writer; idempotent and never raises."""
        writer = self._writer
        if writer is None:
            return
        self._writer = None
        writer.release()

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


class Y4mStdoutFrameSink:
    """Stream RGB ndarrays to a binary file-like as YUV4MPEG2 (C444).

    Designed for the CLI ``capture`` command's pipe mode: when the user
    omits ``-o``, the recording is emitted as a self-describing y4m
    byte stream so downstream tools (``ffmpeg -i -`` etc.) can pick up
    resolution and fps without extra flags.

    The first :meth:`write` locks the frame size from the input array's
    shape and emits the y4m header. Subsequent writes prepend
    ``b"FRAME\\n"`` and append the Y/U/V planes (each ``H * W`` bytes,
    full-resolution chroma — ``C444``). ``C444`` is chosen over the
    more common ``C420`` because subsampled chroma requires even W/H,
    and the producer's frame size is dictated by VRChat's window —
    arbitrary odd dimensions must be allowed through unchanged. The
    fps is rendered as a rational ``n:d`` via
    ``Fraction(fps).limit_denominator(1000)`` so integer rates like
    ``30.0`` stay ``30:1`` while NTSC ``29.97`` becomes ``2997:100``.

    Args:
        fps: Frame rate written into the y4m header. Should match the
            cadence of the producer.
        stream: Destination binary stream. Defaults to
            ``sys.stdout.buffer`` so the CLI's stdout pipe works
            without explicit wiring; tests inject :class:`io.BytesIO`.

    The stream is **never** closed by this sink — :meth:`close` only
    flushes — because the default target (``sys.stdout``) must outlive
    the sink for the surrounding process to finish cleanly.
    """

    _fps: float
    _stream: BinaryIO
    _frame_count: int
    _dims: tuple[int, int] | None

    def __init__(self, fps: float, *, stream: BinaryIO | None = None) -> None:
        self._fps = fps
        self._stream = stream if stream is not None else sys.stdout.buffer
        self._frame_count = 0
        self._dims = None

    @property
    def frame_count(self) -> int:
        """Number of frames written so far."""
        return self._frame_count

    def write(self, frame_rgb: np.ndarray) -> None:
        """Append one frame to the y4m stream.

        Args:
            frame_rgb: ``(H, W, 3)`` uint8 RGB ndarray. The first call
                locks ``(H, W)`` for the lifetime of the sink.

        Raises:
            RuntimeError: A subsequent frame's shape differs from the
                shape locked by the first :meth:`write`.
        """
        h, w = frame_rgb.shape[:2]

        if self._dims is None:
            self._dims = (h, w)
            self._write_header(w, h)
        else:
            locked_h, locked_w = self._dims
            if (h, w) != (locked_h, locked_w):
                raise RuntimeError(
                    "Y4mStdoutFrameSink frame size changed mid-stream: "
                    f"locked=({locked_w}, {locked_h}), got=({w}, {h})"
                )

        # Reorder (H, W, 3) -> (3, H, W) so the Y/U/V planes are
        # contiguous in memory and a single tobytes() emits the
        # planar payload y4m expects.
        yuv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2YUV)
        planes = np.ascontiguousarray(yuv.transpose(2, 0, 1))
        self._stream.write(b"FRAME\n")
        self._stream.write(planes.tobytes())
        self._frame_count += 1

    def _write_header(self, w: int, h: int) -> None:
        rate = Fraction(self._fps).limit_denominator(1000)
        # XCOLORRANGE=FULL declares full-range YUV (Y in [0, 255]).
        # cv2.COLOR_RGB2YUV produces full-range BT.601, but y4m's
        # default is limited-range (16-235), so without this tag
        # ffmpeg would interpret the bytes as TV-range and crush
        # blacks / clip whites on re-encode.
        header = (
            f"YUV4MPEG2 W{w} H{h} "
            f"F{rate.numerator}:{rate.denominator} "
            f"Ip A1:1 C444 XCOLORRANGE=FULL\n"
        ).encode("ascii")
        self._stream.write(header)

    def close(self) -> None:
        """Flush the underlying stream; idempotent and never closes it.

        The default stream is ``sys.stdout.buffer``, which is owned by
        the interpreter - closing it would break anything written
        afterwards (e.g. an ``atexit`` log line). Tests pass their own
        :class:`io.BytesIO` and check it stays open.
        """
        self._stream.flush()

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
