"""VRChat process lifecycle: launch, find, terminate."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import psutil

from vrcpilot.steam import find_steam_executable

#: Steam application id for VRChat.
VRCHAT_STEAM_APP_ID: Final[int] = 438100

#: Process name used by VRChat. On Linux/Steam Deck the client runs under
#: Proton and still presents itself as ``VRChat.exe``, so the same constant
#: is correct on every supported OS.
VRCHAT_PROCESS_NAME: Final[str] = "VRChat.exe"

#: Default total seconds :func:`wait_for_pid` / :func:`wait_for_no_pid`
#: poll before giving up. Sized for Steam's cold-start path on a typical
#: workstation (Steam launcher -> game bootstrapper -> VRChat).
PID_WAIT_TIMEOUT: Final[float] = 30.0

#: Default seconds between polls in :func:`wait_for_pid` /
#: :func:`wait_for_no_pid`. One second keeps the helpers responsive
#: without burning CPU on ``psutil.process_iter`` calls.
PID_WAIT_INTERVAL: Final[float] = 1.0


@dataclass(frozen=True)
class OscConfig:
    """Structured form of VRChat's ``--osc=<in>:<ip>:<out>`` launch flag.

    Defaults mirror VRChat's factory OSC settings, so ``OscConfig()``
    forwards the flag explicitly without changing client semantics -
    useful when a deterministic argv is wanted (logging, tests).

    Attributes:
        in_port: UDP port VRChat listens on for inbound OSC messages.
        out_ip: IP VRChat sends outbound OSC messages to.
        out_port: UDP port VRChat sends outbound OSC messages to.
    """

    in_port: int = 9000
    out_ip: str = "127.0.0.1"
    out_port: int = 9001

    def to_launch_arg(self) -> str:
        """Render as a single ``--osc=...`` argv token."""
        return f"--osc={self.in_port}:{self.out_ip}:{self.out_port}"


def build_vrchat_launch_args(
    *,
    no_vr: bool = False,
    screen_width: int | None = None,
    screen_height: int | None = None,
    osc: OscConfig | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Assemble the VRChat-side argv that follows ``-applaunch <app_id>``.

    Output order is fixed (``no_vr`` -> screen size -> ``osc`` ->
    ``extra_args``) so the argv is byte-stable across runs. Kept
    separate from :func:`build_launch_command` so callers can reuse or
    filter the VRChat-side argv without re-implementing Steam's
    wrapper.

    Args:
        no_vr: When ``True`` append ``--no-vr``.
        screen_width: Optional Unity ``-screen-width`` value.
        screen_height: Optional Unity ``-screen-height`` value.
        osc: Optional :class:`OscConfig`.
        extra_args: Raw tokens appended verbatim. Escape hatch for
            flags this helper does not model.
    """
    args: list[str] = []
    if no_vr:
        args.append("--no-vr")
    if screen_width is not None:
        args.extend(["-screen-width", str(screen_width)])
    if screen_height is not None:
        args.extend(["-screen-height", str(screen_height)])
    if osc is not None:
        args.append(osc.to_launch_arg())
    if extra_args:
        args.extend(extra_args)
    return args


def build_launch_command(
    steam_executable: Path,
    app_id: int = VRCHAT_STEAM_APP_ID,
    *,
    vrchat_args: list[str] | None = None,
) -> list[str]:
    """Build the Steam ``-applaunch`` argv for spawning the game.

    Exposed separately from :func:`launch` so callers can inspect, log,
    or wrap the command without spawning. ``vrchat_args`` lives here
    because Steam's ``-applaunch`` form transports trailing tokens to
    the launched game in the same argv - there is no parallel channel.

    Args:
        steam_executable: Path to the Steam executable. Not validated.
        app_id: Steam application id. Defaults to
            :data:`VRCHAT_STEAM_APP_ID`.
        vrchat_args: Forwarded to VRChat after ``-applaunch <app_id>``.
    """
    cmd = [str(steam_executable), "-applaunch", str(app_id)]
    if vrchat_args:
        cmd.extend(vrchat_args)
    return cmd


