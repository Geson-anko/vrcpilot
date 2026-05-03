"""OCR primitives for VRChat screen analysis.

Public surface:

* :class:`OCREngine` — swappable backend ABC.
* :class:`OCRWord` — single-detection value type (image-local).
* :class:`OCRResult` — screenshot + word tuple, with helpers that
  shift coordinates to desktop-absolute space.
* :class:`RapidOCREngine` — default rapidocr-backed engine.
* :func:`recognize` — runs an :class:`OCREngine` on a captured
  :class:`Screenshot` and bundles the words with it.
* :func:`render` — draws an :class:`OCRResult` onto an ndarray
  suitable for ``PIL.Image.fromarray``.
* :data:`Polygon` — the 4-corner polygon type alias used across the
  module; re-exported here so users implementing their own
  :class:`OCREngine` can annotate against the same shape.

Note on the ``recognize`` name: the helper function and the submodule
that defines it share the name. ``from vrcpilot.ocr import recognize``
returns the function (CPython resolves it via attribute lookup on the
package, where the explicit re-export wins over the auto-bound
submodule). Tests that need to monkey-patch internals on the
submodule should reach it via ``sys.modules['vrcpilot.ocr.recognize']``
to bypass attribute resolution.
"""

from __future__ import annotations

from .base import OCREngine, OCRWord
from .rapidocr import RapidOCREngine
from .recognize import OCRResult, recognize
from .types import Polygon
from .visualize import render

__all__ = [
    "OCREngine",
    "OCRResult",
    "OCRWord",
    "Polygon",
    "RapidOCREngine",
    "recognize",
    "render",
]
