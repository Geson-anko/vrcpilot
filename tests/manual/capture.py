"""Manual scenario: stream frames from VRChat via ``vrcpilot.Capture``.

Drives :class:`vrcpilot.Capture` against a real running VRChat client to
confirm the continuous-frame API works end-to-end. The scenario opens a
``with`` block, reads 30 frames as fast as they arrive (~1 second of
30 fps content), saves the first and last frames as PNGs under
``_manual_artifacts/`` for visual inspection, and logs the per-frame
interval distribution so a human can sanity-check the cadence.

Run with::

    just manual capture

VRChat is launched in Desktop mode with a 1280x720 window so the
captured PNGs land at a familiar resolution and so cropping behaviour is
visible in the output (any desktop bleed indicates a regression -- the
WGC / X11 Composite paths capture the window region only).

Captured frames are written as
``_manual_artifacts/capture_first_<YYYYMMDD_HHMMSS>.png`` and
``_manual_artifacts/capture_last_<YYYYMMDD_HHMMSS>.png``.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

import vrcpilot

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402

_ARTIFACTS = Path(__file__).resolve().parents[2] / "_manual_artifacts"

#: Number of frames to capture in a single run. ~30 frames at 30 fps is
#: about 1 s of content -- long enough to see the cadence, short enough
#: that the manual scenario stays brisk.
_FRAME_COUNT: int = 30


def _save_frame(scenario: str, label: str, image: Image.Image) -> Path:
    """Save *image* under ``_manual_artifacts/`` with a timestamped name.

    Returns the destination path so the caller can log it.
    """
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = _ARTIFACTS / f"{scenario}_{label}_{stamp}.png"
    image.save(out)
    return out


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

    _helpers.log(f"opening Capture and reading {_FRAME_COUNT} frames")
    intervals: list[float] = []
    first_frame: Image.Image | None = None
    last_frame: Image.Image | None = None
    last_t: float | None = None

    with vrcpilot.Capture() as cap:
        for i in range(_FRAME_COUNT):
            arr = cap.read()
            now = time.monotonic()
            if last_t is not None:
                intervals.append(now - last_t)
            last_t = now

            # numpy -> PIL: arr is (H, W, 3) uint8 RGB, which is exactly
            # what Image.fromarray expects without a mode argument.
            image = Image.fromarray(arr)
            if i == 0:
                first_frame = image
                _helpers.log(f"first frame size={image.size}")
            last_frame = image

    assert first_frame is not None
    assert last_frame is not None

    out_first = _save_frame("capture", "first", first_frame)
    _helpers.log(f"saved first frame: {out_first}")
    out_last = _save_frame("capture", "last", last_frame)
    _helpers.log(f"saved last frame: {out_last}")

    if intervals:
        # All log output stays in ASCII to dodge the cp932 encode trap on
        # Windows (CLAUDE.md "Windows 日本語環境（cp932）の非 ASCII 出力").
        avg = sum(intervals) / len(intervals)
        _helpers.log(
            "frame intervals (s): "
            f"min={min(intervals):.4f} "
            f"max={max(intervals):.4f} "
            f"avg={avg:.4f} "
            f"count={len(intervals)}"
        )


def main() -> int:
    return _helpers.run_scenario("capture", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
