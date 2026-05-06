"""Image-query detection of UI elements within :mod:`vrcpilot`.

Public surface:

* :class:`DetectEngine` — ABC for swappable detection backends.
* :class:`Detection` — single image-local detection value type.
* :class:`DetectResult` — bundle of screenshot + query + detections,
  with helpers to translate to desktop-absolute coordinates.
* :class:`TemplateDetectEngine` — multi-scale template-match
  implementation. Currently the only shipped engine: real-device e2e
  showed it landing 10/10 on VRChat's small UI icons while
  feature-based detectors (SIFT / AKAZE / ORB) struggled to extract
  enough keypoints from 18-50 px targets.
* :func:`detect` — run a :class:`DetectEngine` against a
  :class:`Screenshot` plus query image and bundle the result.
* :func:`render` — return an RGB ndarray with a :class:`DetectResult`
  drawn over its screenshot.
* :data:`Polygon` — 4-corner polygon type alias. Re-exported so users
  writing custom engines can annotate with the same shape.
"""

from __future__ import annotations

from vrcpilot.types import Polygon

from .base import DetectEngine, Detection
from .detect import DetectResult, detect
from .template import TemplateDetectEngine
from .visualize import render

__all__ = [
    "DetectEngine",
    "DetectResult",
    "Detection",
    "Polygon",
    "TemplateDetectEngine",
    "detect",
    "render",
]
