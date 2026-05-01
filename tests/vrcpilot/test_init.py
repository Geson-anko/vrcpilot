"""Tests for :mod:`vrcpilot` package top-level."""

import tomllib
from pathlib import Path

import vrcpilot


def _find_pyproject(start: Path) -> Path:
    for parent in [start, *start.parents]:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"pyproject.toml not found upward from {start}")


class TestPackage:
    def test_version(self):
        with open(_find_pyproject(Path(__file__).resolve()), "rb") as f:
            pyproject = tomllib.load(f)

        assert vrcpilot.__version__ == pyproject["project"]["version"]
