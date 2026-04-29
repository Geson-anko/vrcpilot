"""Tests for :mod:`vrcpilot.window`."""

from __future__ import annotations

import sys

import pytest
from PIL import Image
from pytest_mock import MockerFixture

import vrcpilot.window
from tests.helpers import only_linux, only_windows
from vrcpilot.window import focus, take_screenshot, unfocus

if sys.platform == "win32":
    import pywintypes


class TestFocus:
    @only_windows
    def test_returns_false_when_not_running(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=None)

        assert focus() is False

    @only_windows
    def test_returns_false_when_hwnd_not_found(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd_win32", return_value=None)

        assert focus() is False

    @only_windows
    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd_win32", return_value=12345)
        mocker.patch("vrcpilot.window.win32gui.IsIconic", return_value=False)
        set_fg = mocker.patch("vrcpilot.window.win32gui.SetForegroundWindow")
        mocker.patch("vrcpilot.window.win32gui.BringWindowToTop")
        mocker.patch("vrcpilot.window.win32api.keybd_event")

        assert focus() is True
        set_fg.assert_called_once_with(12345)

    @only_windows
    def test_restores_minimized_window(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd_win32", return_value=12345)
        mocker.patch("vrcpilot.window.win32gui.IsIconic", return_value=True)
        show_window_mock = mocker.patch("vrcpilot.window.win32gui.ShowWindow")
        mocker.patch("vrcpilot.window.win32gui.SetForegroundWindow")
        mocker.patch("vrcpilot.window.win32gui.BringWindowToTop")
        mocker.patch("vrcpilot.window.win32api.keybd_event")

        result = focus()

        assert result is True
        assert show_window_mock.called

    @only_windows
    def test_returns_false_on_pywintypes_error(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd_win32", return_value=12345)
        mocker.patch("vrcpilot.window.win32gui.IsIconic", return_value=False)
        mocker.patch(
            "vrcpilot.window.win32gui.SetForegroundWindow",
            side_effect=pywintypes.error(0, "SetForegroundWindow", "msg"),
        )
        mocker.patch("vrcpilot.window.win32api.keybd_event")

        assert focus() is False


class TestUnfocus:
    @only_windows
    def test_returns_false_when_not_running(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=None)

        assert unfocus() is False

    @only_windows
    def test_returns_false_when_hwnd_not_found(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd_win32", return_value=None)

        assert unfocus() is False

    @only_windows
    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd_win32", return_value=12345)
        set_pos = mocker.patch("vrcpilot.window.win32gui.SetWindowPos")

        assert unfocus() is True
        set_pos.assert_called_once()
        # First positional arg is the HWND, second is the insert-after handle.
        args = set_pos.call_args.args
        assert args[0] == 12345

    @only_windows
    def test_returns_false_on_pywintypes_error(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd_win32", return_value=12345)
        mocker.patch(
            "vrcpilot.window.win32gui.SetWindowPos",
            side_effect=pywintypes.error(0, "SetWindowPos", "msg"),
        )

        assert unfocus() is False


class TestPlatformGuard:
    def test_focus_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.window.sys.platform", "darwin")

        with pytest.raises(NotImplementedError):
            vrcpilot.window.focus()

    def test_unfocus_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.window.sys.platform", "darwin")

        with pytest.raises(NotImplementedError):
            vrcpilot.window.unfocus()

    def test_take_screenshot_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.window.sys.platform", "darwin")

        with pytest.raises(NotImplementedError):
            vrcpilot.window.take_screenshot()

    def test_take_screenshot_raises_not_implemented_on_win32(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.window.sys.platform", "win32")

        with pytest.raises(NotImplementedError):
            vrcpilot.window.take_screenshot()


class TestFocusX11:
    @only_linux
    def test_returns_false_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert vrcpilot.window.focus() is False

    @only_linux
    def test_returns_false_when_not_running(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=None)

        assert vrcpilot.window.focus() is False

    @only_linux
    def test_returns_false_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.Xlib.display.Display")
        mocker.patch("vrcpilot.window._find_vrchat_window_x11", return_value=None)

        assert vrcpilot.window.focus() is False

    @only_linux
    def test_returns_false_on_display_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot.window.Xlib.display.Display",
            side_effect=vrcpilot.window.Xlib.error.DisplayError(":0"),
        )

        assert vrcpilot.window.focus() is False

    @only_linux
    def test_success_sends_active_window_message(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)

        fake_window = mocker.Mock()
        fake_root = mocker.Mock()
        fake_screen = mocker.Mock(root=fake_root)
        fake_display = mocker.Mock()
        fake_display.screen.return_value = fake_screen
        mocker.patch("vrcpilot.window.Xlib.display.Display", return_value=fake_display)
        mocker.patch(
            "vrcpilot.window._find_vrchat_window_x11", return_value=fake_window
        )
        # ``ClientMessage`` packs its arguments into a struct on
        # construction; the mocked window cannot satisfy that, so we
        # stub the event class out entirely.
        mocker.patch("vrcpilot.window.Xlib.protocol.event.ClientMessage")

        assert vrcpilot.window.focus() is True
        assert fake_root.send_event.called
        assert fake_display.flush.called
        assert fake_display.close.called


class TestUnfocusX11:
    @only_linux
    def test_returns_false_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert vrcpilot.window.unfocus() is False

    @only_linux
    def test_returns_false_when_not_running(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=None)

        assert vrcpilot.window.unfocus() is False

    @only_linux
    def test_returns_false_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.Xlib.display.Display")
        mocker.patch("vrcpilot.window._find_vrchat_window_x11", return_value=None)

        assert vrcpilot.window.unfocus() is False

    @only_linux
    def test_success_lowers_window(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)

        fake_window = mocker.Mock()
        fake_display = mocker.Mock()
        mocker.patch("vrcpilot.window.Xlib.display.Display", return_value=fake_display)
        mocker.patch(
            "vrcpilot.window._find_vrchat_window_x11", return_value=fake_window
        )

        assert vrcpilot.window.unfocus() is True
        assert fake_window.configure.called
        kwargs = fake_window.configure.call_args.kwargs
        assert "stack_mode" in kwargs
        assert fake_display.flush.called
        assert fake_display.close.called


class TestTakeScreenshot:
    @pytest.fixture(autouse=True)
    def _stub_focus_and_sleep(self, mocker: MockerFixture):
        # ``_take_screenshot_x11`` raises the window before grabbing
        # via ``_focus_x11`` and waits ``time.sleep``. The real
        # ``_focus_x11`` builds an Xlib ClientMessage that can't be
        # populated from Mock attributes, and the sleep would slow the
        # suite down — stub both so each test only exercises the
        # capture path it cares about.
        mocker.patch("vrcpilot.window.focus", return_value=True)
        mocker.patch("vrcpilot.window.time.sleep")

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
        mocker.patch("vrcpilot.window.find_pid", return_value=None)

        assert take_screenshot() is None

    @only_linux
    def test_returns_none_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.Xlib.display.Display")
        mocker.patch("vrcpilot.window._find_vrchat_window_x11", return_value=None)

        assert take_screenshot() is None

    @only_linux
    def test_returns_none_when_rect_unavailable(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.Xlib.display.Display")
        mocker.patch(
            "vrcpilot.window._find_vrchat_window_x11", return_value=mocker.Mock()
        )
        mocker.patch("vrcpilot.window._get_vrchat_rect_x11", return_value=None)

        assert take_screenshot() is None

    @only_linux
    def test_returns_none_on_display_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot.window.Xlib.display.Display",
            side_effect=vrcpilot.window.Xlib.error.DisplayError(":0"),
        )

        assert take_screenshot() is None

    @only_linux
    def test_returns_pil_image_on_success(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.Xlib.display.Display")
        mocker.patch(
            "vrcpilot.window._find_vrchat_window_x11", return_value=mocker.Mock()
        )
        mocker.patch(
            "vrcpilot.window._get_vrchat_rect_x11", return_value=(0, 0, 100, 50)
        )
        mocker.patch("vrcpilot.window.time.sleep")

        fake_shot = mocker.Mock()
        fake_shot.size = (100, 50)
        fake_shot.bgra = bytes(100 * 50 * 4)
        fake_sct = mocker.Mock()
        fake_sct.grab.return_value = fake_shot
        mocker.patch("vrcpilot.window.mss.MSS", return_value=fake_sct)

        result = take_screenshot()

        assert isinstance(result, Image.Image)
        assert result.size == (100, 50)

    @only_linux
    def test_focuses_window_before_capture(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # The capture path raises the VRChat window first so other
        # windows that overlap its rectangle do not bleed into the
        # image. Verify that contract by spying on ``_focus_x11`` and
        # ``time.sleep``.
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.Xlib.display.Display")
        mocker.patch(
            "vrcpilot.window._find_vrchat_window_x11", return_value=mocker.Mock()
        )
        mocker.patch(
            "vrcpilot.window._get_vrchat_rect_x11", return_value=(0, 0, 100, 50)
        )
        focus_spy = mocker.patch("vrcpilot.window.focus", return_value=True)
        sleep_spy = mocker.patch("vrcpilot.window.time.sleep")

        fake_shot = mocker.Mock()
        fake_shot.size = (100, 50)
        fake_shot.bgra = bytes(100 * 50 * 4)
        fake_sct = mocker.Mock()
        fake_sct.grab.return_value = fake_shot
        mocker.patch("vrcpilot.window.mss.MSS", return_value=fake_sct)

        take_screenshot()

        focus_spy.assert_called_once()
        sleep_spy.assert_called_once()
        assert sleep_spy.call_args.args[0] > 0


class TestGetVrchatRectX11:
    @only_linux
    def test_translates_relative_to_screen(self, mocker: MockerFixture):
        # window.get_geometry() yields parent-relative origin + size; the
        # absolute screen position is recovered via translate_coords(root,
        # 0, 0). Pass a translation of (-200, -100) and assert the helper
        # negates it back to (200, 100).
        fake_geom = mocker.Mock(width=100, height=50)
        fake_coords = mocker.Mock(x=-200, y=-100)
        fake_window = mocker.Mock()
        fake_window.get_geometry.return_value = fake_geom
        fake_window.translate_coords.return_value = fake_coords

        fake_root = mocker.Mock()
        fake_screen = mocker.Mock(root=fake_root)
        fake_display = mocker.Mock()
        fake_display.screen.return_value = fake_screen

        result = vrcpilot.window._get_vrchat_rect_x11(fake_display, fake_window)

        assert result == (200, 100, 100, 50)

    @only_linux
    @pytest.mark.parametrize(
        ("width", "height"),
        [(0, 50), (100, 0), (0, 0), (-1, 50), (100, -1)],
    )
    def test_returns_none_when_zero_size(
        self, mocker: MockerFixture, width: int, height: int
    ):
        fake_geom = mocker.Mock(width=width, height=height)
        fake_coords = mocker.Mock(x=0, y=0)
        fake_window = mocker.Mock()
        fake_window.get_geometry.return_value = fake_geom
        fake_window.translate_coords.return_value = fake_coords

        fake_display = mocker.Mock()
        fake_display.screen.return_value = mocker.Mock(root=mocker.Mock())

        assert vrcpilot.window._get_vrchat_rect_x11(fake_display, fake_window) is None

    @only_linux
    def test_returns_none_on_xerror(self, mocker: MockerFixture):
        # ``Xlib.error.XError`` requires positional ``display`` and ``data``
        # arguments (the latter is normally a parsed protocol reply).
        # Defining a tiny subclass lets us raise it without fabricating a
        # protocol payload — only the type matters for the except clause.
        class _FakeXError(vrcpilot.window.Xlib.error.XError):
            def __init__(self):
                pass

        fake_window = mocker.Mock()
        fake_window.get_geometry.return_value = mocker.Mock(width=100, height=50)
        fake_window.translate_coords.side_effect = _FakeXError()

        fake_display = mocker.Mock()
        fake_display.screen.return_value = mocker.Mock(root=mocker.Mock())

        assert vrcpilot.window._get_vrchat_rect_x11(fake_display, fake_window) is None
