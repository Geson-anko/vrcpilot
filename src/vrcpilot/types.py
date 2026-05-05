"""Project-wide type aliases shared across vrcpilot subsystems.

Lives at the package root rather than under any subsystem (``ocr``,
``detect``, …) because the same geometric primitives describe
detections produced by every subsystem. Importing from a single neutral
location avoids circular dependencies between sibling packages.
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
