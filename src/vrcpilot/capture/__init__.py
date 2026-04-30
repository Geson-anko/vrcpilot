"""Continuous-frame capture API for the VRChat window.

Focus-free on both platforms: Linux reads the off-screen pixmap via the
X11 Composite extension and Windows uses Windows.Graphics.Capture, so
the window is never raised. For one-shot grabs paired with on-screen
geometry use :func:`vrcpilot.screenshot.take_screenshot` instead.
"""

from __future__ import annotations

from .loop import CaptureLoop
from .session import Capture

__all__ = ["Capture", "CaptureLoop"]
