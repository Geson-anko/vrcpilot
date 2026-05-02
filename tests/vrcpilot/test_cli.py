"""Tests for :mod:`vrcpilot.cli`.

Tests favour real integration over mock surfaces:

* ``launch`` flows go through :func:`vrcpilot.cli.main` ->
  :func:`vrcpilot.process.launch` -> :class:`subprocess.Popen`, with
  ``Popen`` swapped for :class:`tests.fakes.FakePopen` so the actual
  argv is recorded and asserted on. ``find_steam_executable`` is the
  only stub — it would otherwise hit the real registry / ``$PATH``.
* ``screenshot`` flows construct a real :class:`PIL.Image.Image` from
  a real numpy array and write a real PNG to ``tmp_path``. Only the
  capture boundary (:func:`vrcpilot.cli.take_screenshot`) is mocked.
* ``capture`` flows use the canonical :class:`tests.fakes.FakeCaptureLoop`
  / :class:`tests.fakes.FakeMp4Sink` so the CLI is wired through the
  real :func:`vrcpilot.cli._run_capture` orchestration.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from argcomplete.completers import FilesCompleter
from PIL import Image
from pytest_mock import MockerFixture, MockType

from tests.fakes import FakeCaptureLoop, FakeMp4Sink, FakePopen, FakeProcess
from vrcpilot.cli import _build_parser, main
from vrcpilot.process import VRCHAT_PROCESS_NAME, VRCHAT_STEAM_APP_ID


@pytest.fixture
def fake_popen(mocker: MockerFixture, tmp_path: Path) -> type[FakePopen]:
    """Patch ``subprocess.Popen`` so launch tests can record argv.

    Also stubs :func:`vrcpilot.process.find_steam_executable` to
    honour any ``--steam-path`` override, falling back to a real
    file under ``tmp_path``. That single mock is unavoidable — the
    real lookup would touch the Windows registry or ``$PATH`` — but
    every other byte of the launch chain runs unmodified, including
    the dispatch on ``override is not None``.

    Class-level state is reset every test so ``last_argv`` reflects
    only this test's invocation.
    """
    FakePopen.reset()
    mocker.patch("vrcpilot.process.subprocess.Popen", FakePopen)
    steam_stub = tmp_path / "Steam.exe"
    steam_stub.write_bytes(b"")

    def _find(override: Path | None = None) -> Path:
        return override if override is not None else steam_stub

    mocker.patch("vrcpilot.process.find_steam_executable", side_effect=_find)
    return FakePopen


class TestMain:
    def test_missing_subcommand_exits(self):
        with pytest.raises(SystemExit):
            main([])


class TestArgcompleteIntegration:
    def test_autocomplete_invoked_with_parser(self, mocker: MockerFixture):
        # Use the ``pid`` subcommand since the autouse conftest empties
        # ``process_iter``, making it an honest, mock-free run all the
        # way through.
        autocomplete_mock = mocker.patch("vrcpilot.cli.argcomplete.autocomplete")

        exit_code = main(["pid"])

        assert exit_code == 1
        autocomplete_mock.assert_called_once()
        call_args = autocomplete_mock.call_args
        assert isinstance(call_args.args[0], argparse.ArgumentParser)

    def test_steam_path_has_files_completer(self):
        parser = _build_parser()

        subparsers_action = parser._subparsers._group_actions[0]  # type: ignore[union-attr]
        launch_parser = subparsers_action.choices["launch"]
        steam_path_action = next(
            action
            for action in launch_parser._actions
            if "--steam-path" in action.option_strings
        )

        completer = steam_path_action.completer  # type: ignore[attr-defined]
        assert isinstance(completer, FilesCompleter)
        # argcomplete normalizes allowednames; "exe" should appear in some form.
        allowednames = completer.allowednames
        assert any("exe" in name for name in allowednames)

    def test_autocomplete_does_not_block_normal_run(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # ``pid`` against the autouse empty ``process_iter`` is the
        # cheapest fully-real path through ``main`` - it confirms the
        # ``argcomplete`` hook does not abort regular (non-completion)
        # invocations without needing a Steam launch fake.
        monkeypatch.delenv("_ARGCOMPLETE", raising=False)

        exit_code = main(["pid"])

        assert exit_code == 1

    def test_capture_output_has_files_completer(self):
        parser = _build_parser()

        subparsers_action = parser._subparsers._group_actions[0]  # type: ignore[union-attr]
        capture_parser = subparsers_action.choices["capture"]
        output_action = next(
            action
            for action in capture_parser._actions
            if "--output" in action.option_strings
        )

        completer = output_action.completer  # type: ignore[attr-defined]
        assert isinstance(completer, FilesCompleter)
        allowednames = completer.allowednames
        assert any("mp4" in name for name in allowednames)
