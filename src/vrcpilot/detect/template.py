"""Multi-scale template-matching detection engine.

VRChat UI is rendered pixel-perfect, and feature-based detectors
struggle on its small (18-50 px) icons. A scale-grid sweep of
``cv2.matchTemplate`` reaches them reliably, so this is the default
:class:`~vrcpilot.detect.DetectEngine`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, override

import cv2
import numpy as np
from numpy.typing import NDArray

from vrcpilot.types import Polygon

from ._geometry import nms
from .base import DetectEngine, Detection


class TemplateDetectEngine(DetectEngine):
    """Multi-scale (+ optional rotation) template-matching engine.

    For each ``(scale, rotation)`` the query is transformed and
    ``cv2.matchTemplate`` (TM_CCOEFF_NORMED) produces a score map;
    positions at or above ``threshold`` become candidates, then NMS
    removes duplicates. Outperforms feature-based detectors on
    pixel-stable UI targets like VRChat's icons.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.85,
        scales: Sequence[float] = (
            0.25,
            0.3,
            0.35,
            0.4,
            0.5,
            0.6,
            0.75,
            0.9,
            1.0,
            1.25,
            1.5,
            1.8,
            2.2,
            2.6,
            3.0,
        ),
        rotations_deg: Sequence[float] = (0.0,),
        nms_iou: float = 0.3,
        max_results: int = 32,
    ) -> None:
        """Configure the scale grid, rotation list, threshold and NMS.

        Args:
            threshold: ``cv2.TM_CCOEFF_NORMED`` score cutoff; theoretical
                range ``[-1, 1]``. ``0.85`` is tuned for VRChat Launch
                Pad icons; raise toward ``0.9`` for stricter matching at
                the cost of dropping weaker hits.
            scales: Scale factors applied to the query before matching.
                The default grid spans ``0.25``-``3.0`` so a fixed query
                image can match captures across HD (1280x720) to 4K
                resolutions; spacing is denser at the low end where HD
                icons land (~0.35), coarser above ``1.0`` to keep cost
                bounded at 4K.
            rotations_deg: Rotation angles (degrees) to enumerate. The
                default ``(0.0,)`` skips rotation entirely for speed
                (VRChat UI never rotates).
            nms_iou: IoU above which a lower-confidence candidate is
                suppressed by a higher-confidence one. Defaults to
                ``0.3``.
            max_results: Cap on returned detections. Defaults to ``32``.
        """
        self._threshold = threshold
        self._scales = tuple(scales)
        self._rotations_deg = tuple(rotations_deg)
        self._nms_iou = nms_iou
        self._max_results = max_results

    @override
    def detect(
        self,
        image: NDArray[np.uint8],
        query: NDArray[np.uint8],
    ) -> Sequence[Detection]:
        """Detect instances of *query* in *image*.

        Returns an empty list when nothing clears ``threshold`` or when
        the query is larger than the image at every transform.
        """
        # matchTemplate is single-channel only; RGB would be undefined.
        image_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        query_gray = cv2.cvtColor(query, cv2.COLOR_RGB2GRAY)

        img_h, img_w = image_gray.shape[:2]
        candidates: list[Detection] = []

        for scale in self._scales:
            scaled = _resize_query(query_gray, scale)
            if scaled is None:
                continue

            for rot_deg in self._rotations_deg:
                transformed = _rotate_query(scaled, rot_deg)
                if transformed is None:
                    continue
                t_h, t_w = transformed.shape[:2]
                if t_h > img_h or t_w > img_w:
                    continue

                score_map: Any = cv2.matchTemplate(
                    image_gray, transformed, cv2.TM_CCOEFF_NORMED
                )
                ys, xs = np.where(score_map >= self._threshold)
                rotation_rad = -math.radians(rot_deg)
                for x_int, y_int in zip(xs.tolist(), ys.tolist()):
                    score = float(score_map[y_int, x_int])
                    polygon = _build_polygon(x=x_int, y=y_int, width=t_w, height=t_h)
                    candidates.append(
                        Detection(
                            polygon=polygon,
                            confidence=float(np.clip(score, 0.0, 1.0)),
                            scale=float(scale),
                            rotation=rotation_rad,
                        )
                    )

        deduped = nms(candidates, self._nms_iou)
        return deduped[: self._max_results]


def _resize_query(
    query_gray: NDArray[Any],
    scale: float,
) -> NDArray[Any] | None:
    """Resize ``query_gray``; returns ``None`` if the result is too small.

    ``NDArray[Any]`` is used because ``cv2`` returns the broader
    ``MatLike`` shape that pyright strict cannot narrow.
    """
    h, w = query_gray.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    # cv2 docs: INTER_AREA shrinks cleanly, INTER_CUBIC enlarges sharply.
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized: Any = cv2.resize(query_gray, (new_w, new_h), interpolation=interp)
    if resized.shape[0] < 2 or resized.shape[1] < 2:
        return None
    return resized


def _rotate_query(
    query_gray: NDArray[Any],
    rotation_deg: float,
) -> NDArray[Any] | None:
    """Rotate ``query_gray`` around its centre; identity rotation is a no-op.

    The output canvas is grown to the rotated bbox with 0 padding.
    """
    if rotation_deg == 0.0:
        return query_gray

    h, w = query_gray.shape[:2]
    center = (w / 2.0, h / 2.0)
    rot_mat = cv2.getRotationMatrix2D(center, rotation_deg, 1.0)
    cos = abs(float(rot_mat[0, 0]))
    sin = abs(float(rot_mat[0, 1]))
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    if new_w < 2 or new_h < 2:
        return None
    rot_mat[0, 2] += new_w / 2 - center[0]
    rot_mat[1, 2] += new_h / 2 - center[1]
    rotated: Any = cv2.warpAffine(query_gray, rot_mat, (new_w, new_h), borderValue=0)
    return rotated


def _build_polygon(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> Polygon:
    """Build a TL,TR,BR,BL polygon for a match at ``(x, y)``.

    The corners frame the rotated-template canvas (the score-map peak
    aligns with that canvas, not with the unrotated query).
    """
    return (
        (float(x), float(y)),
        (float(x + width), float(y)),
        (float(x + width), float(y + height)),
        (float(x), float(y + height)),
    )
