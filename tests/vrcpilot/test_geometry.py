"""Tests for :mod:`vrcpilot.geometry`.

The autouse fixture in :mod:`tests.conftest` forces
:func:`vrcpilot.find_pid` to ``None`` for every test, so the geometry
helper short-circuits before reaching any platform API. That makes the
"VRChat not running" path testable on every host without a live VRChat
or even a usable display.

Platform branches that *would* reach into Win32 / X11 are gated by the
helpers in :mod:`tests.helpers` so each runner only executes the path
relevant to its OS.
"""

from __future__ import annotations

import sys

import pytest

from tests.helpers import only_linux, only_windows
from vrcpilot.geometry import get_vrchat_window_rect


class TestGetVrchatWindowRect:
    """Cross-platform: ``find_pid()`` is ``None``, helper must return
    ``None`` regardless of which platform branch is taken."""

    @only_windows
    def test_returns_none_when_vrchat_not_running_windows(self):
        # Win32 path: ``_get_vrchat_rect_win32`` -> ``find_pid()`` is
        # ``None`` (autouse fixture) -> returns ``None`` before any
        # Win32 API is touched.
        assert get_vrchat_window_rect() is None

    @only_linux
    def test_returns_none_when_vrchat_not_running_linux(self):
        # X11 path: ``_get_vrchat_rect_x11`` short-circuits on
        # ``find_pid() is None`` before opening a display, so this
        # works even on hosts with no X server.
        assert get_vrchat_window_rect() is None

    def test_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Patching ``sys.platform`` to a value the helper does not
        # recognise drives the trailing ``raise NotImplementedError``
        # branch. The check is read at call time (not import time) so
        # this works on any host.
        monkeypatch.setattr(sys, "platform", "darwin")

        with pytest.raises(NotImplementedError, match="darwin"):
            get_vrchat_window_rect()
