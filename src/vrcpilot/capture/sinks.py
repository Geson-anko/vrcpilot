"""Frame sinks shared by the CLI ``capture`` command and manual scenarios.

Package-private (underscore-prefixed module) and intentionally absent
from :mod:`vrcpilot.capture`'s ``__all__``: the writer machinery is an
implementation detail of the bundled CLI / manual scripts, not a public
API. External users should compose :class:`vrcpilot.CaptureLoop` with
their own sink.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Self

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
