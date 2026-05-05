"""SIFT-based detection engine.

OpenCV main module (since 4.4) ships SIFT, so we depend only on
``opencv-python`` (already in core deps). Scale and rotation
invariance are handled natively by SIFT -- no template grid sweep.
Multiple instances of the same query in one screenshot are recovered
by an iterative RANSAC loop that masks out inlier keypoints between
rounds.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, override

import cv2
import numpy as np
from numpy.typing import NDArray

from vrcpilot.types import Polygon

from .base import DetectEngine, Detection


class SiftDetectEngine(DetectEngine):
    """SIFT + FLANN + RANSAC Homography ベースの :class:`DetectEngine`.

    SIFT 特徴点を抽出し FLANN (KDTree) でマッチング、Lowe's ratio
    test で良マッチを絞り、``cv2.findHomography`` で RANSAC を回す。
    インライアを除外して再度 RANSAC をかけることで同一クエリの複数
    インスタンスを順次拾い、最後に IoU ベースの NMS で重複候補を
    抑制する。Scale / rotation は Homography の上左 2x2 から復元する。
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
            ratio: Lowe's ratio test の閾値。``m.distance < ratio *
                n.distance`` を満たす knn=2 マッチのみを残す。
                デフォルト ``0.75``。
            min_inliers: Homography が成立したと見なす最小インライア
                数。次ラウンドの継続条件にもなる。デフォルト ``8``。
            ransac_reproj_threshold: ``cv2.findHomography`` の
                ``ransacReprojThreshold``。射影誤差 (px) の閾値。
                デフォルト ``5.0``。
            nms_iou: NMS で重複と判定する IoU 閾値。confidence 降順で
                ソートしたうえで、より高い候補と IoU が ``nms_iou`` を
                超えるものを除外する。デフォルト ``0.3``。
            max_results: 出力する :class:`Detection` の最大数。
                デフォルト ``32``。
            sift_n_features: ``cv2.SIFT_create(nfeatures=...)`` に渡す
                上限。``0`` (デフォルト) は OpenCV の制限なし設定。
        """
        self._ratio = ratio
        self._min_inliers = min_inliers
        self._ransac_reproj_threshold = ransac_reproj_threshold
        self._nms_iou = nms_iou
        self._max_results = max_results
        # cv2 自体に型 stub が薄いため Any で受ける
        # cv2 stubs do not expose SIFT_create / FlannBasedMatcher kwargs,
        # so we suppress strict-mode complaints at the call site.
        self._sift: Any = cv2.SIFT_create(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            nfeatures=sift_n_features
        )
        # KDTree-based FLANN: SIFT (float descriptors) と相性が良い
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
        """``image`` 中から ``query`` のインスタンスを検出する。

        Args:
            image: 検索対象の RGB ``uint8`` ndarray (``(H, W, 3)``)。
            query: 検出したいクエリ画像の RGB ``uint8`` ndarray
                (``(h, w, 3)``)。

        Returns:
            :class:`Detection` の list。SIFT 特徴点が片側でも 2 点
            未満、もしくは Homography が成立しなかった場合は空 list。
        """
        # SIFT は grayscale 入力前提
        image_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        query_gray = cv2.cvtColor(query, cv2.COLOR_RGB2GRAY)

        kp_q, des_q = self._sift.detectAndCompute(query_gray, None)
        kp_i, des_i = self._sift.detectAndCompute(image_gray, None)

        # FLANN knnMatch は両側 >= 2 点必須
        if des_q is None or des_i is None:
            return []
        if len(kp_q) < 2 or len(kp_i) < 2:
            return []

        # knn=2 と Lowe's ratio test で初期 good matches を作る
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

        # インライアを除外しながら同一クエリの多重インスタンスを順次拾う
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

            polygon = _project_query_corners(H, w, h)
            scale, rotation = _decompose_scale_rotation(H)
            confidence = float(np.clip(inlier_count / len(good_matches), 0.0, 1.0))

            candidates.append(
                Detection(
                    polygon=polygon,
                    confidence=confidence,
                    scale=scale,
                    rotation=rotation,
                )
            )

            # 同じインスタンスを 2 度拾わないようインライアを除外する
            good_matches = [m for m, keep in zip(good_matches, inlier_mask) if not keep]

        # 重複候補を NMS で抑制してから max_results で打ち切り
        deduped = _nms(candidates, self._nms_iou)
        return deduped[: self._max_results]


def _project_query_corners(
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


def _decompose_scale_rotation(
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


def _iou(
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


def _nms(
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
        if any(_iou(det.bbox, k.bbox) > iou_threshold for k in kept):
            continue
        kept.append(det)
    return kept
