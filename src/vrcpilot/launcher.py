"""VRChat launch API.

Public entry points for starting VRChat through Steam. The launcher is the
foundation other automation layers build on: anything that drives the live
client first needs the client to be running. Use :func:`launch_vrchat` for
the end-to-end flow and :func:`build_launch_command` when you need to
inspect or customize the command before spawning.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

from vrcpilot._steam import find_steam_executable

#: Steam application id for VRChat. Hard-coded as a published constant rather
#: than discovered at runtime so callers can reference it without launching.
VRCHAT_STEAM_APP_ID: Final[int] = 438100


def build_launch_command(
    steam_executable: Path,
    app_id: int = VRCHAT_STEAM_APP_ID,
) -> list[str]:
    """Build the argv used to launch a Steam game via Steam's CLI.

    Exposed separately from :func:`launch_vrchat` so callers can inspect,
    log, or wrap the command (for example, to spawn it under a sandbox or
    a different process manager) without paying the cost of an actual
    launch. The function is pure and side-effect free, which also makes
    it easy to unit-test command-shape regressions.

    Args:
        steam_executable: Path to the Steam executable. Not validated
            here; pass a path returned from auto-detection or one you
            have already verified.
        app_id: Steam application id of the game to launch. Defaults to
            :data:`VRCHAT_STEAM_APP_ID`.

    Returns:
        Argument vector suitable for :class:`subprocess.Popen`.
    """
    return [str(steam_executable), "-applaunch", str(app_id)]


def launch_vrchat(
    *,
    app_id: int = VRCHAT_STEAM_APP_ID,
    steam_path: Path | None = None,
) -> subprocess.Popen[bytes]:
    """Launch VRChat through Steam and return the spawned subprocess.

    Use this as the standard way to bring VRChat up before driving any
    higher-level automation. The handed-back :class:`~subprocess.Popen`
    represents the Steam launcher invocation, not VRChat itself: Steam
    keeps its own long-lived client process, so the actual game window
    is owned by Steam and may outlive the returned handle. The launcher
    is also detached from the parent's process group / session so that
    the Python script can exit without taking VRChat down with it.

    Steam must be installed and either auto-detectable or supplied via
    ``steam_path``; the user is not required to be signed in beforehand,
    Steam will surface its own login UI if needed.

    Args:
        app_id: Steam application id to launch. Defaults to
            :data:`VRCHAT_STEAM_APP_ID`. Override only when targeting a
            different title (e.g. a test app id).
        steam_path: Optional explicit path to the Steam executable. When
            omitted, the path is auto-detected per platform.

    Returns:
        The :class:`~subprocess.Popen` handle for the launched Steam
        process. Treat its lifetime as informational; do not rely on
        terminating it to stop VRChat.

    Raises:
        SteamNotFoundError: If the Steam executable cannot be located.
    """
    steam_executable = find_steam_executable(steam_path)
    argv = build_launch_command(steam_executable, app_id)

    if sys.platform == "win32":
        return subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
