"""Steam executable discovery utilities."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import cast


class SteamNotFoundError(RuntimeError):
    """Raised when the Steam executable cannot be located."""


_WINDOWS_STANDARD_PATHS: tuple[Path, ...] = (
    Path("C:/Program Files (x86)/Steam/Steam.exe"),
    Path("C:/Program Files/Steam/Steam.exe"),
)


def _find_steam_on_windows() -> Path:
    """Locate ``Steam.exe`` on Windows via the registry or standard paths."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
        steam_path = Path(cast(str, value)) / "Steam.exe"
        if steam_path.is_file():
            return steam_path
    except (OSError, FileNotFoundError):
        pass

    for candidate in _WINDOWS_STANDARD_PATHS:
        if candidate.is_file():
            return candidate

    raise SteamNotFoundError(
        "Steam.exe was not found in registry or standard install paths"
    )


def _find_steam_on_linux() -> Path:
    """Locate the ``steam`` command on Linux via ``PATH`` lookup."""
    located = shutil.which("steam")
    if located is None:
        raise SteamNotFoundError("'steam' command not found in PATH")
    return Path(located)


def find_steam_executable(override: Path | None = None) -> Path:
    """Return the path to the Steam executable.

    Args:
        override: Explicit path to the Steam executable. When provided, the
            path is validated and returned without further auto-detection.

    Returns:
        Path to a verified Steam executable.

    Raises:
        SteamNotFoundError: If ``override`` is provided but does not exist, or
            if auto-detection fails on the current platform, or the platform
            is not supported.
    """
    if override is not None:
        if override.is_file():
            return override
        raise SteamNotFoundError(
            f"Specified Steam executable does not exist: {override}"
        )

    if sys.platform == "win32":
        return _find_steam_on_windows()
    if sys.platform.startswith("linux"):
        return _find_steam_on_linux()

    raise SteamNotFoundError(f"Unsupported platform: {sys.platform}")
