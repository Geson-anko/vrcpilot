"""``vrcpilot capture`` subcommand."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from argcomplete.completers import FilesCompleter

from vrcpilot.capture import CaptureLoop
from vrcpilot.capture.sinks import Mp4FrameSink, Y4mStdoutFrameSink

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
            "Where to write the recording. With no value, streams y4m to "
            "stdout (pipe to ffmpeg etc.). With an existing directory, "
            "writes mp4 to <dir>/vrcpilot_capture_<YYYYMMDD_HHMMSS>.mp4. "
            "Otherwise, treats the value as the mp4 file path."
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


def _resolve_output(arg: Path | None, *, now: datetime) -> Path | None:
    """Resolve ``args.output`` to a concrete mp4 path or ``None``.

    Args:
        arg: Raw value from ``args.output``. ``None`` (flag absent) means
            the caller wants the stdout y4m pipe. A :class:`Path` that
            points at an existing directory is expanded to a
            timestamped default file inside it. Any other :class:`Path`
            is treated as the explicit mp4 path the caller requested.
        now: Timestamp used to build the default filename. Taken as a
            parameter so tests can pin it.

    Returns:
        ``None`` to signal stdout pipe mode, otherwise the resolved
        mp4 :class:`Path`.
    """
    if arg is None:
        return None
    stamp = now.strftime("%Y%m%d_%H%M%S")
    default_name = f"vrcpilot_capture_{stamp}.mp4"
    if arg.is_dir():
        return arg / default_name
    return arg


def run(args: argparse.Namespace) -> int:
    """Execute the ``capture`` subcommand.

    Args:
        args: Parsed argparse namespace. Reads ``args.output`` /
            ``args.fps`` / ``args.duration``. ``output`` ``None``
            streams y4m to stdout (refused when stdout is a TTY); a
            :class:`Path` pointing at an existing directory writes
            ``<dir>/vrcpilot_capture_<YYYYMMDD_HHMMSS>.mp4``; any other
            :class:`Path` is used as the mp4 path verbatim. ``fps`` is
            the target frames per second; passed to both
            :class:`vrcpilot.capture.CaptureLoop` and the sink.
            ``duration`` stops after this many seconds - ``None`` waits
            for ``Ctrl+C`` (KeyboardInterrupt).

    Returns:
        ``0`` on success. In file mode the absolute path of the saved
        mp4 (a single line) is written to stdout; in pipe mode stdout
        carries the binary y4m stream and Python writes nothing extra
        there. ``1`` if recording failed, no frames were captured, or
        stdout was a TTY in pipe mode. Progress messages go to stderr
        so stdout stays parseable / pipe-clean.
    """
    target = _resolve_output(args.output, now=datetime.now())
    fps: float = args.fps
    duration: float | None = args.duration

    sink_cm: Mp4FrameSink | Y4mStdoutFrameSink
    if target is None:
        if sys.stdout.isatty():
            print(
                "vrcpilot: refusing to write a y4m stream to a TTY; "
                "pipe stdout or pass -o <path>",
                file=sys.stderr,
            )
            return 1
        sink_cm = Y4mStdoutFrameSink(fps)
        progress_target = "stdout (y4m)"
    else:
        sink_cm = Mp4FrameSink(target, fps)
        progress_target = str(target)

    try:
        with sink_cm as sink:
            with CaptureLoop(sink.write, fps=fps) as loop:
                loop.start()
                # Progress messages go to stderr so stdout stays
                # parseable as a single absolute-path line in file
                # mode, and pipe-clean (binary y4m only) in stdout
                # mode.
                print(
                    f"Recording to {progress_target} (fps={fps}). "
                    "Press Ctrl+C to stop.",
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
    if target is not None:
        print(str(target.resolve()))
    return 0
