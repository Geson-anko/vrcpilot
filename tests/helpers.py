"""Shared test helpers."""

from __future__ import annotations

import sys

import pytest

#: Skip a test on non-Windows platforms.
#:
#: Use for tests whose body touches Windows-only APIs (e.g.
#: ``subprocess.CREATE_NEW_PROCESS_GROUP``) that are absent on POSIX runners,
#: even when ``sys.platform`` itself is monkey-patched.
only_windows = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows-only behaviour"
)

#: Skip a test on non-Linux platforms.
#:
#: Use for tests that exercise Linux-specific behaviour and would fail on
#: Windows runners regardless of ``sys.platform`` patching.
only_linux = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="Linux-only behaviour"
)
