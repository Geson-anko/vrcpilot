"""Manual scenario: launch VRChat with the ``--no-vr`` flag.

Verifies that :func:`vrcpilot.launch` succeeds with ``no_vr=True`` on a
machine that may not have an HMD attached, that a PID becomes visible,
remains stable after a warm-up window, and that termination reports
success.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import vrcpilot

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402

_NO_VR_WARMUP_SECONDS: float = 20.0


def _scenario() -> None:
    _helpers.log("launching VRChat with no_vr=True")
    vrcpilot.launch(no_vr=True)

    _helpers.log("waiting for VRChat PID")
    pid = _helpers.wait_for_pid()
    _helpers.expect(pid is not None, "VRChat PID did not appear within timeout")
    _helpers.log(f"VRChat PID detected: {pid}")

    _helpers.log(f"warming up for {_NO_VR_WARMUP_SECONDS:.0f}s")
    time.sleep(_NO_VR_WARMUP_SECONDS)

    pid_after = vrcpilot.find_pid()
    _helpers.expect(
        pid_after == pid,
        f"VRChat PID changed after warmup (before={pid}, after={pid_after})",
    )
    _helpers.log(f"VRChat PID stable after warmup: {pid_after}")

    _helpers.log("terminating VRChat")
    terminated = vrcpilot.terminate(timeout=10.0)
    _helpers.expect(terminated, "vrcpilot.terminate() returned False")
    _helpers.log("terminate reported success")


def main() -> int:
    return _helpers.run_scenario("launch_no_vr", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
