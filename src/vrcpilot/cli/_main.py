# PYTHON_ARGCOMPLETE_OK
"""Top-level argv parsing and dispatch for :mod:`vrcpilot.cli`.

The :data:`_COMMANDS` table is the single dispatch point: every
subcommand module registers its parser and contributes one
``run(args) -> int`` entry. The top-level subparsers use
``required=True`` so bare ``vrcpilot`` (no subcommand) fails fast with
a usage error instead of silently exiting 0.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

import argcomplete

# Submodules are imported via their full dotted path and aliased so they
# do NOT clash with same-named re-exports on ``vrcpilot.cli`` (e.g.
# ``focus``/``unfocus`` are exposed as window-function re-exports for
# test patching, while the subcommand modules live alongside them).
import vrcpilot.cli.capture as _cmd_capture
import vrcpilot.cli.focus as _cmd_focus
import vrcpilot.cli.keyboard as _cmd_keyboard
import vrcpilot.cli.launch as _cmd_launch
import vrcpilot.cli.mouse as _cmd_mouse
import vrcpilot.cli.pid as _cmd_pid
import vrcpilot.cli.screenshot as _cmd_screenshot
import vrcpilot.cli.terminate as _cmd_terminate
import vrcpilot.cli.unfocus as _cmd_unfocus

_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "launch": _cmd_launch.run,
    "pid": _cmd_pid.run,
    "terminate": _cmd_terminate.run,
    "focus": _cmd_focus.run,
    "unfocus": _cmd_unfocus.run,
    "screenshot": _cmd_screenshot.run,
    "capture": _cmd_capture.run,
    "mouse": _cmd_mouse.run,
    "keyboard": _cmd_keyboard.run,
}


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands.

    Extracted from :func:`main` so tests and the ``argcomplete`` hook
    can obtain a fully-configured parser without running the command.
    """
    parser = argparse.ArgumentParser(
        prog="vrcpilot",
        description="Automation tooling for VRChat.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _cmd_launch.register(subparsers)
    _cmd_pid.register(subparsers)
    _cmd_terminate.register(subparsers)
    _cmd_focus.register(subparsers)
    _cmd_unfocus.register(subparsers)
    _cmd_screenshot.register(subparsers)
    _cmd_capture.register(subparsers)
    _cmd_mouse.register(subparsers)
    _cmd_keyboard.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ``vrcpilot`` CLI and return an exit code.

    Returns the code instead of calling :func:`sys.exit` so tests can
    pass ``argv`` and assert on the return value.

    Args:
        argv: Argument list passed to :mod:`argparse`. ``None`` reads
            :data:`sys.argv`.

    Returns:
        ``0`` on success, ``2`` on environment errors such as Steam
        missing (mirrors common CLI conventions).
    """
    parser = _build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)

    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")
    return handler(args)
