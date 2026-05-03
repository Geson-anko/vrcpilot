"""``vrcpilot keyboard`` subcommand.

Thin CLI wrapper over :mod:`vrcpilot.controls.keyboard`. Only ``press``
is exposed: a separate ``up`` / ``down`` per CLI invocation cannot work
because each ``vrcpilot`` process opens and closes its own backend
(``/dev/uinput`` on Linux), and the kernel auto-releases all held keys
when the virtual device is destroyed. ``press`` keeps the down -> sleep
-> up sequence inside one process so the keypress actually lands.

The :data:`keyboard_api` alias below is a stable patch target: tests bind
their fakes by patching ``vrcpilot.controls.keyboard._get`` so the real
public ``keyboard.press`` flows through to a recording
:class:`~vrcpilot.controls.keyboard.Keyboard` impl.
"""

from __future__ import annotations

import argparse
import sys

from vrcpilot.controls import (
    VRChatNotFocusedError,
    VRChatNotRunningError,
    keyboard as keyboard_api,
)
from vrcpilot.controls.keyboard import Key

from ._common import SubParsersAction


def register(subparsers: SubParsersAction) -> None:
    """Add the ``keyboard`` subparser plus the ``press`` sub-subcommand."""
    parser = subparsers.add_parser(
        "keyboard",
        help="Synthetic keyboard input (press only; held-state across "
        "invocations is not supported by the CLI).",
    )
    actions = parser.add_subparsers(dest="keyboard_action", required=True)

    press_parser = actions.add_parser(
        "press",
        help="Tap one or more keys (down then up, sequentially).",
    )
    press_parser.add_argument(
        "keys",
        nargs="+",
        type=Key,
        metavar="KEY",
        help="One or more Key enum values (e.g. a, ctrl, escape, f1).",
    )
    press_parser.add_argument(
        "--duration",
        type=float,
        default=0.1,
        help="Down-to-up hold per key, in seconds. Default: 0.1.",
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``keyboard press`` subcommand.

    Silent on success. Guard failures (VRChat not running / not focused)
    print a single ``vrcpilot: <message>`` line to stderr and return
    exit 1. Keys are processed sequentially in argument order and the
    loop bails on the first guard error (no point continuing if VRChat
    is unreachable).

    Returns:
        ``0`` on success, ``1`` on guard failure.
    """
    keys: list[Key] = args.keys
    duration: float = args.duration
    try:
        for key in keys:
            keyboard_api.press(key, duration=duration)
    except (VRChatNotRunningError, VRChatNotFocusedError) as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 1
    return 0
