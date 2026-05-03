"""Tests for :mod:`vrcpilot.ocr.recognize`.

Integration-with-fakes: :func:`take_screenshot` is patched at the
module boundary so no real display / VRChat is needed, and the OCR
engine is the in-memory :class:`tests.fakes.ocr.FakeOCREngine` so
no rapidocr model download is triggered.

The submodule reference is fetched via ``sys.modules`` because the
package binds the ``recognize`` *function* under the name
``vrcpilot.ocr.recognize``, which would otherwise shadow the
submodule in attribute-walking patch helpers.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from types import ModuleType

import numpy as np
import pytest
from numpy.typing import NDArray

import vrcpilot.ocr  # noqa: F401  ensures submodule is registered
from tests.fakes.ocr import FakeOCREngine
from vrcpilot.ocr import OCRResult, OCRWord, recognize
from vrcpilot.ocr.base import Polygon
from vrcpilot.screenshot import Screenshot

_recognize_module: ModuleType = sys.modules["vrcpilot.ocr.recognize"]


def _make_screenshot(
    *,
    x: int = 100,
    y: int = 50,
    width: int = 320,
    height: int = 200,
) -> Screenshot:
    image: NDArray[np.uint8] = np.zeros((height, width, 3), dtype=np.uint8)
    return Screenshot(
        image=image,
        x=x,
        y=y,
        width=width,
        height=height,
        monitor_index=1,
        captured_at=datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_word(
    polygon: Polygon = (
        (10.0, 20.0),
        (60.0, 20.0),
        (60.0, 38.0),
        (10.0, 38.0),
    ),
    text: str = "Hello",
    confidence: float = 0.97,
) -> OCRWord:
    return OCRWord(text=text, polygon=polygon, confidence=confidence)


@pytest.fixture(autouse=True)
def _reset_default_engine() -> Iterator[None]:
    """Reset module-level cache between tests so order is irrelevant."""
    _recognize_module._default_engine = None
    yield
    _recognize_module._default_engine = None


class TestRecognizeWithExplicitEngine:
    def test_returns_ocr_result_with_tuple_words(self, monkeypatch: pytest.MonkeyPatch):
        shot = _make_screenshot()
        monkeypatch.setattr(
            _recognize_module, "take_screenshot", lambda *, settle_seconds=0.05: shot
        )
        word = _make_word()
        engine = FakeOCREngine([word])

        result = recognize(engine=engine)

        assert isinstance(result, OCRResult)
        assert result.screenshot is shot
        assert isinstance(result.words, tuple)
        assert result.words == (word,)
        assert engine.calls == 1

    def test_screenshot_none_skips_engine_and_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            _recognize_module, "take_screenshot", lambda *, settle_seconds=0.05: None
        )
        engine = FakeOCREngine([_make_word()])

        result = recognize(engine=engine)

        assert result is None
        assert engine.calls == 0

    def test_settle_seconds_forwarded(self, monkeypatch: pytest.MonkeyPatch):
        seen: list[float] = []

        def _capture(*, settle_seconds: float = 0.05) -> Screenshot | None:
            seen.append(settle_seconds)
            return _make_screenshot()

        monkeypatch.setattr(_recognize_module, "take_screenshot", _capture)
        engine = FakeOCREngine([])
        recognize(engine=engine, settle_seconds=0.25)

        assert seen == [0.25]


class TestRecognizeDefaultEngineCache:
    def test_default_engine_is_built_once(self, monkeypatch: pytest.MonkeyPatch):
        shot = _make_screenshot()
        monkeypatch.setattr(
            _recognize_module, "take_screenshot", lambda *, settle_seconds=0.05: shot
        )

        word = _make_word()
        build_count = {"n": 0}

        def _factory() -> FakeOCREngine:
            build_count["n"] += 1
            return FakeOCREngine([word])

        # Patch the RapidOCREngine reference inside the recognize
        # submodule so the default-engine path uses our fake.
        monkeypatch.setattr(_recognize_module, "RapidOCREngine", _factory)

        first = recognize()
        second = recognize()

        assert first is not None
        assert second is not None
        assert build_count["n"] == 1
        cached = _recognize_module._default_engine
        assert cached is not None
        assert isinstance(cached, FakeOCREngine)
        assert cached.calls == 2

    def test_resetting_cache_rebuilds_engine(self, monkeypatch: pytest.MonkeyPatch):
        shot = _make_screenshot()
        monkeypatch.setattr(
            _recognize_module, "take_screenshot", lambda *, settle_seconds=0.05: shot
        )

        build_count = {"n": 0}

        def _factory() -> FakeOCREngine:
            build_count["n"] += 1
            return FakeOCREngine([])

        monkeypatch.setattr(_recognize_module, "RapidOCREngine", _factory)

        recognize()
        assert build_count["n"] == 1

        _recognize_module._default_engine = None
        recognize()
        assert build_count["n"] == 2


class TestOCRResultDisplayPolygon:
    def test_shifts_each_point_by_screenshot_offset(self):
        shot = _make_screenshot(x=100, y=50)
        word = _make_word()
        result = OCRResult(screenshot=shot, words=(word,))

        assert result.display_polygon(word) == (
            (110.0, 70.0),
            (160.0, 70.0),
            (160.0, 88.0),
            (110.0, 88.0),
        )

    def test_negative_screenshot_offset(self):
        shot = _make_screenshot(x=-50, y=-20)
        word = _make_word()
        result = OCRResult(screenshot=shot, words=(word,))

        assert result.display_polygon(word) == (
            (-40.0, 0.0),
            (10.0, 0.0),
            (10.0, 18.0),
            (-40.0, 18.0),
        )

    def test_word_need_not_be_in_words(self):
        shot = _make_screenshot(x=100, y=50)
        # Empty words tuple — display_polygon still works.
        result = OCRResult(screenshot=shot, words=())
        word = _make_word()

        assert result.display_polygon(word) == (
            (110.0, 70.0),
            (160.0, 70.0),
            (160.0, 88.0),
            (110.0, 88.0),
        )


class TestOCRResultDisplayBBox:
    def test_shifts_xy_keeps_size(self):
        shot = _make_screenshot(x=100, y=50)
        word = _make_word()
        result = OCRResult(screenshot=shot, words=(word,))

        assert result.display_bbox(word) == (110, 70, 50, 18)

    def test_returns_int_tuple(self):
        shot = _make_screenshot(x=100, y=50)
        word = _make_word()
        result = OCRResult(screenshot=shot, words=(word,))

        bbox = result.display_bbox(word)
        assert all(isinstance(v, int) for v in bbox)
