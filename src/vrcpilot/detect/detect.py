"""High-level :func:`detect` helper and the :class:`DetectResult` value type.

:class:`DetectResult` ties a :class:`Screenshot` to the
:class:`Detection` list produced by a :class:`DetectEngine` so callers
can move between image-local and desktop-absolute coordinates without
re-doing the geometry math.

:func:`detect` is a thin wrapper: the caller supplies the
:class:`Screenshot` (typically from
:func:`vrcpilot.screenshot.take_screenshot`) and a query image, and
this function only runs the engine and packages the result. Capture
and detection are kept as separate concerns so the same detection
pipeline can be replayed against existing images, fed cropped regions,
or driven by a custom capture source.

The module-level ``_default_engine`` cache keeps :func:`detect` cheap
on repeat calls: the (heavy) :class:`SiftDetectEngine` is built
exactly once per process when the user does not pass an ``engine``
argument. Tests that need a fresh cache should reset the variable
explicitly (``vrcpilot.detect.detect._default_engine = None``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from vrcpilot.screenshot import Screenshot
from vrcpilot.types import Polygon

from .base import DetectEngine, Detection
from .sift import SiftDetectEngine


@dataclass(frozen=True, eq=False)
class DetectResult:
    """Captured screenshot + query bundled with their detections.

    ``eq=False`` mirrors :class:`vrcpilot.screenshot.Screenshot`:
    ``screenshot.image`` is a numpy ``ndarray`` and element-wise
    ``__eq__`` cannot back the dataclass-synthesised equality.

    Attributes:
        screenshot: The :class:`Screenshot` the detections came from.
            ``screenshot.x`` / ``screenshot.y`` are the desktop offsets
            used by :meth:`display_polygon` and :meth:`display_bbox`.
        query: The query image (``(h, w, 3)`` uint8 RGB) passed to the
            engine. Stored verbatim for later reference; **not** copied
            (the engine does not mutate it).
        detections: Detected :class:`Detection` tuple. Always a tuple
            so the sequence is immutable from the caller's point of
            view (matches the frozen-dataclass posture of
            :class:`Detection`).
    """

    screenshot: Screenshot
    query: NDArray[np.uint8]
    detections: tuple[Detection, ...]

    def display_polygon(self, det: Detection) -> Polygon:
        """Return ``det.polygon`` shifted to desktop-absolute coordinates.

        Each ``(x, y)`` corner is offset by
        ``(screenshot.x, screenshot.y)``; values stay ``float``.

        Membership in ``self.detections`` is **not** checked: the method
        is a pure geometric transform driven by ``det.polygon``, so a
        caller who builds a :class:`Detection` separately can still
        translate it.
        """
        dx = float(self.screenshot.x)
        dy = float(self.screenshot.y)
        p0, p1, p2, p3 = det.polygon
        return (
            (p0[0] + dx, p0[1] + dy),
            (p1[0] + dx, p1[1] + dy),
            (p2[0] + dx, p2[1] + dy),
            (p3[0] + dx, p3[1] + dy),
        )

    def display_bbox(self, det: Detection) -> tuple[int, int, int, int]:
        """Return ``det.bbox`` shifted to desktop-absolute coordinates.

        ``(x, y)`` move by the screenshot offset; ``(width, height)``
        are unchanged. ``screenshot.x`` / ``screenshot.y`` are already
        ``int`` so no extra rounding is needed.
        """
        x, y, w, h = det.bbox
        return (x + self.screenshot.x, y + self.screenshot.y, w, h)


_default_engine: DetectEngine | None = None


def _get_default_engine() -> DetectEngine:
    """Return the cached default :class:`DetectEngine`, building it if needed.

    The first call constructs a :class:`SiftDetectEngine`; subsequent
    calls reuse the cached instance. Not thread-safe — the project
    runs in a single context, so the worst case under racy access is
    a transient duplicate engine that is immediately replaced.
    """
    global _default_engine
    if _default_engine is None:
        _default_engine = SiftDetectEngine()
    return _default_engine


def detect(
    screenshot: Screenshot,
    query: NDArray[np.uint8],
    *,
    engine: DetectEngine | None = None,
) -> DetectResult:
    """Run detection on *screenshot* against *query* and bundle the results.

    The caller is responsible for capture; pass any
    :class:`Screenshot` (typically from
    :func:`vrcpilot.screenshot.take_screenshot`, but a hand-built one
    or a replayed capture works just as well).

    Args:
        screenshot: Image to search. ``screenshot.image`` is fed to the
            engine and ``screenshot.x`` / ``y`` are preserved so
            :meth:`DetectResult.display_polygon` /
            :meth:`DetectResult.display_bbox` can shift to desktop
            coordinates.
        query: ``(h, w, 3)`` uint8 RGB image to look for in
            *screenshot*.
        engine: Detection backend. ``None`` (default) lazily builds
            and caches a :class:`SiftDetectEngine` via
            :func:`_get_default_engine`.

    Returns:
        :class:`DetectResult` pairing the inputs with the detected
        instances (possibly empty). Never returns ``None``.
    """
    if engine is None:
        engine = _get_default_engine()
    detections = engine.detect(screenshot.image, query)
    return DetectResult(
        screenshot=screenshot,
        query=query,
        detections=tuple(detections),
    )
