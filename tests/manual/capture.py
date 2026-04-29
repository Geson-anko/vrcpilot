"""Manual scenario: stream frames from VRChat and save them as an mp4.

Drives :class:`vrcpilot.Capture` against a real running VRChat client to
confirm the continuous-frame API works end-to-end. The scenario opens a
``with`` block, reads frames as fast as they arrive for ~10 seconds of
wall-clock time, encodes them into a single mp4 video for human review,
and logs the per-frame interval distribution so a human can sanity-check
the cadence.

The mp4 is muxed with ``mp4v`` fourcc at a nominal 30 fps. The actual
frame cadence (which depends on capture backend latency) is not used to
adjust the playback rate; it is reported only via the min / max / avg
interval log line. Reviewers comparing playback duration against the
logged frame count can use that as a regression signal: if the writer
stored, say, 240 frames over a 10 s capture, the mp4 will play back at
approximately 8 s instead of 10 s when opened with a player that honors
the embedded fps.

Run with::

    just manual capture

VRChat is launched in Desktop mode with a 1280x720 window so the
captured frames land at a familiar resolution and so cropping behaviour
is visible in the output (any desktop bleed indicates a regression --
the WGC / X11 Composite paths capture the window region only).

The captured video is written to
``_manual_artifacts/capture_<YYYYMMDD_HHMMSS>.mp4``.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

import vrcpilot

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402

#: Wall-clock duration of the recording. ~10 s is long enough to see the
#: cadence and any glitches, short enough that the manual scenario stays
#: brisk.
_DURATION_SECONDS: float = 10.0

#: Nominal playback fps written into the mp4 container. The Capture
#: backend targets ~30 fps but does not guarantee it; the actual cadence
#: is reported separately via the interval log line.
_NOMINAL_FPS: float = 30.0


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

    _helpers.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _helpers.ARTIFACT_DIR / f"capture_{stamp}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]

    _helpers.log(
        f"opening Capture and recording for {_DURATION_SECONDS:.1f}s to {out_path}"
    )

    intervals: list[float] = []
    frame_count: int = 0
    last_t: float | None = None
    writer: cv2.VideoWriter | None = None

    try:
        with vrcpilot.Capture() as cap:
            start = time.monotonic()
            while True:
                arr = cap.read()
                now = time.monotonic()
                if last_t is not None:
                    intervals.append(now - last_t)
                last_t = now

                if writer is None:
                    h, w = arr.shape[:2]
                    _helpers.log(
                        f"first frame size=(w={w}, h={h}); "
                        f"opening VideoWriter at {_NOMINAL_FPS:.1f} fps"
                    )
                    writer = cv2.VideoWriter(
                        str(out_path),
                        fourcc,
                        _NOMINAL_FPS,
                        (w, h),
                    )
                    if not writer.isOpened():
                        raise RuntimeError(
                            f"cv2.VideoWriter failed to open: {out_path} "
                            f"(fourcc=mp4v, fps={_NOMINAL_FPS}, size=({w}, {h}))"
                        )

                # arr is (H, W, 3) uint8 in RGB; OpenCV expects BGR.
                bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                writer.write(bgr)
                frame_count += 1

                if now - start >= _DURATION_SECONDS:
                    break
    finally:
        if writer is not None:
            writer.release()

    _helpers.log(f"saved video: {out_path} (frames={frame_count})")

    if intervals:
        # All log output stays in ASCII to dodge the cp932 encode trap on
        # Windows (CLAUDE.md "Windows 日本語環境（cp932）の非 ASCII 出力").
        avg = sum(intervals) / len(intervals)
        measured_fps = 1.0 / avg if avg > 0 else float("inf")
        _helpers.log(
            "frame intervals (s): "
            f"min={min(intervals):.4f} "
            f"max={max(intervals):.4f} "
            f"avg={avg:.4f} "
            f"count={len(intervals)} "
            f"measured_fps={measured_fps:.2f} "
            f"nominal_fps={_NOMINAL_FPS:.2f}"
        )


def main() -> int:
    return _helpers.run_scenario("capture", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
