"""``vrcpilot screenshot`` subcommand.

Writes the PNG to disk and dumps the :class:`Screenshot` metadata as a
YAML document on stdout. The schema (stable, grep-able):

- ``path`` — absolute path of the PNG that was written
- ``x`` / ``y`` — window top-left in absolute desktop pixels
- ``width`` / ``height`` — window size in physical pixels
- ``monitor_index`` — index into ``mss.MSS().monitors`` (``0`` is the
  composite, ``1..N`` are individual monitors)
- ``captured_at`` — ISO-8601 UTC timestamp of the grab

Keys are emitted in the order above (``sort_keys=False``) so callers
can rely on it for line-oriented parsing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from argcomplete.completers import FilesCompleter

from vrcpilot.screenshot import Screenshot, take_screenshot

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

    Writes the PNG to ``args.output`` (or ``./vrcpilot_screenshot_
    <YYYYMMDD_HHMMSS>.png`` when unset) and emits the YAML metadata
    document described in the module docstring on stdout. The output
    extension drives the on-disk format via :func:`PIL.Image.save`.

    Returns:
        ``0`` on success, ``1`` if capture failed (with a single
        ``vrcpilot: ...`` line on stderr and no stdout output).
    """
    output: Path | None = args.output
    shot: Screenshot | None = take_screenshot()
    if shot is None:
        print("vrcpilot: could not capture VRChat screenshot", file=sys.stderr)
        return 1
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path.cwd() / f"vrcpilot_screenshot_{stamp}.png"
    sys.stdout.write(shot.save(output))
    return 0
