"""Unit tests for :mod:`vrcpilot.detect.base`.

Covers ``Detection`` derived properties (``bbox`` / ``center``), the
``__post_init__`` length guard, and the ABC enforcement on
``DetectEngine``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from tests.helpers import ImplDetectEngine
from vrcpilot.detect import DetectEngine, Detection
from vrcpilot.types import Polygon


def _detection(
    polygon: Polygon,
    confidence: float = 0.9,
    scale: float = 1.0,
    rotation: float = 0.0,
) -> Detection:
    return Detection(
        polygon=polygon,
        confidence=confidence,
        scale=scale,
        rotation=rotation,
    )


class TestDetectionFrozen:
    def test_detection_is_frozen(self):
        det = _detection(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
        with pytest.raises(FrozenInstanceError):
            # Frozen dataclass: any attribute assignment must fail.
            det.confidence = 0.1  # type: ignore[misc]


class TestDetectionPolygonValidation:
    @pytest.mark.parametrize(
        "bad_polygon",
        [
            (),
            ((0.0, 0.0),),
            ((0.0, 0.0), (1.0, 0.0)),
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
            (
                (0.0, 0.0),
                (1.0, 0.0),
                (1.0, 1.0),
                (0.0, 1.0),
                (0.5, 0.5),
            ),
        ],
    )
    def test_detection_polygon_must_have_4_points(
        self,
        bad_polygon: tuple[tuple[float, float], ...],
    ):
        # The dataclass type pins length to 4, but at runtime
        # mismatched polygons can sneak in via dynamic construction.
        with pytest.raises(ValueError, match="must have exactly 4 points"):
            Detection(
                polygon=cast(Polygon, bad_polygon),
                confidence=0.5,
                scale=1.0,
                rotation=0.0,
            )


class TestDetectionBbox:
    def test_detection_bbox_basic(self):
        # Axis-aligned rectangle: bbox is the rectangle itself.
        polygon: Polygon = (
            (10.0, 20.0),
            (60.0, 20.0),
            (60.0, 38.0),
            (10.0, 38.0),
        )
        assert _detection(polygon).bbox == (10, 20, 50, 18)

    def test_detection_bbox_rotated_polygon(self):
        # Tilted polygon's bbox is the axis-aligned envelope:
        # x in [2, 18], y in [3, 17].
        polygon: Polygon = (
            (10.0, 3.0),
            (18.0, 10.0),
            (10.0, 17.0),
            (2.0, 10.0),
        )
        assert _detection(polygon).bbox == (2, 3, 16, 14)

    def test_detection_bbox_uses_round(self):
        # 0.4 -> 0 (down), 0.6 -> 1 (up): boundary check that
        # ``int(round(...))`` is applied to all four components.
        polygon: Polygon = (
            (10.4, 20.4),
            (60.6, 20.4),
            (60.6, 38.6),
            (10.4, 38.6),
        )
        # x_min=10.4 -> 10, y_min=20.4 -> 20,
        # width=50.2 -> 50, height=18.2 -> 18.
        assert _detection(polygon).bbox == (10, 20, 50, 18)

    def test_detection_bbox_degenerate_polygon_has_zero_size(self):
        polygon: Polygon = (
            (5.0, 7.0),
            (5.0, 7.0),
            (5.0, 7.0),
            (5.0, 7.0),
        )
        assert _detection(polygon).bbox == (5, 7, 0, 0)


class TestDetectionCenter:
    def test_detection_center_axis_aligned(self):
        polygon: Polygon = (
            (10.0, 20.0),
            (60.0, 20.0),
            (60.0, 38.0),
            (10.0, 38.0),
        )
        cx, cy = _detection(polygon).center
        assert (cx, cy) == (35.0, 29.0)
        assert isinstance(cx, float)
        assert isinstance(cy, float)

    def test_detection_center_tilted_polygon(self):
        polygon: Polygon = (
            (10.0, 3.0),
            (18.0, 10.0),
            (10.0, 17.0),
            (2.0, 10.0),
        )
        cx, cy = _detection(polygon).center
        assert cx == pytest.approx(10.0)
        assert cy == pytest.approx(10.0)


class TestDetectEngineABC:
    def test_engine_cannot_be_instantiated_directly(self):
        # ``DetectEngine`` is an ABC: instantiating it raises ``TypeError``
        # because ``detect`` is still abstract.
        with pytest.raises(TypeError):
            DetectEngine()  # type: ignore[abstract]

    def test_engine_subclass_must_implement_detect(self):
        class _Incomplete(DetectEngine):
            pass

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]

    def test_engine_concrete_subclass_dispatches(self):
        # Sanity check: a real subclass that implements ``detect`` must
        # instantiate without complaint and forward both ndarrays.
        polygon: Polygon = (
            (0.0, 0.0),
            (4.0, 0.0),
            (4.0, 4.0),
            (0.0, 4.0),
        )
        canned = (Detection(polygon=polygon, confidence=0.5, scale=1.0, rotation=0.0),)
        engine = ImplDetectEngine(result=canned)
        image: NDArray[np.uint8] = np.zeros((8, 8, 3), dtype=np.uint8)
        query: NDArray[np.uint8] = np.zeros((4, 4, 3), dtype=np.uint8)

        result = engine.detect(image, query)

        assert list(result) == list(canned)
        assert len(engine.calls) == 1
        recorded_image, recorded_query = engine.calls[0]
        assert recorded_image is image
        assert recorded_query is query
