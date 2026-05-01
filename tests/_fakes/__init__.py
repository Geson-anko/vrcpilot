"""Unified test doubles for vrcpilot tests.

Tests must NOT define their own ad-hoc ``_Fake*`` classes for shared
collaborators. Instead, import a fake from this package so the
behaviour and surface are consistent across the suite.

Usage:

    from tests._fakes import FakeCapture, FakePopen

When a fake's surface needs extending, modify the canonical class
here so every test benefits — do not subclass ad-hoc inside a test
file. (Per-test class-level state isolation is provided by helper
fixtures next to each fake; see :mod:`tests._fakes.capture`.)
"""

from __future__ import annotations

from .capture import (
    FakeCapture,
    FakeCaptureLoop,
    FakeMp4Sink,
    FakeWindowsCapture,
    FakeWindowsCaptureControl,
    FakeWindowsFrame,
)
from .process import FakePopen, FakeProcess
from .x11 import FakeXDisplay, FakeXGeometry, FakeXWindow

__all__ = [
    "FakeCapture",
    "FakeCaptureLoop",
    "FakeMp4Sink",
    "FakePopen",
    "FakeProcess",
    "FakeWindowsCapture",
    "FakeWindowsCaptureControl",
    "FakeWindowsFrame",
    "FakeXDisplay",
    "FakeXGeometry",
    "FakeXWindow",
]
