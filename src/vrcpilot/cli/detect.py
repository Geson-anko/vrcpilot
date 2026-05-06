"""``vrcpilot detect`` subcommand.

Runs image-query detection against the current VRChat window and dumps
a YAML document on stdout describing each detection in both
image-local and desktop-absolute coordinates. Optionally writes an
annotated PNG visualization for human review.

Engine selection: :func:`vrcpilot.detect.detect` always uses
:class:`~vrcpilot.detect.TemplateDetectEngine` — there is no engine
kwarg to flip. When ``--threshold`` is omitted the run reuses the
process-cached default engine; passing ``--threshold`` constructs a
fresh :class:`~vrcpilot.detect.TemplateDetectEngine` with that
score-map cutoff so callers can tune match strictness from the CLI
without editing code.

YAML schema (stable, ``sort_keys=False`` so the order is fixed):

- ``captured_at`` - ISO-8601 timestamp of the underlying screenshot
- ``window`` - VRChat window geometry on the desktop
  - ``x`` / ``y`` - top-left in absolute desktop pixels
  - ``width`` / ``height`` - window size in physical pixels
  - ``monitor_index`` - mss monitor index (``0`` = composite, ``1..N``
    individual monitors)
- ``query`` - query image metadata
  - ``path`` - absolute path of the query PNG/JPG
  - ``width`` / ``height`` - query image size in pixels
- ``detections`` - list of detections, each with:
  - ``confidence`` - 0.0-1.0 float
  - ``scale`` - scale factor relative to the query (1.0 = same size)
  - ``rotation`` - rotation in radians (counter-clockwise positive)
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

import cv2
import numpy as np
import yaml
from argcomplete.completers import FilesCompleter
from numpy.typing import NDArray
from PIL import Image

from vrcpilot.detect import DetectEngine, TemplateDetectEngine, detect, render
from vrcpilot.screenshot import Screenshot, take_screenshot

from ._common import SubParsersAction, attach_completer

# Sentinel that distinguishes "--viz absent" (``None``) from
# "--viz with no argument" (this object) once argparse has parsed the
# argv. ``type=Path`` is only applied when the user passes a value, so
# ``args.viz`` ends up as one of: ``None`` / ``_VIZ_DEFAULT`` / ``Path``.
_VIZ_DEFAULT: object = object()


def register(subparsers: SubParsersAction) -> None:
    """Add the ``detect`` subparser to the top-level subparsers."""
    parser = subparsers.add_parser(
        "detect",
        help="Detect a query image inside the running VRChat window.",
    )
    query_action = parser.add_argument(
        "--query",
        type=Path,
        required=True,
        help=(
            "Path to the query image (PNG/JPG) to search for in the " "VRChat window."
        ),
    )
    attach_completer(query_action, FilesCompleter(allowednames=("png", "jpg")))
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "TM_CCOEFF_NORMED score cutoff (theoretical range -1..1) used "
            "by TemplateDetectEngine. Passing this flag constructs a fresh "
            "engine with the given threshold; omit it to use the cached "
            "default (0.85)."
        ),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help=(
            "Limit output to the top-K detections sorted by confidence "
            "(descending). When unset, all detections from the engine "
            "are emitted."
        ),
    )
    viz_action = parser.add_argument(
        "--viz",
        nargs="?",
        const=_VIZ_DEFAULT,
        default=None,
        type=Path,
        help=(
            "Save detection visualization PNG. With no path, writes to cwd "
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
    default_name = f"vrcpilot_detect_viz_{stamp}.png"
    if arg is _VIZ_DEFAULT:
        return Path.cwd() / default_name
    if isinstance(arg, Path):
        if arg.is_dir():
            return arg / default_name
        return arg
    # Defensive fallback: argparse should never hand us anything else,
    # but keeping the branch keeps the type narrowing exhaustive.
    raise TypeError(f"unexpected --viz value: {arg!r}")


def _load_query(path: Path) -> NDArray[np.uint8] | None:
    """Read *path* as RGB ``uint8`` ndarray, or ``None`` on failure.

    Uses :func:`cv2.imread` (BGR) and converts to RGB so the array
    matches the layout expected by :func:`vrcpilot.detect.detect`.
    """
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb.astype(np.uint8, copy=False)


def _build_engine(*, threshold: float | None) -> DetectEngine | None:
    """Construct a :class:`TemplateDetectEngine` only when the user tuned it.

    Returns ``None`` when no tuning flag was passed so :func:`detect`
    falls back to its lazily cached default engine. Otherwise builds a
    fresh :class:`TemplateDetectEngine` with the user-provided
    ``threshold`` and library defaults for everything else.
    """
    if threshold is None:
        return None
    return TemplateDetectEngine(threshold=threshold)


def run(args: argparse.Namespace) -> int:
    """Execute the ``detect`` subcommand.

    Returns:
        ``0`` on success, ``1`` when the VRChat screenshot could not
        be captured or the query image could not be read. On failure a
        single ``vrcpilot: ...`` line is written to stderr and stdout
        stays empty.
    """
    shot: Screenshot | None = take_screenshot()
    if shot is None:
        print("vrcpilot: could not capture VRChat screenshot", file=sys.stderr)
        return 1

    query_path: Path = args.query
    query = _load_query(query_path)
    if query is None:
        print(
            f"vrcpilot: could not read query image: {query_path}",
            file=sys.stderr,
        )
        return 1

    engine = _build_engine(threshold=args.threshold)
    result = detect(shot, query, engine=engine)

    detections = list(result.detections)
    top_k: int | None = args.top_k
    if top_k is not None:
        detections = sorted(detections, key=lambda d: d.confidence, reverse=True)[
            :top_k
        ]

    viz_path = _resolve_viz_path(args.viz, now=datetime.now())
    if viz_path is not None:
        rendered = render(result)
        Image.fromarray(rendered).save(viz_path)

    detections_payload: list[dict[str, object]] = []
    for det in detections:
        polygon = [list(point) for point in det.polygon]
        bbox = list(det.bbox)
        display_polygon = [list(point) for point in result.display_polygon(det)]
        display_bbox = list(result.display_bbox(det))
        detections_payload.append(
            {
                "confidence": det.confidence,
                "scale": det.scale,
                "rotation": det.rotation,
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

    query_height, query_width = query.shape[:2]
    payload: dict[str, object] = {
        "captured_at": shot.captured_at.isoformat(),
        "window": {
            "x": shot.x,
            "y": shot.y,
            "width": shot.width,
            "height": shot.height,
            "monitor_index": shot.monitor_index,
        },
        "query": {
            "path": str(query_path.resolve()),
            "width": int(query_width),
            "height": int(query_height),
        },
        "detections": detections_payload,
    }
    if viz_path is not None:
        payload["viz_path"] = str(viz_path.resolve())

    sys.stdout.write(yaml.safe_dump(payload, sort_keys=False, default_flow_style=False))
    return 0
