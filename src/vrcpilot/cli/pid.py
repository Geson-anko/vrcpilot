"""``vrcpilot pid`` subcommand."""

from __future__ import annotations

import argparse

from vrcpilot.process import find_pids

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``pid`` subparser to the top-level subparsers."""
    subparsers.add_parser(
        "pid",
        help="Print PIDs of running VRChat processes (one per line).",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``pid`` subcommand.

    Prints one PID per line on stdout. Exit code is state-dependent so
    shells can branch with ``if vrcpilot pid >/dev/null; then ...``.

    Returns:
        ``0`` when at least one VRChat PID is running; ``1`` when none
        is observed (stdout stays empty in that case).
    """
    del args
    pids = find_pids()
    if not pids:
        return 1
    for pid in pids:
        print(pid)
    return 0
