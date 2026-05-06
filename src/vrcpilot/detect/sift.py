"""SIFT-based detection engine (opt-in; kept for textured queries).

OpenCV main module (since 4.4) ships SIFT, so we depend only on
``opencv-python`` (already in core deps). Scale and rotation
invariance are handled natively by SIFT — no template grid sweep.
Multiple instances of the same query in one screenshot are recovered
by an iterative RANSAC loop that masks out inlier keypoints between
rounds.

Not the default. In real-device e2e against VRChat's small UI icons,
SIFT detected 3/10 (AKAZE 0/10, Template 10/10), and
:class:`.template.TemplateDetectEngine` is fundamentally better suited
to the pixel-perfect rendering of the UI. This engine is kept for
texture-rich targets (thumbnails, avatar panels, world images, etc.)
where SIFT's scale/rotation invariance pays off.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, override

import cv2
import numpy as np
from numpy.typing import NDArray

from ._geometry import decompose_scale_rotation, nms, project_query_corners
from .base import DetectEngine, Detection


class SiftDetectEngine(DetectEngine):
    """SIFT + FLANN + RANSAC homography :class:`DetectEngine`.

    Extracts SIFT keypoints, matches via FLANN (KDTree), filters with
    Lowe's ratio test, and runs ``cv2.findHomography`` under RANSAC.
    Multiple instances of the same query are recovered by removing
    inliers and re-running RANSAC; an IoU-based NMS suppresses
    duplicates at the end. Scale and rotation are recovered from the
    upper-left 2x2 of the homography.
    """

    def __init__(
        self,
        *,
        ratio: float = 0.75,
        min_inliers: int = 8,
        ransac_reproj_threshold: float = 5.0,
        nms_iou: float = 0.3,
        max_results: int = 32,
        sift_n_features: int = 0,
    ) -> None:
        """Configure SIFT/FLANN/RANSAC/NMS thresholds.

        Args:
            ratio: Lowe's ratio test threshold. Only knn=2 matches with
                ``m.distance < ratio * n.distance`` are kept. Defaults
                to ``0.75``.
            min_inliers: Minimum inlier count for a homography to be
                accepted; also gates iteration of the next round.
                Defaults to ``8``.
            ransac_reproj_threshold: ``ransacReprojThreshold`` (px) for
                ``cv2.findHomography``. Defaults to ``5.0``.
            nms_iou: IoU threshold for NMS suppression. Candidates are
                sorted by confidence descending; any whose IoU with a
                higher-confidence candidate exceeds ``nms_iou`` is
                dropped. Defaults to ``0.3``.
            max_results: Maximum number of :class:`Detection` to return.
                Defaults to ``32``.
            sift_n_features: Forwarded to
                ``cv2.SIFT_create(nfeatures=...)``. ``0`` (default) is
                OpenCV's "no limit" setting.
        """
        self._ratio = ratio
        self._min_inliers = min_inliers
        self._ransac_reproj_threshold = ransac_reproj_threshold
        self._nms_iou = nms_iou
        self._max_results = max_results
        # cv2 stubs do not expose SIFT_create / FlannBasedMatcher kwargs,
        # so we suppress strict-mode complaints at the call site.
        self._sift: Any = cv2.SIFT_create(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            nfeatures=sift_n_features
        )
        # KDTree-based FLANN pairs well with SIFT's float descriptors.
        index_params: dict[str, bool | int | float | str] = {
            "algorithm": 1,
            "trees": 5,
        }
        search_params: dict[str, bool | int | float | str] = {"checks": 50}
        self._matcher: Any = cv2.FlannBasedMatcher(index_params, search_params)

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
            List of :class:`Detection`. Empty when either side has
            fewer than 2 SIFT keypoints, or when no homography passed
            RANSAC.
        """
        # SIFT operates on grayscale.
        image_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        query_gray = cv2.cvtColor(query, cv2.COLOR_RGB2GRAY)

        kp_q, des_q = self._sift.detectAndCompute(query_gray, None)
        kp_i, des_i = self._sift.detectAndCompute(image_gray, None)

        # FLANN knnMatch needs at least 2 keypoints on each side.
        if des_q is None or des_i is None:
            return []
        if len(kp_q) < 2 or len(kp_i) < 2:
            return []

        # knn=2 plus Lowe's ratio test produces the initial good matches.
        raw_matches: Any = self._matcher.knnMatch(des_q, des_i, k=2)
        good_matches: list[Any] = []
        for pair in raw_matches:
            if len(pair) < 2:
                continue
            m, n = pair[0], pair[1]
            if m.distance < self._ratio * n.distance:
                good_matches.append(m)

        h, w = query_gray.shape[:2]
        candidates: list[Detection] = []

        # Recover multiple instances by stripping inliers between rounds.
        while len(good_matches) >= self._min_inliers:
            src_pts = np.array(
                [kp_q[m.queryIdx].pt for m in good_matches],
                dtype=np.float32,
            ).reshape(-1, 1, 2)
            dst_pts = np.array(
                [kp_i[m.trainIdx].pt for m in good_matches],
                dtype=np.float32,
            ).reshape(-1, 1, 2)

            if len(src_pts) < 4:
                break

            homography_result: Any = cv2.findHomography(
                src_pts,
                dst_pts,
                cv2.RANSAC,
                self._ransac_reproj_threshold,
            )
            H, mask = homography_result
            if H is None or mask is None:
                break

            inlier_mask = mask.ravel().astype(bool)
            inlier_count = int(inlier_mask.sum())
            if inlier_count < self._min_inliers:
                break

            polygon = project_query_corners(H, w, h)
            scale, rotation = decompose_scale_rotation(H)
            confidence = float(np.clip(inlier_count / len(good_matches), 0.0, 1.0))

            candidates.append(
                Detection(
                    polygon=polygon,
                    confidence=confidence,
                    scale=scale,
                    rotation=rotation,
                )
            )

            # Drop inliers so the same instance is not picked up twice.
            good_matches = [m for m, keep in zip(good_matches, inlier_mask) if not keep]

        # Suppress duplicates with NMS, then cap at max_results.
        deduped = nms(candidates, self._nms_iou)
        return deduped[: self._max_results]
