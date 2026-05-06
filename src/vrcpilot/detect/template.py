"""Multi-scale template-matching detection engine.

VRChat UI icons such as Launch Pad entries are rendered
pixel-perfect, and at 18-50 px feature-based detectors (SIFT / AKAZE
/ ORB) cannot extract enough keypoints. In real-device e2e SIFT
recovered only 3/10 and AKAZE 0/10, so this module makes
``cv2.matchTemplate`` swept across a scale grid (with optional
rotation enumeration) the default detector.

Differences vs. SIFT / AKAZE:

* No feature extractor — the query image itself is transformed at
  each ``(scale, rotation)`` and ``cv2.matchTemplate(...,
  cv2.TM_CCOEFF_NORMED)`` produces a score map; positions at or above
  ``threshold`` become candidates.
* Polygons are not derived from a homography. The axis-aligned bbox
  carrying the chosen ``scale`` and ``rotation`` is mapped directly
  to its 4 corners.
* Everything else (NMS deduplication, ``max_results`` cap) shares the
  helpers used by SIFT / AKAZE.
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

    For each ``(scale, rotation)`` pair the query is transformed,
    ``cv2.matchTemplate`` produces a score map, and any position at or
    above ``threshold`` becomes a :class:`Detection`. Detection rate
    is higher than SIFT / AKAZE on pixel-stable targets such as
    VRChat's UI icons. An IoU-based NMS suppresses duplicates at the
    end.
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
        """Configure scale grid / rotation list / threshold / NMS.

        Args:
            threshold: ``cv2.TM_CCOEFF_NORMED`` score threshold; the
                theoretical range is ``[-1, 1]``. Real-device e2e on
                Launch Pad icons (44-105 px queries rendered at ~35 px
                on screen) showed ``0.85`` to be the sweet spot — 10/10
                detections with false positives essentially gone.
                Raising it to ``0.9`` eliminates false positives at
                the cost of dropping weak matches (around 0.85
                confidence).
            scales: Scale factors to try. Each value resizes the query
                via ``cv2.resize(query, (int(w*scale),
                int(h*scale)))`` and runs ``matchTemplate`` against
                the screenshot. The default grid spans ``0.25`` to
                ``3.0`` so the engine can cope with VRChat's HD
                (1280x720) to 4K (3840x2160) capture resolution range
                regardless of which source resolution the query images
                were cropped from. Spacing is denser (≈ 1.15-1.2x
                ratio) at the low end where Launch Pad icons typically
                land for HD captures (~0.35), and coarser (≈ 1.2x)
                above 1.0 to keep the grid size practical at 4K.
            rotations_deg: Rotation angles (degrees) to enumerate.
                When only ``0.0`` is provided, the rotation step is
                skipped entirely for speed (intended for use cases
                like VRChat UI where rotation is never expected).
                Defaults to ``(0.0,)``.
            nms_iou: IoU threshold for NMS suppression. Candidates are
                sorted by confidence descending; any whose IoU with a
                higher-confidence candidate exceeds ``nms_iou`` is
                dropped. Defaults to ``0.3``.
            max_results: Maximum number of :class:`Detection` to return.
                Defaults to ``32``.
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

        Args:
            image: RGB ``uint8`` ndarray ``(H, W, 3)`` to search.
            query: RGB ``uint8`` ndarray ``(h, w, 3)`` to look for.

        Returns:
            List of :class:`Detection`. Empty when no candidate
            exceeds the threshold, or when the query is larger than
            the image at every ``(scale, rotation)``.
        """
        # matchTemplate expects a single channel; passing RGB directly
        # yields undefined behaviour, so convert to grayscale.
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
                # matchTemplate requires template <= image.
                if t_h > img_h or t_w > img_w:
                    continue

                # TM_CCOEFF_NORMED yields [-1, 1] (1 = perfect match).
                score_map: Any = cv2.matchTemplate(
                    image_gray, transformed, cv2.TM_CCOEFF_NORMED
                )
                ys, xs = np.where(score_map >= self._threshold)
                if len(xs) == 0:
                    continue

                rotation_rad = -math.radians(rot_deg)
                for x_int, y_int in zip(xs.tolist(), ys.tolist()):
                    score = float(score_map[y_int, x_int])
                    polygon = _build_polygon(
                        x=int(x_int),
                        y=int(y_int),
                        width=t_w,
                        height=t_h,
                    )
                    candidates.append(
                        Detection(
                            polygon=polygon,
                            confidence=float(np.clip(score, 0.0, 1.0)),
                            scale=float(scale),
                            rotation=rotation_rad,
                        )
                    )

        # Suppress duplicates with NMS, then cap at max_results.
        deduped = nms(candidates, self._nms_iou)
        return deduped[: self._max_results]


def _resize_query(
    query_gray: NDArray[Any],
    scale: float,
) -> NDArray[Any] | None:
    """Resize ``query_gray`` to ``scale``, returning ``None`` if degenerate.

    The input/return types are widened to ``NDArray[Any]`` because
    ``cv2.cvtColor`` returns the broader ``MatLike`` shape and pyright
    strict cannot narrow it back to ``NDArray[uint8]``. The helper is
    private to this module so the looser typing is contained.
    """
    h, w = query_gray.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    # Best practice per cv2 docs: INTER_AREA when shrinking,
    # INTER_CUBIC when growing. Identity scale is fine with INTER_AREA.
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized: Any = cv2.resize(query_gray, (new_w, new_h), interpolation=interp)
    if resized.shape[0] < 2 or resized.shape[1] < 2:
        # matchTemplate cannot meaningfully handle a 1px template.
        return None
    return resized


def _rotate_query(
    query_gray: NDArray[Any],
    rotation_deg: float,
) -> NDArray[Any] | None:
    """Rotate ``query_gray`` around its centre by ``rotation_deg``.

    When ``rotation_deg == 0`` the rotation step is **skipped**
    entirely and the input is returned as-is (fast path). The output
    canvas is sized to the rotated bbox with 0-padding outside. Loose
    typing for the same reason as :func:`_resize_query`.
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
    """Build the 4-corner polygon of a matched template instance.

    The polygon orientation matches :data:`vrcpilot.types.Polygon`
    (TL, TR, BR, BL). The corners are the axis-aligned bbox of the
    *rotated* template at ``(x, y)``: ``cv2.matchTemplate`` returns
    integer top-left coordinates of the rotated template's bounding
    box (the canvas built by :func:`_rotate_query`), so the bbox of
    that canvas — not of the original unrotated query — is what
    aligns with the score-map peak.
    """
    return (
        (float(x), float(y)),
        (float(x + width), float(y)),
        (float(x + width), float(y + height)),
        (float(x), float(y + height)),
    )
