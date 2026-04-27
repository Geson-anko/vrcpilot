"""Tests for :mod:`vrcpilot._steam`."""

from __future__ import annotations

from pathlib import Path

import pytest

from vrcpilot._steam import SteamNotFoundError, find_steam_executable


def test_override_returns_existing_path(tmp_path: Path):
    fake_steam = tmp_path / "Steam.exe"
    fake_steam.write_bytes(b"")

    result = find_steam_executable(override=fake_steam)

    assert result == fake_steam


def test_override_missing_path_raises(tmp_path: Path):
    missing = tmp_path / "nope" / "Steam.exe"

    with pytest.raises(SteamNotFoundError, match="does not exist"):
        find_steam_executable(override=missing)


def test_linux_auto_detect(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("vrcpilot._steam.shutil.which", lambda _name: "/usr/bin/steam")

    assert find_steam_executable() == Path("/usr/bin/steam")


def test_linux_auto_detect_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("vrcpilot._steam.shutil.which", lambda _name: None)

    with pytest.raises(SteamNotFoundError, match="'steam' command not found"):
        find_steam_executable()


def test_unsupported_platform(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sys.platform", "darwin")

    with pytest.raises(SteamNotFoundError, match="Unsupported platform"):
        find_steam_executable()
