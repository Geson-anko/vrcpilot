"""``vrcpilot status`` subcommand."""

from __future__ import annotations

import argparse

from vrcpilot.process import find_pid

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``status`` subparser to the top-level subparsers."""
    subparsers.add_parser(
        "status",
        help="Report whether VRChat is currently running.",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``status`` subcommand.

    Exit code is state-dependent (unlike :func:`vrcpilot.cli.terminate.run`)
    so shells can branch with ``if vrcpilot status; then ...``.

    Returns:
        ``0`` if running (PID printed), ``1`` otherwise.
    """
    del args
    pid = find_pid()
    if pid is None:
        print("VRChat is not running")
        return 1
    print(f"VRChat is running (pid={pid})")
    return 0
