"""``vrcpilot screenshot`` subcommand.

Captures the VRChat window and emits its metadata as YAML on stdout.
The output mode depends on whether ``-o / --output`` is given:

- **With ``-o``** (file mode): The PNG is written to the given path and
  the YAML carries a ``path`` field with the absolute on-disk location.
  Use this when you want a separately-stored PNG you can open later.
- **Without ``-o``** (inline mode, default): No PNG file is written;
  the image is embedded in the YAML as a base64-encoded PNG under the
  ``image`` key. Designed for ``vrcpilot screenshot | vrcpilot ocr``
  pipelines so no stray files accumulate in the cwd.

Schema (file mode, stable, grep-able):

- ``path`` -- absolute path of the PNG that was written
- ``x`` / ``y`` -- window top-left in absolute desktop pixels
- ``width`` / ``height`` -- window size in physical pixels
- ``monitor_index`` -- index into ``mss.MSS().monitors`` (``0`` is the
  composite, ``1..N`` are individual monitors)
- ``captured_at`` -- ISO-8601 UTC timestamp of the grab

Schema (inline mode, stable, grep-able):

- ``x``, ``y``, ``width``, ``height``, ``monitor_index``,
  ``captured_at`` (same as above)
- ``image`` -- base64-encoded PNG bytes (emitted last so the metadata
  remains line-grep-friendly)

Keys are emitted with ``sort_keys=False`` so callers can rely on the
order for line-oriented parsing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from argcomplete.completers import FilesCompleter

from vrcpilot.screenshot import take_screenshot

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
            "Path where the PNG screenshot is written. When omitted, the "
            "image is embedded as base64 PNG in the YAML output (no file "
            "is written) so the result can be piped directly to "
            "'vrcpilot ocr' / 'detect'."
        ),
    )
    attach_completer(
        output_action, FilesCompleter(allowednames=("png",), directories=True)
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``screenshot`` subcommand.

    When ``args.output`` is given, writes the PNG to that path and emits
    ``path``-referencing YAML on stdout. When omitted, no file is
    written and the YAML embeds the PNG as base64 under ``image:``. The
    output extension drives the on-disk format via
    :func:`PIL.Image.save`.

    Returns:
        ``0`` on success, ``1`` if capture failed (with a single
        ``vrcpilot: ...`` line on stderr and no stdout output).
    """
    output: Path | None = args.output
    shot = take_screenshot()
    if shot is None:
        print("vrcpilot: could not capture VRChat screenshot", file=sys.stderr)
        return 1
    sys.stdout.write(shot.save(output))
    return 0
