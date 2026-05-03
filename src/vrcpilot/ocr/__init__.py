"""OCR primitives for VRChat screen analysis.

This package exposes the swappable :class:`OCREngine` ABC together
with the :class:`OCRWord` value type. Concrete backends (e.g.
:class:`vrcpilot.ocr.rapidocr.RapidOCREngine`) and high-level helpers
are added in subsequent layers.
"""

from __future__ import annotations

from .base import OCREngine, OCRWord

__all__ = ["OCREngine", "OCRWord"]
