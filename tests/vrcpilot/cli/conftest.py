"""Shared fixtures for the :mod:`vrcpilot.cli` test suite.

The autouse fixture here pins ``sys.stdin.isatty()`` to ``True`` for
every CLI test by default. ``vrcpilot.cli._common.resolve_screenshot``
takes the piped-stdin branch whenever stdin is not a tty, but pytest
runners under common harnesses (uv, CI containers) leave stdin as a
non-tty pipe -- without this fixture, ``ocr`` / ``detect`` tests that
do not explicitly pipe a screenshot would read garbage from the test
runner's stdin and try to parse it as a screenshot YAML.

With this fixture in place the default state is "no piped stdin", which
since commit 10's removal of the live-capture fallback means
``--screenshot``-less ``ocr`` / ``detect`` invocations exit 1 with an
explanatory message. Tests that explicitly cover the stdin route
override this default by patching ``vrcpilot.cli._common.sys.stdin``
with a ``StringIO`` (whose ``isatty()`` naturally returns ``False``);
the explicit patch shadows the autouse default and is unwound first
when the test ends.
"""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def _stdin_is_tty_by_default(mocker: MockerFixture) -> None:
    """Default ``sys.stdin.isatty()`` to ``True`` for CLI tests."""
    mocker.patch("vrcpilot.cli._common.sys.stdin.isatty", return_value=True)
