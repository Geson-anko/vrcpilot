"""Unit tests for :mod:`vrcpilot.ocr.base`.

Covers ``OCRWord`` derived properties (``bbox`` / ``center``), the
``__post_init__`` length guard, and the ABC enforcement on
``OCREngine``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from vrcpilot.ocr.base import OCREngine, OCRWord, Polygon


def _word(polygon: Polygon, text: str = "x", confidence: float = 0.9) -> OCRWord:
    return OCRWord(text=text, polygon=polygon, confidence=confidence)


class TestOCRWordFrozen:
    def test_word_is_frozen(self):
        word = _word(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
        with pytest.raises(FrozenInstanceError):
            # Frozen dataclass: any attribute assignment must fail.
            word.text = "y"  # type: ignore[misc]


class TestOCRWordPolygonValidation:
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
    def test_word_polygon_must_have_4_points(
        self,
        bad_polygon: tuple[tuple[float, float], ...],
    ):
        # The dataclass type pins length to 4, but at runtime
        # mismatched polygons can sneak in via dynamic construction.
        with pytest.raises(ValueError, match="must have exactly 4 points"):
            OCRWord(
                text="x",
                polygon=cast(Polygon, bad_polygon),
                confidence=0.5,
            )


class TestOCRWordBBox:
    def test_word_bbox_basic(self):
        # Axis-aligned rectangle: bbox is the rectangle itself.
        polygon: Polygon = (
            (10.0, 20.0),
            (60.0, 20.0),
            (60.0, 38.0),
            (10.0, 38.0),
        )
        assert _word(polygon).bbox == (10, 20, 50, 18)

    def test_word_bbox_rotated_polygon(self):
        # Tilted polygon's bbox is the axis-aligned envelope:
        # x ∈ [2, 18], y ∈ [3, 17].
        polygon: Polygon = (
            (10.0, 3.0),
            (18.0, 10.0),
            (10.0, 17.0),
            (2.0, 10.0),
        )
        assert _word(polygon).bbox == (2, 3, 16, 14)

    def test_word_bbox_uses_round(self):
        # 0.4 → 0 (down), 0.6 → 1 (up): boundary check that
        # ``int(round(...))`` is applied to all four components.
        polygon: Polygon = (
            (10.4, 20.4),
            (60.6, 20.4),
            (60.6, 38.6),
            (10.4, 38.6),
        )
        # x_min=10.4 → 10, y_min=20.4 → 20,
        # width=50.2 → 50, height=18.2 → 18.
        assert _word(polygon).bbox == (10, 20, 50, 18)

    def test_word_bbox_degenerate_polygon_has_zero_size(self):
        polygon: Polygon = (
            (5.0, 7.0),
            (5.0, 7.0),
            (5.0, 7.0),
            (5.0, 7.0),
        )
        assert _word(polygon).bbox == (5, 7, 0, 0)


class TestOCRWordCenter:
    def test_word_center_axis_aligned(self):
        polygon: Polygon = (
            (10.0, 20.0),
            (60.0, 20.0),
            (60.0, 38.0),
            (10.0, 38.0),
        )
        cx, cy = _word(polygon).center
        assert (cx, cy) == (35.0, 29.0)
        assert isinstance(cx, float)
        assert isinstance(cy, float)

    def test_word_center_tilted_polygon(self):
        polygon: Polygon = (
            (10.0, 3.0),
            (18.0, 10.0),
            (10.0, 17.0),
            (2.0, 10.0),
        )
        cx, cy = _word(polygon).center
        assert cx == pytest.approx(10.0)
        assert cy == pytest.approx(10.0)


class TestOCREngineABC:
    def test_engine_cannot_be_instantiated_directly(self):
        # ``OCREngine`` is an ABC: instantiating it raises ``TypeError``
        # because ``recognize`` is still abstract.
        with pytest.raises(TypeError):
            OCREngine()  # type: ignore[abstract]

    def test_engine_subclass_must_implement_recognize(self):
        class _Incomplete(OCREngine):
            pass

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]

    def test_engine_concrete_subclass_can_be_constructed(self):
        # Sanity check: a subclass that implements ``recognize`` must
        # instantiate without complaint and dispatch correctly.
        captured: list[NDArray[np.uint8]] = []

        class _Echo(OCREngine):
            def recognize(self, image: NDArray[np.uint8]) -> Sequence[OCRWord]:
                captured.append(image)
                return ()

        engine = _Echo()
        image: NDArray[np.uint8] = np.zeros((4, 4, 3), dtype=np.uint8)
        result = engine.recognize(image)
        assert list(result) == []
        assert len(captured) == 1
