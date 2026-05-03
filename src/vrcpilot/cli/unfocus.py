"""``vrcpilot unfocus`` subcommand."""

from __future__ import annotations

import argparse
import sys

from vrcpilot import cli as _cli

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``unfocus`` subparser to the top-level subparsers."""
    subparsers.add_parser(
        "unfocus",
        help="Send the running VRChat window to the bottom of the z-order.",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``unfocus`` subcommand.

    Silent on success so callers can ``vrcpilot unfocus && ...`` without
    parsing stdout. On failure, a single ``vrcpilot: ...`` line is
    written to stderr.

    Returns:
        ``0`` on success, ``1`` on any failure (VRChat not running,
        window unavailable, native Wayland).
    """
    del args
    if _cli.unfocus():
        return 0
    print("vrcpilot: could not unfocus VRChat", file=sys.stderr)
    return 1
