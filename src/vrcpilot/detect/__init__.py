"""Image-query detection of UI elements within VRChat captures.

:class:`TemplateDetectEngine` is the default backend; the public
surface is engine-agnostic so callers can swap in a custom
:class:`DetectEngine`.
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
