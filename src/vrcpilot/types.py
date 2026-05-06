"""Type aliases shared across subsystems.

Lives at the package root so ``ocr`` and ``detect`` can both import
without creating sibling cycles.
"""

from __future__ import annotations

#: 4-corner polygon, ordered TL, TR, BR, BL. Image-local pixels.
type Polygon = tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
]
