"""Manual scenario: drive ``vrcpilot.controls.mouse`` against real VRChat.

Launches VRChat in Desktop mode, warms up, then exercises ``move``,
``click``, ``press``/``release``, and ``scroll`` so a human can verify
the synthetic events actually reach the VRChat window. The
``ensure_target`` guard is also covered: one step deliberately calls
``vrcpilot.unfocus()`` and then issues a click, which must bring
VRChat back to the foreground before the click lands.

The pattern follows :mod:`tests.manual.focus_unfocus`: alternating
operations (move-left -> click, move-right -> click, etc.) so two
back-to-back identical calls do not look like a no-op, and a
screenshot per step is dropped under ``_manual_artifacts/`` for
review.

Run with::

    just manual controls_mouse_click

Prerequisites:

* Desktop session must be reachable (X11 or XWayland; native Wayland
  is rejected by ``ensure_target``).
* Steam must already be running -- ``vrcpilot.launch()`` will time out
  otherwise.
* The current user needs write access to ``/dev/uinput`` for inputtino
  to open its virtual device. If construction fails with a
  ``RuntimeError``, run::

      sudo usermod -aG input $USER

  and log out / back in (or follow your distro's udev rule guidance).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import mss

import vrcpilot
from vrcpilot.controls import mouse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402


def _screen_center() -> tuple[int, int]:
    """Return the centre pixel of the union of all monitors.

    Computed at runtime via ``mss`` so no resolution is hard-coded.
    """
    with mss.mss() as sct:
        bbox = sct.monitors[0]
        cx = int(bbox["width"]) // 2
        cy = int(bbox["height"]) // 2
    return cx, cy


def _scenario() -> None:
    _helpers.log("calling vrcpilot.launch(no_vr=True)")
    vrcpilot.launch(no_vr=True)

    _helpers.log("waiting for VRChat PID")
    pid = _helpers.wait_for_pid()
    assert pid is not None, "VRChat PID was not observed before timeout"
    _helpers.log(f"VRChat started (pid={pid})")

    _helpers.warmup()

    cx, cy = _screen_center()
    _helpers.log(f"screen centre: ({cx}, {cy})")

    # Step 1/6: absolute move to the centre. Verifies move_abs path
    # against mss-derived screen size.
    _helpers.log("mouse.move(cx, cy) (1/6: absolute move to centre)")
    mouse.move(cx, cy)
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("controls_mouse_click", "1_move_center")

    # Step 2/6: relative nudge so the cursor visibly moves from the
    # previous position -- a no-op move would not be observable.
    _helpers.log("mouse.move(+50, +30, relative=True) (2/6: relative nudge)")
    mouse.move(50, 30, relative=True)
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("controls_mouse_click", "2_move_relative")

    # Step 3/6: a left click at the current position. VRChat's main
    # menu being visible is not strictly required; the click event
    # itself is the artifact under test.
    _helpers.log("mouse.click() (3/6: single left click)")
    mouse.click()
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("controls_mouse_click", "3_click")

    # Step 4/6: send VRChat to the background, then click. The guard
    # in mouse.click() should call vrcpilot.window.focus() and bring
    # VRChat back before the click is delivered.
    _helpers.log("vrcpilot.unfocus() then mouse.click() (4/6: guard recovers focus)")
    assert vrcpilot.unfocus(), "vrcpilot.unfocus() returned False"
    time.sleep(0.5)
    mouse.click()
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("controls_mouse_click", "4_click_after_unfocus")

    # Step 5/6: explicit press / release pair -- exercises the
    # held-button code path that click() does not (click uses the
    # built-in inputtino duration instead).
    _helpers.log("mouse.press()/release() (5/6: held-button pair)")
    mouse.press("left")
    time.sleep(0.1)
    mouse.release("left")
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("controls_mouse_click", "5_press_release")

    # Step 6/6: scroll down then back up. Two opposite directions so
    # the net visual position is the same and a stuck scroll wheel is
    # easy to spot.
    _helpers.log("mouse.scroll(+2) then mouse.scroll(-2) (6/6: scroll round-trip)")
    mouse.scroll(2)
    time.sleep(0.3)
    mouse.scroll(-2)
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("controls_mouse_click", "6_scroll")


def main() -> int:
    return _helpers.run_scenario("controls_mouse_click", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
