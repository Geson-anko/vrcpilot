"""Integration-real tests for :class:`vrcpilot.ocr.rapidocr.RapidOCREngine`.

Hits the actual rapidocr engine (PP-OCRv4 onnx). Skipped when the
optional ``[ocr]`` extra is not installed. The first test invocation
will trigger a one-time ~15MB model download into the venv's
``rapidocr/models/`` directory; subsequent runs reuse the cache.
"""

from __future__ import annotations

from importlib.util import find_spec

import pytest

if find_spec("rapidocr") is None or find_spec("onnxruntime") is None:
    pytest.skip(
        "rapidocr/onnxruntime not installed; install with [ocr] extra",
        allow_module_level=True,
    )

# noqa: E402 — module-level skip must precede these imports.
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from vrcpilot.ocr import OCRWord, RapidOCREngine  # noqa: E402


def _hello_image() -> np.ndarray:
    """Render the literal text ``Hello`` onto a 320x80 white RGB canvas."""
    img = Image.new("RGB", (320, 80), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Default PIL font is small but large-enough for OCR to pick up
    # consistently; we draw the text twice with offset to thicken
    # strokes so the small bitmap font is more legible.
    text = "Hello"
    for ox, oy in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        draw.text((30 + ox, 20 + oy), text, fill=(0, 0, 0))
    return np.array(img, dtype=np.uint8)


class TestRapidOCREngineHappyPath:
    def test_recognizes_hello_text(self):
        engine = RapidOCREngine()
        words = engine.recognize(_hello_image())

        # At least one detection
        assert len(words) >= 1
        # All elements should be OCRWord instances
        for w in words:
            assert isinstance(w, OCRWord)

        # Concatenate texts case-insensitively to tolerate slight
        # variations (e.g. "hello", "Hello", "HELLO").
        joined = " ".join(w.text for w in words).lower()
        assert "hello" in joined

        # Confidence: at least one detection should be reasonably
        # confident on a clean black-on-white synthetic image.
        best = max(w.confidence for w in words)
        assert best > 0.5

        # bbox for any detection should land within image bounds.
        for w in words:
            x, y, bw, bh = w.bbox
            assert 0 <= x <= 320
            assert 0 <= y <= 80
            assert bw >= 0
            assert bh >= 0
            assert x + bw <= 320 + 1  # allow 1px round-off
            assert y + bh <= 80 + 1


class TestRapidOCREngineEmpty:
    def test_blank_image_returns_empty_list(self):
        engine = RapidOCREngine()
        blank = np.full((100, 100, 3), 255, dtype=np.uint8)
        words = engine.recognize(blank)
        assert words == []
