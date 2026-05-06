"""Shared helpers for the :mod:`vrcpilot.cli` subcommand modules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from argcomplete.completers import FilesCompleter

from vrcpilot.screenshot import Screenshot

# argparse does not export the subparsers-action class publicly but it
# is exactly what ``add_subparsers()`` returns — typing the per-command
# ``register()`` hooks against it keeps the API self-documenting at the
# cost of a single private-usage suppression.
type SubParsersAction = argparse._SubParsersAction[argparse.ArgumentParser]  # pyright: ignore[reportPrivateUsage]


def attach_completer(action: argparse.Action, completer: object) -> None:
    """Attach an ``argcomplete`` completer to an argparse ``Action``.

    ``argcomplete`` reads ``action.completer`` at completion time but
    argparse itself does not declare the attribute, so a direct
    assignment trips ``reportAttributeAccessIssue`` under pyright
    strict. Routing through ``setattr`` keeps that noise out of
    the subparser registration sites.
    """
    setattr(action, "completer", completer)  # noqa: B010 - argcomplete's documented hook


def add_screenshot_input_arg(parser: argparse.ArgumentParser) -> None:
    """Register ``--screenshot <yaml-path>`` on ``parser``.

    Subcommands that operate on a :class:`~vrcpilot.screenshot.Screenshot`
    use this to opt into the shared input-resolution contract handled by
    :func:`resolve_screenshot`. No short form is exposed so future
    subcommand-local flags (notably ``vrcpilot detect``'s query options)
    can claim ``-s`` without colliding. The completer offers
    ``.yaml`` / ``.yml`` files plus directories.
    """
    action = parser.add_argument(
        "-s",
        "--screenshot",
        type=Path,
        default=None,
        metavar="YAML",
        help=(
            "Read a previously captured screenshot from this YAML file "
            "(as emitted by ``vrcpilot screenshot``) instead of capturing "
            "a fresh one."
        ),
    )
    attach_completer(
        action, FilesCompleter(allowednames=("yaml", "yml"), directories=True)
    )


def resolve_screenshot(args: argparse.Namespace) -> Screenshot | None:
    """Resolve a :class:`Screenshot` from CLI args or piped stdin.

    Priority order:

    1. ``args.screenshot`` (set by :func:`add_screenshot_input_arg`) — read
       the YAML file from disk and decode via :meth:`Screenshot.load`.
    2. Piped stdin (``not sys.stdin.isatty()``) — read the YAML text from
       stdin and decode via :meth:`Screenshot.load`.

    When ``--screenshot`` is given, stdin is *not* read even if it is
    piped (the flag takes precedence and the stdin payload is silently
    ignored). Pass exactly one source per invocation to avoid surprises.

    If neither is available (no flag and stdin is a tty), an explanatory
    message is written to stderr and ``None`` is returned. Callers
    typically map ``None`` to ``return 1``.
    """
    screenshot_arg: Path | None = getattr(args, "screenshot", None)
    if screenshot_arg is not None:
        try:
            text = screenshot_arg.read_text()
        except FileNotFoundError:
            print(
                f"vrcpilot: --screenshot file not found: {screenshot_arg}",
                file=sys.stderr,
            )
            return None
        try:
            return Screenshot.load(text)
        except ValueError as exc:
            print(f"vrcpilot: {exc}", file=sys.stderr)
            return None

    if not sys.stdin.isatty():
        try:
            return Screenshot.load(sys.stdin.read())
        except ValueError as exc:
            print(f"vrcpilot: {exc}", file=sys.stderr)
            return None

    print(
        "vrcpilot: no screenshot provided; "
        "pass --screenshot <yaml> or pipe 'vrcpilot screenshot' output via stdin",
        file=sys.stderr,
    )
    return None
