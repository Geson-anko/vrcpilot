"""Tests for :mod:`vrcpilot.detect.visualize`.

Pure unit-level: we build a :class:`DetectResult` from a synthetic
ndarray and a hand-crafted :class:`Detection`, then assert the rendered
ndarray has the expected shape, leaves the input untouched, and uses
the right text colour for each branch (auto-contrast vs. override).
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest
from numpy.typing import NDArray

from vrcpilot.detect import Detection, DetectResult, Polygon, render
from vrcpilot.screenshot import Screenshot


def _make_result(
    image: NDArray[np.uint8],
    *,
    polygon: Polygon = (
        (10.0, 30.0),
        (60.0, 30.0),
        (60.0, 50.0),
        (10.0, 50.0),
    ),
    confidence: float = 0.92,
    scale: float = 1.25,
    rotation: float = 0.0,
) -> DetectResult:
    height, width = image.shape[:2]
    shot = Screenshot(
        image=image,
        x=0,
        y=0,
        width=width,
        height=height,
        monitor_index=1,
        captured_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
    )
    det = Detection(
        polygon=polygon,
        confidence=confidence,
        scale=scale,
        rotation=rotation,
    )
    query: NDArray[np.uint8] = np.zeros((4, 4, 3), dtype=np.uint8)
    return DetectResult(screenshot=shot, query=query, detections=(det,))


def _full(value: int, shape: tuple[int, int, int] = (100, 200, 3)) -> NDArray[np.uint8]:
    return np.full(shape, value, dtype=np.uint8)


class TestRenderShapeAndPurity:
    def test_returns_ndarray_with_matching_shape_and_dtype(self):
        image = _full(255)
        result = _make_result(image)

        out = render(result)

        assert out.shape == image.shape
        assert out.dtype == image.dtype

    def test_input_image_is_not_mutated(self):
        image = _full(255)
        snapshot = image.copy()
        result = _make_result(image)

        render(result)

        assert np.array_equal(image, snapshot)

    def test_something_was_drawn(self):
        image = _full(255)
        result = _make_result(image)

        out = render(result)

        diff = (out != image).any(axis=-1)
        assert int(diff.sum()) > 0

    def test_empty_detections_returns_copy_unchanged(self):
        image = _full(128)
        height, width = image.shape[:2]
        shot = Screenshot(
            image=image,
            x=0,
            y=0,
            width=width,
            height=height,
            monitor_index=1,
            captured_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
        query: NDArray[np.uint8] = np.zeros((4, 4, 3), dtype=np.uint8)
        result = DetectResult(screenshot=shot, query=query, detections=())

        out = render(result)

        assert out.shape == image.shape
        assert out.dtype == image.dtype
        assert np.array_equal(out, image)
        # Confirm it is a copy, not the same array.
        assert out is not image


class TestRenderAutoContrast:
    @pytest.mark.parametrize(
        ("background", "expects_dark_text"),
        [
            (255, True),  # white background → black text
            (0, False),  # black background → white text
        ],
    )
    def test_text_color_chosen_by_background_luminance(
        self, background: int, expects_dark_text: bool
    ):
        image = _full(background)
        result = _make_result(image)

        out = render(result)

        diff_mask = (out != image).any(axis=-1)
        changed = out[diff_mask]
        assert changed.size > 0

        if expects_dark_text:
            # White bg + green box (0,255,0) + black text. The text
            # pixels are (0,0,0); confirm at least one near-black
            # changed pixel exists.
            near_black = (changed.sum(axis=-1) < 60).sum()
            assert near_black > 0
        else:
            # Black bg + green box (0,255,0) + white text. The text
            # pixels are (255,255,255); confirm at least one
            # near-white changed pixel exists.
            near_white = (changed.sum(axis=-1) > 700).sum()
            assert near_white > 0


class TestRenderExplicitTextColor:
    def test_override_color_appears_in_diff(self):
        image = _full(255)
        result = _make_result(image)

        out = render(result, text_color=(255, 0, 0))

        diff_mask = (out != image).any(axis=-1)
        changed = out[diff_mask]
        # At least one pixel should be (very) red — high R, low G/B.
        red_pixels = (
            (changed[:, 0] > 200) & (changed[:, 1] < 60) & (changed[:, 2] < 60)
        ).sum()
        assert red_pixels > 0

    def test_box_color_override_appears_in_diff(self):
        image = _full(255)
        result = _make_result(image)

        out = render(result, box_color=(0, 0, 255), text_color=(0, 0, 255))

        diff_mask = (out != image).any(axis=-1)
        changed = out[diff_mask]
        blue_pixels = (
            (changed[:, 0] < 60) & (changed[:, 1] < 60) & (changed[:, 2] > 200)
        ).sum()
        assert blue_pixels > 0


class TestRenderEdgeCases:
    def test_bbox_at_top_edge_falls_back_below(self):
        # Polygon touches y=0; without the fallback, putText would be
        # placed at a negative y. The fallback path must keep the call
        # exception-free and still draw something.
        image = _full(255)
        result = _make_result(
            image,
            polygon=(
                (10.0, 0.0),
                (60.0, 0.0),
                (60.0, 12.0),
                (10.0, 12.0),
            ),
        )

        out = render(result)

        assert out.shape == image.shape
        diff = (out != image).any(axis=-1)
        assert int(diff.sum()) > 0
