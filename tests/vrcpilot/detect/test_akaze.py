"""Unit tests for :class:`vrcpilot.detect.akaze.AkazeDetectEngine`.

Synthetic textured backgrounds + an icon with distinctive geometry
exercise the AKAZE + BFMatcher(Hamming) + RANSAC pipeline end-to-end
without any mocking. AKAZE ships in the OpenCV main module, so these
tests run wherever the project's core ``opencv-python`` dep does.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from vrcpilot.detect import AkazeDetectEngine, Detection


def _make_textured_background(
    seed: int = 42,
    height: int = 720,
    width: int = 1024,
) -> NDArray[np.uint8]:
    """Random noise + scattered coloured rectangles, RGB ``uint8``.

    AKAZE needs texture to lock onto; a flat canvas yields zero
    keypoints. Gaussian-blurring the noise gives smoother gradients that
    match the assumptions of the KAZE diffusion detector. The canvas
    is sized larger than the SIFT counterpart so a 180×180 query
    survives both ``scale=1.5`` enlargement and a 90° rotation without
    clipping.
    """
    rng = np.random.default_rng(seed)
    bg_signed = rng.integers(0, 256, size=(height, width, 3), dtype=np.int32)
    bg = bg_signed.astype(np.uint8)
    bg = cv2.GaussianBlur(bg, (3, 3), 0)
    for _ in range(10):
        x = int(rng.integers(0, width - 80))
        y = int(rng.integers(0, height - 80))
        cw = int(rng.integers(20, 80))
        ch = int(rng.integers(20, 80))
        color = tuple(int(c) for c in rng.integers(0, 256, size=3))
        cv2.rectangle(bg, (x, y), (x + cw, y + ch), color, -1)
    return bg


def _make_textured_icon(size: int = 180) -> NDArray[np.uint8]:
    """Clean-background icon with bold geometric overlays.

    Mirrors the kind of high-contrast UI icon AKAZE was designed for
    (KAZE diffusion gives few responses on per-pixel noise; it locks
    onto smooth regions joined by sharp edges). The bold strokes here
    yield ~100+ stable keypoints at ``size=180`` — comfortably above
    the ``min_inliers=8`` threshold even after ``scale=0.7`` shrinkage.
    """
    icon: NDArray[np.uint8] = np.full((size, size, 3), 240, dtype=np.uint8)
    cv2.rectangle(icon, (8, 8), (size - 8, size - 8), (50, 50, 50), 3)
    cv2.circle(icon, (size // 2, size // 2), size // 3, (200, 30, 30), 4)
    cv2.line(icon, (10, 10), (size - 10, size - 10), (30, 200, 30), 3)
    cv2.line(icon, (10, size - 10), (size - 10, 10), (30, 30, 200), 3)
    cv2.rectangle(
        icon,
        (size // 4, size // 4),
        (3 * size // 4, 3 * size // 4),
        (200, 200, 30),
        2,
    )
    pts = np.array(
        [[size // 2, 12], [12, size - 12], [size - 12, size - 12]],
        dtype=np.int32,
    )
    cv2.polylines(icon, [pts], True, (150, 30, 150), 2)
    return icon


def _paste_warped(
    bg: NDArray[np.uint8],
    icon: NDArray[np.uint8],
    scale: float,
    rotation_deg: float,
    x: int,
    y: int,
) -> tuple[NDArray[np.uint8], tuple[float, float]]:
    """Rotate + scale ``icon`` and paste it onto a copy of ``bg``.

    Returns the new image and the centre ``(cx, cy)`` of the placed
    (rotated) icon in ``bg``-local pixel coordinates. ``(x, y)`` is
    the top-left of the bounding box of the warped icon in ``bg``.
    """
    out = bg.copy()
    h, w = icon.shape[:2]
    center = (w / 2.0, h / 2.0)
    rot_mat = cv2.getRotationMatrix2D(center, rotation_deg, scale)
    cos = abs(float(rot_mat[0, 0]))
    sin = abs(float(rot_mat[0, 1]))
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    rot_mat[0, 2] += new_w / 2 - center[0]
    rot_mat[1, 2] += new_h / 2 - center[1]
    warped = cv2.warpAffine(icon, rot_mat, (new_w, new_h), borderValue=(0, 0, 0))
    mask_src: NDArray[np.uint8] = np.full((h, w), 255, dtype=np.uint8)
    mask = cv2.warpAffine(mask_src, rot_mat, (new_w, new_h), borderValue=0)

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
        region_mask = mask[src_y0:src_y1, src_x0:src_x1] > 0
        out[y0:y1, x0:x1][region_mask] = warped[src_y0:src_y1, src_x0:src_x1][
            region_mask
        ]
    cx = x + new_w / 2.0
    cy = y + new_h / 2.0
    return out, (cx, cy)


class TestAkazeDetectEngineBasic:
    def test_finds_query_at_default_transform(self):
        bg = _make_textured_background()
        icon = _make_textured_icon()
        img, (true_cx, true_cy) = _paste_warped(bg, icon, 1.0, 0.0, 200, 150)

        engine = AkazeDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        for d in dets:
            assert isinstance(d, Detection)

        best = max(dets, key=lambda d: d.confidence)
        cx, cy = best.center
        # AKAZE は SIFT より keypoint 局在化が粗めなため ±6px に緩める。
        assert abs(cx - true_cx) < 6
        assert abs(cy - true_cy) < 6
        assert best.confidence > 0.5
        assert 0.8 < best.scale < 1.2
        assert abs(best.rotation) < 0.1

    def test_polygon_corners_are_finite_and_in_image(self):
        bg = _make_textured_background()
        icon = _make_textured_icon()
        img, _ = _paste_warped(bg, icon, 1.0, 0.0, 200, 150)

        engine = AkazeDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        det = dets[0]
        for x, y in det.polygon:
            assert math.isfinite(x)
            assert math.isfinite(y)
            # Polygon centre lands inside the 720×1024 canvas;
            # corners may overshoot by a couple of pixels under
            # extreme RANSAC but should be well within bounds here.
            assert -10 < x < 1034
            assert -10 < y < 730


class TestAkazeDetectEngineScale:
    @pytest.mark.parametrize("scale", [0.7, 1.0, 1.5])
    def test_recovers_scale(self, scale: float):
        bg = _make_textured_background()
        icon = _make_textured_icon()
        img, (true_cx, true_cy) = _paste_warped(bg, icon, scale, 0.0, 250, 200)

        engine = AkazeDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        best = max(dets, key=lambda d: d.confidence)
        cx, cy = best.center
        # Centre tolerance scales with the icon size on screen.
        assert abs(cx - true_cx) < 10
        assert abs(cy - true_cy) < 10
        # Scale recovery is noisy on textured icons; ±35% is realistic.
        assert scale * 0.65 < best.scale < scale * 1.35


class TestAkazeDetectEngineRotation:
    @pytest.mark.parametrize("rotation_deg", [0.0, 30.0, -45.0, 90.0])
    def test_recovers_rotation(self, rotation_deg: float):
        bg = _make_textured_background()
        icon = _make_textured_icon()
        img, (true_cx, true_cy) = _paste_warped(bg, icon, 1.0, rotation_deg, 250, 200)

        engine = AkazeDetectEngine()
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        best = max(dets, key=lambda d: d.confidence)
        cx, cy = best.center
        assert abs(cx - true_cx) < 10
        assert abs(cy - true_cy) < 10
        # cv2.getRotationMatrix2D applies a clockwise rotation in
        # image-space (Y-down) for positive angles, but the resulting
        # rotation matrix's atan2(c, a) returns the *opposite* sign --
        # so we compare against the negated truth, modulo 2π wrap.
        expected_rad = -math.radians(rotation_deg)
        diff = (best.rotation - expected_rad + math.pi) % (2 * math.pi) - math.pi
        assert abs(diff) < 0.25


class TestAkazeDetectEngineMultiInstance:
    def test_finds_at_least_one_of_two_instances(self):
        # AKAZE's M-LDB (binary) descriptors give Lowe's ratio test
        # less headroom than SIFT's float descriptors do: when two
        # similar instances appear, each query keypoint typically has
        # two near-equal matches (one per instance) and the ratio test
        # rejects both. This is a known limitation of binary-descriptor
        # + Lowe-ratio pipelines and the reason real-world multi-instance
        # tasks in this codebase favour scenes with distinct instances.
        # The test below pins the contract: the engine must not crash
        # when two instances are present and must recover at least the
        # dominant one — even when the weaker instance gets starved out.
        bg = _make_textured_background()
        icon = _make_textured_icon()
        img, c1 = _paste_warped(bg, icon, 0.8, 0.0, 30, 30)
        img, c2 = _paste_warped(img, icon, 1.5, 75.0, 600, 350)

        engine = AkazeDetectEngine(ratio=0.9, min_inliers=6)
        dets = engine.detect(img, icon)

        assert len(dets) >= 1
        # Whichever instance was recovered must land on its truth centre.
        assert any(
            abs(d.center[0] - truth[0]) < 14 and abs(d.center[1] - truth[1]) < 14
            for d in dets
            for truth in (c1, c2)
        )


class TestAkazeDetectEngineNoMatch:
    def test_returns_empty_when_query_is_absent(self):
        bg = _make_textured_background(seed=99)
        icon = _make_textured_icon()
        engine = AkazeDetectEngine()
        dets = engine.detect(bg, icon)
        assert list(dets) == []

    def test_returns_empty_when_image_has_no_features(self):
        # A flat canvas yields zero AKAZE keypoints; the engine must
        # bail without crashing on the empty descriptor matrix.
        flat: NDArray[np.uint8] = np.full((100, 100, 3), 255, dtype=np.uint8)
        icon = _make_textured_icon()
        engine = AkazeDetectEngine()
        dets = engine.detect(flat, icon)
        assert list(dets) == []

    def test_returns_empty_when_query_has_no_features(self):
        bg = _make_textured_background()
        flat_icon: NDArray[np.uint8] = np.full((50, 50, 3), 128, dtype=np.uint8)
        engine = AkazeDetectEngine()
        dets = engine.detect(bg, flat_icon)
        assert list(dets) == []


class TestAkazeDetectEngineMaxResults:
    def test_max_results_truncates_output(self):
        # Build a scene with several variants so the iterative loop
        # produces multiple candidates, then verify the ``max_results``
        # cap is honoured.
        bg = _make_textured_background()
        icon = _make_textured_icon()
        img, _ = _paste_warped(bg, icon, 0.8, 0.0, 30, 30)
        img, _ = _paste_warped(img, icon, 1.5, 75.0, 600, 350)

        engine = AkazeDetectEngine(ratio=0.9, min_inliers=6, max_results=1)
        dets = engine.detect(img, icon)
        assert len(dets) <= 1
