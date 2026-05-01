"""Tests for :mod:`vrcpilot.window` (top-level platform dispatch).

The dispatch raises ``NotImplementedError`` for platforms other than
Windows or Linux. We intentionally do NOT exercise that branch by
patching ``sys.platform`` — the real interpreter only ever runs on one
platform at a time, and the unsupported branch cannot reasonably be
hit in production. What this file verifies is that on the *current*
platform, ``focus()`` / ``unfocus()`` are wired to a backend that
gracefully reports ``False`` when VRChat is not running (the autouse
fixture in :mod:`tests.conftest` forces that condition).
"""

from __future__ import annotations

import sys
import warnings

import pytest

import vrcpilot.window


class TestPublicSurface:
    def test_module_exposes_focus_and_unfocus(self):
        # The package re-exports these via ``vrcpilot.__all__``; the
        # window module itself must keep them as the canonical entry
        # points so the dispatch layer cannot be silently removed.
        assert callable(vrcpilot.window.focus)
        assert callable(vrcpilot.window.unfocus)


class TestDispatchOnCurrentPlatform:
    """Smoke-tests the dispatch on whatever platform we are running on.

    The autouse ``_no_real_vrchat`` fixture (see ``tests/conftest.py``)
    pins ``find_pid()`` to ``None`` for the whole suite, so both backends
    must short-circuit to ``False`` before touching any platform API.
    Native-Wayland Linux hosts also emit a :class:`RuntimeWarning` from
    the X11 backend; we silence that here so the assertion below is
    portable across XWayland, native Wayland, and Windows runners.
    """

    def test_focus_returns_false_when_vrchat_not_running(self):
        if sys.platform not in ("win32", "linux"):
            pytest.skip("dispatch only wired for Windows and Linux")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            assert vrcpilot.window.focus() is False

    def test_unfocus_returns_false_when_vrchat_not_running(self):
        if sys.platform not in ("win32", "linux"):
            pytest.skip("dispatch only wired for Windows and Linux")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            assert vrcpilot.window.unfocus() is False
