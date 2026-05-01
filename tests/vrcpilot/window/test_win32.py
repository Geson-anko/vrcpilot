"""Tests for :mod:`vrcpilot.window.win32`."""

from __future__ import annotations

import sys

from pytest_mock import MockerFixture

from tests.helpers import only_windows
from vrcpilot.window import focus, unfocus

if sys.platform == "win32":
    import pywintypes


@only_windows
class TestFocus:
    def test_returns_false_when_not_running(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=None)

        assert focus() is False

    def test_returns_false_when_hwnd_not_found(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.win32.find_vrchat_hwnd", return_value=None)

        assert focus() is False

    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.win32.find_vrchat_hwnd", return_value=12345)
        mocker.patch("vrcpilot.window.win32.win32gui.IsIconic", return_value=False)
        mocker.patch("vrcpilot.window.win32.win32gui.SetForegroundWindow")
        mocker.patch("vrcpilot.window.win32.win32gui.BringWindowToTop")
        mocker.patch("vrcpilot.window.win32.win32api.keybd_event")

        assert focus() is True

    def test_restores_minimized_window(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.win32.find_vrchat_hwnd", return_value=12345)
        mocker.patch("vrcpilot.window.win32.win32gui.IsIconic", return_value=True)
        show_window_mock = mocker.patch("vrcpilot.window.win32.win32gui.ShowWindow")
        mocker.patch("vrcpilot.window.win32.win32gui.SetForegroundWindow")
        mocker.patch("vrcpilot.window.win32.win32gui.BringWindowToTop")
        mocker.patch("vrcpilot.window.win32.win32api.keybd_event")

        result = focus()

        assert result is True
        assert show_window_mock.called

    def test_returns_false_on_pywintypes_error(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.win32.find_vrchat_hwnd", return_value=12345)
        mocker.patch("vrcpilot.window.win32.win32gui.IsIconic", return_value=False)
        mocker.patch(
            "vrcpilot.window.win32.win32gui.SetForegroundWindow",
            side_effect=pywintypes.error(0, "SetForegroundWindow", "msg"),
        )
        mocker.patch("vrcpilot.window.win32.win32api.keybd_event")

        assert focus() is False


@only_windows
class TestUnfocus:
    def test_returns_false_when_not_running(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=None)

        assert unfocus() is False

    def test_returns_false_when_hwnd_not_found(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.win32.find_vrchat_hwnd", return_value=None)

        assert unfocus() is False

    def test_returns_true_on_success(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.win32.find_vrchat_hwnd", return_value=12345)
        mocker.patch("vrcpilot.window.win32.win32gui.SetWindowPos")

        assert unfocus() is True

    def test_returns_false_on_pywintypes_error(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.window.win32.find_pid", return_value=4242)
        mocker.patch("vrcpilot.window.win32.find_vrchat_hwnd", return_value=12345)
        mocker.patch(
            "vrcpilot.window.win32.win32gui.SetWindowPos",
            side_effect=pywintypes.error(0, "SetWindowPos", "msg"),
        )

        assert unfocus() is False
