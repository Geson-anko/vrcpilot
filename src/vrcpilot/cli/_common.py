"""Shared helpers for the :mod:`vrcpilot.cli` subcommand modules."""

from __future__ import annotations

import argparse

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
