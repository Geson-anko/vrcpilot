"""Tests for :mod:`vrcpilot.capture` public surface.

The package is the documented entry point for both the one-shot
``Capture`` session and the threaded ``CaptureLoop`` driver. We
verify here that the canonical names are exported and that
``__all__`` matches them — backend behaviour is covered by the
sibling ``test_session`` / ``test_loop`` files.
"""

from __future__ import annotations

import vrcpilot.capture
from vrcpilot.capture import Capture, CaptureLoop


class TestPublicSurface:
    def test_module_exports_capture_and_capture_loop(self):
        # The two names are the documented entry points; importing them
        # directly catches accidental renames or missing re-exports.
        assert vrcpilot.capture.Capture is Capture
        assert vrcpilot.capture.CaptureLoop is CaptureLoop

    def test_all_lists_capture_and_capture_loop(self):
        # ``__all__`` is consumed by ``from ... import *`` and by tooling
        # that infers the public surface; keep it in sync with the
        # actual exports so consumers cannot accidentally grow a
        # dependency on internals.
        assert set(vrcpilot.capture.__all__) == {"Capture", "CaptureLoop"}
