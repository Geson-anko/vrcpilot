"""``vrcpilot launch`` subcommand."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from argcomplete.completers import FilesCompleter

from vrcpilot.process import (
    PID_WAIT_TIMEOUT,
    VRCHAT_STEAM_APP_ID,
    OscConfig,
    launch,
    # Imported by name (rather than referenced via ``vrcpilot.process``)
    # so tests can patch ``vrcpilot.cli.launch.wait_for_pid`` to control
    # the wait outcome without touching the rest of the process module.
    wait_for_pid,
)
from vrcpilot.steam import SteamNotFoundError

from ._common import SubParsersAction, attach_completer


def register(subparsers: SubParsersAction) -> None:
    """Add the ``launch`` subparser to the top-level subparsers."""
    launch_parser = subparsers.add_parser(
        "launch",
        help="Launch VRChat through Steam.",
    )
    launch_parser.add_argument(
        "--app-id",
        type=int,
        default=VRCHAT_STEAM_APP_ID,
        help="Steam app id to launch (default: VRChat's app id).",
    )
    steam_path_action = launch_parser.add_argument(
        "--steam-path",
        type=Path,
        default=None,
        help="Override the auto-detected Steam executable path.",
    )
    attach_completer(
        steam_path_action, FilesCompleter(allowednames=("exe",), directories=True)
    )
    launch_parser.add_argument(
        "--no-vr",
        action="store_true",
        help="Force desktop mode (passes --no-vr to VRChat).",
    )
    launch_parser.add_argument(
        "--screen-width",
        type=int,
        default=None,
        help="Window width passed to Unity as -screen-width.",
    )
    launch_parser.add_argument(
        "--screen-height",
        type=int,
        default=None,
        help="Window height passed to Unity as -screen-height.",
    )
    launch_parser.add_argument(
        "--osc-in-port",
        type=int,
        default=None,
        help=(
            "OSC inbound port. When set, OSC config (including --osc-out-ip "
            "and --osc-out-port) is forwarded to VRChat. When unset, all "
            "--osc-out-* flags are ignored."
        ),
    )
    launch_parser.add_argument(
        "--osc-out-ip",
        type=str,
        default="127.0.0.1",
        help="OSC outbound IP. Only meaningful with --osc-in-port (default 127.0.0.1).",
    )
    launch_parser.add_argument(
        "--osc-out-port",
        type=int,
        default=9001,
        help="OSC outbound port. Only meaningful with --osc-in-port (default 9001).",
    )
    launch_parser.add_argument(
        "--wait-timeout",
        type=float,
        default=PID_WAIT_TIMEOUT,
        help=(
            "Seconds to wait for VRChat to appear after launch. "
            f"Default {PID_WAIT_TIMEOUT}. Pass 0 (or any non-positive "
            "value) to skip the wait and exit immediately after spawning."
        ),
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``launch`` subcommand.

    ``osc_in_port`` gates the entire OSC triple: when ``None`` no
    ``--osc`` flag is forwarded and ``osc_out_ip`` / ``osc_out_port``
    are silently ignored. Keeps the CLI ergonomic at the cost of
    accepting unused flags without warning.

    When ``--wait-timeout`` is positive the command blocks until a
    VRChat PID is observed, then prints it on stdout. ``--wait-timeout
    0`` (or any non-positive value) spawns and returns immediately
    without waiting; callers can use ``vrcpilot pid`` to discover the
    PID later.

    Returns:
        ``0`` on launch (PID printed when waited), ``1`` if the wait
        timed out before VRChat appeared, ``2`` if Steam was not found.
    """
    osc = (
        OscConfig(
            in_port=args.osc_in_port,
            out_ip=args.osc_out_ip,
            out_port=args.osc_out_port,
        )
        if args.osc_in_port is not None
        else None
    )
    try:
        launch(
            app_id=args.app_id,
            steam_path=args.steam_path,
            no_vr=args.no_vr,
            screen_width=args.screen_width,
            screen_height=args.screen_height,
            osc=osc,
        )
    except SteamNotFoundError as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 2

    timeout: float = args.wait_timeout
    if timeout <= 0:
        return 0

    pid = wait_for_pid(timeout=timeout)
    if pid is None:
        print(
            f"vrcpilot: VRChat did not start within {timeout}s",
            file=sys.stderr,
        )
        return 1
    print(pid, flush=True)
    return 0
