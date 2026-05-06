"""Unit tests for :class:`vrcpilot.detect.template.TemplateDetectEngine`.

Verified against synthetic images. Template matching does not need
features, so the textured icons used for SIFT / AKAZE are unnecessary
here; a flat-coloured background plus a simple-shape query is closer to
the real VRChat UI.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from vrcpilot.detect import Detection, TemplateDetectEngine


def _make_flat_background(
    height: int = 480,
    width: int = 640,
    color: tuple[int, int, int] = (40, 40, 40),
) -> NDArray[np.uint8]:
    """Solid-colour RGB ``uint8`` canvas.

    A flat-coloured canvas mirrors the real VRChat UI background.
    Template matching does not need background texture, and isolating
    the target this way makes ground-truth coordinates easy to read.
    """
    bg = np.empty((height, width, 3), dtype=np.uint8)
    bg[:, :, 0] = color[0]
    bg[:, :, 1] = color[1]
    bg[:, :, 2] = color[2]
    return bg


def _make_simple_icon(size: int = 40) -> NDArray[np.uint8]:
    """Simple high-contrast icon: filled square + circle + cross.

    Pixel-perfect simple shapes that mirror VRChat's Launch Pad icons
    (~50 px). Feature-based engines hardly extract keypoints from
    targets like these, but template matching is stable.
    """
    icon: NDArray[np.uint8] = np.full((size, size, 3), 255, dtype=np.uint8)
    cv2.rectangle(icon, (4, 4), (size - 4, size - 4), (20, 80, 200), -1)
    cv2.circle(icon, (size // 2, size // 2), size // 4, (250, 250, 50), -1)
    cv2.line(icon, (4, 4), (size - 4, size - 4), (10, 10, 10), 2)
    cv2.line(icon, (4, size - 4), (size - 4, 4), (10, 10, 10), 2)
    return icon


def _paste_at(
    bg: NDArray[np.uint8],
    icon: NDArray[np.uint8],
    x: int,
    y: int,
    *,
    scale: float = 1.0,
) -> tuple[NDArray[np.uint8], tuple[float, float]]:
    """Resize ``icon`` to ``scale`` and paste at ``(x, y)`` (top-left).

    Returns ``(image, (cx, cy))`` where ``(cx, cy)`` is the centre
    of the pasted region in image-local coordinates.
    """
    out = bg.copy()
    h, w = icon.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized = cv2.resize(icon, (new_w, new_h), interpolation=interp)

    bg_h, bg_w = out.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(bg_w, x + new_w)
    y1 = min(bg_h, y + new_h)
    if x0 < x1 and y0 < y1:
        src_x0 = x0 - x
        src_y0 = y0 - y
        src_x1 = src_x0 + (x1 - x0)
        src_y1 = src_y0 + (y1 - y0)
        out[y0:y1, x0:x1] = resized[src_y0:src_y1, src_x0:src_x1]
    cx = x + new_w / 2.0
    cy = y + new_h / 2.0
    return out, (cx, cy)


def _paste_rotated(
    bg: NDArray[np.uint8],
    icon: NDArray[np.uint8],
    rotation_deg: float,
    x: int,
    y: int,
) -> tuple[NDArray[np.uint8], tuple[float, float]]:
    """Rotate ``icon`` (no scale change) and paste at ``(x, y)``.

    Rotated bbox is computed first so the paste location matches what
    :class:`TemplateDetectEngine` would search for at that rotation.
    """
    out = bg.copy()
    h, w = icon.shape[:2]
    center = (w / 2.0, h / 2.0)
    rot_mat = cv2.getRotationMatrix2D(center, rotation_deg, 1.0)
    cos = abs(float(rot_mat[0, 0]))
    sin = abs(float(rot_mat[0, 1]))
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    rot_mat[0, 2] += new_w / 2 - center[0]
    rot_mat[1, 2] += new_h / 2 - center[1]
    warped = cv2.warpAffine(icon, rot_mat, (new_w, new_h), borderValue=(40, 40, 40))

    bg_h, bg_w = out.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(bg_w, x + new_w)
    y1 = min(bg_h, y + new_h)
    if x0 < x1 and y0 < y1:
        src_x0 = x0 - x
        src_y0 = y0 - y
        src_x1 = src_x0 + (x1 - x0)
        src_y1 = src_y0 + (y1 - y0)
        out[y0:y1, x0:x1] = warped[src_y0:src_y1, src_x0:src_x1]
    cx = x + new_w / 2.0
    cy = y + new_h / 2.0
    return out, (cx, cy)


class TestTemplateDetectEngineBasic:
    def test_finds_query_at_default_transform(self):
        bg = _make_flat_background()
        icon = _make_simple_icon()
        img, (true_cx, true_cy) = _paste_at(bg, icon, 200, 150)

        engine = TemplateDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        for d in dets:
            assert isinstance(d, Detection)

        best = max(dets, key=lambda d: d.confidence)
        cx, cy = best.center
        # Pixel-perfect identical paste, so the match should be
        # extremely precise.
        assert abs(cx - true_cx) < 2
        assert abs(cy - true_cy) < 2
        assert best.confidence > 0.9
        assert 0.9 < best.scale < 1.1
        assert abs(best.rotation) < 1e-6

    def test_polygon_corners_are_finite_and_in_image(self):
        bg = _make_flat_background()
        icon = _make_simple_icon()
        img, _ = _paste_at(bg, icon, 200, 150)

        engine = TemplateDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        det = dets[0]
        for x, y in det.polygon:
            assert math.isfinite(x)
            assert math.isfinite(y)
            assert -1 < x < 641
            assert -1 < y < 481


class TestTemplateDetectEngineScale:
    @pytest.mark.parametrize("scale", [0.5, 0.7, 1.0, 1.3])
    def test_recovers_scale(self, scale: float):
        bg = _make_flat_background()
        icon = _make_simple_icon()
        img, (true_cx, true_cy) = _paste_at(bg, icon, 250, 200, scale=scale)

        engine = TemplateDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        best = max(dets, key=lambda d: d.confidence)
        cx, cy = best.center
        # Picking the nearest neighbour on the scale grid leaves a
        # few-pixel centre error.
        assert abs(cx - true_cx) < 5
        assert abs(cy - true_cy) < 5
        # Tolerance accounts for the scale grid step (~0.1).
        assert abs(best.scale - scale) <= 0.15


class TestTemplateDetectEngineRotation:
    def test_recovers_rotation_when_grid_includes_it(self):
        bg = _make_flat_background()
        icon = _make_simple_icon()
        img, (true_cx, true_cy) = _paste_rotated(bg, icon, 30.0, 250, 200)

        # The engine only follows rotation when rotations_deg is
        # passed explicitly.
        engine = TemplateDetectEngine(rotations_deg=(0.0, 30.0, -30.0))
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        best = max(dets, key=lambda d: d.confidence)
        cx, cy = best.center
        # The bbox centre of the rotated paste matches the detected
        # bbox centre.
        assert abs(cx - true_cx) < 6
        assert abs(cy - true_cy) < 6
        # rotation is radians (CCW positive). The template matches at
        # rot_deg=30, so Detection.rotation is close to -30deg = -pi/6.
        expected_rad = -math.radians(30.0)
        diff = (best.rotation - expected_rad + math.pi) % (2 * math.pi) - math.pi
        assert abs(diff) < 1e-6


class TestTemplateDetectEngineMultiInstance:
    def test_finds_two_instances(self):
        bg = _make_flat_background()
        icon = _make_simple_icon()
        img, c1 = _paste_at(bg, icon, 80, 80)
        img, c2 = _paste_at(img, icon, 380, 250)

        engine = TemplateDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 2
        # Each ground-truth centre must land near at least one detection.
        for truth in (c1, c2):
            assert any(
                abs(d.center[0] - truth[0]) < 4 and abs(d.center[1] - truth[1]) < 4
                for d in dets
            )


class TestTemplateDetectEngineNoMatch:
    def test_returns_empty_when_query_is_absent(self):
        bg = _make_flat_background()
        icon = _make_simple_icon()
        engine = TemplateDetectEngine()
        dets = engine.detect(bg, icon)
        assert list(dets) == []

    def test_returns_empty_when_query_larger_than_image(self):
        # 100x100 image, 200x200 query — every (scale, rotation) yields
        # template > image, so the engine must skip cleanly.
        small_image: NDArray[np.uint8] = np.full((100, 100, 3), 40, dtype=np.uint8)
        big_query: NDArray[np.uint8] = np.full((200, 200, 3), 255, dtype=np.uint8)
        # Use only scales >= 1.0 so every transformed template is too big.
        engine = TemplateDetectEngine(scales=(1.0, 1.5))
        dets = engine.detect(small_image, big_query)
        assert list(dets) == []


class TestTemplateDetectEngineMaxResults:
    def test_max_results_truncates_output(self):
        bg = _make_flat_background()
        icon = _make_simple_icon()
        img, _ = _paste_at(bg, icon, 80, 80)
        img, _ = _paste_at(img, icon, 380, 250)

        engine = TemplateDetectEngine(max_results=1)
        dets = engine.detect(img, icon)
        assert len(dets) <= 1
