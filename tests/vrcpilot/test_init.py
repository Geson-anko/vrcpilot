"""Tests for :mod:`vrcpilot` package top-level."""

import tomllib
from pathlib import Path

import vrcpilot

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestPackage:
    def test_version(self):
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)

        assert vrcpilot.__version__ == pyproject["project"]["version"]
