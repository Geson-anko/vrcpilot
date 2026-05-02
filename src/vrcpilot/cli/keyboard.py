"""``vrcpilot keyboard`` subcommand.

Thin CLI wrapper over :mod:`vrcpilot.controls.keyboard`. Each action
forwards directly to the public module functions (``keyboard.up``,
``keyboard.down``, ``keyboard.press``) so the focus-guard and backend
dispatch stay shared with library callers.

The :mod:`keyboard_api` alias below is a stable patch target: tests bind
their fakes by patching ``vrcpilot.controls.keyboard._get`` so the real
public ``keyboard.up`` / ``keyboard.down`` / ``keyboard.press`` flows
through to a recording :class:`~vrcpilot.controls.keyboard.Keyboard`
impl.
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
    """Add the ``keyboard`` subparser plus its three action sub-subcommands."""
    parser = subparsers.add_parser(
        "keyboard",
        help="Synthetic keyboard input (up / down / press).",
    )
    actions = parser.add_subparsers(dest="keyboard_action", required=True)

    up_parser = actions.add_parser(
        "up",
        help="Release one or more keys (sequentially, in argument order).",
    )
    up_parser.add_argument(
        "keys",
        nargs="+",
        type=Key,
        metavar="KEY",
        help="One or more Key enum values (e.g. a, ctrl, escape, f1).",
    )

    down_parser = actions.add_parser(
        "down",
        help="Press and hold one or more keys (sequentially, in argument order).",
    )
    down_parser.add_argument(
        "keys",
        nargs="+",
        type=Key,
        metavar="KEY",
        help="One or more Key enum values (e.g. a, ctrl, escape, f1).",
    )

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
    """Execute the ``keyboard`` subcommand.

    Silent on success. Guard failures (VRChat not running / not focused)
    print a single ``vrcpilot: <message>`` line to stderr and return
    exit 1. The action dispatch uses ``args.keyboard_action`` set by the
    sub-subparser; keys are processed sequentially in argument order and
    the loop bails on the first guard error (no point continuing if
    VRChat is unreachable).

    Returns:
        ``0`` on success, ``1`` on guard failure.
    """
    keys: list[Key] = args.keys
    try:
        match args.keyboard_action:
            case "up":
                for key in keys:
                    keyboard_api.up(key)
            case "down":
                for key in keys:
                    keyboard_api.down(key)
            case "press":
                duration: float = args.duration
                for key in keys:
                    keyboard_api.press(key, duration=duration)
            case _:  # pragma: no cover - argparse required=True prevents this
                raise AssertionError(
                    f"Unknown keyboard action: {args.keyboard_action!r}"
                )
    except (VRChatNotRunningError, VRChatNotFocusedError) as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 1
    return 0
