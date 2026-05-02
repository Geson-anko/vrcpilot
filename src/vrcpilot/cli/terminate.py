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
    callers do not need a preflight ``status`` check.
    """
    del args
    if terminate():
        print("Terminated VRChat.")
    else:
        print("VRChat is not running.")
    return 0
