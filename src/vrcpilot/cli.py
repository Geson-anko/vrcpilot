# PYTHON_ARGCOMPLETE_OK
"""Command line interface for vrcpilot.

Thin wrapper that translates the public Python API into exit codes;
behavioural logic stays in the library.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import argcomplete
from argcomplete.completers import FilesCompleter
from PIL import Image

from vrcpilot import CaptureLoop
from vrcpilot.capture.sinks import Mp4FrameSink
from vrcpilot.process import (
    VRCHAT_STEAM_APP_ID,
    OscConfig,
    find_pid,
    launch,
    terminate,
)
from vrcpilot.screenshot import take_screenshot
from vrcpilot.steam import SteamNotFoundError
from vrcpilot.window import focus, unfocus


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

    launch_parser = subparsers.add_parser(
        "launch",
        help="Launch VRChat through Steam.",
    )
    launch_parser.add_argument(
        "--app-id",
        type=int,
        default=VRCHAT_STEAM_APP_ID,
        help="Steam app id to launch (default: VRChat's app id).",
    )
    steam_path_action = launch_parser.add_argument(
        "--steam-path",
        type=Path,
        default=None,
        help="Override the auto-detected Steam executable path.",
    )
    _attach_completer(
        steam_path_action, FilesCompleter(allowednames=("exe",), directories=True)
    )
    launch_parser.add_argument(
        "--no-vr",
        action="store_true",
        help="Force desktop mode (passes --no-vr to VRChat).",
    )
    launch_parser.add_argument(
        "--screen-width",
        type=int,
        default=None,
        help="Window width passed to Unity as -screen-width.",
    )
    launch_parser.add_argument(
        "--screen-height",
        type=int,
        default=None,
        help="Window height passed to Unity as -screen-height.",
    )
    launch_parser.add_argument(
        "--osc-in-port",
        type=int,
        default=None,
        help=(
            "OSC inbound port. When set, OSC config (including --osc-out-ip "
            "and --osc-out-port) is forwarded to VRChat. When unset, all "
            "--osc-out-* flags are ignored."
        ),
    )
    launch_parser.add_argument(
        "--osc-out-ip",
        type=str,
        default="127.0.0.1",
        help="OSC outbound IP. Only meaningful with --osc-in-port (default 127.0.0.1).",
    )
    launch_parser.add_argument(
        "--osc-out-port",
        type=int,
        default=9001,
        help="OSC outbound port. Only meaningful with --osc-in-port (default 9001).",
    )

    subparsers.add_parser(
        "status",
        help="Report whether VRChat is currently running.",
    )

    subparsers.add_parser(
        "terminate",
        help="Forcefully terminate any running VRChat process.",
    )

    subparsers.add_parser(
        "focus",
        help="Bring the running VRChat window to the foreground.",
    )

    subparsers.add_parser(
        "unfocus",
        help="Send the running VRChat window to the bottom of the z-order.",
    )

    screenshot_parser = subparsers.add_parser(
        "screenshot",
        help="Capture a screenshot of the running VRChat window.",
    )
    output_action = screenshot_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Path where the PNG screenshot is written. Defaults to "
            "./vrcpilot_screenshot_<YYYYMMDD_HHMMSS>.png in the current "
            "directory."
        ),
    )
    _attach_completer(
        output_action, FilesCompleter(allowednames=("png",), directories=True)
    )

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
    _attach_completer(
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

    return parser


def _attach_completer(action: argparse.Action, completer: object) -> None:
    """Attach an ``argcomplete`` completer to an argparse ``Action``.

    ``argcomplete`` reads ``action.completer`` at completion time but
    argparse itself does not declare the attribute, so a direct
    assignment trips ``reportAttributeAccessIssue`` under pyright
    strict. Routing through ``setattr`` keeps that noise out of
    :func:`_build_parser`.
    """
    setattr(action, "completer", completer)  # noqa: B010 - argcomplete's documented hook


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

    match args.command:
        case "launch":
            return _run_launch(
                app_id=args.app_id,
                steam_path=args.steam_path,
                no_vr=args.no_vr,
                screen_width=args.screen_width,
                screen_height=args.screen_height,
                osc_in_port=args.osc_in_port,
                osc_out_ip=args.osc_out_ip,
                osc_out_port=args.osc_out_port,
            )
        case "status":
            return _run_status()
        case "terminate":
            return _run_terminate()
        case "focus":
            return _run_focus()
        case "unfocus":
            return _run_unfocus()
        case "screenshot":
            return _run_screenshot(output=args.output)
        case "capture":
            return _run_capture(
                output=args.output,
                fps=args.fps,
                duration=args.duration,
            )
        case _:
            parser.error(f"Unknown command: {args.command}")


def _run_launch(
    *,
    app_id: int,
    steam_path: Path | None,
    no_vr: bool,
    screen_width: int | None,
    screen_height: int | None,
    osc_in_port: int | None,
    osc_out_ip: str,
    osc_out_port: int,
) -> int:
    """Execute the ``launch`` subcommand.

    ``osc_in_port`` gates the entire OSC triple: when ``None`` no
    ``--osc`` flag is forwarded and ``osc_out_ip`` / ``osc_out_port``
    are silently ignored. Keeps the CLI ergonomic at the cost of
    accepting unused flags without warning.

    Returns:
        ``0`` on launch, ``2`` if Steam was not found.
    """
    osc = (
        OscConfig(
            in_port=osc_in_port,
            out_ip=osc_out_ip,
            out_port=osc_out_port,
        )
        if osc_in_port is not None
        else None
    )
    try:
        launch(
            app_id=app_id,
            steam_path=steam_path,
            no_vr=no_vr,
            screen_width=screen_width,
            screen_height=screen_height,
            osc=osc,
        )
    except SteamNotFoundError as exc:
        print(f"vrcpilot: {exc}", file=sys.stderr)
        return 2
    print("Launched VRChat.")
    return 0


def _run_status() -> int:
    """Execute the ``status`` subcommand.

    Exit code is state-dependent (unlike :func:`_run_terminate`) so
    shells can branch with ``if vrcpilot status; then ...``.

    Returns:
        ``0`` if running (PID printed), ``1`` otherwise.
    """
    pid = find_pid()
    if pid is None:
        print("VRChat is not running")
        return 1
    print(f"VRChat is running (pid={pid})")
    return 0


def _run_terminate() -> int:
    """Execute the ``terminate`` subcommand.

    Idempotent: exit ``0`` whether VRChat was running or not, so
    callers do not need a preflight ``status`` check.
    """
    if terminate():
        print("Terminated VRChat.")
    else:
        print("VRChat is not running.")
    return 0


def _run_focus() -> int:
    """Execute the ``focus`` subcommand.

    Returns:
        ``0`` on success, ``1`` on any failure (VRChat not running,
        window unavailable, native Wayland).
    """
    if focus():
        print("Focused VRChat.")
        return 0
    print("Could not focus VRChat.")
    return 1


def _run_unfocus() -> int:
    """Execute the ``unfocus`` subcommand.

    Returns:
        ``0`` on success, ``1`` on any failure (VRChat not running,
        window unavailable, native Wayland).
    """
    if unfocus():
        print("Unfocused VRChat.")
        return 0
    print("Could not unfocus VRChat.")
    return 1


def _run_screenshot(*, output: Path | None) -> int:
    """Execute the ``screenshot`` subcommand.

    Args:
        output: Destination path. ``None`` writes
            ``./vrcpilot_screenshot_<YYYYMMDD_HHMMSS>.png``. Extension
            determines the on-disk format via :func:`PIL.Image.save`.

    Returns:
        ``0`` on success, ``1`` if capture failed.
    """
    shot = take_screenshot()
    if shot is None:
        print("Could not capture VRChat screenshot.", file=sys.stderr)
        return 1
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path.cwd() / f"vrcpilot_screenshot_{stamp}.png"
    Image.fromarray(shot.image).save(output)
    print(f"Saved screenshot to {output}.")
    return 0


def _run_capture(
    *,
    output: Path | None,
    fps: float,
    duration: float | None,
) -> int:
    """Execute the ``capture`` subcommand.

    Args:
        output: Destination ``.mp4`` path. ``None`` writes
            ``./vrcpilot_capture_<YYYYMMDD_HHMMSS>.mp4``.
        fps: Target frames per second; passed to both
            :class:`CaptureLoop` and the mp4 container.
        duration: Stop after this many seconds. ``None`` waits for
            ``Ctrl+C`` (KeyboardInterrupt).

    Returns:
        ``0`` on success, ``1`` if recording failed or no frames were
        captured.
    """
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path.cwd() / f"vrcpilot_capture_{stamp}.mp4"

    try:
        with Mp4FrameSink(output, fps) as sink:
            with CaptureLoop(sink.write, fps=fps) as loop:
                loop.start()
                print(f"Recording to {output} (fps={fps}). Press Ctrl+C to stop.")
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
    print(f"Saved capture to {output} (frames={saved_frames}).")
    return 0
