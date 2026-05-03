"""High-level :func:`recognize` helper and the :class:`OCRResult` value type.

:class:`OCRResult` ties a :class:`Screenshot` to the
:class:`OCRWord` list produced by an :class:`OCREngine` so that callers
can move between image-local and desktop-absolute coordinates without
re-doing the geometry math.

:func:`recognize` is a thin pure-OCR step: the caller supplies the
:class:`Screenshot` (typically from
:func:`vrcpilot.screenshot.take_screenshot`), and this function only
runs the engine and packages the result. Capture and OCR are kept as
separate concerns so the same OCR pipeline can be replayed against
existing images, fed cropped regions, or driven by a custom capture
source.

The module-level ``_default_engine`` cache keeps :func:`recognize`
cheap on repeat calls: the (heavy) :class:`RapidOCREngine` is built
exactly once per process when the user does not pass an ``engine``
argument. Tests that need a fresh cache should reset the variable
explicitly (``vrcpilot.ocr.recognize._default_engine = None``).
"""

from __future__ import annotations

from dataclasses import dataclass

from vrcpilot.screenshot import Screenshot

from .base import OCREngine, OCRWord
from .rapidocr import RapidOCREngine
from .types import Polygon


@dataclass(frozen=True, eq=False)
class OCRResult:
    """Captured screenshot bundled with its OCR detections.

    ``eq=False`` mirrors :class:`vrcpilot.screenshot.Screenshot`:
    ``screenshot.image`` is a numpy ``ndarray`` and element-wise
    ``__eq__`` cannot back the dataclass-synthesised equality.

    Attributes:
        screenshot: The :class:`Screenshot` the words were extracted
            from. ``screenshot.x`` / ``screenshot.y`` are the desktop
            offsets used by :meth:`display_polygon` and
            :meth:`display_bbox`.
        words: Detected :class:`OCRWord` tuple. Always a ``tuple`` so
            the sequence is immutable from the caller's point of view
            (matches the frozen-dataclass posture of :class:`OCRWord`).
    """

    screenshot: Screenshot
    words: tuple[OCRWord, ...]

    def display_polygon(self, word: OCRWord) -> Polygon:
        """Return ``word.polygon`` shifted to desktop-absolute coordinates.

        Each ``(x, y)`` corner is offset by
        ``(screenshot.x, screenshot.y)``; values stay ``float``.

        Membership in ``self.words`` is **not** checked: the method is
        a pure geometric transform driven by ``word.polygon``, so a
        caller who builds an ``OCRWord`` separately can still translate
        it.
        """
        dx = float(self.screenshot.x)
        dy = float(self.screenshot.y)
        p0, p1, p2, p3 = word.polygon
        return (
            (p0[0] + dx, p0[1] + dy),
            (p1[0] + dx, p1[1] + dy),
            (p2[0] + dx, p2[1] + dy),
            (p3[0] + dx, p3[1] + dy),
        )

    def display_bbox(self, word: OCRWord) -> tuple[int, int, int, int]:
        """Return ``word.bbox`` shifted to desktop-absolute coordinates.

        ``(x, y)`` move by the screenshot offset; ``(width, height)``
        are unchanged. ``screenshot.x`` / ``screenshot.y`` are already
        ``int`` so no extra rounding is needed.
        """
        x, y, w, h = word.bbox
        return (x + self.screenshot.x, y + self.screenshot.y, w, h)


_default_engine: OCREngine | None = None


def _get_default_engine() -> OCREngine:
    """Return the cached default :class:`OCREngine`, building it if needed.

    The first call constructs a :class:`RapidOCREngine`; subsequent
    calls reuse the cached instance. Not thread-safe — the project
    runs in a single context, so the worst case under racy access is
    a transient duplicate engine that is immediately replaced.
    """
    global _default_engine
    if _default_engine is None:
        _default_engine = RapidOCREngine()
    return _default_engine


def recognize(
    screenshot: Screenshot,
    *,
    engine: OCREngine | None = None,
) -> OCRResult:
    """Run OCR on *screenshot* and bundle the words with it.

    The caller is responsible for capture; pass any
    :class:`Screenshot` (typically from
    :func:`vrcpilot.screenshot.take_screenshot`, but a hand-built one
    or a replayed capture works just as well).

    Args:
        screenshot: Image to recognise. ``screenshot.image`` is fed
            to the engine and ``screenshot.x`` / ``y`` are preserved
            so :meth:`OCRResult.display_polygon` /
            :meth:`OCRResult.display_bbox` can shift to desktop
            coordinates.
        engine: OCR backend. ``None`` (default) lazily builds and
            caches a :class:`RapidOCREngine` via
            :func:`_get_default_engine`.

    Returns:
        :class:`OCRResult` pairing *screenshot* with the detected
        words (possibly empty). Never returns ``None``.
    """
    if engine is None:
        engine = _get_default_engine()
    words = engine.recognize(screenshot.image)
    return OCRResult(screenshot=screenshot, words=tuple(words))
