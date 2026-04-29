"""Tests for :mod:`vrcpilot.capture`."""

from __future__ import annotations

import pytest
from PIL import Image
from pytest_mock import MockerFixture

import vrcpilot.capture
from tests.helpers import only_linux, only_windows
from vrcpilot.capture import take_screenshot


class TestPlatformGuard:
    def test_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.capture.sys.platform", "darwin")

        with pytest.raises(NotImplementedError):
            take_screenshot()


class TestTakeScreenshot:
    @only_linux
    def test_returns_none_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert take_screenshot() is None

    @only_linux
    def test_returns_none_when_not_running(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.find_pid", return_value=None)

        assert take_screenshot() is None

    @only_linux
    def test_returns_none_when_display_unavailable(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # ``x11_display`` yields ``None`` when the X server can't be
        # reached (e.g. SSH without X forwarding). Patch its callable
        # on the capture module to enter that path deterministically.
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        fake_cm = mocker.MagicMock()
        fake_cm.__enter__.return_value = None
        mocker.patch("vrcpilot.capture.x11_display", return_value=fake_cm)

        assert take_screenshot() is None

    @only_linux
    def test_returns_none_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        fake_cm = mocker.MagicMock()
        fake_cm.__enter__.return_value = mocker.Mock()
        mocker.patch("vrcpilot.capture.x11_display", return_value=fake_cm)
        mocker.patch("vrcpilot.capture.find_vrchat_window", return_value=None)

        assert take_screenshot() is None

    @only_linux
    def test_returns_none_on_composite_xerror(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # ``Xlib.error.XError`` requires positional ``display`` / ``data``
        # arguments (the latter is normally a parsed protocol reply).
        # Defining a tiny subclass lets us raise it without fabricating
        # a protocol payload — only the type matters for the except.
        class _FakeXError(vrcpilot.capture.Xlib.error.XError):
            def __init__(self):
                pass

        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        fake_display = mocker.Mock()
        fake_cm = mocker.MagicMock()
        fake_cm.__enter__.return_value = fake_display
        mocker.patch("vrcpilot.capture.x11_display", return_value=fake_cm)
        mocker.patch("vrcpilot.capture.find_vrchat_window", return_value=mocker.Mock())
        mocker.patch(
            "vrcpilot.capture.composite.query_version", side_effect=_FakeXError()
        )

        assert take_screenshot() is None

    @only_linux
    @pytest.mark.parametrize(
        ("width", "height"),
        [(0, 50), (100, 0), (0, 0), (-1, 50), (100, -1)],
    )
    def test_returns_none_when_geometry_zero_or_negative(
        self,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
        width: int,
        height: int,
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        fake_display = mocker.Mock()
        fake_cm = mocker.MagicMock()
        fake_cm.__enter__.return_value = fake_display
        mocker.patch("vrcpilot.capture.x11_display", return_value=fake_cm)
        fake_window = mocker.Mock()
        fake_window.get_geometry.return_value = mocker.Mock(width=width, height=height)
        mocker.patch("vrcpilot.capture.find_vrchat_window", return_value=fake_window)
        mocker.patch("vrcpilot.capture.composite.query_version")
        mocker.patch("vrcpilot.capture.composite.redirect_window")
        mocker.patch("vrcpilot.capture.composite.name_window_pixmap")

        assert take_screenshot() is None

    @only_linux
    def test_returns_pil_image_on_success(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        fake_display = mocker.Mock()
        fake_cm = mocker.MagicMock()
        fake_cm.__enter__.return_value = fake_display
        mocker.patch("vrcpilot.capture.x11_display", return_value=fake_cm)

        fake_window = mocker.Mock()
        fake_window.get_geometry.return_value = mocker.Mock(width=100, height=50)
        mocker.patch("vrcpilot.capture.find_vrchat_window", return_value=fake_window)

        fake_pixmap = mocker.Mock()
        fake_pixmap.get_image.return_value = mocker.Mock(data=bytes(100 * 50 * 4))
        mocker.patch("vrcpilot.capture.composite.query_version")
        mocker.patch("vrcpilot.capture.composite.redirect_window")
        mocker.patch(
            "vrcpilot.capture.composite.name_window_pixmap", return_value=fake_pixmap
        )

        result = take_screenshot()

        assert isinstance(result, Image.Image)
        assert result.size == (100, 50)
        # The capture path must release the temporary Pixmap regardless
        # of geometry, so the ``free()`` call is part of the contract.
        fake_pixmap.free.assert_called_once()

    @only_linux
    def test_does_not_focus_window(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # The Composite path must capture without raising the window —
        # otherwise the user's z-order is disturbed. Patch ``focus`` and
        # assert it isn't reached during a successful capture.
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        fake_display = mocker.Mock()
        fake_cm = mocker.MagicMock()
        fake_cm.__enter__.return_value = fake_display
        mocker.patch("vrcpilot.capture.x11_display", return_value=fake_cm)

        fake_window = mocker.Mock()
        fake_window.get_geometry.return_value = mocker.Mock(width=10, height=10)
        mocker.patch("vrcpilot.capture.find_vrchat_window", return_value=fake_window)

        fake_pixmap = mocker.Mock()
        fake_pixmap.get_image.return_value = mocker.Mock(data=bytes(10 * 10 * 4))
        mocker.patch("vrcpilot.capture.composite.query_version")
        mocker.patch("vrcpilot.capture.composite.redirect_window")
        mocker.patch(
            "vrcpilot.capture.composite.name_window_pixmap", return_value=fake_pixmap
        )

        # ``focus`` is a sibling public API; if anyone wires it back into
        # the capture path this spy fires.
        focus_spy = mocker.patch("vrcpilot.window.focus")

        take_screenshot()

        focus_spy.assert_not_called()


class _FakeWindowsCapture:
    """Test double for ``windows_capture.WindowsCapture``.

    Records constructor kwargs on the class, captures the registered
    ``on_frame_arrived`` handler, and lets each test fire a configured
    frame (or none, to simulate a timeout) from inside ``CaptureControl.wait()``.
    """

    last_kwargs: dict[str, object] = {}
    start_raises: BaseException | None = None
    frame_to_deliver: tuple[bytes, int, int] | None = None
    stop_calls: list[None] = []

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs
        self._frame_handler = None
        self._closed_handler = None

    def event(self, fn):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        if fn.__name__ == "on_frame_arrived":
            self._frame_handler = fn
        elif fn.__name__ == "on_closed":
            self._closed_handler = fn
        return fn

    def start_free_threaded(self):  # pyright: ignore[reportUnknownParameterType]
        if type(self).start_raises is not None:
            raise type(self).start_raises
        outer = self

        class _Control:
            def wait(self_inner) -> None:
                if (
                    outer.frame_to_deliver is not None
                    and outer._frame_handler is not None
                ):
                    data, w, h = outer.frame_to_deliver

                    class _Buf:
                        def __init__(self, payload: bytes):
                            self._payload = payload

                        def tobytes(self) -> bytes:
                            return self._payload

                    class _Frame:
                        def __init__(self, payload: bytes, width: int, height: int):
                            self.frame_buffer = _Buf(payload)
                            self.width = width
                            self.height = height

                    class _InternalControl:
                        @staticmethod
                        def stop() -> None:
                            type(outer).stop_calls.append(None)

                    outer._frame_handler(_Frame(data, w, h), _InternalControl())

            def stop(self_inner) -> None:
                pass

        return _Control()


@pytest.fixture
def fake_windows_capture(mocker: MockerFixture) -> type[_FakeWindowsCapture]:
    """Patch ``vrcpilot.capture.WindowsCapture`` with a fresh fake class.

    A fresh subclass per test isolates the class-level ``last_kwargs`` /
    ``frame_to_deliver`` / ``stop_calls`` mutable state so tests cannot
    leak fixture state into one another.
    """

    class _Fake(_FakeWindowsCapture):
        last_kwargs: dict[str, object] = {}
        start_raises: BaseException | None = None
        frame_to_deliver: tuple[bytes, int, int] | None = None
        stop_calls: list[None] = []

    mocker.patch("vrcpilot.capture.WindowsCapture", _Fake)
    return _Fake


class TestTakeScreenshotWin32:
    @only_windows
    def test_returns_none_when_not_running(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.find_pid", return_value=None)

        assert take_screenshot() is None

    @only_windows
    def test_returns_none_when_hwnd_not_found(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=None)

        assert take_screenshot() is None

    @only_windows
    def test_returns_none_on_oserror_at_start(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=12345)
        fake_windows_capture.start_raises = OSError("WGC unavailable")

        assert take_screenshot() is None

    @only_windows
    def test_returns_none_on_capture_timeout(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # ``frame_to_deliver`` left as ``None`` simulates the case where
        # the capture session never delivered a frame before the watchdog
        # fired.
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=12345)

        assert take_screenshot() is None

    @only_windows
    @pytest.mark.parametrize(
        ("width", "height"),
        [(0, 50), (100, 0), (0, 0), (-1, 50), (100, -1)],
    )
    def test_returns_none_on_zero_geometry(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
        width: int,
        height: int,
    ):
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=12345)
        # Allocate a payload large enough to satisfy ``Image.frombytes`` if
        # it were reached; the contract is that the size guard must short
        # out before the PIL call.
        fake_windows_capture.frame_to_deliver = (b"\x00" * (4 * 4 * 4), width, height)

        assert take_screenshot() is None

    @only_windows
    def test_returns_pil_image_on_success(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=12345)
        fake_windows_capture.frame_to_deliver = (bytes(100 * 50 * 4), 100, 50)

        result = take_screenshot()

        assert isinstance(result, Image.Image)
        assert result.size == (100, 50)

    @only_windows
    def test_does_not_focus_window(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        # WGC must capture without raising the window. Patch ``focus`` and
        # confirm a successful capture does not reach into it.
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=12345)
        fake_windows_capture.frame_to_deliver = (bytes(10 * 10 * 4), 10, 10)
        focus_spy = mocker.patch("vrcpilot.window.focus")

        take_screenshot()

        focus_spy.assert_not_called()

    @only_windows
    def test_capture_uses_no_border_no_cursor(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=12345)
        fake_windows_capture.frame_to_deliver = (bytes(4 * 4 * 4), 4, 4)

        take_screenshot()

        assert fake_windows_capture.last_kwargs == {
            "cursor_capture": False,
            "draw_border": False,
            "window_hwnd": 12345,
        }

    @only_windows
    def test_stops_capture_after_first_frame(
        self,
        mocker: MockerFixture,
        fake_windows_capture: type[_FakeWindowsCapture],
    ):
        mocker.patch("vrcpilot.capture.find_pid", return_value=4242)
        mocker.patch("vrcpilot.capture.find_vrchat_hwnd", return_value=12345)
        fake_windows_capture.frame_to_deliver = (bytes(4 * 4 * 4), 4, 4)

        take_screenshot()

        assert len(fake_windows_capture.stop_calls) == 1
