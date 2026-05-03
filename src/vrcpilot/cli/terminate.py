"""``vrcpilot terminate`` subcommand."""

from __future__ import annotations

import argparse

from vrcpilot.process import terminate

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``terminate`` subparser to the top-level subparsers."""
    subparsers.add_parser(
        "terminate",
        help="Forcefully terminate any running VRChat process.",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``terminate`` subcommand.

    Idempotent: exit ``0`` whether VRChat was running or not, so
    callers do not need a preflight ``pid`` check. When at least one
    process was killed, the killed PIDs are printed one per line on
    stdout. The no-op path stays silent so consumers can pipe through
    ``xargs`` without worrying about a stray header line.
    """
    del args
    for pid in terminate():
        print(pid)
    return 0
