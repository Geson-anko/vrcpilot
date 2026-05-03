"""OCR primitives for VRChat screen analysis.

Public surface:

* :class:`OCREngine` — swappable backend ABC.
* :class:`OCRWord` — single-detection value type (image-local).
* :class:`OCRResult` — screenshot + word tuple, with helpers that
  shift coordinates to desktop-absolute space.
* :class:`RapidOCREngine` — default rapidocr-backed engine.
* :func:`recognize` — high-level helper that captures a screenshot
  and runs an :class:`OCREngine`.
* :func:`render` — draws an :class:`OCRResult` onto an ndarray
  suitable for ``PIL.Image.fromarray``.

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
from .visualize import render

__all__ = [
    "OCREngine",
    "OCRResult",
    "OCRWord",
    "RapidOCREngine",
    "recognize",
    "render",
]
