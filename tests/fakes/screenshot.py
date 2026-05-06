"""Screenshot-related test doubles.

Builds the on-disk PNG plus matching CLI-format YAML text used by the
``vrcpilot ocr`` / ``vrcpilot detect`` screenshot-input tests, so each
test does not have to hand-roll the same dump.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image
from pytest_mock import MockerFixture


def write_screenshot_payload(
    tmp_path: Path,
    *,
    width: int = 64,
    height: int = 48,
    x: int = 100,
    y: int = 50,
    monitor_index: int = 1,
    captured_at: datetime | None = None,
) -> tuple[Path, str]:
    """Write a real PNG under ``tmp_path`` and return a YAML text pair.

    The PNG goes to ``tmp_path / "screenshot.png"`` (zeros, RGB
    ``uint8``); the YAML text matches the ``vrcpilot screenshot`` CLI
    contract verbatim — keys in the order ``path``, ``x``, ``y``,
    ``width``, ``height``, ``monitor_index``, ``captured_at`` so tests
    can assert ordering. The returned ``yaml_path`` is
    ``tmp_path / "screenshot.yaml"`` and is deliberately *not* written
    so tests can choose to write the text or feed it raw.
    """
    if captured_at is None:
        captured_at = datetime.now(timezone.utc)
    png_path = tmp_path / "screenshot.png"
    Image.fromarray(np.zeros((height, width, 3), dtype=np.uint8)).save(png_path)
    payload: dict[str, object] = {
        "path": str(png_path.resolve()),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "monitor_index": monitor_index,
        "captured_at": captured_at.isoformat(),
    }
    yaml_text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
    yaml_path = tmp_path / "screenshot.yaml"
    return yaml_path, yaml_text


def patch_stdin_with_screenshot(
    mocker: MockerFixture,
    tmp_path: Path,
    **kwargs: Any,
) -> str:
    """Write a PNG under ``tmp_path`` and stream its YAML via ``sys.stdin``.

    Thin convenience wrapper around :func:`write_screenshot_payload`:
    builds the screenshot YAML for ``tmp_path`` and patches
    ``vrcpilot.cli._common.sys.stdin`` with an :class:`io.StringIO`
    carrying the YAML text, so subsequent
    :func:`vrcpilot.cli._common.resolve_screenshot` calls hit the
    piped-stdin branch. ``StringIO.isatty()`` returns ``False`` natively,
    which is exactly the piped-stdin signal ``resolve_screenshot`` looks
    for, so no extra ``isatty`` patch is required.

    Args:
        mocker: ``pytest-mock`` fixture used to apply the patch.
        tmp_path: Directory that receives the backing PNG.
        **kwargs: Forwarded verbatim to :func:`write_screenshot_payload`
            (``width``, ``height``, ``x``, ``y``, ``monitor_index``,
            ``captured_at``).

    Returns:
        The flowed YAML text — useful when a test wants to assert on
        what the CLI will read.
    """
    _, yaml_text = write_screenshot_payload(tmp_path, **kwargs)
    mocker.patch("vrcpilot.cli._common.sys.stdin", new=io.StringIO(yaml_text))
    return yaml_text
