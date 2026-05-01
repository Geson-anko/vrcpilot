"""Tests for :mod:`vrcpilot.screenshot`.

The autouse fixture in :mod:`tests.conftest` forces
:func:`vrcpilot.find_pid` to ``None``, so :func:`take_screenshot`
short-circuits at the focus step (``focus()`` returns ``False`` when
no PID is observed) and returns ``None`` without ever opening a real
display or invoking ``mss``. That makes the "VRChat not running" path
testable on every host without a live VRChat or compositor.
"""

from __future__ import annotations

import sys

import pytest

from tests.helpers import only_linux, only_windows
from vrcpilot.screenshot import take_screenshot


class TestTakeScreenshotInputValidation:
    """Pure unit-level tests — no platform branching involved."""

    @pytest.mark.parametrize("settle_seconds", [-0.001, -0.05, -1.0, -1e9])
    def test_negative_settle_raises_value_error(self, settle_seconds: float):
        with pytest.raises(ValueError, match="settle_seconds must be >= 0"):
            take_screenshot(settle_seconds=settle_seconds)


class TestTakeScreenshotPlatformBehaviour:
    """Cross-platform happy/short-circuit paths."""

    @only_windows
    def test_returns_none_when_vrchat_not_running_windows(self):
        # Win32 path: ``focus()`` short-circuits on missing PID and
        # ``take_screenshot`` reflects that as ``None``.
        assert take_screenshot() is None

    @only_linux
    def test_returns_none_when_vrchat_not_running_linux(self):
        # X11 path: ``focus()`` returns ``False`` on missing PID
        # before even opening a display, so this works on hosts
        # without an X server.
        assert take_screenshot() is None

    @only_linux
    def test_returns_none_and_warns_on_wayland_native(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Native Wayland (XDG_SESSION_TYPE=wayland and no DISPLAY) is
        # an explicitly unsupported configuration. The contract is to
        # warn AND return ``None`` so polling callers can keep going.
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert take_screenshot() is None


class TestTakeScreenshotPlatformDispatch:
    def test_raises_not_implemented_on_unsupported_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Patching ``sys.platform`` exercises the trailing
        # ``elif sys.platform != "win32"`` branch in the dispatch.
        # Read at call time, so this works on any real host.
        monkeypatch.setattr(sys, "platform", "darwin")

        with pytest.raises(NotImplementedError, match="darwin"):
            take_screenshot()
