"""Detect-related test doubles.

Stand-in for :class:`vrcpilot.detect.DetectEngine` used by integration
tests of :func:`vrcpilot.detect.detect` and the ``vrcpilot detect`` CLI
command. ``FakeDetectEngine`` returns a pre-baked list of
:class:`Detection` from every :meth:`detect` call regardless of the
input image or query.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import override

import numpy as np
from numpy.typing import NDArray

from vrcpilot.detect import DetectEngine, Detection


class FakeDetectEngine(DetectEngine):
    """Detect engine that always returns a fixed detection list.

    The constructor takes a ``Sequence[Detection]`` and stores it
    verbatim. Each :meth:`detect` call returns the same list, records
    the image and query identities in :attr:`last_image` /
    :attr:`last_query`, and increments :attr:`calls` so tests can assert
    what the engine saw and how often it was hit.
    """

    def __init__(self, detections: Sequence[Detection]) -> None:
        self._detections: list[Detection] = list(detections)
        self.calls: int = 0
        self.last_image: NDArray[np.uint8] | None = None
        self.last_query: NDArray[np.uint8] | None = None

    @override
    def detect(
        self,
        image: NDArray[np.uint8],
        query: NDArray[np.uint8],
    ) -> Sequence[Detection]:
        self.calls += 1
        self.last_image = image
        self.last_query = query
        return list(self._detections)
