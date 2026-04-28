"""Manual end-to-end scenario: drive VRChat through the ``vrcpilot`` CLI.

Runs ``vrcpilot launch`` / ``status`` / ``terminate`` via ``uv run`` and
verifies each subcommand's exit code and stdout. ``_helpers.run_scenario``
ensures VRChat is killed before and after the run regardless of outcome.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402


def _vrcpilot(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``uv run vrcpilot <args>`` and return the completed process."""
    cmd = ["uv", "run", "vrcpilot", *args]
    _helpers.log(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stdout:
        _helpers.log(f"  stdout: {result.stdout.strip()}")
    if result.stderr:
        _helpers.log(f"  stderr: {result.stderr.strip()}")
    _helpers.log(f"  exit: {result.returncode}")
    return result


def _scenario() -> None:
    status = _vrcpilot("status")
    _helpers.expect(
        status.returncode == 1,
        f"initial status exit code: expected 1, got {status.returncode}",
    )
    _helpers.expect(
        "VRChat is not running" in status.stdout,
        f"initial status stdout missing 'VRChat is not running': {status.stdout!r}",
    )

    launch = _vrcpilot("launch")
    _helpers.expect(
        launch.returncode == 0,
        f"launch exit code: expected 0, got {launch.returncode}",
    )
    _helpers.expect(
        "Launched VRChat." in launch.stdout,
        f"launch stdout missing 'Launched VRChat.': {launch.stdout!r}",
    )

    pid = _helpers.wait_for_pid()
    _helpers.expect(
        isinstance(pid, int),
        f"expected a VRChat PID after launch, got {pid!r}",
    )
    _helpers.log(f"VRChat PID = {pid}")

    _helpers.warmup()

    running = _vrcpilot("status")
    _helpers.expect(
        running.returncode == 0,
        f"running status exit code: expected 0, got {running.returncode}",
    )
    _helpers.expect(
        "VRChat is running" in running.stdout,
        f"running status stdout missing 'VRChat is running': {running.stdout!r}",
    )

    terminate = _vrcpilot("terminate")
    _helpers.expect(
        terminate.returncode == 0,
        f"terminate exit code: expected 0, got {terminate.returncode}",
    )
    _helpers.expect(
        "Terminated VRChat." in terminate.stdout,
        f"terminate stdout missing 'Terminated VRChat.': {terminate.stdout!r}",
    )

    final = _vrcpilot("status")
    _helpers.expect(
        final.returncode == 1,
        f"final status exit code: expected 1, got {final.returncode}",
    )


def main() -> int:
    return _helpers.run_scenario("cli_launch_terminate", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
