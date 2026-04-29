"""Tests for :mod:`vrcpilot.window`."""

from __future__ import annotations

import sys

import pytest
from pytest_mock import MockerFixture

import vrcpilot.window
from tests.helpers import only_windows
from vrcpilot.window import focus, unfocus

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
        mocker.patch("vrcpilot.window._find_vrchat_hwnd", return_value=None)

        assert focus() is False

    @only_windows
    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd", return_value=12345)
        mocker.patch("vrcpilot.window.win32gui.IsIconic", return_value=False)
        set_fg = mocker.patch("vrcpilot.window.win32gui.SetForegroundWindow")
        mocker.patch("vrcpilot.window.win32gui.BringWindowToTop")
        mocker.patch("vrcpilot.window.win32api.keybd_event")

        assert focus() is True
        set_fg.assert_called_once_with(12345)

    @only_windows
    def test_restores_minimized_window(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd", return_value=12345)
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
        mocker.patch("vrcpilot.window._find_vrchat_hwnd", return_value=12345)
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
        mocker.patch("vrcpilot.window._find_vrchat_hwnd", return_value=None)

        assert unfocus() is False

    @only_windows
    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd", return_value=12345)
        set_pos = mocker.patch("vrcpilot.window.win32gui.SetWindowPos")

        assert unfocus() is True
        set_pos.assert_called_once()
        # First positional arg is the HWND, second is the insert-after handle.
        args = set_pos.call_args.args
        assert args[0] == 12345

    @only_windows
    def test_returns_false_on_pywintypes_error(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window._find_vrchat_hwnd", return_value=12345)
        mocker.patch(
            "vrcpilot.window.win32gui.SetWindowPos",
            side_effect=pywintypes.error(0, "SetWindowPos", "msg"),
        )

        assert unfocus() is False


class TestPlatformGuard:
    def test_focus_raises_not_implemented_on_non_win32(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.window.sys.platform", "linux")

        with pytest.raises(NotImplementedError):
            vrcpilot.window.focus()

    def test_unfocus_raises_not_implemented_on_non_win32(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.window.sys.platform", "linux")

        with pytest.raises(NotImplementedError):
            vrcpilot.window.unfocus()
