"""Detection engine abstract base class and the :class:`Detection` value type.

All coordinates handled here are *image-local* — the origin is the
top-left of the captured image, not the desktop. Conversion to
desktop-absolute coordinates is the responsibility of higher-level
helpers (e.g. ``DetectResult.display_polygon``), not the engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from vrcpilot.types import Polygon


@dataclass(frozen=True)
class Detection:
    """Single detection in image-local coordinates.

    Attributes:
        polygon: 4 頂点 (TL, TR, BR, BL)。Homography 等で射影された
            一般四角形を許容する。
        confidence: 0.0–1.0 の信頼度（マッチングのインライア比率等）。
        scale: クエリ画像基準のスケール（1.0 = 等倍）。
        rotation: ラジアン (反時計回り正)。
    """

    polygon: Polygon
    confidence: float
    scale: float
    rotation: float

    def __post_init__(self) -> None:
        # Static typing pins the length at 4, but runtime tuple-building
        # callers can still slip past. Guard at construction time too,
        # mirroring OCRWord.__post_init__.
        if len(self.polygon) != 4:
            raise ValueError(
                f"Detection.polygon must have exactly 4 points; "
                f"got {len(self.polygon)}"
            )

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """Axis-aligned bounding box ``(x, y, width, height)``.

        ``width`` and ``height`` are always non-negative (zero for a
        degenerate polygon).
        """
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)
        return (
            int(round(x_min)),
            int(round(y_min)),
            int(round(x_max - x_min)),
            int(round(y_max - y_min)),
        )

    @property
    def center(self) -> tuple[float, float]:
        """Mean of polygon vertices as ``(x, y)`` floats."""
        mean_x = sum(p[0] for p in self.polygon) / 4
        mean_y = sum(p[1] for p in self.polygon) / 4
        return (float(mean_x), float(mean_y))


class DetectEngine(ABC):
    """差し替え可能な検出バックエンドの抽象基底。

    ユーザーは自前のサブクラスを定義することで SIFT 以外のエンジン (ORB、テンプレートマッチ、商用 API 等) を差し込める。
    """

    @abstractmethod
    def detect(
        self,
        image: NDArray[np.uint8],
        query: NDArray[np.uint8],
    ) -> Sequence[Detection]:
        """``(H, W, 3)`` uint8 RGB の screenshot から *query* を検出する。

        Args:
            image: 検索対象の RGB 画像。``np.uint8`` dtype 必須。
            query: 検出したいクエリ画像。同じく ``(h, w, 3)`` uint8 RGB。

        Returns:
            検出された :class:`Detection` の列。座標はすべて image-local
            (``image`` 左上原点)。デスクトップ座標への変換は呼び出し側
            の責務。
        """
