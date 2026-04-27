"""VRChat launch API."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

from vrcpilot._steam import find_steam_executable

VRCHAT_STEAM_APP_ID: Final[int] = 438100


def build_launch_command(
    steam_executable: Path,
    app_id: int = VRCHAT_STEAM_APP_ID,
) -> list[str]:
    """Build the argv used to launch a Steam game via Steam's CLI.

    Args:
        steam_executable: Path to the Steam executable.
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

    The returned :class:`~subprocess.Popen` represents the Steam launcher
    invocation. Steam keeps its own client process; whether VRChat survives
    the Python process exit depends on Steam's own lifecycle, not this
    ``Popen``.

    Args:
        app_id: Steam application id to launch. Defaults to
            :data:`VRCHAT_STEAM_APP_ID`.
        steam_path: Optional explicit path to the Steam executable. When
            omitted, the path is auto-detected via
            :func:`vrcpilot._steam.find_steam_executable`.

    Returns:
        The :class:`~subprocess.Popen` handle for the launched Steam process.

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
