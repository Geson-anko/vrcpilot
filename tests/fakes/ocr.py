"""OCR-related test doubles.

Stand-in for :class:`vrcpilot.ocr.OCREngine` used by Phase 2C / Phase 3
tests where exercising the real rapidocr backend is irrelevant —
``FakeOCREngine`` returns a pre-baked list of :class:`OCRWord` from
every :meth:`recognize` call regardless of the input image.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import override

import numpy as np
from numpy.typing import NDArray

from vrcpilot.ocr import OCREngine, OCRWord


class FakeOCREngine(OCREngine):
    """OCR engine that always returns a fixed word list.

    The constructor takes a ``Sequence[OCRWord]`` and stores it
    verbatim. Each :meth:`recognize` call returns the same list and
    increments :attr:`calls` so tests can assert the engine was hit
    the expected number of times (e.g. cache hit vs. miss).
    """

    def __init__(self, words: Sequence[OCRWord]) -> None:
        self._words: list[OCRWord] = list(words)
        self.calls: int = 0

    @override
    def recognize(self, image: NDArray[np.uint8]) -> Sequence[OCRWord]:
        del image
        self.calls += 1
        return list(self._words)
