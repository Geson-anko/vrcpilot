"""Image-query detection of UI elements within :mod:`vrcpilot`.

Public surface:

* :class:`DetectEngine` — ABC for swappable detection backends.
* :class:`Detection` — single image-local detection value type.
* :class:`DetectResult` — bundle of screenshot + query + detections,
  with helpers to translate to desktop-absolute coordinates.
* :class:`TemplateDetectEngine` — default multi-scale template-match
  implementation. Highest detection rate on VRChat's small UI icons.
* :class:`AkazeDetectEngine` — opt-in AKAZE feature-based engine.
  Not viable on VRChat's small UI icons in practice (see the class
  docstring); kept for texture-rich targets.
* :class:`SiftDetectEngine` — opt-in SIFT feature-based engine. Picks
  up more than AKAZE but still trails Template on UI icons.
* :func:`detect` — run a :class:`DetectEngine` against a
  :class:`Screenshot` plus query image and bundle the result.
* :func:`render` — return an RGB ndarray with a :class:`DetectResult`
  drawn over its screenshot.
* :data:`Polygon` — 4-corner polygon type alias. Re-exported so users
  writing custom engines can annotate with the same shape.
"""

from __future__ import annotations

from vrcpilot.types import Polygon

from .akaze import AkazeDetectEngine
from .base import DetectEngine, Detection
from .detect import DetectResult, detect
from .sift import SiftDetectEngine
from .template import TemplateDetectEngine
from .visualize import render

__all__ = [
    "AkazeDetectEngine",
    "DetectEngine",
    "DetectResult",
    "Detection",
    "Polygon",
    "SiftDetectEngine",
    "TemplateDetectEngine",
    "detect",
    "render",
]
