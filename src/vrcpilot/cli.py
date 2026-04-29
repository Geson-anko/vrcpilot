# PYTHON_ARGCOMPLETE_OK
"""Command line interface for vrcpilot.

Thin wrapper around the public Python API so the same workflows are
reachable from a shell. The CLI is intentionally minimal: it shells out
to the library functions and translates exceptions into exit codes,
keeping behavioral logic in the library itself.

Invocation::

    python -m vrcpilot launch [--app-id ID] [--steam-path PATH] [--no-vr]
        [--screen-width N] [--screen-height N]
        [--osc-in-port N [--osc-out-ip IP] [--osc-out-port N]]
    python -m vrcpilot status
    python -m vrcpilot terminate
    python -m vrcpilot focus
    python -m vrcpilot unfocus
    python -m vrcpilot screenshot [-o PATH | --output PATH]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import argcomplete
from argcomplete.completers import FilesCompleter
from PIL import Image

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.process import (
    VRCHAT_STEAM_APP_ID,
    OscConfig,
    find_pid,
    launch,
    terminate,
)
from vrcpilot.screenshot import take_screenshot
from vrcpilot.window import focus, unfocus


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands.

    Extracted from :func:`main` so tests (and the ``argcomplete`` shell
    hook) can obtain a fully-configured parser without running the
    command. Each call returns a fresh parser; callers that mutate it
    should not share the instance.
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
    steam_path_action.completer = FilesCompleter(  # type: ignore[attr-defined]
        allowednames=("exe",), directories=True
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
    output_action.completer = FilesCompleter(  # type: ignore[attr-defined]
        allowednames=("png",), directories=True
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ``vrcpilot`` command line interface.

    Entry point used both by the console script and by ``python -m
    vrcpilot``. Returns an exit code instead of calling :func:`sys.exit`
    so it stays trivially testable: pass ``argv`` explicitly from a test
    and assert on the return value.

    Args:
        argv: Optional argument list passed to :mod:`argparse`. When
            ``None`` (the default), arguments are read from
            :data:`sys.argv`.

    Returns:
        Process exit code. ``0`` on success, ``2`` on a recoverable error
        such as Steam not being found (mirrors common CLI conventions for
        usage / environment errors).
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

    Bridges the flat CLI argument shape onto :func:`launch`. The
    inbound OSC port acts as the gate: when it is ``None`` the entire OSC
    triple is suppressed (no ``--osc`` flag is forwarded, and
    ``osc_out_ip`` / ``osc_out_port`` are silently ignored). This keeps
    the CLI ergonomic — users who do not care about OSC do not have to
    blank the outbound defaults — at the cost of letting unused flags
    pass without a warning.

    Args:
        app_id: Steam app id to launch.
        steam_path: Optional explicit path to the Steam executable.
        no_vr: When ``True``, force desktop mode via ``--no-vr``.
        screen_width: Optional Unity ``-screen-width`` value.
        screen_height: Optional Unity ``-screen-height`` value.
        osc_in_port: When provided, an :class:`OscConfig` is built using this
            inbound port together with ``osc_out_ip`` and ``osc_out_port``
            and forwarded to VRChat. When ``None``, no OSC flag is sent and
            the outbound options are ignored.
        osc_out_ip: OSC outbound IP. Only meaningful when ``osc_in_port`` is
            set.
        osc_out_port: OSC outbound port. Only meaningful when ``osc_in_port``
            is set.

    Returns:
        ``0`` if VRChat was launched successfully, ``2`` if Steam was not found.
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

    Reports whether VRChat is currently running by delegating to
    :func:`find_pid`. The exit code is intentionally
    state-dependent — unlike :func:`_run_terminate`, which is idempotent —
    so shell users can branch on it (``if vrcpilot status; then ...``).

    Returns:
        ``0`` if a VRChat process was found (PID is printed to stdout),
        ``1`` if no VRChat process is running.
    """
    pid = find_pid()
    if pid is None:
        print("VRChat is not running")
        return 1
    print(f"VRChat is running (pid={pid})")
    return 0


def _run_terminate() -> int:
    """Execute the ``terminate`` subcommand.

    Termination is treated as idempotent: callers can invoke it without
    knowing whether VRChat is currently running, and either outcome is
    reported on stdout with a successful exit code.

    Returns:
        ``0`` whether VRChat was running or not.
    """
    if terminate():
        print("Terminated VRChat.")
    else:
        print("VRChat is not running.")
    return 0


def _run_focus() -> int:
    """Execute the ``focus`` subcommand.

    Thin wrapper around :func:`focus`. The boolean return value is
    translated into an exit code so shell callers can branch on it; the
    CLI does not try to attribute *why* a failure occurred (the
    underlying API does not surface that), so a single generic message
    is emitted on failure.

    Returns:
        ``0`` if VRChat was brought to the foreground, ``1`` if the
        operation failed (VRChat not running, window not yet available,
        or unsupported session such as native Wayland).
    """
    if focus():
        print("Focused VRChat.")
        return 0
    print("Could not focus VRChat.")
    return 1


def _run_unfocus() -> int:
    """Execute the ``unfocus`` subcommand.

    Counterpart of :func:`_run_focus` for sending VRChat to the bottom
    of the z-order. Same exit-code contract: ``0`` on success, ``1`` on
    any failure mode reported by :func:`unfocus`.

    Returns:
        ``0`` if VRChat was sent to the bottom of the z-order, ``1`` if
        the operation failed (VRChat not running, window not yet
        available, or unsupported session such as native Wayland).
    """
    if unfocus():
        print("Unfocused VRChat.")
        return 0
    print("Could not unfocus VRChat.")
    return 1


def _run_screenshot(*, output: Path | None) -> int:
    """Execute the ``screenshot`` subcommand.

    Bridges :func:`take_screenshot` to the file system: when capture
    succeeds the returned :class:`vrcpilot.Screenshot`'s ``image``
    ndarray is converted to a :class:`PIL.Image.Image` via
    :func:`PIL.Image.fromarray` and written with ``Image.save`` (the
    format is inferred from the path's extension). When the underlying
    API returns ``None`` — VRChat not running, window not yet
    available, native Wayland session, screen grabber failure — a
    generic message is emitted on stderr and the CLI exits non-zero so
    shell callers can branch on it.

    Args:
        output: Destination path for the captured image. When ``None``
            the file is written to the current working directory as
            ``vrcpilot_screenshot_<YYYYMMDD_HHMMSS>.png``. The extension
            determines the on-disk format (use ``.png`` for the
            documented PNG behaviour).

    Returns:
        ``0`` if the screenshot was captured and saved, ``1`` if the
        capture failed.
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
