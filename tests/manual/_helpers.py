"""Shared utilities for the manual end-to-end VRChat scenarios.

Each script in ``tests/manual/`` follows the same pattern: ensure no
VRChat is running, drive the API or CLI, verify, and always clean up.
The helpers here keep that boilerplate in one place so individual
scenarios stay readable.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import mss
import mss.tools

import vrcpilot

# Fixed wait after a PID first appears, to let VRChat finish initializing.
WARMUP_SECONDS: float = 15.0

_PID_WAIT_TIMEOUT: float = 30.0
_PID_WAIT_INTERVAL: float = 1.0

_ARTIFACT_DIR: Path = Path(__file__).resolve().parents[2] / "_manual_artifacts"


def log(msg: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def wait_for_pid(
    timeout: float = _PID_WAIT_TIMEOUT,
    interval: float = _PID_WAIT_INTERVAL,
) -> int | None:
    """Poll :func:`vrcpilot.find_pid` until a PID appears or *timeout*
    elapses."""
    deadline = time.monotonic() + timeout
    while True:
        pid = vrcpilot.find_pid()
        if pid is not None:
            return pid
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)


def wait_for_no_pid(
    timeout: float = _PID_WAIT_TIMEOUT,
    interval: float = _PID_WAIT_INTERVAL,
) -> bool:
    """Poll until :func:`vrcpilot.find_pid` returns ``None`` or *timeout*
    elapses."""
    deadline = time.monotonic() + timeout
    while True:
        if vrcpilot.find_pid() is None:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def ensure_no_vrchat() -> None:
    """Terminate any running VRChat and wait for it to disappear.

    Used as both pre- and post-condition by every scenario so a stray
    process from a prior failed run cannot pollute the test, and so the
    user's environment is left clean even on failure.
    """
    pid = vrcpilot.find_pid()
    if pid is None:
        log("no existing VRChat process")
        return
    log(f"existing VRChat detected (pid={pid}); terminating")
    vrcpilot.terminate()
    if wait_for_no_pid():
        log("existing VRChat terminated")
    else:
        log("WARNING: VRChat still present after terminate()")


def warmup(seconds: float = WARMUP_SECONDS) -> None:
    """Sleep *seconds* to let VRChat settle after launch."""
    log(f"warming up for {seconds:.0f}s")
    time.sleep(seconds)


def save_monitor_screenshot(scenario: str, label: str) -> Path:
    """Capture all monitors and save under ``_manual_artifacts/``.

    For a VRChat-window-only screenshot, use :func:`vrcpilot.take_screenshot`
    instead; this helper is for whole-desktop visual records.

    Use this in manual scenarios to leave a visual record at key steps
    so a human can review what VRChat looked like after the action ran.
    The save location is also emitted via :func:`log`.

    Args:
        scenario: Scenario identifier used as a filename prefix to keep
            artifacts grouped per script (e.g. ``"focus_unfocus"``).
        label: Step name within the scenario (e.g. ``"focus"``,
            ``"unfocus"``); becomes the second filename segment.

    Returns:
        Absolute :class:`~pathlib.Path` to the saved PNG. The filename
        pattern is ``{scenario}_{label}_{YYYYMMDD_HHMMSS}.png``.
    """
    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _ARTIFACT_DIR / f"{scenario}_{label}_{stamp}.png"
    with mss.mss() as sct:
        img = sct.grab(sct.monitors[0])
    mss.tools.to_png(img.rgb, img.size, output=str(path))
    log(f"screenshot saved: {path}")
    return path


def run_scenario(name: str, body: Callable[[], None]) -> int:
    """Run *body* with pre/post cleanup and convert the outcome to an exit
    code.

    *body* may return normally for success, or raise to signal failure.
    Either way :func:`ensure_no_vrchat` runs both before and after, and a
    final ``PASS:`` / ``FAIL:`` line is emitted.
    """
    log(f"=== scenario: {name} ===")
    log("pre-cleanup")
    ensure_no_vrchat()
    try:
        body()
    except Exception as exc:
        log(f"scenario raised: {exc!r}")
        print(f"FAIL: {name}: {exc}", flush=True)
        return 1
    finally:
        log("post-cleanup")
        ensure_no_vrchat()
    print(f"PASS: {name}", flush=True)
    return 0
