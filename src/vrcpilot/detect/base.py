"""Detection engine abstract base class and the :class:`Detection` value type.

All coordinates handled here are *image-local* — the origin is the
top-left of the captured image, not the desktop. Conversion to
desktop-absolute coordinates is the responsibility of higher-level
helpers (e.g. ``DetectResult.display_polygon``), not the engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from vrcpilot.types import Polygon


@dataclass(frozen=True)
class Detection:
    """Single detection in image-local coordinates.

    Attributes:
        polygon: 4 corners (TL, TR, BR, BL). Arbitrary quadrilaterals
            (e.g. projected through a homography) are allowed.
        confidence: 0.0-1.0 score (typically a match-inlier ratio).
        scale: Scale relative to the query image (1.0 = same size).
        rotation: Radians (counter-clockwise positive).
    """

    polygon: Polygon
    confidence: float
    scale: float
    rotation: float

    def __post_init__(self) -> None:
        # Static typing pins the length at 4, but runtime tuple-building
        # callers can still slip past. Guard at construction time too,
        # mirroring OCRWord.__post_init__.
        if len(self.polygon) != 4:
            raise ValueError(
                f"Detection.polygon must have exactly 4 points; "
                f"got {len(self.polygon)}"
            )

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """Axis-aligned bounding box ``(x, y, width, height)``.

        ``width`` and ``height`` are always non-negative (zero for a
        degenerate polygon).
        """
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)
        return (
            int(round(x_min)),
            int(round(y_min)),
            int(round(x_max - x_min)),
            int(round(y_max - y_min)),
        )

    @property
    def center(self) -> tuple[float, float]:
        """Mean of polygon vertices as ``(x, y)`` floats."""
        mean_x = sum(p[0] for p in self.polygon) / 4
        mean_y = sum(p[1] for p in self.polygon) / 4
        return (float(mean_x), float(mean_y))


class DetectEngine(ABC):
    """Abstract base for swappable detection backends.

    Users plug in alternative engines (ORB, template match, a hosted
    API, etc.) by subclassing and implementing :meth:`detect`.
    """

    @abstractmethod
    def detect(
        self,
        image: NDArray[np.uint8],
        query: NDArray[np.uint8],
    ) -> Sequence[Detection]:
        """Detect instances of *query* in ``(H, W, 3)`` uint8 RGB *image*.

        Args:
            image: RGB image to search. Must be ``np.uint8`` dtype.
            query: Query image to look for. ``(h, w, 3)`` uint8 RGB.

        Returns:
            Detected :class:`Detection` sequence. Coordinates are
            image-local (origin = top-left of *image*); translation to
            desktop coordinates is the caller's responsibility.
        """
