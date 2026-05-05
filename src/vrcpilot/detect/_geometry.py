"""Geometry helpers shared across feature-based :class:`DetectEngine` impls.

Pulled out of ``sift.py`` so that ``akaze.py`` (and any future engine that
follows the same Homography + RANSAC + NMS recipe) can reuse the same
post-processing without duplicating projection/IoU/NMS code. The module is
private to :mod:`vrcpilot.detect` — not re-exported through
``vrcpilot.detect.__init__``.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from vrcpilot.types import Polygon

from .base import Detection


def project_query_corners(
    H: NDArray[np.floating[Any]],
    width: int,
    height: int,
) -> Polygon:
    """Project the query's 4 corners through ``H`` into image coordinates.

    Returns the polygon ordered TL -> TR -> BR -> BL, matching the
    convention pinned in :data:`vrcpilot.types.Polygon`.
    """
    corners = np.array(
        [
            [0.0, 0.0],
            [float(width), 0.0],
            [float(width), float(height)],
            [0.0, float(height)],
        ],
        dtype=np.float32,
    ).reshape(-1, 1, 2)
    projected: Any = cv2.perspectiveTransform(corners, H)
    pts = projected.reshape(-1, 2)
    return (
        (float(pts[0][0]), float(pts[0][1])),
        (float(pts[1][0]), float(pts[1][1])),
        (float(pts[2][0]), float(pts[2][1])),
        (float(pts[3][0]), float(pts[3][1])),
    )


def decompose_scale_rotation(
    H: NDArray[np.floating[Any]],
) -> tuple[float, float]:
    """Recover (scale, rotation_rad) from the upper-left 2x2 of ``H``.

    Assumes a near-similarity transform (isotropic scale + rotation).
    Mild perspective distortion is tolerated by collapsing to the 2x2
    block. Returns rotation in radians (counter-clockwise positive).
    """
    a = float(H[0, 0])
    b = float(H[0, 1])
    c = float(H[1, 0])
    d = float(H[1, 1])
    rotation = math.atan2(c, a)
    scale = math.sqrt(a * a + c * c)
    # Suppress unused-variable warning while keeping the 2x2 block
    # readable as documentation of the assumption.
    _ = (b, d)
    return scale, rotation


def iou(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> float:
    """Axis-aligned IoU for ``(x, y, w, h)`` boxes.

    Returns ``0.0`` when either box has zero area.
    """
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0
    inter_x0 = max(ax, bx)
    inter_y0 = max(ay, by)
    inter_x1 = min(ax + aw, bx + bw)
    inter_y1 = min(ay + ah, by + bh)
    iw = max(0, inter_x1 - inter_x0)
    ih = max(0, inter_y1 - inter_y0)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    if union <= 0:
        return 0.0
    return inter / union


def nms(
    detections: list[Detection],
    iou_threshold: float,
) -> list[Detection]:
    """Greedy NMS in confidence-descending order.

    Higher-confidence detections suppress lower-confidence ones whose
    bbox IoU exceeds ``iou_threshold``. Order within the result is
    confidence-descending.
    """
    if not detections:
        return []
    sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: list[Detection] = []
    for det in sorted_dets:
        if any(iou(det.bbox, k.bbox) > iou_threshold for k in kept):
            continue
        kept.append(det)
    return kept
