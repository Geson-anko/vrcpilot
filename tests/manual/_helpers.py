"""Shared utilities for the manual end-to-end VRChat scenarios.

Each script in ``tests/manual/`` follows the same pattern: ensure no
VRChat is running, drive the API or CLI, verify, and always clean up.
The helpers here keep that boilerplate in one place so individual
scenarios stay readable.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

# Manual scenarios run as scripts (``python tests/manual/foo.py``) rather
# than via pytest, so the repo root is not on ``sys.path`` -- ``uv run``
# only injects ``src``. Bootstrap it here so ``from tests.helpers`` below
# resolves without each scenario having to repeat the dance.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import mss  # noqa: E402
import mss.tools  # noqa: E402
from PIL import Image  # noqa: E402

import vrcpilot  # noqa: E402
from tests.helpers import wait_for_no_pid, wait_for_pid  # noqa: E402

__all__ = [
    "ARTIFACT_DIR",
    "WARMUP_SECONDS",
    "ensure_no_vrchat",
    "log",
    "run_scenario",
    "save_image",
    "save_monitor_screenshot",
    "wait_for_no_pid",
    "wait_for_pid",
    "warmup",
]

# Fixed wait after a PID first appears, to let VRChat finish
# initializing -- not just spawning the process but also loading the
# default world and settling into a stable foreground state. 15s was
# enough for focus/unfocus probes that only need the window to exist,
# but synthetic input scenarios race the world load otherwise; 45s
# leaves headroom even on first-run shader compilation.
WARMUP_SECONDS: float = 45.0

#: Directory used by manual scenarios to drop visual artifacts (PNGs).
#:
#: Located at ``<repo>/_manual_artifacts/`` and gitignored. Scenarios may
#: write directly with :func:`save_monitor_screenshot` /
#: :func:`save_image`, or read this constant when they need a custom
#: filename pattern. The directory is created lazily by the helpers
#: themselves, so callers do not need to ensure existence first.
ARTIFACT_DIR: Path = Path(__file__).resolve().parents[2] / "_manual_artifacts"


def log(msg: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


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
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ARTIFACT_DIR / f"{scenario}_{label}_{stamp}.png"
    with mss.mss() as sct:
        img = sct.grab(sct.monitors[0])
    mss.tools.to_png(img.rgb, img.size, output=str(path))
    log(f"screenshot saved: {path}")
    return path


def save_image(scenario: str, label: str, image: Image.Image) -> Path:
    """Save a :class:`PIL.Image.Image` under :data:`ARTIFACT_DIR`.

    Companion to :func:`save_monitor_screenshot`: the latter grabs the
    whole desktop with mss, while this one persists an image the
    scenario already has in hand (e.g. a ``vrcpilot.Capture`` frame
    converted via ``Image.fromarray``, or a
    ``vrcpilot.take_screenshot()`` result). Both share the same naming
    convention so artifacts from a single scenario sort together
    chronologically.

    Args:
        scenario: Scenario identifier used as filename prefix
            (e.g. ``"capture"``).
        label: Step name within the scenario
            (e.g. ``"first"``, ``"last"``).
        image: Image to save. Format is inferred from the ``.png``
            suffix.

    Returns:
        Absolute :class:`~pathlib.Path` to the saved PNG. The pattern
        is ``{scenario}_{label}_{YYYYMMDD_HHMMSS}.png``.
    """
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ARTIFACT_DIR / f"{scenario}_{label}_{stamp}.png"
    image.save(out)
    return out


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
