"""Tests for :mod:`vrcpilot.capture`.

The :class:`vrcpilot.capture.Capture` class is exercised end-to-end with
two test doubles standing in for the real platform backends:

- ``_FakeWindowsCapture`` patches the WGC entry point so frames can be
  emitted at any time from the test, controlling the latest-only
  semantics under the implementation's :class:`threading.Event` /
  ``threading.Lock`` machinery.
- ``mocker.patch`` of ``open_x11_display`` / ``find_vrchat_window`` /
  ``composite.*`` is used for the X11 path so the tests run on every
  CI platform without needing a real X server.
"""

from __future__ import annotations

from typing import override

import numpy as np
import pytest
from pytest_mock import MockerFixture

from tests.helpers import only_linux, only_windows
from vrcpilot.capture import Capture

# ---------------------------------------------------------------------------
# Test double: WindowsCapture
# ---------------------------------------------------------------------------


class _FakeControl:
    """Minimal stand-in for ``windows_capture.CaptureControl``.

    Records each call to :meth:`stop` so tests can assert the close
    handshake; ``wait`` is left unimplemented because ``Capture.close``
    does not block on the worker thread (the real session is free-
    threaded and we wake it through ``Event.set``).
    """

    def __init__(self) -> None:
        self.stop_calls: int = 0
        self.stop_raises: BaseException | None = None

    def stop(self) -> None:
        self.stop_calls += 1
        if self.stop_raises is not None:
            raise self.stop_raises


