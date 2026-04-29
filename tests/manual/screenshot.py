"""Manual scenario: capture a VRChat-only screenshot via ``vrcpilot.take_screenshot()``.

Drives ``vrcpilot.take_screenshot()`` against a real running VRChat
client to confirm that the returned PIL image contains **only** the
VRChat window region (not the surrounding desktop, taskbar, or other
applications).

VRChat is launched in Desktop mode with a 1280x720 window so the client
is smaller than the screen. That makes the cropping behaviour observable
on inspection: a correct capture shows VRChat content edge-to-edge in
the saved PNG, with no desktop background bleeding in around the
borders.

Run with::

    just manual screenshot

The captured image is written to
``_manual_artifacts/screenshot_vrchat_<YYYYMMDD_HHMMSS>.png`` for the
human or Claude Code to open and verify.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import vrcpilot

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402

_ARTIFACTS = Path(__file__).resolve().parents[2] / "_manual_artifacts"


def _scenario() -> None:
    _helpers.log(
        "calling vrcpilot.launch(no_vr=True, screen_width=1280, screen_height=720)"
    )
    vrcpilot.launch(no_vr=True, screen_width=1280, screen_height=720)

    _helpers.log("waiting for VRChat PID")
    pid = _helpers.wait_for_pid()
    assert pid is not None, "VRChat PID was not observed before timeout"
    _helpers.log(f"VRChat started (pid={pid})")

    _helpers.warmup()

    _helpers.log("calling vrcpilot.take_screenshot()")
    image = vrcpilot.take_screenshot()
    assert image is not None, "vrcpilot.take_screenshot() returned None"
    _helpers.log(f"captured size={image.size}")

    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = _ARTIFACTS / f"screenshot_vrchat_{stamp}.png"
    image.save(out)
    _helpers.log(f"VRChat screenshot saved: {out}")


def main() -> int:
    return _helpers.run_scenario("screenshot", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
