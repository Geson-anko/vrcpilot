"""Tests for :mod:`vrcpilot.window` (top-level platform dispatch)."""

from __future__ import annotations

import pytest

import vrcpilot.window


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
