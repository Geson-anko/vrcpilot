"""``vrcpilot detect`` subcommand.

Runs image-query detection against the current VRChat window and emits
a YAML document on stdout (image-local + desktop-absolute coordinates
per detection). ``--viz`` additionally writes an annotated PNG.

YAML keys are emitted in a fixed order (``sort_keys=False``):
``captured_at``, ``window``, ``query``, ``detections``, optional
``viz_path``. Each detection carries ``confidence`` / ``scale`` /
``rotation`` plus ``pos`` (image-local) and ``display_pos``
(desktop-absolute) ``polygon`` and ``bbox``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from argcomplete.completers import FilesCompleter
from numpy.typing import NDArray
from PIL import Image

from vrcpilot.detect import (
    DetectEngine,
    Detection,
    TemplateDetectEngine,
    detect,
    render,
)
from vrcpilot.screenshot import Screenshot, take_screenshot

from ._common import SubParsersAction, attach_completer

# Sentinel for "--viz with no argument" — distinct from "--viz absent"
# (``None``) and "--viz <path>" (``Path``).
_VIZ_DEFAULT: object = object()


def register(subparsers: SubParsersAction) -> None:
    """Register the ``detect`` subparser."""
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
    """Resolve ``args.viz`` to an output path.

    ``None`` propagates (no visualization requested). The default
    filename uses *now* so tests can pin the timestamp.
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
    raise TypeError(f"unexpected --viz value: {arg!r}")


def _load_query(path: Path) -> NDArray[np.uint8] | None:
    """Read *path* as RGB ``uint8`` ndarray, or ``None`` on failure."""
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb.astype(np.uint8, copy=False)


def _build_engine(*, threshold: float | None) -> DetectEngine | None:
    """Tuned :class:`TemplateDetectEngine`, or ``None`` to use the default."""
    if threshold is None:
        return None
    return TemplateDetectEngine(threshold=threshold)


def run(args: argparse.Namespace) -> int:
    """Execute the ``detect`` subcommand.

    Returns ``0`` on success, ``1`` when the screenshot or query image
    cannot be read (a ``vrcpilot: ...`` line is written to stderr and
    stdout stays empty).
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

    detections: Sequence[Detection] = result.detections
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
