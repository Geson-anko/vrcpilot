"""``vrcpilot paste`` subcommand.

Thin CLI wrapper over :func:`vrcpilot.clipboard.paste`. Reads the text
to paste from a positional argument or, when omitted, from stdin -- the
stdin fallback exists so callers can avoid shell-quoting headaches and
pipe multi-line text directly (``cat msg.txt | vrcpilot paste``). Both
:class:`~vrcpilot.controls.VRChatNotRunningError` /
:class:`~vrcpilot.controls.VRChatNotFocusedError` (raised by the keyboard
focus guard) and :class:`pyperclip.PyperclipException` (raised when the
clipboard backend is missing or busy) are caught and reported as a
single ``vrcpilot: <message>`` line on stderr with exit ``1``.

Exit codes:
    * ``0`` -- paste succeeded (silent on stdout/stderr).
    * ``1`` -- VRChat guard failure or clipboard backend error.
    * ``2`` -- no text supplied: positional omitted AND stdin is a tty.
      Without the tty check, an interactive ``vrcpilot paste`` would
      block on ``sys.stdin.read()`` waiting for EOF.
"""

from __future__ import annotations

import argparse
import sys

import pyperclip

from vrcpilot import clipboard
from vrcpilot.controls import VRChatNotFocusedError, VRChatNotRunningError

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``paste`` subparser to the top-level subparsers."""
    parser = subparsers.add_parser(
        "paste",
        help=(
            "Copy text to the clipboard and send Ctrl+V to VRChat. "
            "Reads from stdin when TEXT is omitted and stdin is piped."
        ),
    )
    parser.add_argument(
        "text",
        nargs="?",
        default=None,
        metavar="TEXT",
        help=(
            "Text to paste. Omit to read from stdin (only when stdin is "
            "piped; on a tty this exits with code 2)."
        ),
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``paste`` subcommand.

    Silent on success. See the module docstring for the full exit-code
    contract.

    Returns:
        ``0`` on success, ``1`` on VRChat guard / pyperclip failure,
        ``2`` when no text is provided and stdin is a tty.
    """
    raw: str | None = args.text
    if raw is None:
        if sys.stdin.isatty():
            print("vrcpilot: no text provided", file=sys.stderr)
            return 2
        text = sys.stdin.read()
    else:
        text = raw
    try:
        clipboard.paste(text)
    except (VRChatNotRunningError, VRChatNotFocusedError) as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 1
    except pyperclip.PyperclipException as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 1
    return 0
