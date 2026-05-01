"""Tests for :mod:`vrcpilot.session`."""

from __future__ import annotations

import pytest

from vrcpilot.session import is_wayland_native


class TestIsWaylandNative:
    @pytest.mark.parametrize(
        ("xdg_session_type", "display", "expected"),
        [
            # Pure Wayland session: no DISPLAY exported, X11 is unreachable.
            ("wayland", None, True),
            # Wayland with XWayland: DISPLAY is set, X11 ops still work.
            ("wayland", ":0", False),
            # Plain X11 session.
            ("x11", None, False),
            ("x11", ":0", False),
            # XDG_SESSION_TYPE not set at all.
            (None, None, False),
            (None, ":0", False),
            # Other / unknown session types should not be treated as native Wayland.
            ("tty", None, False),
            ("mir", ":0", False),
        ],
    )
    def test_env_combinations(
        self,
        monkeypatch: pytest.MonkeyPatch,
        xdg_session_type: str | None,
        display: str | None,
        expected: bool,
    ):
        if xdg_session_type is None:
            monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        else:
            monkeypatch.setenv("XDG_SESSION_TYPE", xdg_session_type)
        if display is None:
            monkeypatch.delenv("DISPLAY", raising=False)
        else:
            monkeypatch.setenv("DISPLAY", display)

        assert is_wayland_native() is expected

    def test_empty_display_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch):
        # ``DISPLAY=""`` is falsy and should not block native-Wayland detection,
        # mirroring how X11 clients themselves treat an empty DISPLAY.
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        monkeypatch.setenv("DISPLAY", "")

        assert is_wayland_native() is True
