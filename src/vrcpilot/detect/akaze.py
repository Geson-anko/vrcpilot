"""AKAZE-based detection engine (opt-in; kept for comparison / future use).

AKAZE は OpenCV の main module 同梱の特徴点抽出器で、SIFT と比べて
低テクスチャ画像でも keypoint が出やすい設計。ただし VRChat の Launch
Pad 等 18-51 px の小型 UI アイコンに対しては実機 e2e で **0/10** 件と
事実上機能せず、``threshold`` を OpenCV デフォルト ``0.001`` から
``0.0001`` まで一桁下げても有効解は得られなかった (フィーチャースケー
ル自体が画像に対して大きすぎる)。同じ条件で SIFT は 3/10、Template は
10/10 出るため :class:`.template.TemplateDetectEngine` をデフォルトに
据えている (詳細は :func:`.detect._get_default_engine`)。

本モジュールは「より大きい / よりテクスチャのある対象 (アバターパネル
全体、ワールドサムネイル等) で AKAZE 由来のスケール / 回転不変性が
役立つ場面」のための opt-in バックエンドとして残す。

差分 (vs. SiftDetectEngine):

* 抽出器: ``cv2.AKAZE_create()``
* descriptor: AKAZE デフォルトは M-LDB (バイナリ)。FLANN KDTree は
  float 専用なので使えず、``cv2.BFMatcher(cv2.NORM_HAMMING)`` の
  knnMatch に切り替える
* それ以外 (Lowe's ratio test → 反復 RANSAC → polygon 復元 → NMS) は
  SIFT と同じパイプラインを共有 (helpers は :mod:`._geometry`)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, override

import cv2
import numpy as np
from numpy.typing import NDArray

from ._geometry import decompose_scale_rotation, nms, project_query_corners
from .base import DetectEngine, Detection


class AkazeDetectEngine(DetectEngine):
    """AKAZE + BFMatcher(Hamming) + 反復 RANSAC ベースの :class:`DetectEngine`.

    AKAZE 特徴点を抽出し、BFMatcher(Hamming) で knn=2 マッチング、
    Lowe's ratio test で良マッチを絞り、``cv2.findHomography`` で
    RANSAC を回す。インライアを除外して再度 RANSAC をかけることで
    同一クエリの複数インスタンスを順次拾い、最後に IoU ベースの NMS
    で重複候補を抑制する。Scale / rotation は Homography の上左 2x2
    から復元する。

    VRChat の小型 UI アイコンでは keypoint がほぼ抽出できず実用解に
    ならない (モジュール docstring 参照)。テクスチャ豊富なクエリ向け
    の opt-in バックエンドとして扱うこと。
    """

    def __init__(
        self,
        *,
        ratio: float = 0.75,
        min_inliers: int = 8,
        ransac_reproj_threshold: float = 5.0,
        nms_iou: float = 0.3,
        max_results: int = 32,
        threshold: float = 0.001,
    ) -> None:
        """Configure AKAZE/BFMatcher/RANSAC/NMS thresholds.

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
            threshold: AKAZE の応答閾値 (``cv2.AKAZE_create(threshold=...)``)。
                デフォルト ``0.001`` は OpenCV の標準値。VRChat の小型
                UI アイコン (18-51 px) では実機 e2e で本値を ``0.0001``
                まで一桁下げても有効な keypoint が抽出できず 0/10 件
                だったため、本エンジンはデフォルトに採用していない
                (Template Engine がデフォルト)。``threshold`` 引数は
                より大きい / テクスチャ豊富な対象向けの実験フックとして
                残してある。
        """
        self._ratio = ratio
        self._min_inliers = min_inliers
        self._ransac_reproj_threshold = ransac_reproj_threshold
        self._nms_iou = nms_iou
        self._max_results = max_results
        # cv2 自体に型 stub が薄いため Any で受ける。
        # AKAZE の descriptor デフォルトは M-LDB (バイナリ) なので、
        # FLANN KDTree ではなく BFMatcher(Hamming) を使う。
        self._akaze: Any = cv2.AKAZE_create(threshold=threshold)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        self._matcher: Any = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

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
            :class:`Detection` の list。AKAZE 特徴点が片側でも 2 点
            未満、もしくは Homography が成立しなかった場合は空 list。
        """
        # AKAZE は grayscale 入力前提
        image_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        query_gray = cv2.cvtColor(query, cv2.COLOR_RGB2GRAY)

        kp_q, des_q = self._akaze.detectAndCompute(query_gray, None)
        kp_i, des_i = self._akaze.detectAndCompute(image_gray, None)

        # knnMatch は両側 >= 2 点必須
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

            # 同じインスタンスを 2 度拾わないようインライアを除外する
            good_matches = [m for m, keep in zip(good_matches, inlier_mask) if not keep]

        # 重複候補を NMS で抑制してから max_results で打ち切り
        deduped = nms(candidates, self._nms_iou)
        return deduped[: self._max_results]
