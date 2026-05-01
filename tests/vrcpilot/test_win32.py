"""Tests for :mod:`vrcpilot.win32`."""

from __future__ import annotations

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("Only windows.", allow_module_level=True)

from pytest_mock import MockerFixture

from tests.helpers import only_windows


@only_windows
class TestGetWindowRect:
    @pytest.fixture
    def mock_set_thread_dpi(self, mocker: MockerFixture):
        """Patch ``SetThreadDpiAwarenessContext`` to a recordable mock.

        Returns a sentinel handle from the first call (the ``old_ctx``)
        and is reused for the restore call. Without this, every test
        would invoke the real Win32 API and mutate the test runner
        thread's DPI awareness as a side effect.
        """
        if sys.platform != "win32":
            pytest.skip("Windows-only fixture")
        import ctypes

        sentinel_old_ctx = 0x1234ABCD
        mock = mocker.patch.object(
            ctypes.windll.user32,
            "SetThreadDpiAwarenessContext",
            return_value=sentinel_old_ctx,
        )
        return mock

    def test_returns_origin_and_size_on_success(
        self, mocker: MockerFixture, mock_set_thread_dpi
    ):
        # ``GetWindowRect`` returns ``(left, top, right, bottom)`` and the
        # helper's contract is to convert to origin + size form.
        from vrcpilot.win32 import get_window_rect

        mocker.patch(
            "vrcpilot.win32.win32gui.GetWindowRect",
            return_value=(100, 200, 900, 800),
        )

        assert get_window_rect(12345) == (100, 200, 800, 600)

    def test_supports_negative_origin(self, mocker: MockerFixture, mock_set_thread_dpi):
        # Multi-monitor setups can place the primary window's origin at
        # negative coordinates when the user dragged VRChat onto a
        # left-of-primary monitor. The helper must preserve the sign.
        from vrcpilot.win32 import get_window_rect

        mocker.patch(
            "vrcpilot.win32.win32gui.GetWindowRect",
            return_value=(-1920, 0, -1120, 600),
        )

        assert get_window_rect(12345) == (-1920, 0, 800, 600)

    def test_returns_none_when_hwnd_destroyed(
        self, mocker: MockerFixture, mock_set_thread_dpi
    ):
        # ``pywintypes.error`` is what ``win32gui`` raises when the HWND
        # has gone away between lookup and the rect query; the helper
        # surfaces this as ``None`` so callers can degrade gracefully.
        import pywintypes

        from vrcpilot.win32 import get_window_rect

        mocker.patch(
            "vrcpilot.win32.win32gui.GetWindowRect",
            side_effect=pywintypes.error(
                1400, "GetWindowRect", "Invalid window handle."
            ),
        )

        assert get_window_rect(99999) is None

    @pytest.mark.parametrize(
        ("rect"),
        [
            (100, 200, 100, 800),  # zero width
            (100, 200, 900, 200),  # zero height
            (100, 200, 50, 800),  # negative width (right < left)
            (100, 200, 900, 100),  # negative height (bottom < top)
        ],
    )
    def test_returns_none_on_degenerate_rect(
        self,
        mocker: MockerFixture,
        rect: tuple[int, int, int, int],
        mock_set_thread_dpi,
    ):
        from vrcpilot.win32 import get_window_rect

        mocker.patch("vrcpilot.win32.win32gui.GetWindowRect", return_value=rect)

        assert get_window_rect(12345) is None

    def test_returns_none_when_rect_query_raises(
        self, mocker: MockerFixture, mock_set_thread_dpi
    ):
        # If GetWindowRect raises (HWND destroyed mid-call) the helper
        # must surface ``None`` rather than propagating the error. The
        # internal ``finally``-based DPI context restoration is an
        # implementation detail and intentionally not asserted here.
        import pywintypes

        from vrcpilot.win32 import get_window_rect

        mocker.patch(
            "vrcpilot.win32.win32gui.GetWindowRect",
            side_effect=pywintypes.error(
                1400, "GetWindowRect", "Invalid window handle."
            ),
        )

        assert get_window_rect(99999) is None
