"""Tests for :mod:`vrcpilot.controls` public surface.

The subpackage and the top-level package must expose the same core
symbols: ``ensure_target``, the two error types, and the :class:`Key`
enum. Wiring them in two places is what lets users write either
``vrcpilot.ensure_target`` or ``from vrcpilot.controls import
ensure_target`` interchangeably; if either re-export drifts away from
the canonical implementation, tests in other modules that
``mocker.patch`` one of them would silently miss the other call site.
"""

from __future__ import annotations

from enum import StrEnum

import vrcpilot
import vrcpilot.controls


class TestSubpackageSurface:
    def test_exposes_ensure_target(self):
        assert callable(vrcpilot.controls.ensure_target)

    def test_exposes_error_types(self):
        assert issubclass(vrcpilot.controls.VRChatNotRunningError, RuntimeError)
        assert issubclass(vrcpilot.controls.VRChatNotFocusedError, RuntimeError)

    def test_exposes_key_enum(self):
        assert issubclass(vrcpilot.controls.Key, StrEnum)


class TestTopLevelReexport:
    def test_ensure_target_is_same_object(self):
        assert vrcpilot.ensure_target is vrcpilot.controls.ensure_target

    def test_error_types_are_same_objects(self):
        assert vrcpilot.VRChatNotRunningError is vrcpilot.controls.VRChatNotRunningError
        assert vrcpilot.VRChatNotFocusedError is vrcpilot.controls.VRChatNotFocusedError

    def test_key_is_same_object(self):
        assert vrcpilot.Key is vrcpilot.controls.Key
