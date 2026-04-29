"""Tests for :mod:`vrcpilot._win32`."""

from __future__ import annotations

import sys

import pytest
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
        from vrcpilot._win32 import get_window_rect

        mocker.patch(
            "vrcpilot._win32.win32gui.GetWindowRect",
            return_value=(100, 200, 900, 800),
        )

        assert get_window_rect(12345) == (100, 200, 800, 600)

    def test_supports_negative_origin(self, mocker: MockerFixture, mock_set_thread_dpi):
        # Multi-monitor setups can place the primary window's origin at
        # negative coordinates when the user dragged VRChat onto a
        # left-of-primary monitor. The helper must preserve the sign.
        from vrcpilot._win32 import get_window_rect

        mocker.patch(
            "vrcpilot._win32.win32gui.GetWindowRect",
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

        from vrcpilot._win32 import get_window_rect

        mocker.patch(
            "vrcpilot._win32.win32gui.GetWindowRect",
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
        from vrcpilot._win32 import get_window_rect

        mocker.patch("vrcpilot._win32.win32gui.GetWindowRect", return_value=rect)

        assert get_window_rect(12345) is None

    def test_calls_get_window_rect_in_dpi_aware_context(
        self, mocker: MockerFixture, mock_set_thread_dpi
    ):
        # The helper must (1) switch the current thread to per-monitor DPI
        # aware V2, (2) call GetWindowRect inside that context, and
        # (3) restore the previous context when done. We assert the
        # ordering of those three calls so the contract is locked in.
        from vrcpilot._win32 import (
            _DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
            get_window_rect,
        )

        get_rect = mocker.patch(
            "vrcpilot._win32.win32gui.GetWindowRect",
            return_value=(0, 0, 800, 600),
        )
        # ``mock_set_thread_dpi`` returns 0x1234ABCD as the sentinel
        # ``old_ctx`` from the first call; the second call should pass
        # that same sentinel back in to restore the original context.
        sentinel_old_ctx = mock_set_thread_dpi.return_value

        manager = mocker.MagicMock()
        manager.attach_mock(mock_set_thread_dpi, "set_dpi")
        manager.attach_mock(get_rect, "get_rect")

        result = get_window_rect(12345)

        assert result == (0, 0, 800, 600)
        # First call: switch to per-monitor aware V2.
        # Middle call: GetWindowRect on the target hwnd.
        # Last call: restore to the previously-returned context.
        assert manager.mock_calls == [
            mocker.call.set_dpi(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2),
            mocker.call.get_rect(12345),
            mocker.call.set_dpi(sentinel_old_ctx),
        ]

    def test_restores_context_even_when_rect_query_fails(
        self, mocker: MockerFixture, mock_set_thread_dpi
    ):
        # If GetWindowRect raises (HWND destroyed mid-call), the previous
        # DPI context must still be restored via the ``finally`` block.
        # Otherwise the test runner thread (or the user's worker thread)
        # would leak per-monitor V2 awareness.
        import pywintypes

        from vrcpilot._win32 import get_window_rect

        mocker.patch(
            "vrcpilot._win32.win32gui.GetWindowRect",
            side_effect=pywintypes.error(
                1400, "GetWindowRect", "Invalid window handle."
            ),
        )

        assert get_window_rect(99999) is None

        sentinel_old_ctx = mock_set_thread_dpi.return_value
        # Two calls total: enable per-monitor V2, then restore old_ctx.
        assert mock_set_thread_dpi.call_count == 2
        restore_call = mock_set_thread_dpi.call_args_list[-1]
        assert restore_call.args == (sentinel_old_ctx,)
