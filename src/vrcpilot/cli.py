"""Command line interface for vrcpilot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.launcher import VRCHAT_STEAM_APP_ID, launch_vrchat


def main(argv: list[str] | None = None) -> int:
    """Run the ``vrcpilot`` command line interface.

    Args:
        argv: Optional argument list passed to :mod:`argparse`. When ``None``
            (the default), arguments are read from :data:`sys.argv`.

    Returns:
        Process exit code. ``0`` on success, ``2`` on a recoverable error such
        as Steam not being found.
    """
    parser = argparse.ArgumentParser(
        prog="vrcpilot",
        description="Automation tooling for VRChat.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    launch_parser.add_argument(
        "--steam-path",
        type=Path,
        default=None,
        help="Override the auto-detected Steam executable path.",
    )

    args = parser.parse_args(argv)

    match args.command:
        case "launch":
            return _run_launch(app_id=args.app_id, steam_path=args.steam_path)
        case _:
            parser.error(f"Unknown command: {args.command}")


def _run_launch(*, app_id: int, steam_path: Path | None) -> int:
    """Execute the ``launch`` subcommand.

    Args:
        app_id: Steam app id to launch.
        steam_path: Optional explicit path to the Steam executable.

    Returns:
        ``0`` if Steam was launched successfully, ``2`` if Steam was not found.
    """
    try:
        process = launch_vrchat(app_id=app_id, steam_path=steam_path)
    except SteamNotFoundError as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 2
    print(f"Launched Steam process pid={process.pid}")
    return 0
