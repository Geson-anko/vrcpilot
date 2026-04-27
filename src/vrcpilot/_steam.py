"""Steam executable discovery utilities.

Internal module. The only symbol intended for external use is
:class:`SteamNotFoundError`, which is re-exported from :mod:`vrcpilot`.
The discovery routines are platform-specific and may change as more
operating systems are supported.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


class SteamNotFoundError(RuntimeError):
    """Raised when the Steam executable cannot be located.

    This signals that auto-detection failed on the current platform,
    that an explicit override path does not exist, or that the platform
    itself is not supported. Catch this at the boundary of any workflow
    that depends on Steam being installed and surface a user-actionable
    message; recovery typically requires the user to install Steam or
    pass an explicit path.
    """


_WINDOWS_STANDARD_PATHS: tuple[Path, ...] = (
    Path("C:/Program Files (x86)/Steam/Steam.exe"),
    Path("C:/Program Files/Steam/Steam.exe"),
)


def _find_steam_on_windows() -> Path:
    """Locate ``Steam.exe`` on Windows via the registry or standard paths."""
    # sys.platform == "win32" narrows so pyright resolves the Windows-only
    # winreg stubs from typeshed; without the guard the imports are unknown
    # on POSIX type-check runs.
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"
            ) as key:
                value, _ = winreg.QueryValueEx(key, "SteamPath")
            if isinstance(value, str):
                steam_path = Path(value) / "Steam.exe"
                if steam_path.is_file():
                    return steam_path
        except OSError:
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
    """Return the path to the Steam executable for the current platform.

    Use this as the single entry point whenever a Steam binary is needed;
    it centralises platform-specific discovery (Windows registry plus
    standard install dirs, Linux ``PATH`` lookup) so callers do not have
    to branch on :data:`sys.platform`. Pass ``override`` to skip detection
    entirely — useful for portable Steam installs and tests.

    Args:
        override: Explicit path to the Steam executable. When provided, the
            path is validated and returned without further auto-detection.

    Returns:
        Path to a verified Steam executable.

    Raises:
        SteamNotFoundError: If ``override`` is provided but does not exist,
            if auto-detection fails on the current platform, or if the
            platform is not supported.
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
