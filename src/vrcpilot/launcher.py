"""VRChat launch API.

Public entry points for starting VRChat through Steam. The launcher is the
foundation other automation layers build on: anything that drives the live
client first needs the client to be running. Use :func:`launch_vrchat` for
the end-to-end flow and :func:`build_launch_command` when you need to
inspect or customize the command before spawning.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import psutil

from vrcpilot._steam import find_steam_executable

#: Steam application id for VRChat. Hard-coded as a published constant rather
#: than discovered at runtime so callers can reference it without launching.
VRCHAT_STEAM_APP_ID: Final[int] = 438100

#: Process name used by VRChat across platforms. On Linux/Steam Deck the
#: client runs under Proton and still presents itself as ``VRChat.exe``,
#: so the same constant is correct for every supported OS.
VRCHAT_PROCESS_NAME: Final[str] = "VRChat.exe"


@dataclass(frozen=True)
class OscConfig:
    """Python representation of VRChat's ``--osc=in:ip:out`` launch flag.

    VRChat accepts a single ``--osc=<in_port>:<out_ip>:<out_port>`` argument
    that pins the OSC server it spins up at startup. This dataclass models
    that triple as a typed, structured value so callers do not assemble the
    string by hand and so two configurations can be compared with ``==``.

    Defaults intentionally mirror VRChat's own factory OSC settings, so
    ``OscConfig()`` reproduces the client's out-of-the-box behaviour while
    still forwarding the flag explicitly — useful when you want the
    deterministic argv (e.g. for logging) without changing semantics.

    The dataclass is ``frozen=True``: instances are hashable and safe to
    share across threads or use as cache keys. To change a port, construct
    a new instance (or use :func:`dataclasses.replace`).

    Attributes:
        in_port: UDP port VRChat listens on for inbound OSC messages.
        out_ip: IP address VRChat sends outbound OSC messages to.
        out_port: UDP port VRChat sends outbound OSC messages to.

    Examples:
        >>> OscConfig() == OscConfig(9000, "127.0.0.1", 9001)
        True
        >>> OscConfig(in_port=9100).to_launch_arg()
        '--osc=9100:127.0.0.1:9001'
    """

    in_port: int = 9000
    out_ip: str = "127.0.0.1"
    out_port: int = 9001

    def to_launch_arg(self) -> str:
        """Render the configuration as a single ``--osc=...`` CLI token.

        The result is one argv element (no spaces), ready to be appended to
        the VRChat-side argument list returned by
        :func:`build_vrchat_launch_args`.

        Returns:
            The argument string to pass to VRChat.

        Examples:
            >>> OscConfig().to_launch_arg()
            '--osc=9000:127.0.0.1:9001'
        """
        return f"--osc={self.in_port}:{self.out_ip}:{self.out_port}"


def build_vrchat_launch_args(
    *,
    no_vr: bool = False,
    screen_width: int | None = None,
    screen_height: int | None = None,
    osc: OscConfig | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Assemble the VRChat-specific argument list passed after ``-applaunch``.

    Pure helper that turns a structured set of options into the flat token
    list VRChat (and the underlying Unity runtime) expect. It is kept
    separate from :func:`build_launch_command` because the two operate on
    different layers: this function only knows about VRChat's own flags,
    while :func:`build_launch_command` deals with Steam's wrapper argv.
    Splitting them lets callers reuse, inspect, or further filter the
    VRChat-side argv without re-implementing Steam's invocation contract.

    The output order is fixed — ``no_vr`` → ``screen_width`` →
    ``screen_height`` → ``osc`` → ``extra_args`` — so the produced argv is
    byte-stable across runs, which keeps tests, logs, and reproducibility
    tooling honest.

    ``extra_args`` is the deliberate escape hatch for flags this helper
    does not model (e.g. ``--profile=N`` or future VRChat options): tokens
    are forwarded verbatim with no interpretation, so callers retain full
    control when the structured arguments are not enough.

    Args:
        no_vr: When ``True``, append ``--no-vr`` to launch in desktop mode.
        screen_width: Optional Unity ``-screen-width`` value.
        screen_height: Optional Unity ``-screen-height`` value.
        osc: Optional :class:`OscConfig`; rendered via
            :meth:`OscConfig.to_launch_arg`.
        extra_args: Additional raw tokens appended verbatim after every
            structured option. Use for flags this helper does not model.

    Returns:
        A list of CLI tokens ready to splice in after the Steam
        ``-applaunch <app_id>`` prefix.
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
    """Build the argv used to launch a Steam game via Steam's CLI.

    Exposed separately from :func:`launch_vrchat` so callers can inspect,
    log, or wrap the command (for example, to spawn it under a sandbox or
    a different process manager) without paying the cost of an actual
    launch. The function is pure and side-effect free, which also makes
    it easy to unit-test command-shape regressions.

    Steam's ``-applaunch`` form forwards every trailing token to the
    launched game, which is how VRChat ends up receiving its own flags
    even though the process Python actually spawns is Steam itself. That
    one-step transport is the reason ``vrchat_args`` belongs here rather
    than as a parallel ``Popen`` argument.

    Args:
        steam_executable: Path to the Steam executable. Not validated
            here; pass a path returned from auto-detection or one you
            have already verified.
        app_id: Steam application id of the game to launch. Defaults to
            :data:`VRCHAT_STEAM_APP_ID`.
        vrchat_args: Optional list of arguments forwarded to VRChat after
            ``-applaunch <app_id>``. Pre-built via
            :func:`build_vrchat_launch_args` or supplied as raw tokens.

    Returns:
        Argument vector suitable for :class:`subprocess.Popen`.
    """
    cmd = [str(steam_executable), "-applaunch", str(app_id)]
    if vrchat_args:
        cmd.extend(vrchat_args)
    return cmd


def launch_vrchat(
    *,
    app_id: int = VRCHAT_STEAM_APP_ID,
    steam_path: Path | None = None,
    no_vr: bool = False,
    screen_width: int | None = None,
    screen_height: int | None = None,
    osc: OscConfig | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.Popen[bytes]:
    """Launch VRChat through Steam and return the spawned subprocess.

    Use this as the standard way to bring VRChat up before driving any
    higher-level automation. The handed-back :class:`~subprocess.Popen`
    represents the Steam launcher invocation, not VRChat itself: Steam
    keeps its own long-lived client process, so the actual game window
    is owned by Steam and may outlive the returned handle. The launcher
    is also detached from the parent's process group / session so that
    the Python script can exit without taking VRChat down with it.

    Steam must be installed and either auto-detectable or supplied via
    ``steam_path``; the user is not required to be signed in beforehand,
    Steam will surface its own login UI if needed.

    The keyword arguments below mirror :func:`build_vrchat_launch_args` —
    they are forwarded as-is and converted into the VRChat argv that
    Steam's ``-applaunch`` form transports to the game. Use ``extra_args``
    when you need to pass an option this function does not model
    explicitly (e.g. uncommon or future VRChat flags).

    Args:
        app_id: Steam application id to launch. Defaults to
            :data:`VRCHAT_STEAM_APP_ID`. Override only when targeting a
            different title (e.g. a test app id).
        steam_path: Optional explicit path to the Steam executable. When
            omitted, the path is auto-detected per platform.
        no_vr: Pass ``--no-vr`` to launch VRChat in desktop mode.
        screen_width: Optional ``-screen-width`` value forwarded to Unity.
        screen_height: Optional ``-screen-height`` value forwarded to
            Unity.
        osc: Optional :class:`OscConfig` rendered into ``--osc=...``. Pass
            ``OscConfig()`` to forward the flag with VRChat's defaults, or
            customise ports/IP as needed.
        extra_args: Additional raw tokens forwarded verbatim to VRChat.
            Escape hatch for options this signature does not cover.

    Returns:
        The :class:`~subprocess.Popen` handle for the launched Steam
        process. Treat its lifetime as informational; do not rely on
        terminating it to stop VRChat.

    Raises:
        SteamNotFoundError: If the Steam executable cannot be located.
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
        return subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def find_vrchat_pid() -> int | None:
    """Return the PID of a running VRChat process, or ``None`` if absent.

    Use this to check whether VRChat is already up before deciding to
    launch it, or to obtain a handle for higher-level automation that
    needs to attach to the live process. The lookup is read-only — it
    does not signal or otherwise disturb the process.

    Iterates over running processes via :func:`psutil.process_iter` and
    returns the first one whose name matches :data:`VRCHAT_PROCESS_NAME`.
    Enumeration order is OS-defined, so when multiple instances are
    running the choice is not configurable; callers that need every PID
    should walk :func:`psutil.process_iter` themselves.

    Returns:
        The PID of the first matching process, or ``None`` if no VRChat
        process is currently running.
    """
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == VRCHAT_PROCESS_NAME:
            return proc.pid
    return None


def terminate_vrchat(*, timeout: float = 5.0) -> bool:
    """Forcefully terminate any running VRChat processes.

    Iterates over running processes and sends SIGKILL
    (:meth:`psutil.Process.kill`, which uses ``TerminateProcess`` on
    Windows) to every process whose name matches
    :data:`VRCHAT_PROCESS_NAME`. Forceful termination is appropriate for
    automation: VRChat does not require an orderly shutdown for typical
    workflows.

    Args:
        timeout: Seconds to wait for the killed processes to disappear
            before returning, giving the OS time to reap them. If a
            process is still listed after the timeout, the function
            still returns ``True`` — the kill was issued, even if the
            wait did not observe completion.

    Returns:
        ``True`` if at least one matching process was found and killed,
        ``False`` if no VRChat process was running.
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
            # Process exited between enumeration and kill — treat as success.
            pass
    psutil.wait_procs(procs, timeout=timeout)
    return True
