"""``vrcpilot ocr`` subcommand.

Runs OCR against the current VRChat window and dumps a YAML document on
stdout that ties each recognised word back to both image-local and
desktop-absolute coordinates. Optionally also writes an annotated PNG
visualization for human review.

YAML schema (stable, ``sort_keys=False`` so the order is fixed):

- ``captured_at`` - ISO-8601 timestamp of the underlying screenshot
- ``window`` - VRChat window geometry on the desktop
  - ``x`` / ``y`` - top-left in absolute desktop pixels
  - ``width`` / ``height`` - window size in physical pixels
  - ``monitor_index`` - mss monitor index (``0`` = composite, ``1..N``
    individual monitors)
- ``words`` - list of detections, each with:
  - ``text`` - recognised string
  - ``confidence`` - 0.0-1.0 float
  - ``pos`` - image-local coordinates (origin = window top-left)
    - ``polygon`` - 4 ``[x, y]`` corners (TL, TR, BR, BL)
    - ``bbox`` - ``[x, y, width, height]``
  - ``display_pos`` - desktop-absolute coordinates (``pos`` shifted by
    ``window.x`` / ``window.y``)
- ``viz_path`` - absolute path of the annotated PNG (only present when
  ``--viz`` was passed)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml
from argcomplete.completers import FilesCompleter
from PIL import Image

from vrcpilot import cli as _cli
from vrcpilot.ocr import OCRResult

from ._common import SubParsersAction, attach_completer

# Sentinel that distinguishes "--viz absent" (``None``) from
# "--viz with no argument" (this object) once argparse has parsed the
# argv. ``type=Path`` is only applied when the user passes a value, so
# ``args.viz`` ends up as one of: ``None`` / ``_VIZ_DEFAULT`` / ``Path``.
_VIZ_DEFAULT: object = object()


def register(subparsers: SubParsersAction) -> None:
    """Add the ``ocr`` subparser to the top-level subparsers."""
    parser = subparsers.add_parser(
        "ocr",
        help="Run OCR on the running VRChat window.",
    )
    viz_action = parser.add_argument(
        "--viz",
        nargs="?",
        const=_VIZ_DEFAULT,
        default=None,
        type=Path,
        help=(
            "Save OCR visualization PNG. With no path, writes to cwd "
            "with a timestamp; with a directory, writes inside that "
            "directory using the same default filename."
        ),
    )
    attach_completer(
        viz_action, FilesCompleter(allowednames=("png",), directories=True)
    )


def _resolve_viz_path(arg: object, *, now: datetime) -> Path | None:
    """Resolve ``args.viz`` to an absolute output path or ``None``.

    Args:
        arg: Raw value from ``args.viz``. One of ``None`` (flag absent),
            :data:`_VIZ_DEFAULT` (flag with no argument), or a
            :class:`Path` (flag with explicit argument).
        now: Timestamp used to build the default filename. Taken as a
            parameter so tests can pin it.

    Returns:
        Resolved :class:`Path` to write the PNG to, or ``None`` when the
        caller did not request a visualization.
    """
    if arg is None:
        return None
    stamp = now.strftime("%Y%m%d_%H%M%S")
    default_name = f"vrcpilot_ocr_viz_{stamp}.png"
    if arg is _VIZ_DEFAULT:
        return Path.cwd() / default_name
    if isinstance(arg, Path):
        if arg.is_dir():
            return arg / default_name
        return arg
    # Defensive fallback: argparse should never hand us anything else,
    # but keeping the branch keeps the type narrowing exhaustive.
    raise TypeError(f"unexpected --viz value: {arg!r}")


def run(args: argparse.Namespace) -> int:
    """Execute the ``ocr`` subcommand.

    Returns:
        ``0`` on success, ``1`` when OCR could not be performed (e.g.
        VRChat is not running). On failure a single ``vrcpilot: ...``
        line is written to stderr and stdout stays empty.
    """
    result: OCRResult | None = _cli.recognize()
    if result is None:
        print("vrcpilot: could not run OCR", file=sys.stderr)
        return 1

    viz_path = _resolve_viz_path(args.viz, now=datetime.now())
    if viz_path is not None:
        rendered = _cli.render(result)
        Image.fromarray(rendered).save(viz_path)

    shot = result.screenshot
    words_payload: list[dict[str, object]] = []
    for word in result.words:
        polygon = [list(point) for point in word.polygon]
        bbox = list(word.bbox)
        display_polygon = [list(point) for point in result.display_polygon(word)]
        display_bbox = list(result.display_bbox(word))
        words_payload.append(
            {
                "text": word.text,
                "confidence": word.confidence,
                "pos": {
                    "polygon": polygon,
                    "bbox": bbox,
                },
                "display_pos": {
                    "polygon": display_polygon,
                    "bbox": display_bbox,
                },
            }
        )

    payload: dict[str, object] = {
        "captured_at": shot.captured_at.isoformat(),
        "window": {
            "x": shot.x,
            "y": shot.y,
            "width": shot.width,
            "height": shot.height,
            "monitor_index": shot.monitor_index,
        },
        "words": words_payload,
    }
    if viz_path is not None:
        payload["viz_path"] = str(viz_path.resolve())

    sys.stdout.write(yaml.safe_dump(payload, sort_keys=False, default_flow_style=False))
    return 0
