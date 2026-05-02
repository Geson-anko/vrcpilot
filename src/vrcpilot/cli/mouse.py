"""``vrcpilot mouse`` subcommand.

Thin CLI wrapper over :mod:`vrcpilot.controls.mouse`. Each action
forwards directly to the public module functions (``mouse.move``,
``mouse.click``, ``mouse.press``, ``mouse.release``, ``mouse.scroll``)
so the focus-guard and backend dispatch stay shared with library
callers.

The :mod:`mouse_api` alias below is a stable patch target: tests bind
their fakes by patching ``vrcpilot.cli.mouse.mouse_api`` (or, in
practice, ``vrcpilot.controls.mouse._get`` so ``mouse_api.<func>``
flows through to a real :class:`~vrcpilot.controls.mouse.Mouse` impl).
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
    """Add the ``mouse`` subparser plus its five action sub-subcommands."""
    parser = subparsers.add_parser(
        "mouse",
        help="Synthetic mouse input (move / click / press / release / scroll).",
    )
    actions = parser.add_subparsers(dest="mouse_action", required=True)

    move_parser = actions.add_parser(
        "move",
        help="Move the cursor to (X, Y), or by (X, Y) with --rel.",
    )
    move_parser.add_argument("x", type=int)
    move_parser.add_argument("y", type=int)
    move_parser.add_argument(
        "--rel",
        action="store_true",
        help="Treat X and Y as relative deltas instead of absolute pixels.",
    )

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

    press_parser = actions.add_parser(
        "press",
        help="Press and hold a mouse button (default: left).",
    )
    press_parser.add_argument(
        "button",
        nargs="?",
        type=MouseButton,
        default=MouseButton.LEFT,
        help="Mouse button: left / right / middle. Default: left.",
    )

    release_parser = actions.add_parser(
        "release",
        help="Release a previously pressed mouse button (default: left).",
    )
    release_parser.add_argument(
        "button",
        nargs="?",
        type=MouseButton,
        default=MouseButton.LEFT,
        help="Mouse button: left / right / middle. Default: left.",
    )

    scroll_parser = actions.add_parser(
        "scroll",
        help="Scroll vertically by AMOUNT notches (positive = down).",
    )
    scroll_parser.add_argument("amount", type=int)


def run(args: argparse.Namespace) -> int:
    """Execute the ``mouse`` subcommand.

    Silent on success. Guard failures (VRChat not running / not focused)
    print a single ``vrcpilot: <message>`` line to stderr and return
    exit 1. The action dispatch uses ``args.mouse_action`` set by the
    sub-subparser.

    Returns:
        ``0`` on success, ``1`` on guard failure.
    """
    try:
        match args.mouse_action:
            case "move":
                mouse_api.move(args.x, args.y, relative=args.rel)
            case "click":
                mouse_api.click(args.button, count=args.count, duration=args.duration)
            case "press":
                mouse_api.press(args.button)
            case "release":
                mouse_api.release(args.button)
            case "scroll":
                mouse_api.scroll(args.amount)
            case _:  # pragma: no cover - argparse required=True prevents this
                raise AssertionError(f"Unknown mouse action: {args.mouse_action!r}")
    except (VRChatNotRunningError, VRChatNotFocusedError) as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 1
    return 0
