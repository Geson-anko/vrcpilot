"""Tests for :mod:`vrcpilot.window.x11`.

The module under test raises ``ImportError`` on non-Linux platforms,
and the real connection paths require a reachable X server. Two
module-level skips up front gate the rest of the file: platform first,
then display reachability. Below the gate, the autouse
``_no_real_vrchat`` fixture (see :mod:`tests.conftest`) pins
``find_pid()`` to ``None`` so both helpers short-circuit to ``False``
before any X protocol traffic is sent — that single shared fixture
covers the dominant happy-VRChat-not-running branch with zero mocks.
The shared ``except Xlib.error.XError`` contract (any X protocol
failure surfaces as ``False``) is exercised once via
:class:`tests._fakes.FakeXWindow` on the simpler ``unfocus_window``
path, avoiding both a fragile real-X11 setup and wholesale Xlib-module
mocks.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

if sys.platform != "linux":
    pytest.skip("Linux-only module", allow_module_level=True)

from tests.helpers import has_x11_display

if not has_x11_display():
    pytest.skip("X11 display unavailable", allow_module_level=True)

import Xlib.error
from pytest_mock import MockerFixture

from tests._fakes import FakeXDisplay, FakeXWindow
from vrcpilot.window.x11 import focus_window, unfocus_window


class _FakeXError(Xlib.error.XError):
    """Bare ``XError`` subclass that skips the parent ``__init__``.

    The real ``Xlib.error.XError.__init__`` expects a parsed protocol
    reply; tests just need an instance to raise.
    """

    def __init__(self) -> None:  # noqa: D401
        pass


@contextmanager
def _fake_display_cm(
    display: FakeXDisplay | None,
) -> Iterator[FakeXDisplay | None]:
    """Wrap a fake display so it satisfies the ``x11_display()`` contract."""
    yield display


class TestFocusWindow:
    def test_returns_false_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        # Drive the native-Wayland branch by twiddling real env vars
        # (``is_wayland_native`` reads ``XDG_SESSION_TYPE`` and
        # ``DISPLAY``). The branch must warn and return ``False``.
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert focus_window() is False

    def test_returns_false_when_vrchat_not_running(self):
        # Autouse fixture pins ``find_pid()`` to ``None``; the helper
        # short-circuits before opening a real X11 display.
        assert focus_window() is False


class TestUnfocusWindow:
    def test_returns_false_on_wayland_native(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert unfocus_window() is False

    def test_returns_false_when_vrchat_not_running(self):
        # Autouse fixture pins ``find_pid()`` to ``None``.
        assert unfocus_window() is False

    def test_returns_false_on_xerror(self, mocker: MockerFixture):
        # Inject XError on ``window.configure``: FakeXWindow with
        # ``raises`` set throws on the first recorded call, exercising
        # the ``except Xlib.error.XError`` branch shared by both
        # ``focus_window`` and ``unfocus_window``. ``find_pid`` returns
        # non-None so we reach the X path; ``x11_display`` is replaced
        # with a fake context manager yielding a benign FakeXDisplay
        # (the lookup is short-circuited by patching
        # ``find_vrchat_window``).
        mocker.patch("vrcpilot.window.x11.find_pid", return_value=4242)
        mocker.patch(
            "vrcpilot.window.x11.x11_display",
            return_value=_fake_display_cm(FakeXDisplay()),
        )
        mocker.patch(
            "vrcpilot.window.x11.find_vrchat_window",
            return_value=FakeXWindow(raises=_FakeXError()),
        )

        assert unfocus_window() is False