class _FakeFrameBuffer:
    """Mimic ``windows_capture.Frame.frame_buffer`` -- only ``tobytes`` is
    used."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def tobytes(self) -> bytes:
        return self._payload


class _FakeFrame:
    """Mimic ``windows_capture.Frame`` -- only the fields ``Capture`` reads."""

    def __init__(self, payload: bytes, width: int, height: int) -> None:
        self.frame_buffer = _FakeFrameBuffer(payload)
        self.width = width
        self.height = height


class _FakeWindowsCapture:
    """Test double for ``windows_capture.WindowsCapture``.

    Records constructor kwargs on the class, captures the ``@event``-
    decorated handlers, and exposes :meth:`emit_frame` so each test can
    fire frames synchronously into ``Capture``'s registered
    ``on_frame_arrived`` callback. Unlike the real library, no
    background thread is spawned.

    Subclassed inside :func:`fake_windows_capture` so each test gets a
    fresh class with its own mutable class-level state -- prevents
    bleed-through of ``last_kwargs`` / ``start_raises`` /
    ``last_instance`` between tests.
    """

    last_kwargs: dict[str, object] = {}
    start_raises: BaseException | None = None
    # Reference to the most recently constructed instance, set so tests
    # can reach in to call :meth:`emit_frame` after ``Capture.__init__``
    # has consumed the constructor.
    last_instance: _FakeWindowsCapture | None = None

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs
        type(self).last_instance = self
        self._frame_handler: object = None
        self._closed_handler: object = None
        self._control = _FakeControl()

    def event(self, fn: object) -> object:
        # Replicates ``windows_capture.WindowsCapture.event`` which routes
        # by ``__name__``. The function is returned untouched so the
        # decorator preserves the original definition.
        name = getattr(fn, "__name__", "")
        if name == "on_frame_arrived":
            self._frame_handler = fn
        elif name == "on_closed":
            self._closed_handler = fn
        return fn

    def start_free_threaded(self) -> _FakeControl:
        if type(self).start_raises is not None:
            raise type(self).start_raises
        return self._control

    def emit_frame(self, payload: bytes, width: int, height: int) -> None:
        """Synchronously invoke the registered ``on_frame_arrived`` callback.

        Mirrors the real library's free-threaded callback firing but
        lets the test choose exactly when frames arrive, which is what
        makes the latest-only semantics deterministically testable.
        """
        handler = self._frame_handler
        assert handler is not None, "on_frame_arrived was not registered"
        # The real library passes a Frame and an InternalCaptureControl;
        # the capture implementation only reads frame_buffer / width /
        # height and ignores the control, so a simple stand-in suffices.
        handler(_FakeFrame(payload, width, height), object())  # type: ignore[operator]

    @property
    def control(self) -> _FakeControl:
        return self._control


@pytest.fixture
def fake_windows_capture(
    mocker: MockerFixture,
) -> type[_FakeWindowsCapture]:
    """Patch ``WindowsCapture`` in the Win32 backend module with a fresh fake.

    A fresh subclass per test isolates the class-level ``last_kwargs`` /
    ``start_raises`` / ``last_instance`` mutable state so tests cannot
    leak fixture state into one another.
    """

    class _Fake(_FakeWindowsCapture):
        last_kwargs: dict[str, object] = {}
        start_raises: BaseException | None = None
        last_instance: _FakeWindowsCapture | None = None

    mocker.patch("vrcpilot.capture.win32.WindowsCapture", _Fake)
    return _Fake


# ---------------------------------------------------------------------------
# Helpers for the X11 path
# ---------------------------------------------------------------------------


def _patch_x11_backend(
    mocker: MockerFixture,
    *,
    width: int = 100,
    height: int = 50,
    pid: int = 4242,
) -> tuple[object, object, object]:
    """Wire up the standard happy-path mocks for an X11 ``Capture``.

    Returns the ``(display, window, pixmap)`` mocks so tests can layer
    additional assertions or per-test side effects on top.
    """
    fake_display = mocker.Mock()
    fake_window = mocker.Mock()
    fake_window.get_geometry.return_value = mocker.Mock(width=width, height=height)
    fake_pixmap = mocker.Mock()
    fake_pixmap.get_image.return_value = mocker.Mock(data=bytes(width * height * 4))

    mocker.patch("vrcpilot.capture.x11.find_pid", return_value=pid)
    mocker.patch("vrcpilot.capture.x11.open_x11_display", return_value=fake_display)
    mocker.patch("vrcpilot.capture.x11.find_vrchat_window", return_value=fake_window)
    mocker.patch("vrcpilot.capture.x11.composite.query_version")
    mocker.patch("vrcpilot.capture.x11.composite.redirect_window")
    mocker.patch(
        "vrcpilot.capture.x11.composite.name_window_pixmap",
        return_value=fake_pixmap,
    )
    return fake_display, fake_window, fake_pixmap


def _make_xerror_subclass() -> type[BaseException]:
    """Return a no-arg subclass of the real ``Xlib.error.XError``.

    The real ``XError`` requires a ``display`` and a parsed protocol
    reply -- inconvenient in pure-unit tests. A subclass with an empty
    ``__init__`` keeps the type identity that the implementation
    catches without needing a real reply payload. ``__str__`` is also
    overridden because the parent reads ``self._data`` which is left
    unset by the empty ``__init__`` -- the f-string in capture.py would
    otherwise recurse forever in ``GetAttrData.__getattr__``.
    """
    import vrcpilot.capture.x11 as _x11_backend

    real_xerror = _x11_backend.Xlib.error.XError

    class _NoArgXError(real_xerror):  # type: ignore[misc, valid-type]
        @override
        def __init__(self) -> None:  # noqa: D401
            pass

        @override
        def __str__(self) -> str:
            return "_NoArgXError"

    return _NoArgXError


# ---------------------------------------------------------------------------
# Cross-platform behaviour
# ---------------------------------------------------------------------------


class TestCapture:
    # --- platform / argument validation --------------------------------

    def test_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # The class must refuse unsupported platforms outright -- there
        # is no fallback backend, so silently degrading would mislead.
        monkeypatch.setattr("vrcpilot.capture.sys.platform", "darwin")

        with pytest.raises(NotImplementedError):
            Capture()

    @pytest.mark.parametrize("frame_timeout", [0.0, -0.1, -1.0])
    def test_rejects_non_positive_frame_timeout(self, frame_timeout: float):
        # Zero or negative timeouts would either spin or raise on every
        # ``read`` call; we surface the misuse at construction time so
        # the failure points at the caller, not at the first ``read``.
        with pytest.raises(ValueError, match="frame_timeout must be > 0"):
            Capture(frame_timeout=frame_timeout)

    # --- Win32 lifecycle -----------------------------------------------

    @only_windows
    def test_win32_lifecycle_returns_rgb_frame(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # Construct the WGC backend, emit a recognisable BGRA payload,
        # and verify Capture decodes a contiguous (H, W, 3) RGB array.
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)

        # 4 BGRA pixels: B=0x10 G=0x20 R=0x30 A=0xff -- after BGRA -> RGB
        # the first three channels per pixel should be (0x30, 0x20, 0x10).
        payload = b"\x10\x20\x30\xff" * (2 * 2)

        with Capture(frame_timeout=1.0) as cap:
            instance = fake_windows_capture.last_instance
            assert instance is not None
            instance.emit_frame(payload, 2, 2)

            frame = cap.read()

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (2, 2, 3)
        assert frame.dtype == np.uint8
        assert frame.flags["C_CONTIGUOUS"]
        assert tuple(frame[0, 0].tolist()) == (0x30, 0x20, 0x10)

    @only_windows
    def test_win32_read_returns_latest_frame_only(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # Emit two frames back-to-back without an intervening read; the
        # latest-only buffer should drop the first and surface only the
        # most recent. Otherwise consumers fall behind by accumulating
        # FIFO lag -- the explicit anti-pattern this design rejects.
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)

        a_payload = b"\x00\x00\x00\xff" * 4  # all black -> RGB (0,0,0)
        b_payload = b"\x10\x20\x30\xff" * 4  # -> RGB (0x30,0x20,0x10)

        with Capture(frame_timeout=1.0) as cap:
            instance = fake_windows_capture.last_instance
            assert instance is not None
            instance.emit_frame(a_payload, 2, 2)
            instance.emit_frame(b_payload, 2, 2)

            frame = cap.read()

        assert tuple(frame[0, 0].tolist()) == (0x30, 0x20, 0x10)

    @only_windows
    def test_win32_read_times_out_when_no_frame(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # When the WGC session never delivers a frame, ``read`` must
        # raise ``TimeoutError`` rather than hang indefinitely.
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)

        with Capture(frame_timeout=0.05) as cap:
            with pytest.raises(TimeoutError, match="No frame arrived"):
                cap.read()

    @only_windows
    def test_win32_init_raises_when_vrchat_not_running(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=None)

        with pytest.raises(RuntimeError, match="VRChat is not running"):
            Capture()

    @only_windows
    def test_win32_init_raises_when_hwnd_missing(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=None)

        with pytest.raises(RuntimeError, match="window is not yet mapped"):
            Capture()

    @only_windows
    def test_win32_init_wraps_oserror_at_start(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # WGC start can fail with OSError on machines without the right
        # GPU / OS support. Capture must re-raise as RuntimeError so the
        # caller sees a single failure mode, with the original OSError
        # preserved on ``__cause__`` for diagnosis.
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)
        original = OSError("WGC unavailable")
        fake_windows_capture.start_raises = original

        with pytest.raises(RuntimeError, match="Failed to start WGC session") as ei:
            Capture()
        assert ei.value.__cause__ is original

    @only_windows
    def test_win32_passes_expected_kwargs_to_windows_capture(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # Capture must turn off the cursor overlay and the WGC border so
        # the returned frame contains only window content, not OS chrome.
        # ``window_hwnd`` pins the target so the wrong window cannot be
        # captured if a same-titled one appears later.
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=98765)

        cap = Capture()
        try:
            assert fake_windows_capture.last_kwargs == {
                "cursor_capture": False,
                "draw_border": False,
                "window_hwnd": 98765,
            }
        finally:
            cap.close()

    # --- X11 lifecycle -------------------------------------------------

    @only_linux
    def test_x11_lifecycle_returns_rgb_frame(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # Provide a constant BGRA buffer; verify ``read`` returns a
        # contiguous (H, W, 3) RGB array of the right shape.
        monkeypatch.setenv("DISPLAY", ":0")
        _patch_x11_backend(mocker, width=4, height=3)

        with Capture() as cap:
            frame = cap.read()

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (3, 4, 3)
        assert frame.dtype == np.uint8
        assert frame.flags["C_CONTIGUOUS"]

    @only_linux
    def test_x11_init_raises_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        # Capture must raise on native Wayland (no X server reachable),
        # *not* warn-and-return-None. Single-shot screenshot has the
        # warning path; continuous capture is fail-fast by design.
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.raises(RuntimeError, match="native Wayland is not supported"):
            Capture()

    @only_linux
    def test_x11_init_raises_when_vrchat_not_running(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.x11.find_pid", return_value=None)

        with pytest.raises(RuntimeError, match="VRChat is not running"):
            Capture()

    @only_linux
    def test_x11_init_raises_when_display_unavailable(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.x11.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.x11.open_x11_display", return_value=None)

        with pytest.raises(RuntimeError, match="X11 display unavailable"):
            Capture()

    @only_linux
    def test_x11_init_raises_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # If the window can't be located we must close the display we
        # just opened before re-raising; otherwise the X server socket
        # leaks across each retry.
        monkeypatch.setenv("DISPLAY", ":0")
        fake_display = mocker.Mock()
        mocker.patch("vrcpilot.capture.x11.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot.capture.x11.open_x11_display",
            return_value=fake_display,
        )
        mocker.patch("vrcpilot.capture.x11.find_vrchat_window", return_value=None)

        with pytest.raises(RuntimeError, match="window is not yet mapped"):
            Capture()
        fake_display.close.assert_called_once()

    @only_linux
    def test_x11_init_raises_on_composite_xerror(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        fake_display = mocker.Mock()
        fake_window = mocker.Mock()
        mocker.patch("vrcpilot.capture.x11.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot.capture.x11.open_x11_display",
            return_value=fake_display,
        )
        mocker.patch(
            "vrcpilot.capture.x11.find_vrchat_window",
            return_value=fake_window,
        )

        xerr_cls = _make_xerror_subclass()
        mocker.patch(
            "vrcpilot.capture.x11.composite.query_version",
            side_effect=xerr_cls(),
        )

        with pytest.raises(RuntimeError, match="X11 Composite extension"):
            Capture()
        fake_display.close.assert_called_once()

    @only_linux
    def test_x11_read_raises_on_invalid_geometry(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # A window can resize to zero between init and the next read; we
        # surface that as a typed RuntimeError instead of producing an
        # empty array, which would mask the underlying bug.
        monkeypatch.setenv("DISPLAY", ":0")
        _, fake_window, _ = _patch_x11_backend(mocker, width=4, height=3)

        cap = Capture()
        try:
            fake_window.get_geometry.return_value = mocker.Mock(width=0, height=0)
            with pytest.raises(RuntimeError, match="invalid geometry"):
                cap.read()
        finally:
            cap.close()

    @only_linux
    def test_x11_read_translates_xerror(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # Inject an XError on the get_image call. Capture must wrap it as
        # a RuntimeError -- callers catch ``RuntimeError`` and decide to
        # retry; raw ``Xlib.error.XError`` would force them to import
        # python-xlib just for error handling.
        monkeypatch.setenv("DISPLAY", ":0")
        _, _, fake_pixmap = _patch_x11_backend(mocker, width=4, height=3)
        xerr_cls = _make_xerror_subclass()
        fake_pixmap.get_image.side_effect = xerr_cls()

        with Capture() as cap:
            with pytest.raises(RuntimeError, match="X11 capture failed"):
                cap.read()

    # --- close / context-manager semantics -----------------------------

    @only_windows
    def test_close_is_idempotent_on_windows(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # ``close`` may be called from ``__exit__``, by an explicit
        # caller, or from a finally block -- doubling up must be safe.
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)

        cap = Capture()
        cap.close()
        cap.close()
        cap.close()

        # Second/third calls are no-ops, so stop() is invoked exactly
        # once on the underlying CaptureControl.
        instance = fake_windows_capture.last_instance
        assert instance is not None
        assert instance.control.stop_calls == 1

    @only_linux
    def test_close_is_idempotent_on_linux(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        fake_display, _, _ = _patch_x11_backend(mocker)

        cap = Capture()
        cap.close()
        cap.close()
        cap.close()

        # Display.close runs only on the first ``Capture.close`` call;
        # idempotence is enforced by the ``_closed`` flag.
        fake_display.close.assert_called_once()

    @only_windows
    def test_read_after_close_raises_on_windows(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)

        cap = Capture()
        cap.close()
        with pytest.raises(RuntimeError, match="Capture is closed"):
            cap.read()

    @only_linux
    def test_read_after_close_raises_on_linux(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        _patch_x11_backend(mocker)

        cap = Capture()
        cap.close()
        with pytest.raises(RuntimeError, match="Capture is closed"):
            cap.read()

    @only_windows
    def test_exit_closes_capture(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)

        with Capture() as cap:
            pass

        with pytest.raises(RuntimeError, match="Capture is closed"):
            cap.read()

    @only_windows
    def test_exit_does_not_suppress_exception(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # The context manager must propagate exceptions from the with-
        # block. Suppression would silently swallow real failures and
        # is not the contract we want.
        mocker.patch("vrcpilot.capture.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.win32.find_vrchat_hwnd", return_value=12345)

        class _Sentinel(Exception):
            pass

        with pytest.raises(_Sentinel):
            with Capture():
                raise _Sentinel("boom")
