"""Multi-scale template-matching detection engine.

VRChat の Launch Pad 等の UI アイコンはピクセルパーフェクトに描画
されており、18-50 px の小さなクエリでは特徴点ベース (SIFT / AKAZE /
ORB) が満足な keypoint を出せない。実機 e2e でも SIFT が 10 件中 3
件、AKAZE が 0 件しか検出できなかったため、本モジュールでは
``cv2.matchTemplate`` を scale grid 上で sweep し、必要に応じて
rotation も列挙するシンプルな実装をデフォルトに据える。

差分 (vs. SIFT / AKAZE):

* 抽出器なし — クエリ画像そのものを各 scale (× rotation) に変換し
  ``cv2.matchTemplate(..., cv2.TM_CCOEFF_NORMED)`` で score map を
  作り、``threshold`` 以上の位置を候補化する。
* polygon は :func:`._geometry.project_query_corners` を使わず、
  scale + rotation を持つ axis-aligned 矩形を 4 隅に展開して直接
  写像する (Homography は介在しない)。
* それ以外 (NMS による重複抑制、``max_results`` での打ち切り) は
  SIFT / AKAZE と同じ helpers を共有する。
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
    """Multi-scale (+ optional rotation) テンプレートマッチ実装。

    各 ``(scale, rotation)`` ペアについてクエリを変換した上で
    ``cv2.matchTemplate`` で score map を作り、``threshold`` 以上の
    位置を ``Detection`` として収集する。VRChat の UI アイコンの
    ようにピクセルレベルで安定描画される対象に対しては SIFT / AKAZE
    より検出率が高い。最後に IoU ベースの NMS で重複候補を抑制する。
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
            0.7,
            0.8,
            0.9,
            1.0,
            1.25,
            1.5,
        ),
        rotations_deg: Sequence[float] = (0.0,),
        nms_iou: float = 0.3,
        max_results: int = 32,
    ) -> None:
        """Configure scale grid / rotation list / threshold / NMS.

        Args:
            threshold: ``cv2.TM_CCOEFF_NORMED`` の score 閾値。``[-1,
                1]`` が理論域。VRChat の Launch Pad アイコン (44-105 px
                クエリを画面上 ~35 px に縮小して描画) で実機 e2e を
                スイープした結果、``0.85`` で 10/10 検出かつ false
                positive がほぼ消える sweet spot だったので採用。
                ``0.9`` まで上げると誤検出は 0 になる代わり弱マッチ
                (confidence 0.85 付近のもの) が落ちるトレードオフ。
            scales: 試行するスケール係数の列。各値で
                ``cv2.resize(query, (int(w*scale), int(h*scale)))``
                を作って matchTemplate にかける。デフォルトは
                ``0.25`` から ``1.5`` までを 12 段でカバーする。
                Launch Pad 上の icon は 100 px クエリに対して画面上
                35 px 程度 (scale ≈ 0.35) で表示されるため lower
                bound は 0.25 まで広げてある。
            rotations_deg: 試行する回転角 (度) の列。``0.0`` のみ
                指定された場合、回転変換そのものを skip して高速に
                処理する (VRChat UI のようにそもそも回転しない用途
                を想定)。デフォルト ``(0.0,)``。
            nms_iou: NMS で重複と判定する IoU 閾値。confidence 降順
                でソートしたうえで、より高い候補と IoU が ``nms_iou``
                を超えるものを除外する。デフォルト ``0.3``。
            max_results: 出力する :class:`Detection` の最大数。
                デフォルト ``32``。
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
        """``image`` 中から ``query`` のインスタンスを検出する。

        Args:
            image: 検索対象の RGB ``uint8`` ndarray (``(H, W, 3)``)。
            query: 検出したいクエリ画像の RGB ``uint8`` ndarray
                (``(h, w, 3)``)。

        Returns:
            :class:`Detection` の list。閾値超過候補が無い、または
            すべての (scale, rotation) でクエリが image より大きく
            なる場合は空 list。
        """
        # matchTemplate は単チャネル前提。RGB のまま渡すと結果が
        # 不定なので grayscale 化する。
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
                # matchTemplate は template <= image を要求する
                if t_h > img_h or t_w > img_w:
                    continue

                # TM_CCOEFF_NORMED は [-1, 1] (1 が完全一致)
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
                        rotation_deg=rot_deg,
                    )
                    candidates.append(
                        Detection(
                            polygon=polygon,
                            confidence=float(np.clip(score, 0.0, 1.0)),
                            scale=float(scale),
                            rotation=rotation_rad,
                        )
                    )

        # 重複候補を NMS で抑制してから max_results で打ち切り
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
    # 縮小は INTER_AREA、拡大は INTER_CUBIC が一般的なベストプラ
    # クティス (cv2 ドキュメント参照)。等倍は INTER_AREA で問題なし。
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized: Any = cv2.resize(query_gray, (new_w, new_h), interpolation=interp)
    if resized.shape[0] < 2 or resized.shape[1] < 2:
        # matchTemplate は 1px template を実用上扱えない。安全側に倒す。
        return None
    return resized


def _rotate_query(
    query_gray: NDArray[Any],
    rotation_deg: float,
) -> NDArray[Any] | None:
    """Rotate ``query_gray`` around its centre by ``rotation_deg``.

    ``rotation_deg == 0`` のときは回転変換を **skip** して入力を
    そのまま返す (高速化)。回転後のキャンバスは回転後の bbox に
    リサイズされ、外側は 0 padding。型が ``NDArray[Any]`` で広く
    なっている理由は :func:`_resize_query` と同じ。
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
    rotation_deg: float,
) -> Polygon:
    """Build the 4-corner polygon of a matched template instance.

    The polygon orientation matches :data:`vrcpilot.types.Polygon`
    (TL, TR, BR, BL). When ``rotation_deg == 0`` the corners are the
    axis-aligned bbox of the matched region; otherwise the corners
    are the bbox of the *rotated* template at ``(x, y)`` (this matches
    how the template was prepared by :func:`_rotate_query`).
    """
    return (
        (float(x), float(y)),
        (float(x + width), float(y)),
        (float(x + width), float(y + height)),
        (float(x), float(y + height)),
    )
