"""Tests for :mod:`vrcpilot.steam`."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import only_linux
from vrcpilot.steam import SteamNotFoundError, find_steam_executable


class TestFindSteamExecutableOverride:
    """``override`` is platform-agnostic — verify on the current host."""

    def test_override_returns_existing_path(self, tmp_path: Path):
        fake_steam = tmp_path / "Steam.exe"
        fake_steam.write_bytes(b"")

        result = find_steam_executable(override=fake_steam)

        assert result == fake_steam

    def test_override_missing_path_raises(self, tmp_path: Path):
        missing = tmp_path / "nope" / "Steam.exe"

        with pytest.raises(SteamNotFoundError, match="does not exist"):
            find_steam_executable(override=missing)

    def test_override_directory_raises(self, tmp_path: Path):
        # ``is_file()`` is the gate, so a directory should be rejected even
        # though the path exists.
        with pytest.raises(SteamNotFoundError, match="does not exist"):
            find_steam_executable(override=tmp_path)


class TestFindSteamExecutableLinux:
    """Linux auto-detect path delegates to ``shutil.which``."""

    @only_linux
    def test_returns_path_when_steam_on_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        steam = tmp_path / "steam"
        steam.write_bytes(b"")
        monkeypatch.setattr("vrcpilot.steam.shutil.which", lambda _name: str(steam))

        assert find_steam_executable() == steam

    @only_linux
    def test_raises_when_not_on_path(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("vrcpilot.steam.shutil.which", lambda _name: None)

        with pytest.raises(SteamNotFoundError, match="'steam' command not found"):
            find_steam_executable()
