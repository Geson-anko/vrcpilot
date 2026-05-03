"""Reusable type aliases for the OCR module.

Centralised here so the verbose 4-tuple-of-2-tuple polygon spelling is
written once and re-exported from :mod:`vrcpilot.ocr` for use by
:class:`OCRWord`, :class:`OCREngine` implementers, helpers like
:meth:`OCRResult.display_polygon`, and downstream user code that builds
its own backend.
"""

from __future__ import annotations

#: 4-corner polygon ordered TL -> TR -> BR -> BL. Each corner is an
#: ``(x, y)`` 2-tuple in image-local pixel coordinates (``float``).
type Polygon = tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
]
