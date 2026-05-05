"""画像クエリで UI 要素位置を検出する vrcpilot.detect パッケージ。

Public surface:

* :class:`DetectEngine` — 差し替え可能なバックエンドの ABC。
* :class:`Detection` — 検出 1 件の値型 (image-local)。
* :class:`DetectResult` — screenshot + query + detections のバンドル。
  デスクトップ絶対座標へ変換するヘルパを提供する。
* :class:`TemplateDetectEngine` — デフォルトの multi-scale テンプレート
  マッチ実装。
* :class:`AkazeDetectEngine` — AKAZE ベースの opt-in 実装（特徴点向き）。
* :class:`SiftDetectEngine` — SIFT ベースの opt-in 実装。
* :func:`detect` — :class:`DetectEngine` を :class:`Screenshot` と
  クエリ画像に対して実行し結果をまとめる関数。
* :func:`render` — :class:`DetectResult` を screenshot 上に重ね描き
  した RGB ndarray を返す。
* :data:`Polygon` — 4 頂点ポリゴンの型エイリアス。独自エンジンを書く
  ユーザーが同じ形状で型注釈を付けられるよう再エクスポート。
"""

from __future__ import annotations

from vrcpilot.types import Polygon

from .akaze import AkazeDetectEngine
from .base import DetectEngine, Detection
from .detect import DetectResult, detect
from .sift import SiftDetectEngine
from .template import TemplateDetectEngine
from .visualize import render

__all__ = [
    "AkazeDetectEngine",
    "DetectEngine",
    "DetectResult",
    "Detection",
    "Polygon",
    "SiftDetectEngine",
    "TemplateDetectEngine",
    "detect",
    "render",
]
