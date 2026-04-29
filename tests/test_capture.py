"""Tests for :mod:`vrcpilot.capture`."""

from __future__ import annotations

import pytest
from PIL import Image
from pytest_mock import MockerFixture

import vrcpilot.capture
from tests.helpers import only_linux
from vrcpilot.capture import take_screenshot


class TestPlatformGuard:
    def test_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.capture.sys.platform", "darwin")

        with pytest.raises(NotImplementedError):
            take_screenshot()

    def test_raises_not_implemented_on_win32(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("vrcpilot.capture.sys.platform", "win32")

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