def launch(
    *,
    app_id: int = VRCHAT_STEAM_APP_ID,
    steam_path: Path | None = None,
    no_vr: bool = False,
    screen_width: int | None = None,
    screen_height: int | None = None,
    osc: OscConfig | None = None,
    extra_args: list[str] | None = None,
) -> None:
    """Launch VRChat through Steam.

    Detached from the parent's process group / session so the calling
    Python script can exit without taking VRChat down with it. The
    spawned PID is intentionally not returned: it is the short-lived
    Steam invoker, not VRChat itself; use :func:`find_pid` to observe
    VRChat.

    Args:
        app_id: Steam application id. Defaults to
            :data:`VRCHAT_STEAM_APP_ID`.
        steam_path: Explicit Steam executable path; auto-detected when
            ``None``.
        no_vr: Forward ``--no-vr`` (desktop mode).
        screen_width: Unity ``-screen-width`` value.
        screen_height: Unity ``-screen-height`` value.
        osc: Optional :class:`OscConfig` rendered into ``--osc=...``.
        extra_args: Raw tokens forwarded verbatim to VRChat.

    Raises:
        SteamNotFoundError: Steam executable cannot be located.
    """
    steam_executable = find_steam_executable(steam_path)
    vrchat_args = build_vrchat_launch_args(
        no_vr=no_vr,
        screen_width=screen_width,
        screen_height=screen_height,
        osc=osc,
        extra_args=extra_args,
    )
    argv = build_launch_command(steam_executable, app_id, vrchat_args=vrchat_args)

    if sys.platform == "win32":
        subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return
    subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def find_pid() -> int | None:
    """Return the PID of a running VRChat process, or ``None`` if absent.

    Returns the first match from :func:`psutil.process_iter` - when
    multiple instances run, enumeration order is OS-defined and the
    choice is not configurable. Use :func:`find_pids` to retrieve every
    matching PID.
    """
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == VRCHAT_PROCESS_NAME:
            return proc.pid
    return None


def find_pids() -> list[int]:
    """Return PIDs of every running VRChat process.

    The order of the returned list reflects the OS-defined enumeration
    order of :func:`psutil.process_iter` and should not be treated as
    stable across runs. Returns an empty list when no VRChat instance
    is running.
    """
    return [
        proc.pid
        for proc in psutil.process_iter(["name"])
        if proc.info["name"] == VRCHAT_PROCESS_NAME
    ]


def wait_for_pid(
    timeout: float = PID_WAIT_TIMEOUT,
    interval: float = PID_WAIT_INTERVAL,
) -> int | None:
    """Poll for a VRChat PID until one appears or ``timeout`` elapses.

    Uses :func:`find_pid` so the first match wins (enumeration order is
    OS-defined). Suitable for both the ``launch`` CLI flow and e2e
    scenarios that need to wait for the game to finish bootstrapping.

    Args:
        timeout: Maximum total seconds to wait before giving up.
            Defaults to :data:`PID_WAIT_TIMEOUT`.
        interval: Seconds to sleep between polls. Defaults to
            :data:`PID_WAIT_INTERVAL`.

    Returns:
        The first observed PID, or ``None`` if the deadline expired
        before any VRChat process appeared.
    """
    deadline = time.monotonic() + timeout
    while True:
        pid = find_pid()
        if pid is not None:
            return pid
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)


def wait_for_no_pid(
    timeout: float = PID_WAIT_TIMEOUT,
    interval: float = PID_WAIT_INTERVAL,
) -> bool:
    """Poll until no VRChat process is running, or ``timeout`` elapses.

    Mirror of :func:`wait_for_pid` for the teardown path: poll until
    :func:`find_pid` reports ``None``. Useful after :func:`terminate`
    to confirm the kill actually settled.

    Args:
        timeout: Maximum total seconds to wait before giving up.
            Defaults to :data:`PID_WAIT_TIMEOUT`.
        interval: Seconds to sleep between polls. Defaults to
            :data:`PID_WAIT_INTERVAL`.

    Returns:
        ``True`` once VRChat is gone; ``False`` if the deadline expired
        with the process still present.
    """
    deadline = time.monotonic() + timeout
    while True:
        if find_pid() is None:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def terminate(*, timeout: float = 5.0) -> bool:
    """Forcefully ``kill`` every running VRChat process.

    Args:
        timeout: Seconds to wait for the killed processes to disappear
            before returning. The function returns ``True`` even if a
            process is still listed after the timeout - the kill was
            issued, only the wait did not observe completion.

    Returns:
        ``True`` if at least one process was killed, ``False`` if none
        were running.
    """
    procs = [
        p
        for p in psutil.process_iter(["name"])
        if p.info["name"] == VRCHAT_PROCESS_NAME
    ]
    if not procs:
        return False
    for proc in procs:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            # Process exited between enumeration and kill - treat as success.
            pass
    psutil.wait_procs(procs, timeout=timeout)
    return True
