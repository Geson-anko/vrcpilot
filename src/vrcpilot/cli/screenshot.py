"""``vrcpilot screenshot`` subcommand."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from argcomplete.completers import FilesCompleter
from PIL import Image

from vrcpilot import cli as _cli

from ._common import SubParsersAction, attach_completer


def register(subparsers: SubParsersAction) -> None:
    """Add the ``screenshot`` subparser to the top-level subparsers."""
    screenshot_parser = subparsers.add_parser(
        "screenshot",
        help="Capture a screenshot of the running VRChat window.",
    )
    output_action = screenshot_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Path where the PNG screenshot is written. Defaults to "
            "./vrcpilot_screenshot_<YYYYMMDD_HHMMSS>.png in the current "
            "directory."
        ),
    )
    attach_completer(
        output_action, FilesCompleter(allowednames=("png",), directories=True)
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``screenshot`` subcommand.

    Args:
        args: Parsed argparse namespace. Reads ``args.output`` —
            destination path. ``None`` writes
            ``./vrcpilot_screenshot_<YYYYMMDD_HHMMSS>.png``. Extension
            determines the on-disk format via :func:`PIL.Image.save`.

    Returns:
        ``0`` on success, ``1`` if capture failed.
    """
    output: Path | None = args.output
    shot = _cli.take_screenshot()
    if shot is None:
        print("Could not capture VRChat screenshot.", file=sys.stderr)
        return 1
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path.cwd() / f"vrcpilot_screenshot_{stamp}.png"
    Image.fromarray(shot.image).save(output)
    print(f"Saved screenshot to {output}.")
    return 0
