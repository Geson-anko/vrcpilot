"""Tests for :mod:`vrcpilot.x11`."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from tests.helpers import only_linux


@only_linux
class TestOpenX11Display:
    def test_returns_display_on_success(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        from vrcpilot.x11 import open_x11_display

        monkeypatch.setenv("DISPLAY", ":0")
        fake_display = mocker.Mock()
        mocker.patch("vrcpilot.x11.Xlib.display.Display", return_value=fake_display)

        assert open_x11_display() is fake_display

    def test_returns_none_on_oserror(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # Connection failures (X server unreachable, missing
        # XAUTHORITY, etc.) raise into the open call; the helper
        # converts them to ``None`` so long-lived callers can fall back
        # rather than crash.
        from vrcpilot.x11 import open_x11_display

        monkeypatch.setenv("DISPLAY", ":99")
        mocker.patch(
            "vrcpilot.x11.Xlib.display.Display", side_effect=OSError("unreachable")
        )

        assert open_x11_display() is None

    def test_returns_none_on_display_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # ``DisplayError`` covers malformed DISPLAY values (parser
        # failures); should also degrade to ``None``.
        import vrcpilot.x11 as x11_mod
        from vrcpilot.x11 import open_x11_display

        monkeypatch.setenv("DISPLAY", "garbage")
        mocker.patch(
            "vrcpilot.x11.Xlib.display.Display",
            side_effect=x11_mod.Xlib.error.DisplayError("garbage"),
        )

        assert open_x11_display() is None


@only_linux
class TestGetWindowRect:
    def test_returns_origin_and_size_on_success(self, mocker: MockerFixture):
        # ``translate_coords`` reports the inverse of the window's
        # screen-space origin under python-xlib (see commit 77a6422),
        # so the helper sign-flips ``coords.x`` / ``coords.y`` to give
        # callers an origin in the conventional sense.
        from vrcpilot.x11 import get_window_rect

        fake_display = mocker.Mock()
        fake_window = mocker.Mock()
        fake_window.translate_coords.return_value = mocker.Mock(x=-100, y=-200)
        fake_window.get_geometry.return_value = mocker.Mock(width=800, height=600)

        assert get_window_rect(fake_display, fake_window) == (100, 200, 800, 600)

    def test_returns_none_on_xerror(self, mocker: MockerFixture):
        # Defining a tiny ``XError`` subclass with a no-arg ``__init__``
        # bypasses the real protocol-payload requirement; only the type
        # hierarchy matters for the except clause.
        import vrcpilot.x11 as x11_mod
        from vrcpilot.x11 import get_window_rect

        class _FakeXError(x11_mod.Xlib.error.XError):
            def __init__(self) -> None:  # noqa: D401
                # Skip parent ``__init__`` which expects a parsed reply.
                pass

        fake_display = mocker.Mock()
        fake_window = mocker.Mock()
        fake_window.translate_coords.side_effect = _FakeXError()

        assert get_window_rect(fake_display, fake_window) is None

    @pytest.mark.parametrize(
        ("width", "height"),
        [(0, 50), (100, 0), (-1, 50), (100, -1), (0, 0)],
    )
    def test_returns_none_on_degenerate_geometry(
        self, mocker: MockerFixture, width: int, height: int
    ):
        from vrcpilot.x11 import get_window_rect

        fake_display = mocker.Mock()
        fake_window = mocker.Mock()
        fake_window.translate_coords.return_value = mocker.Mock(x=0, y=0)
        fake_window.get_geometry.return_value = mocker.Mock(width=width, height=height)

        assert get_window_rect(fake_display, fake_window) is None
