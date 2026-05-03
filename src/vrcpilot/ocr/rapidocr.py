"""Rapidocr バックエンドの :class:`OCREngine` 実装。

`rapidocr` パッケージをコンストラクタ内で遅延 import するため、
本モジュール自体のロードでは外部 `rapidocr` を解決しない。
これにより `[ocr]` extra 未導入時でも
``from vrcpilot.ocr import OCREngine`` 等は問題なく動作する。
"""

from __future__ import annotations

from typing import Any, override

import numpy as np
from numpy.typing import NDArray

from .base import OCREngine, OCRWord, Polygon


class RapidOCREngine(OCREngine):
    """Rapidocr (PP-OCRv4) バックエンドの具象 :class:`OCREngine`。

    コンストラクタ内で ``from rapidocr import RapidOCR`` を遅延 import
    する。`[ocr]` extra 未導入で本クラスをインスタンス化しようとすると
    :class:`ImportError` が送出される。
    """

    def __init__(self, *, params: dict[str, Any] | None = None) -> None:
        """Construct the underlying rapidocr engine.

        Args:
            params: ``RapidOCR(params=...)`` にそのまま転送される設定
                辞書。``None`` のときはデフォルト構成 (PP-OCRv4) で
                動作する。

        Raises:
            ImportError: ``rapidocr`` がインストールされていない場合。
        """
        try:
            from rapidocr import RapidOCR  # type: ignore[reportMissingTypeStubs]
        except ImportError as e:
            raise ImportError(
                "rapidocr is required for RapidOCREngine. "
                "Install with: pip install vrcpilot[ocr]"
            ) from e

        # rapidocr 自体に型 stub が無いため Any で受ける
        self._engine: Any = RapidOCR(params=params)

    @override
    def recognize(self, image: NDArray[np.uint8]) -> list[OCRWord]:
        """Run rapidocr on an RGB ``uint8`` image.

        Args:
            image: ``(H, W, 3)`` の RGB uint8 ndarray。
                BGR 変換は不要 (rapidocr 3.x は RGB ndarray を
                直接受け取る)。

        Returns:
            検出された :class:`OCRWord` の list。検出ゼロのときは
            空 list を返す。
        """
        result: Any = self._engine(image)

        # rapidocr v3.x: 検出ゼロのとき .boxes / .txts / .scores が
        # それぞれ None になる。3 つすべて存在するときのみ語を構築。
        boxes: Any = getattr(result, "boxes", None)
        txts: Any = getattr(result, "txts", None)
        scores: Any = getattr(result, "scores", None)
        if boxes is None or txts is None or scores is None:
            return []

        words: list[OCRWord] = []
        # 3 配列の長さは rapidocr 仕様上揃うが、防御的に min を取る
        n = min(len(boxes), len(txts), len(scores))
        for i in range(n):
            box = boxes[i]
            polygon: Polygon = (
                (float(box[0][0]), float(box[0][1])),
                (float(box[1][0]), float(box[1][1])),
                (float(box[2][0]), float(box[2][1])),
                (float(box[3][0]), float(box[3][1])),
            )
            words.append(
                OCRWord(
                    text=str(txts[i]),
                    polygon=polygon,
                    confidence=float(scores[i]),
                )
            )
        return words
