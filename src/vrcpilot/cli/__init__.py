# PYTHON_ARGCOMPLETE_OK
"""Command line interface for vrcpilot.

Thin wrapper that translates the public Python API into exit codes;
behavioural logic stays in the library. Each subcommand lives in
``vrcpilot.cli.<name>`` and exposes a ``register(subparsers)`` /
``run(args) -> int`` pair which :mod:`._main` wires together.
:func:`main` is the entry point for both the ``vrcpilot`` console
script and ``python -m vrcpilot``.

The ``time`` / ``argcomplete`` / ``focus`` / ``unfocus`` /
``take_screenshot`` / ``CaptureLoop`` / ``Mp4FrameSink`` re-exports
exist solely as stable patch targets for tests; production callsites
inside subcommand modules read them as ``vrcpilot.cli.<name>`` so
``mocker.patch`` can substitute fakes without monkeying the underlying
library modules.
"""

from __future__ import annotations

import time as time  # re-exported for test patching

import argcomplete as argcomplete  # re-exported for test patching

from vrcpilot.capture import CaptureLoop as CaptureLoop
from vrcpilot.capture.sinks import Mp4FrameSink as Mp4FrameSink
from vrcpilot.screenshot import take_screenshot as take_screenshot
from vrcpilot.window import focus as _window_focus, unfocus as _window_unfocus

# Importing ``_main`` triggers loading of the per-command submodules
# (``vrcpilot.cli.focus`` etc.) which, by Python import-system rules,
# overwrites any same-named attributes on this package. Re-bind the
# ``focus`` / ``unfocus`` window-function attributes AFTER ``_main``
# loads so production callsites (``_cli.focus()`` inside the per-command
# submodules) and ``mocker.patch("vrcpilot.cli.focus", ...)`` keep
# resolving to a callable.
from ._main import (
    _build_parser as _build_parser,  # pyright: ignore[reportPrivateUsage]
    main as main,
)

focus = _window_focus
unfocus = _window_unfocus

__all__ = ["main"]
