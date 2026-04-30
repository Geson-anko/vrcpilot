"""VRChat window capture API for continuous-frame (video) workloads.

Public entry point for grabbing successive frames of the running VRChat
window as :class:`numpy.ndarray` instances. Capture is **focus-free** on
both platforms: Linux reads the off-screen pixmap via the X11 Composite
extension, and Windows uses the Windows.Graphics.Capture API (the same
backend OBS's "Window Capture (Windows 10 1903+)" mode is built on).
The window is not raised to the foreground, so callers avoid the side
effect (and the settle delay) of focusing the window before each frame.

Choose between the two capture entry points based on workload:

- :class:`Capture` (this module) — keep one session open and pull
  many frames from it. Right when latency and "what's on screen *now*"
  matter (video, ML inference, screen recording).
- :func:`vrcpilot.screenshot.take_screenshot` — one focused shot
  with on-screen geometry attached. Right when an automation step
  needs to know *where* on the desktop the window is to compute
  click coordinates, run OCR, or diff a region.

Companion to :mod:`vrcpilot.window` (z-order control) and
:mod:`vrcpilot.process` (lifecycle).

Native Wayland sessions are not supported. ``Capture`` raises
:class:`RuntimeError` on Wayland because a streaming session cannot
function at all without X11 / XWayland; :func:`take_screenshot` instead
emits a :class:`RuntimeWarning` and returns ``None`` so that polling
callers can recover gracefully.
"""

from __future__ import annotations

import sys
from types import TracebackType
from typing import Self

import numpy as np

from vrcpilot._backends.capture_base import CaptureBackend


def _select_capture_backend(*, frame_timeout: float) -> CaptureBackend:
    """Return the platform-appropriate :class:`CaptureBackend`.

    Imports the chosen backend lazily so platform-specific dependencies
    (``windows_capture`` on Windows, ``Xlib`` on Linux) never need to be
    importable on the other platform.
    """
    if sys.platform == "win32":
        from vrcpilot._backends.capture_win32 import Win32CaptureBackend

        return Win32CaptureBackend(frame_timeout=frame_timeout)
    if sys.platform == "linux":
        from vrcpilot._backends.capture_x11 import X11CaptureBackend

        return X11CaptureBackend()
    raise NotImplementedError(f"Capture is not supported on {sys.platform}")


class Capture:
    """Continuous-frame capture session for the VRChat window.

    Constructed once and reused: a single session opens the platform
    backend (WGC on Windows, X11 Composite on Linux) and keeps it alive
    until :meth:`close` is called, so subsequent :meth:`read` calls reuse
    the same connection rather than paying setup cost per frame. Use
    :class:`Capture` for video / frame-stream workloads; for one-shot
    GUI-automation captures (with focus + window geometry) use
    :func:`vrcpilot.screenshot.take_screenshot` instead.

    The capture is **focus-free**: the window is not raised to the
    foreground and frames are produced even when VRChat is fully occluded
    by other windows.

    :meth:`read` is **latest-only**, not FIFO. Each call returns the most
    recent frame the backend has produced and discards anything older
    that was waiting. This is intentional for video workloads: when a
    consumer falls behind, a FIFO queue would let lag accumulate
    indefinitely; latest-only caps the worst-case staleness at a single
    frame interval. Callers that genuinely need every frame (e.g. lossy
    recording at a fixed rate) must drive :meth:`read` faster than the
    producer.

    Use as a context manager (recommended)::

        import vrcpilot
        with vrcpilot.Capture() as cap:
            for _ in range(60):
                frame = cap.read()  # (H, W, 3) uint8 RGB

    Or with explicit lifecycle::

        cap = vrcpilot.Capture()
        try:
            frame = cap.read()
        finally:
            cap.close()

    The instance is single-use: do not nest two ``with`` blocks against
    the same instance, and do not reopen after :meth:`close`.

    Args:
        frame_timeout: Seconds :meth:`read` will wait for a frame before
            raising :class:`TimeoutError`. Must be ``> 0``. Defaults to
            ``2.0``, generous for the typical ~33 ms WGC delivery cadence.

    Raises:
        NotImplementedError: When constructed on a platform other than
            Windows or Linux.
        RuntimeError: When the platform backend cannot be brought up:
            VRChat is not running, the top-level window is not yet
            mapped, the X11 display is unavailable, the X11 Composite
            extension is missing, the WGC session fails to start, or the
            session is native Wayland (Capture requires X11 / XWayland).
        ValueError: When ``frame_timeout`` is not strictly positive.
    """

    _backend: CaptureBackend
    _closed: bool

    def __init__(self, *, frame_timeout: float = 2.0) -> None:
        if frame_timeout <= 0:
            raise ValueError("frame_timeout must be > 0")

        self._closed = False
        self._backend = _select_capture_backend(frame_timeout=frame_timeout)

    def read(self) -> np.ndarray:
        """Return the latest unread frame as an RGB ``ndarray``.

        Blocks until a fresh frame is available or :attr:`frame_timeout`
        seconds elapse. Old frames buffered while the caller was busy are
        discarded -- the call returns the most recent frame, not the
        oldest, so latency does not accumulate when consumers fall
        behind.

        The returned array is independent of any internal buffer: it is
        safe to retain, edit in place, or hand off to a writer.

        Returns:
            ``(H, W, 3)`` ``uint8`` RGB :class:`numpy.ndarray`. The
            shape can change between calls if the VRChat window is
            resized; callers that require a fixed size should resize
            themselves.

        Raises:
            RuntimeError: When the capture has already been closed, or
                when the platform backend reports a fatal error (X11
                ``XError``, invalid window geometry, etc.).
            TimeoutError: When no frame arrives within
                :attr:`frame_timeout` seconds (Windows / WGC only; the
                X11 path is synchronous).
        """
        if self._closed:
            raise RuntimeError("Capture is closed")
        return self._backend.read()

    def close(self) -> None:
        """Release the platform backend; idempotent and exception-safe.

        Subsequent calls to :meth:`read` raise :class:`RuntimeError`.
        Calling :meth:`close` more than once is a no-op. Backend cleanup
        failures are surfaced as :class:`RuntimeWarning` rather than
        raised, so contexts like ``__exit__`` are always safe.
        """
        if self._closed:
            return
        self._closed = True
        self._backend.close()

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
