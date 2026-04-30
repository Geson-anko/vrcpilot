"""Tests for :mod:`vrcpilot.screenshot`."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import mss
import numpy as np
import pytest
from pytest_mock import MockerFixture

from vrcpilot.screenshot import Screenshot, _resolve_monitor_index, take_screenshot

# Three-monitor layout used by most tests:
#   index 0 = composite of all monitors
#   index 1 = left  monitor at (0,    0) 1920x1080
#   index 2 = right monitor at (1920, 0) 1920x1080
_LEFT_RIGHT_MONITORS: list[dict[str, int]] = [
    {"left": 0, "top": 0, "width": 3840, "height": 1080},
    {"left": 0, "top": 0, "width": 1920, "height": 1080},
    {"left": 1920, "top": 0, "width": 1920, "height": 1080},
]


def _build_fake_sct(
    mocker: MockerFixture,
    *,
    width: int,
    height: int,
    monitors: list[dict[str, int]] | None = None,
    grab_side_effect: BaseException | None = None,
) -> Any:
    """Construct an mss-style fake suitable for ``mocker.patch`` injection.

    The fake behaves like an ``mss.MSS`` instance: it has a ``grab``
    method, a ``monitors`` attribute, and a ``close`` method (since the
    production code uses explicit ``close()`` rather than the context
    manager — see the comment in ``screenshot.py``).
    """
    fake_shot = mocker.Mock()
    fake_shot.rgb = bytes(width * height * 3)
    fake_shot.size = mocker.Mock(width=width, height=height)

    fake_sct = mocker.Mock()
    if grab_side_effect is not None:
        fake_sct.grab.side_effect = grab_side_effect
    else:
        fake_sct.grab.return_value = fake_shot
    fake_sct.monitors = monitors if monitors is not None else _LEFT_RIGHT_MONITORS
    return fake_sct


def _patch_happy_path(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    platform: str = "win32",
    rect: tuple[int, int, int, int] = (100, 200, 800, 600),
    monitors: list[dict[str, int]] | None = None,
) -> Any:
    """Wire up the collaborators ``take_screenshot`` calls.

    The focus step is patched at the platform-specific *backend*
    boundary (``vrcpilot.window.win32.focus_window`` or
    ``vrcpilot.window.x11.focus_window``) so the in-process
    ``vrcpilot.window.focus`` dispatcher runs for real — only the
    external Win32 / Xlib bindings are stubbed.

    Returns the fake ``mss.MSS`` instance so tests can inspect its
    ``grab`` invocations or override its ``side_effect``.
    """
    # Eagerly import the relevant backend BEFORE monkeypatching
    # ``sys.platform`` so the ``Xlib``-gated imports inside the linux
    # backend run under the host's real platform (i.e. they no-op on
    # Windows where ``Xlib`` is unavailable). Also lets ``mocker.patch``
    # resolve the dotted path on hosts that have not naturally imported
    # the module.
    if platform == "win32":
        import vrcpilot.window.win32  # noqa: F401
    elif platform == "linux":
        import vrcpilot.window.x11  # noqa: F401

    monkeypatch.setattr("vrcpilot.screenshot.sys.platform", platform)
    monkeypatch.setattr("vrcpilot.window.sys.platform", platform)
    if platform == "win32":
        mocker.patch("vrcpilot.window.win32.focus_window", return_value=True)
    elif platform == "linux":
        mocker.patch("vrcpilot.screenshot.is_wayland_native", return_value=False)
        mocker.patch("vrcpilot.window.x11.focus_window", return_value=True)
    mocker.patch("vrcpilot.screenshot.time.sleep")
    mocker.patch("vrcpilot.screenshot.get_vrchat_window_rect", return_value=rect)

    fake_sct = _build_fake_sct(mocker, width=rect[2], height=rect[3], monitors=monitors)
    mocker.patch("vrcpilot.screenshot.mss.MSS", return_value=fake_sct)
    return fake_sct


class TestSettleSecondsValidation:
    @pytest.mark.parametrize("bad_value", [-0.001, -0.05, -1.0, -100.0])
    def test_negative_settle_seconds_raises(self, bad_value: float):
        with pytest.raises(ValueError, match="settle_seconds must be >= 0"):
            take_screenshot(settle_seconds=bad_value)

    def test_zero_settle_seconds_is_allowed(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        _patch_happy_path(mocker, monkeypatch)

        result = take_screenshot(settle_seconds=0)

        assert result is not None


class TestPlatformGuard:
    def test_unsupported_platform_raises(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # Need to also patch focus / sleep so the test does not reach
        # the real ``vrcpilot.window.focus`` on the host before the
        # platform check fires.
        monkeypatch.setattr("vrcpilot.screenshot.sys.platform", "darwin")

        with pytest.raises(NotImplementedError, match="darwin"):
            take_screenshot()

    def test_wayland_native_warns_and_returns_none(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.screenshot.sys.platform", "linux")
        mocker.patch("vrcpilot.screenshot.is_wayland_native", return_value=True)

        with pytest.warns(RuntimeWarning, match="Wayland native"):
            assert take_screenshot() is None


class TestTakeScreenshot:
    def test_returns_screenshot_with_metadata_on_success(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # Force the win32 rectangle path so the test runs identically on
        # any host. The Linux path is symmetrical, just patched a bit
        # differently - see ``test_uses_x11_rect_helper_on_linux``.
        _patch_happy_path(mocker, monkeypatch, rect=(100, 200, 800, 600))

        result = take_screenshot()

        assert result is not None
        assert result.image.shape == (600, 800, 3)
        assert result.image.dtype == np.uint8
        assert (result.x, result.y, result.width, result.height) == (
            100,
            200,
            800,
            600,
        )
        assert result.captured_at.tzinfo is timezone.utc
        # Center is at (500, 500), inside the left monitor (1920x1080).
        assert result.monitor_index == 1

    def test_uses_x11_rect_helper_on_linux(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        _patch_happy_path(
            mocker, monkeypatch, platform="linux", rect=(50, 60, 800, 600)
        )

        result = take_screenshot()

        assert result is not None
        assert (result.x, result.y) == (50, 60)

    def test_returns_none_when_focus_fails(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # Patch at the backend boundary so ``vrcpilot.window.focus`` runs
        # for real - this is the integration we care about.
        monkeypatch.setattr("vrcpilot.screenshot.sys.platform", "win32")
        monkeypatch.setattr("vrcpilot.window.sys.platform", "win32")
        mocker.patch("vrcpilot.window.win32.focus_window", return_value=False)

        assert take_screenshot() is None

    def test_returns_none_when_rect_helper_returns_none(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("vrcpilot.screenshot.sys.platform", "win32")
        monkeypatch.setattr("vrcpilot.window.sys.platform", "win32")
        mocker.patch("vrcpilot.window.win32.focus_window", return_value=True)
        mocker.patch("vrcpilot.screenshot.time.sleep")
        mocker.patch("vrcpilot.screenshot.get_vrchat_window_rect", return_value=None)

        assert take_screenshot() is None

    def test_returns_none_on_mss_screenshot_error(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        _patch_happy_path(mocker, monkeypatch)
        # Override grab to raise the recoverable mss failure.
        fake_sct = _build_fake_sct(
            mocker,
            width=800,
            height=600,
            grab_side_effect=mss.ScreenShotError("simulated"),
        )
        mocker.patch("vrcpilot.screenshot.mss.MSS", return_value=fake_sct)

        assert take_screenshot() is None


class TestMonitorIndexResolution:
    @pytest.mark.parametrize(
        ("rect", "expected_index"),
        [
            # Center at (500, 500) -> left monitor.
            ((100, 200, 800, 600), 1),
            # Center at (2880, 540) -> right monitor.
            ((2400, 100, 960, 880), 2),
            # Window straddling both monitors but center on the left.
            ((1500, 0, 800, 100), 1),
            # Window straddling both monitors but center on the right.
            ((1700, 0, 800, 100), 2),
        ],
    )
    def test_returns_monitor_containing_center(
        self,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
        rect: tuple[int, int, int, int],
        expected_index: int,
    ):
        _patch_happy_path(mocker, monkeypatch, rect=rect)

        result = take_screenshot()

        assert result is not None
        assert result.monitor_index == expected_index

    def test_offscreen_window_falls_back_to_zero(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ):
        # Center far outside any individual monitor -> composite (0).
        _patch_happy_path(mocker, monkeypatch, rect=(10_000, 10_000, 100, 100))

        result = take_screenshot()

        assert result is not None
        assert result.monitor_index == 0

    def test_resolve_helper_uses_center_point(self):
        # Direct unit test of the helper — keeps the full pipeline tests
        # readable while still pinning the boundary semantics.
        monitors: list[dict[str, int]] = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
        ]
        # Edge case: the right edge ``cx == right`` is *not* inside the
        # monitor (half-open interval), so this rect's center at exactly
        # the right edge falls back to 0.
        assert _resolve_monitor_index((1920 - 2, 0, 4, 4), monitors) == 0
        # Centered well inside.
        assert _resolve_monitor_index((100, 100, 200, 200), monitors) == 1


class TestScreenshotDataclass:
    def test_is_frozen(self):
        shot = Screenshot(
            image=np.zeros((10, 10, 3), dtype=np.uint8),
            x=0,
            y=0,
            width=10,
            height=10,
            monitor_index=1,
            captured_at=datetime.now(timezone.utc),
        )

        with pytest.raises(FrozenInstanceError):
            shot.x = 999  # type: ignore[misc]

    def test_image_field_is_writable_copy(self):
        # The frozen container is immutable, but the underlying ndarray
        # is *not* shared with mss internals (we ``.copy()`` before
        # building the dataclass), so callers can safely mutate it.
        arr = np.zeros((4, 4, 3), dtype=np.uint8)
        shot = Screenshot(
            image=arr,
            x=0,
            y=0,
            width=4,
            height=4,
            monitor_index=1,
            captured_at=datetime.now(timezone.utc),
        )

        shot.image[0, 0, 0] = 255
        assert shot.image[0, 0, 0] == 255
