"""Tests for :mod:`vrcpilot` package top-level."""

import tomllib
from pathlib import Path

import pytest

import vrcpilot

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestPackage:
    def test_version(self):
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)

        assert vrcpilot.__version__ == pyproject["project"]["version"]

    @pytest.mark.parametrize(
        "name",
        [
            "VRCHAT_PROCESS_NAME",
            "VRCHAT_STEAM_APP_ID",
            "build_launch_command",
            "build_vrchat_launch_args",
        ],
    )
    def test_internal_symbols_not_exposed_at_top_level(self, name: str):
        """Internal process helpers must stay under ``vrcpilot.process``.

        These names are intentionally excluded from the top-level public
        surface so that ``vrcpilot.<name>`` does not advertise internal
        plumbing. They remain importable via ``vrcpilot.process.<name>``.
        """
        assert not hasattr(vrcpilot, name)
        assert name not in vrcpilot.__all__
