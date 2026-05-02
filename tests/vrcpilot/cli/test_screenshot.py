"""Tests for :mod:`vrcpilot.cli.screenshot`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image
from pytest_mock import MockerFixture

from vrcpilot.cli import main
from vrcpilot.screenshot import Screenshot


def _make_screenshot(
    *,
    width: int = 8,
    height: int = 4,
    x: int = 10,
    y: int = 20,
    monitor_index: int = 1,
    captured_at: datetime | None = None,
) -> Screenshot:
    """Build a real :class:`Screenshot` with a small ndarray.

    The CLI now reads geometry / timestamp fields in addition to the
    image, so a real dataclass instance is required (the legacy duck-
    typed ``_Shot`` no longer suffices).
    """
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


@pytest.fixture
def patched_take_screenshot(mocker: MockerFixture) -> Screenshot:
    """Patch the screenshot capture boundary with a real dataclass instance.

    Capturing the real desktop is platform-specific and out of scope
    for CLI tests; everything below the ``take_screenshot`` call —
    PIL conversion, PNG encoding, file write, YAML dump — runs end-
    to-end against the canonical :class:`Screenshot`.
    """
    shot = _make_screenshot()
    mocker.patch("vrcpilot.cli.take_screenshot", return_value=shot)
    return shot


class TestScreenshotCommand:
    def test_writes_png_to_output_path(
        self,
        patched_take_screenshot: Screenshot,
        tmp_path: Path,
    ):
        del patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        assert output.is_file()
        with Image.open(output) as img:
            assert img.size == (8, 4)

    def test_stdout_is_yaml_with_expected_keys(
        self,
        patched_take_screenshot: Screenshot,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        del patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        loaded = yaml.safe_load(capsys.readouterr().out)
        assert set(loaded.keys()) == {
            "path",
            "x",
            "y",
            "width",
            "height",
            "monitor_index",
            "captured_at",
        }

    def test_yaml_path_is_absolute(
        self,
        patched_take_screenshot: Screenshot,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        del patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        loaded = yaml.safe_load(capsys.readouterr().out)
        assert Path(loaded["path"]).is_absolute()

    def test_yaml_path_matches_saved_png(
        self,
        patched_take_screenshot: Screenshot,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        del patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        loaded = yaml.safe_load(capsys.readouterr().out)
        assert Path(loaded["path"]) == output.resolve()

    def test_yaml_geometry_matches_dataclass(
        self,
        patched_take_screenshot: Screenshot,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        shot = patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        loaded = yaml.safe_load(capsys.readouterr().out)
        assert loaded["x"] == shot.x
        assert loaded["y"] == shot.y
        assert loaded["width"] == shot.width
        assert loaded["height"] == shot.height
        assert loaded["monitor_index"] == shot.monitor_index

    def test_yaml_captured_at_is_isoformat(
        self,
        patched_take_screenshot: Screenshot,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        shot = patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 0
        loaded = yaml.safe_load(capsys.readouterr().out)
        # Round-trip through ``fromisoformat`` to guarantee the dump is
        # a parseable ISO-8601 string (PyYAML by default would emit a
        # bespoke ``!!timestamp`` tag for naive ``datetime`` values).
        parsed = datetime.fromisoformat(loaded["captured_at"])
        assert parsed == shot.captured_at

    def test_default_output_is_cwd_with_timestamp(
        self,
        patched_take_screenshot: Screenshot,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        del patched_take_screenshot
        monkeypatch.chdir(tmp_path)

        exit_code = main(["screenshot"])

        assert exit_code == 0
        produced = list(tmp_path.glob("vrcpilot_screenshot_*.png"))
        assert len(produced) == 1
        assert produced[0].suffix == ".png"

    def test_short_output_flag(
        self,
        patched_take_screenshot: Screenshot,
        tmp_path: Path,
    ):
        del patched_take_screenshot
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "-o", str(output)])

        assert exit_code == 0
        assert output.is_file()

    def test_reports_failure(
        self,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        mocker.patch("vrcpilot.cli.take_screenshot", return_value=None)
        output = tmp_path / "shot.png"

        exit_code = main(["screenshot", "--output", str(output)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "vrcpilot: could not capture VRChat screenshot" in captured.err
        assert not output.exists()
