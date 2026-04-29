"""Manual scenario: launch VRChat in Desktop mode and verify focus/unfocus.

Drives ``vrcpilot.focus()`` and ``vrcpilot.unfocus()`` against a real
running VRChat client to confirm that the window can be brought to the
foreground and sent to the bottom of the z-order. Each operation is
followed by a screenshot saved under ``_manual_artifacts/`` for visual
inspection.

Run with::

    just manual focus_unfocus

VRChat is launched with ``no_vr=True`` (Desktop mode) so the focus /
unfocus effects are observable without an HMD.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import vrcpilot

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402


def _scenario() -> None:
    _helpers.log("calling vrcpilot.launch(no_vr=True)")
    vrcpilot.launch(no_vr=True)

    _helpers.log("waiting for VRChat PID")
    pid = _helpers.wait_for_pid()
    assert pid is not None, "VRChat PID was not observed before timeout"
    _helpers.log(f"VRChat started (pid={pid})")

    _helpers.warmup()

    _helpers.log("calling vrcpilot.focus()")
    assert vrcpilot.focus(), "vrcpilot.focus() returned False"
    time.sleep(0.5)
    _helpers.take_screenshot("focus_unfocus", "focus")

    _helpers.log("calling vrcpilot.unfocus()")
    assert vrcpilot.unfocus(), "vrcpilot.unfocus() returned False"
    time.sleep(0.5)
    _helpers.take_screenshot("focus_unfocus", "unfocus")


def main() -> int:
    return _helpers.run_scenario("focus_unfocus", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
