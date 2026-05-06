"""Tests for :mod:`vrcpilot.screenshot`.

The autouse fixture in :mod:`tests.conftest` forces
:func:`vrcpilot.find_pid` to ``None``, so :func:`take_screenshot`
short-circuits at the focus step (``focus()`` returns ``False`` when
no PID is observed) and returns ``None`` without ever opening a real
display or invoking ``mss``. That makes the "VRChat not running" path
testable on every host without a live VRChat or compositor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from tests.fakes import write_screenshot_payload
from tests.helpers import only_linux, only_windows
from vrcpilot.screenshot import Screenshot, take_screenshot


def _make_screenshot(
    *,
    width: int = 8,
    height: int = 4,
    x: int = 10,
    y: int = 20,
    monitor_index: int = 1,
    captured_at: datetime | None = None,
) -> Screenshot:
    """Build a real :class:`Screenshot` with a deterministic ndarray."""
    if captured_at is None:
        captured_at = datetime(2026, 5, 3, 12, 34, 56, 789012, tzinfo=timezone.utc)
    return Screenshot(
        image=np.zeros((height, width, 3), dtype=np.uint8),
        x=x,
        y=y,
        width=width,
        height=height,
        monitor_index=monitor_index,
        captured_at=captured_at,
    )


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


class TestScreenshotSave:
    """``Screenshot.save`` writes the PNG and emits the CLI YAML schema."""

    def test_save_writes_png_and_returns_yaml(self, tmp_path: Path):
        shot = _make_screenshot()
        png_path = tmp_path / "shot.png"

        text = shot.save(png_path)

        assert png_path.is_file()
        loaded = yaml.safe_load(text)
        assert loaded == {
            "path": str(png_path.resolve()),
            "x": shot.x,
            "y": shot.y,
            "width": shot.width,
            "height": shot.height,
            "monitor_index": shot.monitor_index,
            "captured_at": shot.captured_at.isoformat(),
        }

    def test_save_yaml_keys_in_stable_order(self, tmp_path: Path):
        shot = _make_screenshot()
        png_path = tmp_path / "shot.png"

        text = shot.save(png_path)

        # Python 3.7+ preserves dict insertion order, and
        # ``yaml.safe_dump(sort_keys=False)`` emits keys in that order,
        # so ``yaml.safe_load(...).keys()`` round-trips the on-disk
        # ordering. This is more explicit than splitting lines on ``:``.
        loaded = yaml.safe_load(text)
        assert list(loaded.keys()) == [
            "path",
            "x",
            "y",
            "width",
            "height",
            "monitor_index",
            "captured_at",
        ]

    def test_save_path_is_absolute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Operate from inside ``tmp_path`` so a relative path written by
        # the caller resolves to a known absolute location we can
        # compare against.
        monkeypatch.chdir(tmp_path)
        shot = _make_screenshot()
        relative = Path("shot.png")

        text = shot.save(relative)

        loaded = yaml.safe_load(text)
        path_value = loaded["path"]
        assert Path(path_value).is_absolute()
        assert Path(path_value) == (tmp_path / "shot.png").resolve()

    def test_save_round_trips_through_load(self, tmp_path: Path):
        shot = _make_screenshot()
        png_path = tmp_path / "shot.png"

        text = shot.save(png_path)
        restored = Screenshot.load(text)

        assert restored.x == shot.x
        assert restored.y == shot.y
        assert restored.width == shot.width
        assert restored.height == shot.height
        assert restored.monitor_index == shot.monitor_index
        assert restored.captured_at == shot.captured_at
        assert restored.image.shape == shot.image.shape
        assert restored.image.dtype == shot.image.dtype


class TestScreenshotLoad:
    """``Screenshot.load`` validates and restores from CLI YAML text."""

    def test_load_returns_screenshot_with_image(self, tmp_path: Path):
        _, yaml_text = write_screenshot_payload(
            tmp_path,
            width=32,
            height=16,
            x=5,
            y=7,
            monitor_index=2,
        )

        shot = Screenshot.load(yaml_text)

        assert shot.x == 5
        assert shot.y == 7
        assert shot.width == 32
        assert shot.height == 16
        assert shot.monitor_index == 2
        assert shot.image.shape == (16, 32, 3)
        assert shot.image.dtype == np.uint8

    def test_load_rejects_non_mapping(self):
        text = yaml.safe_dump([1, 2, 3])

        with pytest.raises(ValueError, match="mapping"):
            Screenshot.load(text)

    @pytest.mark.parametrize(
        "missing_key",
        [
            "path",
            "x",
            "y",
            "width",
            "height",
            "monitor_index",
            "captured_at",
        ],
    )
    def test_load_rejects_missing_required_key(self, tmp_path: Path, missing_key: str):
        _, yaml_text = write_screenshot_payload(tmp_path)
        payload = yaml.safe_load(yaml_text)
        del payload[missing_key]
        broken = yaml.safe_dump(payload, sort_keys=False)

        with pytest.raises(ValueError, match="invalid screenshot YAML"):
            Screenshot.load(broken)

    def test_load_rejects_invalid_field_type(self, tmp_path: Path):
        _, yaml_text = write_screenshot_payload(tmp_path)
        payload = yaml.safe_load(yaml_text)
        payload["x"] = "abc"
        broken = yaml.safe_dump(payload, sort_keys=False)

        with pytest.raises(ValueError, match="invalid screenshot YAML"):
            Screenshot.load(broken)

    def test_load_rejects_missing_png(self, tmp_path: Path):
        _, yaml_text = write_screenshot_payload(tmp_path)
        payload = yaml.safe_load(yaml_text)
        payload["path"] = str(tmp_path / "does_not_exist.png")
        broken = yaml.safe_dump(payload, sort_keys=False)

        with pytest.raises(ValueError, match="PNG referenced by"):
            Screenshot.load(broken)

    def test_load_rejects_non_image_file(self, tmp_path: Path):
        _, yaml_text = write_screenshot_payload(tmp_path)
        payload = yaml.safe_load(yaml_text)
        bogus = tmp_path / "not_an_image.png"
        bogus.write_bytes(b"this is not a PNG, just plain text")
        payload["path"] = str(bogus)
        broken = yaml.safe_dump(payload, sort_keys=False)

        with pytest.raises(ValueError, match="not a valid image"):
            Screenshot.load(broken)

    def test_load_rejects_invalid_captured_at(self, tmp_path: Path):
        _, yaml_text = write_screenshot_payload(tmp_path)
        payload = yaml.safe_load(yaml_text)
        payload["captured_at"] = "not-a-timestamp"
        broken = yaml.safe_dump(payload, sort_keys=False)

        with pytest.raises(ValueError, match="invalid screenshot YAML"):
            Screenshot.load(broken)
