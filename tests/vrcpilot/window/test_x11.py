"""Tests for :mod:`vrcpilot.window.x11`."""

from __future__ import annotations

import sys

import pytest
from pytest_mock import MockerFixture

import vrcpilot.window
from tests.helpers import only_linux

if sys.platform == "linux":
    import vrcpilot.window.x11 as _x11_backend


@only_linux
class TestFocus:
    def test_returns_false_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert vrcpilot.window.focus() is False

    def test_returns_false_when_not_running(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=None)

        assert vrcpilot.window.focus() is False

    def test_returns_false_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=4242)
        mocker.patch("vrcpilot.x11.Xlib.display.Display")
        mocker.patch("vrcpilot.window.x11.find_vrchat_window", return_value=None)

        assert vrcpilot.window.focus() is False

    def test_returns_false_on_display_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot.x11.Xlib.display.Display",
            side_effect=_x11_backend.Xlib.error.DisplayError(":0"),
        )

        assert vrcpilot.window.focus() is False

    def test_success_sends_active_window_message(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=4242)

        fake_window = mocker.Mock()
        fake_root = mocker.Mock()
        fake_screen = mocker.Mock(root=fake_root)
        fake_display = mocker.Mock()
        fake_display.screen.return_value = fake_screen
        mocker.patch("vrcpilot.x11.Xlib.display.Display", return_value=fake_display)
        mocker.patch("vrcpilot.window.x11.find_vrchat_window", return_value=fake_window)
        # ``ClientMessage`` packs its arguments into a struct on
        # construction; the mocked window cannot satisfy that, so we
        # stub the event class out entirely.
        mocker.patch("vrcpilot.window.x11.Xlib.protocol.event.ClientMessage")

        assert vrcpilot.window.focus() is True
        assert fake_root.send_event.called
        assert fake_display.flush.called
        assert fake_display.close.called


@only_linux
class TestUnfocus:
    def test_returns_false_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert vrcpilot.window.unfocus() is False

    def test_returns_false_when_not_running(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=None)

        assert vrcpilot.window.unfocus() is False

    def test_returns_false_when_window_not_found(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=4242)
        mocker.patch("vrcpilot.x11.Xlib.display.Display")
        mocker.patch("vrcpilot.window.x11.find_vrchat_window", return_value=None)

        assert vrcpilot.window.unfocus() is False

    def test_success_lowers_window(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("DISPLAY", ":0")
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=4242)

        fake_window = mocker.Mock()
        fake_display = mocker.Mock()
        mocker.patch("vrcpilot.x11.Xlib.display.Display", return_value=fake_display)
        mocker.patch("vrcpilot.window.x11.find_vrchat_window", return_value=fake_window)

        assert vrcpilot.window.unfocus() is True
        assert fake_window.configure.called
        kwargs = fake_window.configure.call_args.kwargs
        assert "stack_mode" in kwargs
        assert fake_display.flush.called
        assert fake_display.close.called
