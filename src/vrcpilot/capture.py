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
import threading
import warnings
from types import TracebackType
from typing import TYPE_CHECKING, Self

import numpy as np

from vrcpilot._x11 import (
    find_vrchat_window,
    is_wayland_native,
    open_x11_display,
)
from vrcpilot.process import find_pid

if TYPE_CHECKING or sys.platform == "linux":
    import Xlib.display
    import Xlib.error
    from Xlib import X
    from Xlib.ext import composite
    from Xlib.xobject.drawable import Window as _XWindow

if sys.platform == "win32":
    # ``windows_capture`` ships no type stubs (it's a thin wrapper over a
    # PyO3 native module), so the import trips ``reportMissingTypeStubs``
    # and downstream attribute reads come back as ``Unknown``. We narrow
    # with isinstance / asserts at use sites.
    from windows_capture import (  # pyright: ignore[reportMissingTypeStubs]
        WindowsCapture,
    )

    from vrcpilot._win32 import find_vrchat_hwnd


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

    _frame_timeout: float
    _closed: bool

    # WGC-only attributes; created in ``_init_win32`` on Windows runs.
    _latest_frame: tuple[np.ndarray, int, int] | None
    _frame_lock: threading.Lock
    _frame_event: threading.Event
    _control: object  # ``windows_capture.CaptureControl`` (no stubs).

    # X11-only attributes; created in ``_init_x11`` on Linux runs.
    _display: Xlib.display.Display
    _window: _XWindow

    def __init__(self, *, frame_timeout: float = 2.0) -> None:
        if frame_timeout <= 0:
            raise ValueError("frame_timeout must be > 0")

        self._frame_timeout = frame_timeout
        self._closed = False

        if sys.platform == "win32":
            self._init_win32()
        elif sys.platform == "linux":
            self._init_x11()
        else:
            raise NotImplementedError(
                f"Capture is not supported on {sys.platform}",
            )

    # --- Win32 / WGC backend -------------------------------------------------

    def _init_win32(self) -> None:
        """Bring up the WGC backend and start the free-threaded session."""
        if sys.platform != "win32":
            # Defensive narrow for pyright on non-Windows runs.
            raise RuntimeError("unreachable")

        pid = find_pid()
        if pid is None:
            raise RuntimeError("VRChat is not running")

        hwnd = find_vrchat_hwnd(pid)
        if hwnd is None:
            raise RuntimeError("VRChat top-level window is not yet mapped")

        # Single-slot latest-frame buffer; threading.Event wakes ``read``.
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._frame_event = threading.Event()

        capture = WindowsCapture(  # pyright: ignore[reportUnknownVariableType]
            cursor_capture=False,
            draw_border=False,
            window_hwnd=hwnd,
        )

        @capture.event  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator, reportArgumentType]
        def on_frame_arrived(frame: object, control: object) -> None:  # pyright: ignore[reportUnusedFunction]
            del control  # We never stop from inside the handler.
            # ``frame.frame_buffer`` is a row-tight ``(H, W, 4)`` BGRA ndarray;
            # the library has already collapsed the GPU stride for us. Convert
            # BGRA -> RGB and copy out so the buffer is safe to keep after the
            # handler returns (the underlying ctypes memory is reused).
            buf = frame.frame_buffer.tobytes()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue, reportUnknownVariableType]
            width = int(frame.width)  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue, reportUnknownMemberType]
            height = int(frame.height)  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue, reportUnknownMemberType]
            assert isinstance(buf, bytes)
            if width <= 0 or height <= 0:
                # Spurious frame; ignore. ``read`` will keep waiting.
                return
            bgra = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 4)
            rgb = np.ascontiguousarray(bgra[..., 2::-1])
            with self._frame_lock:
                self._latest_frame = (rgb, width, height)
                self._frame_event.set()

        @capture.event  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator, reportArgumentType]
        def on_closed() -> None:  # pyright: ignore[reportUnusedFunction]
            pass

        try:
            self._control = capture.start_free_threaded()  # pyright: ignore[reportUnknownMemberType]
        except OSError as exc:
            raise RuntimeError(f"Failed to start WGC session: {exc}") from exc

    def _read_win32(self) -> np.ndarray:
        """Block on the latest-frame slot and return one RGB ndarray."""
        if not self._frame_event.wait(timeout=self._frame_timeout):
            # ``close`` may have set the event; re-check the closed flag
            # before raising ``TimeoutError`` so the message stays accurate.
            if self._closed:
                raise RuntimeError("Capture is closed")
            raise TimeoutError(
                f"No frame arrived within {self._frame_timeout}s",
            )
        with self._frame_lock:
            if self._closed:
                # ``close`` raced ahead and woke us; do not return a frame.
                raise RuntimeError("Capture is closed")
            slot = self._latest_frame
            self._latest_frame = None
            self._frame_event.clear()
        if slot is None:
            # Event was set but slot was already drained; treat as timeout.
            raise TimeoutError(
                f"No frame arrived within {self._frame_timeout}s",
            )
        rgb, _w, _h = slot
        return rgb

    def _close_win32(self) -> None:
        """Stop the WGC session, wake any waiter, and drain the slot."""
        try:
            self._control.stop()  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        except Exception as exc:  # noqa: BLE001 - close() must not raise
            warnings.warn(
                f"WGC stop() failed: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
        # Wake any thread blocked in ``read`` so it observes ``_closed = True``.
        self._frame_event.set()
        with self._frame_lock:
            self._latest_frame = None

    # --- X11 / Composite backend --------------------------------------------

    def _init_x11(self) -> None:
        """Open the X display, locate the window, and redirect via
        Composite."""
        if sys.platform != "linux":
            # Defensive narrow for pyright on non-Linux runs.
            raise RuntimeError("unreachable")

        if is_wayland_native():
            raise RuntimeError(
                "Capture requires X11 or XWayland; native Wayland is not supported",
            )

        pid = find_pid()
        if pid is None:
            raise RuntimeError("VRChat is not running")

        display = open_x11_display()
        if display is None:
            raise RuntimeError("X11 display unavailable")

        try:
            window = find_vrchat_window(display, pid)
            if window is None:
                raise RuntimeError("VRChat top-level window is not yet mapped")

            # Verify the server speaks Composite -- raises XError when
            # the extension isn't loaded so we can fail fast.
            try:
                composite.query_version(display)
            except Xlib.error.XError as exc:
                raise RuntimeError(
                    f"X11 Composite extension not available: {exc}",
                ) from exc

            try:
                # Redirect the window to off-screen storage so we can read
                # its pixels regardless of stacking order. Idempotent when
                # a compositor (picom, mutter, kwin...) already redirects.
                # python-xlib stubs declare ``update`` as a callable but
                # the protocol value is the int constant
                # ``RedirectAutomatic``.
                composite.redirect_window(window, composite.RedirectAutomatic)  # pyright: ignore[reportArgumentType]
            except Xlib.error.XError as exc:
                raise RuntimeError(f"Failed to redirect window: {exc}") from exc
        except BaseException:
            # Any failure between display open and successful redirect must
            # release the connection; otherwise an exception during init
            # leaks the X server socket.
            try:
                display.close()
            except Exception:  # noqa: BLE001 - cleanup must not mask the cause
                pass
            raise

        self._display = display
        self._window = window

    def _read_x11(self) -> np.ndarray:
        """Re-grab the window pixmap through Composite and return RGB
        ndarray."""
        if sys.platform != "linux":
            # Defensive narrow for pyright on non-Linux runs.
            raise RuntimeError("unreachable")

        try:
            geom = self._window.get_geometry()
            width = int(geom.width)
            height = int(geom.height)
            if width <= 0 or height <= 0:
                raise RuntimeError("Window has invalid geometry")
            pixmap = composite.name_window_pixmap(self._window)
            try:
                reply = pixmap.get_image(0, 0, width, height, X.ZPixmap, 0xFFFFFFFF)
            finally:
                pixmap.free()
        except Xlib.error.XError as exc:
            raise RuntimeError(f"X11 capture failed: {exc}") from exc

        bgra = np.frombuffer(reply.data, dtype=np.uint8).reshape(height, width, 4)
        return np.ascontiguousarray(bgra[..., 2::-1])

    def _close_x11(self) -> None:
        """Close the held X display connection (no unredirect, no pixmap)."""
        try:
            self._display.close()
        except Exception as exc:  # noqa: BLE001 - close() must not raise
            warnings.warn(
                f"X11 display close failed: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )

    # --- Public API ---------------------------------------------------------

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
        if sys.platform == "win32":
            return self._read_win32()
        if sys.platform == "linux":
            return self._read_x11()
        # Unreachable: ``__init__`` already filtered platforms.
        raise NotImplementedError(f"Capture is not supported on {sys.platform}")

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
        if sys.platform == "win32":
            self._close_win32()
        elif sys.platform == "linux":
            self._close_x11()

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
