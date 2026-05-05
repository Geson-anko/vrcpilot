"""画像クエリで UI 要素位置を検出する vrcpilot.detect パッケージ。

Phase 4 で公開 API が出揃うまでは骨格のみ。
"""

from __future__ import annotations

from .base import DetectEngine, Detection
from .sift import SiftDetectEngine

__all__ = ["DetectEngine", "Detection", "SiftDetectEngine"]
