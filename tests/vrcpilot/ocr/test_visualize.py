"""Tests for :mod:`vrcpilot.ocr.visualize`.

Pure unit-level: we build an :class:`OCRResult` from a synthetic
ndarray and a hand-crafted :class:`OCRWord`, then assert the rendered
ndarray has the expected shape, leaves the input untouched, and uses
the right text colour for each branch (auto-contrast vs. override).
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest
from numpy.typing import NDArray

from vrcpilot.ocr import OCRResult, OCRWord, Polygon, render
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
    text: str = "Hi",
) -> OCRResult:
    height, width = image.shape[:2]
    shot = Screenshot(
        image=image,
        x=0,
        y=0,
        width=width,
        height=height,
        monitor_index=1,
        captured_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
    )
    word = OCRWord(text=text, polygon=polygon, confidence=0.9)
    return OCRResult(screenshot=shot, words=(word,))


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

    def test_empty_words_returns_copy_unchanged(self):
        image = _full(128)
        height, width = image.shape[:2]
        shot = Screenshot(
            image=image,
            x=0,
            y=0,
            width=width,
            height=height,
            monitor_index=1,
            captured_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        )
        result = OCRResult(screenshot=shot, words=())

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
