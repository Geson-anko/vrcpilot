"""Tests for :mod:`vrcpilot.window`."""

from __future__ import annotations

import sys

import pytest
from pytest_mock import MockerFixture

import vrcpilot.window
from tests.helpers import only_linux, only_windows
from vrcpilot.window import focus, unfocus

if sys.platform == "win32":
    import pywintypes
if sys.platform == "linux":
    import vrcpilot._backends.window_x11 as _x11_backend


class TestFocus:
    @only_windows
    def test_returns_false_when_not_running(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=None)

        assert focus() is False

    @only_windows
    def test_returns_false_when_hwnd_not_found(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._backends.window_win32.find_vrchat_hwnd", return_value=None
        )

        assert focus() is False

    @only_windows
    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._backends.window_win32.find_vrchat_hwnd", return_value=12345
        )
        mocker.patch(
            "vrcpilot._backends.window_win32.win32gui.IsIconic", return_value=False
        )
        set_fg = mocker.patch(
            "vrcpilot._backends.window_win32.win32gui.SetForegroundWindow"
        )
        mocker.patch("vrcpilot._backends.window_win32.win32gui.BringWindowToTop")
        mocker.patch("vrcpilot._backends.window_win32.win32api.keybd_event")

        assert focus() is True
        set_fg.assert_called_once_with(12345)

    @only_windows
    def test_restores_minimized_window(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._backends.window_win32.find_vrchat_hwnd", return_value=12345
        )
        mocker.patch(
            "vrcpilot._backends.window_win32.win32gui.IsIconic", return_value=True
        )
        show_window_mock = mocker.patch(
            "vrcpilot._backends.window_win32.win32gui.ShowWindow"
        )
        mocker.patch("vrcpilot._backends.window_win32.win32gui.SetForegroundWindow")
        mocker.patch("vrcpilot._backends.window_win32.win32gui.BringWindowToTop")
        mocker.patch("vrcpilot._backends.window_win32.win32api.keybd_event")

        result = focus()

        assert result is True
        assert show_window_mock.called

    @only_windows
    def test_returns_false_on_pywintypes_error(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._backends.window_win32.find_vrchat_hwnd", return_value=12345
        )
        mocker.patch(
            "vrcpilot._backends.window_win32.win32gui.IsIconic", return_value=False
        )
        mocker.patch(
            "vrcpilot._backends.window_win32.win32gui.SetForegroundWindow",
            side_effect=pywintypes.error(0, "SetForegroundWindow", "msg"),
        )
        mocker.patch("vrcpilot._backends.window_win32.win32api.keybd_event")

        assert focus() is False


class TestUnfocus:
    @only_windows
    def test_returns_false_when_not_running(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=None)

        assert unfocus() is False

    @only_windows
    def test_returns_false_when_hwnd_not_found(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._backends.window_win32.find_vrchat_hwnd", return_value=None
        )

        assert unfocus() is False

    @only_windows
    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._backends.window_win32.find_vrchat_hwnd", return_value=12345
        )
        set_pos = mocker.patch("vrcpilot._backends.window_win32.win32gui.SetWindowPos")

        assert unfocus() is True
        set_pos.assert_called_once()
        # First positional arg is the HWND, second is the insert-after handle.
        args = set_pos.call_args.args
        assert args[0] == 12345

    @only_windows
    def test_returns_false_on_pywintypes_error(self, mocker: MockerFixture):
        mocker.patch("vrcpilot._backends.window_win32.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._backends.window_win32.find_vrchat_hwnd", return_value=12345
        )
        mocker.patch(
            "vrcpilot._backends.window_win32.win32gui.SetWindowPos",
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
        mocker.patch("vrcpilot._backends.window_x11.find_pid", return_value=None)

        assert vrcpilot.window.focus() is False

    @only_linux
    def test_returns_false_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot._backends.window_x11.find_pid", return_value=4242)
        mocker.patch("vrcpilot._x11.Xlib.display.Display")
        mocker.patch(
            "vrcpilot._backends.window_x11.find_vrchat_window", return_value=None
        )

        assert vrcpilot.window.focus() is False

    @only_linux
    def test_returns_false_on_display_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot._backends.window_x11.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot._x11.Xlib.display.Display",
            side_effect=_x11_backend.Xlib.error.DisplayError(":0"),
        )

        assert vrcpilot.window.focus() is False

    @only_linux
    def test_success_sends_active_window_message(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot._backends.window_x11.find_pid", return_value=4242)

        fake_window = mocker.Mock()
        fake_root = mocker.Mock()
        fake_screen = mocker.Mock(root=fake_root)
        fake_display = mocker.Mock()
        fake_display.screen.return_value = fake_screen
        mocker.patch("vrcpilot._x11.Xlib.display.Display", return_value=fake_display)
        mocker.patch(
            "vrcpilot._backends.window_x11.find_vrchat_window", return_value=fake_window
        )
        # ``ClientMessage`` packs its arguments into a struct on
        # construction; the mocked window cannot satisfy that, so we
        # stub the event class out entirely.
        mocker.patch("vrcpilot._backends.window_x11.Xlib.protocol.event.ClientMessage")

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
        mocker.patch("vrcpilot._backends.window_x11.find_pid", return_value=None)

        assert vrcpilot.window.unfocus() is False

    @only_linux
    def test_returns_false_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot._backends.window_x11.find_pid", return_value=4242)
        mocker.patch("vrcpilot._x11.Xlib.display.Display")
        mocker.patch(
            "vrcpilot._backends.window_x11.find_vrchat_window", return_value=None
        )

        assert vrcpilot.window.unfocus() is False

    @only_linux
    def test_success_lowers_window(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot._backends.window_x11.find_pid", return_value=4242)

        fake_window = mocker.Mock()
        fake_display = mocker.Mock()
        mocker.patch("vrcpilot._x11.Xlib.display.Display", return_value=fake_display)
        mocker.patch(
            "vrcpilot._backends.window_x11.find_vrchat_window", return_value=fake_window
        )

        assert vrcpilot.window.unfocus() is True
        assert fake_window.configure.called
        kwargs = fake_window.configure.call_args.kwargs
        assert "stack_mode" in kwargs
        assert fake_display.flush.called
        assert fake_display.close.called
