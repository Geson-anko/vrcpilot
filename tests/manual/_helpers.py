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

import vrcpilot

# Fixed wait after a PID first appears, to let VRChat finish initializing.
WARMUP_SECONDS: float = 15.0

_PID_WAIT_TIMEOUT: float = 30.0
_PID_WAIT_INTERVAL: float = 1.0
_TERMINATE_TIMEOUT: float = 10.0


def log(msg: str) -> None:
    """Print *msg* prefixed with the current wall-clock time."""
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def pass_(msg: str) -> None:
    """Emit a final ``PASS:`` line for the scenario."""
    print(f"PASS: {msg}", flush=True)


def fail(msg: str) -> None:
    """Emit a final ``FAIL:`` line for the scenario."""
    print(f"FAIL: {msg}", flush=True)


def wait_for_pid(
    timeout: float = _PID_WAIT_TIMEOUT,
    interval: float = _PID_WAIT_INTERVAL,
) -> int | None:
    """Poll :func:`vrcpilot.find_pid` until it returns a PID or *timeout*
    elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pid = vrcpilot.find_pid()
        if pid is not None:
            return pid
        time.sleep(interval)
    return vrcpilot.find_pid()


def wait_for_no_pid(
    timeout: float = _PID_WAIT_TIMEOUT,
    interval: float = _PID_WAIT_INTERVAL,
) -> bool:
    """Poll until :func:`vrcpilot.find_pid` returns ``None``.

    Returns ``True`` once VRChat is gone, ``False`` if *timeout* elapsed
    while a PID was still observed.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if vrcpilot.find_pid() is None:
            return True
        time.sleep(interval)
    return vrcpilot.find_pid() is None


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
    vrcpilot.terminate(timeout=_TERMINATE_TIMEOUT)
    if wait_for_no_pid():
        log("existing VRChat terminated")
    else:
        log("WARNING: VRChat still present after terminate()")


def run_scenario(name: str, body: Callable[[], None]) -> int:
    """Run *body* with pre/post cleanup and convert its outcome to an exit
    code.

    *body* may return normally for success, or raise to signal failure.
    Either way ``ensure_no_vrchat`` runs both before and after, and a
    final ``PASS:`` / ``FAIL:`` line is emitted.
    """
    log(f"=== scenario: {name} ===")
    log("pre-cleanup")
    ensure_no_vrchat()
    try:
        body()
    except Exception as exc:
        log(f"scenario raised: {exc!r}")
        fail(f"{name}: {exc}")
        return 1
    finally:
        log("post-cleanup")
        ensure_no_vrchat()
    pass_(name)
    return 0


def warmup() -> None:
    """Sleep :data:`WARMUP_SECONDS` to let VRChat settle after launch."""
    log(f"warming up for {WARMUP_SECONDS:.0f}s")
    time.sleep(WARMUP_SECONDS)


def expect(condition: bool, message: str) -> None:
    """Raise :class:`AssertionError` with *message* when *condition* is
    false."""
    if not condition:
        raise AssertionError(message)


def exit_with(code: int) -> None:
    """Wrapper around :func:`sys.exit` so callers do not need to import sys."""
    sys.exit(code)
