"""``vrcpilot unfocus`` subcommand."""

from __future__ import annotations

import argparse

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

    Returns:
        ``0`` on success, ``1`` on any failure (VRChat not running,
        window unavailable, native Wayland).
    """
    del args
    if _cli.unfocus():
        print("Unfocused VRChat.")
        return 0
    print("Could not unfocus VRChat.")
    return 1
