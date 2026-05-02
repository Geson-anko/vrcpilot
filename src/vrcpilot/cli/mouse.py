"""``vrcpilot mouse`` subcommand.

Thin CLI wrapper over :mod:`vrcpilot.controls.mouse`. Only ``click`` is
exposed: a separate ``press`` / ``release`` per CLI invocation cannot
work because each ``vrcpilot`` process opens and closes its own backend
(``/dev/uinput`` on Linux), and the kernel auto-releases all held
buttons when the virtual device is destroyed. ``click`` keeps the
down -> sleep -> up sequence inside one process so the click actually
lands. Mirrors the same trade-off applied to the ``keyboard``
subcommand.

The :data:`mouse_api` alias below is a stable patch target: tests bind
their fakes by patching ``vrcpilot.controls.mouse._get`` so the real
public ``mouse.click`` flows through to a recording
:class:`~vrcpilot.controls.mouse.Mouse` impl.
"""

from __future__ import annotations

import argparse
import sys

from vrcpilot.controls import (
    VRChatNotFocusedError,
    VRChatNotRunningError,
    mouse as mouse_api,
)
from vrcpilot.controls.mouse import MouseButton

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``mouse`` subparser plus the ``click`` sub-subcommand."""
    parser = subparsers.add_parser(
        "mouse",
        help="Synthetic mouse input (click only; held-state across "
        "invocations is not supported by the CLI).",
    )
    actions = parser.add_subparsers(dest="mouse_action", required=True)

    click_parser = actions.add_parser(
        "click",
        help="Click a mouse button (default: left).",
    )
    click_parser.add_argument(
        "button",
        nargs="?",
        type=MouseButton,
        default=MouseButton.LEFT,
        help="Mouse button: left / right / middle. Default: left.",
    )
    click_parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of clicks. Default: 1.",
    )
    click_parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Down-to-up hold per click, in seconds. Default: 0.0.",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``mouse click`` subcommand.

    Silent on success. Guard failures (VRChat not running / not focused)
    print a single ``vrcpilot: <message>`` line to stderr and return
    exit 1.

    Returns:
        ``0`` on success, ``1`` on guard failure.
    """
    try:
        mouse_api.click(args.button, count=args.count, duration=args.duration)
    except (VRChatNotRunningError, VRChatNotFocusedError) as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 1
    return 0
