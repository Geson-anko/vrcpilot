"""``vrcpilot capture`` subcommand."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from argcomplete.completers import FilesCompleter

from vrcpilot import cli as _cli

from ._common import SubParsersAction, attach_completer


def register(subparsers: SubParsersAction) -> None:
    """Add the ``capture`` subparser to the top-level subparsers."""
    capture_parser = subparsers.add_parser(
        "capture",
        help="Record VRChat at a fixed FPS and save as mp4.",
    )
    capture_output_action = capture_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Path where the mp4 video is written. Defaults to "
            "./vrcpilot_capture_<YYYYMMDD_HHMMSS>.mp4 in the current "
            "directory."
        ),
    )
    attach_completer(
        capture_output_action,
        FilesCompleter(allowednames=("mp4",), directories=True),
    )
    capture_parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Target frames per second (default: 30).",
    )
    capture_parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help=(
            "Stop after this many seconds. When unset, recording "
            "continues until Ctrl+C."
        ),
    )


def run(args: argparse.Namespace) -> int:
    """Execute the ``capture`` subcommand.

    Args:
        args: Parsed argparse namespace. Reads ``args.output`` /
            ``args.fps`` / ``args.duration``. ``output`` ``None``
            writes ``./vrcpilot_capture_<YYYYMMDD_HHMMSS>.mp4``.
            ``fps`` is the target frames per second; passed to both
            :class:`vrcpilot.capture.CaptureLoop` and the mp4
            container. ``duration`` stops after this many seconds —
            ``None`` waits for ``Ctrl+C`` (KeyboardInterrupt).

    Returns:
        ``0`` on success — the absolute path of the saved mp4 (a
        single line) is written to stdout. ``1`` if recording failed
        or no frames were captured. Progress messages go to stderr so
        stdout stays parseable.
    """
    output: Path | None = args.output
    fps: float = args.fps
    duration: float | None = args.duration

    if output is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path.cwd() / f"vrcpilot_capture_{stamp}.mp4"

    try:
        with _cli.Mp4FrameSink(output, fps) as sink:
            with _cli.CaptureLoop(sink.write, fps=fps) as loop:
                loop.start()
                # Progress messages go to stderr so stdout stays
                # parseable as a single absolute-path line. Callers
                # like ``out=$(vrcpilot capture --duration 5)`` get the
                # path without having to filter out chatter.
                print(
                    f"Recording to {output} (fps={fps}). Press Ctrl+C to stop.",
                    file=sys.stderr,
                )
                try:
                    if duration is not None:
                        time.sleep(duration)
                    else:
                        while True:
                            time.sleep(3600)
                except KeyboardInterrupt:
                    pass
            saved_frames = sink.frame_count
    except RuntimeError as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 1

    if saved_frames == 0:
        print("vrcpilot: no frames captured.", file=sys.stderr)
        return 1
    print(str(output.resolve()))
    return 0
