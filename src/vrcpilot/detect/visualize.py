"""Render a :class:`DetectResult` onto a copy of its screenshot image.

The output is an RGB ``uint8`` ndarray; callers typically save it via
``PIL.Image.fromarray(...)``. The screenshot image inside the result is
**not** mutated — :func:`render` always works on a fresh copy.

Auto-contrast: when ``text_color`` is left ``None``, each detection
picks its own colour by sampling the original (pre-draw) bbox patch.
A mostly-bright background gets black text, a mostly-dark background
gets white. This avoids producing unreadable white-on-white or
black-on-black overlays without forcing the caller to think about it.
"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from .detect import DetectResult


def _decide_text_color(
    original: NDArray[np.uint8],
    bbox: tuple[int, int, int, int],
) -> tuple[int, int, int]:
    """Pick black or white based on the mean luminance of *bbox*.

    The patch is clipped to the image bounds; a fully-out-of-bounds bbox
    yields an empty slice, which we treat as a bright background (mean =
    255) so the resulting text is black. This matches the "default to
    readable on white" intuition when no signal exists.
    """
    h, w = original.shape[:2]
    bx, by, bw, bh = bbox
    x0 = max(0, bx)
    y0 = max(0, by)
    x1 = min(w, bx + bw)
    y1 = min(h, by + bh)
    if x1 <= x0 or y1 <= y0:
        return (0, 0, 0)
    patch = original[y0:y1, x0:x1]
    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    mean = float(gray.mean())
    if mean > 128:
        return (0, 0, 0)
    return (255, 255, 255)


def render(
    result: DetectResult,
    *,
    box_color: tuple[int, int, int] = (0, 255, 0),
    text_color: tuple[int, int, int] | None = None,
    font_scale: float = 0.6,
    thickness: int = 2,
) -> NDArray[np.uint8]:
    """Draw detections onto a copy of the screenshot image.

    Each :class:`~vrcpilot.detect.Detection` is rendered as a polygon
    outline plus a ``"<confidence> x<scale>"`` label placed just above
    the bounding box (or just below, when the text would otherwise go
    off the top of the image). Same placement convention as the OCR
    renderer in :func:`vrcpilot.ocr.render`.

    Args:
        result: :class:`DetectResult` to render. ``screenshot.image``
            is the background and ``detections`` are drawn on top.
        box_color: RGB triple for the polygon outline (same green as
            OCR, ``(0, 255, 0)``).
        text_color: RGB triple for the label. ``None`` (default) picks
            black or white per detection based on the underlying
            patch's mean luminance.
        font_scale: ``cv2.putText`` font scale.
        thickness: Stroke thickness for both polygon and label.

    Returns:
        ``(H, W, 3)`` ``uint8`` RGB ndarray with the same shape and
        dtype as ``result.screenshot.image``. The input image is left
        untouched.
    """
    original = result.screenshot.image
    canvas: NDArray[np.uint8] = original.copy()

    for det in result.detections:
        polygon_pts = np.array(det.polygon, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(
            canvas,
            [polygon_pts],
            isClosed=True,
            color=box_color,
            thickness=thickness,
        )

        bbox = det.bbox
        chosen_color: tuple[int, int, int] = (
            text_color if text_color is not None else _decide_text_color(original, bbox)
        )

        label = f"{det.confidence:.2f} x{det.scale:.2f}"

        bx, by, _bw, bh = bbox
        # Only the text height is used for the above/below choice;
        # width and baseline are returned by the API but irrelevant here.
        (_text_w, text_h), _baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        # Prefer placing text above the bbox; fall back below when
        # the top edge lacks the height to fit it.
        if by - text_h - 4 >= 0:
            text_y = by - 4
        else:
            text_y = by + bh + text_h + 4
        cv2.putText(
            canvas,
            label,
            (bx, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            chosen_color,
            thickness,
            cv2.LINE_AA,
        )

    return canvas
