"""``vrcpilot focus`` subcommand."""

from __future__ import annotations

import argparse
import sys

from vrcpilot import cli as _cli

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``focus`` subparser to the top-level subparsers."""
    subparsers.add_parser(
        "focus",
        help="Bring the running VRChat window to the foreground.",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``focus`` subcommand.

    Silent on success so callers can ``vrcpilot focus && ...`` without
    parsing stdout. On failure, a single ``vrcpilot: ...`` line is
    written to stderr.

    Returns:
        ``0`` on success, ``1`` on any failure (VRChat not running,
        window unavailable, native Wayland).
    """
    del args
    if _cli.focus():
        return 0
    print("vrcpilot: could not focus VRChat", file=sys.stderr)
    return 1
