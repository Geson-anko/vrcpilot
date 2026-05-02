"""Tests for :mod:`vrcpilot.cli.terminate`."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from tests.fakes import FakeProcess
from vrcpilot.cli import main
from vrcpilot.process import VRCHAT_PROCESS_NAME


@pytest.fixture
def stub_wait_procs(mocker: MockerFixture) -> None:
    """Short-circuit ``psutil.wait_procs`` for fake-process inputs.

    The real :func:`psutil.wait_procs` type-checks its first arg as a
    list of :class:`psutil.Process`; handing it ``FakeProcess``
    instances raises. The CLI flow does not care about the wait
    result, so a ``([], [])`` return is enough to keep the run
    end-to-end while bypassing the type check.
    """
    mocker.patch("vrcpilot.process.psutil.wait_procs", return_value=([], []))


class TestTerminateCommand:
    def test_prints_killed_pids(
        self,
        mocker: MockerFixture,
        stub_wait_procs: None,
        capsys: pytest.CaptureFixture[str],
    ):
        del stub_wait_procs
        mocker.patch(
            "vrcpilot.process.psutil.process_iter",
            return_value=[FakeProcess(name=VRCHAT_PROCESS_NAME, pid=4242)],
        )

        exit_code = main(["terminate"])

        assert exit_code == 0
        assert capsys.readouterr().out == "4242\n"

    def test_silent_when_nothing_running(self, capsys: pytest.CaptureFixture[str]):
        # Autouse empty default makes this a real, mock-free run of
        # the negative path.
        exit_code = main(["terminate"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    @pytest.mark.parametrize(
        "running_pids",
        [
            [],
            [777],
            [101, 202, 303],
        ],
    )
    def test_exit_code_zero_in_both_cases(
        self,
        running_pids: list[int],
        mocker: MockerFixture,
        stub_wait_procs: None,
    ):
        del stub_wait_procs
        mocker.patch(
            "vrcpilot.process.psutil.process_iter",
            return_value=[
                FakeProcess(name=VRCHAT_PROCESS_NAME, pid=pid) for pid in running_pids
            ],
        )

        exit_code = main(["terminate"])

        assert exit_code == 0

    def test_multiple_killed_pids_each_on_own_line(
        self,
        mocker: MockerFixture,
        stub_wait_procs: None,
        capsys: pytest.CaptureFixture[str],
    ):
        del stub_wait_procs
        mocker.patch(
            "vrcpilot.process.psutil.process_iter",
            return_value=[
                FakeProcess(name=VRCHAT_PROCESS_NAME, pid=111),
                FakeProcess(name=VRCHAT_PROCESS_NAME, pid=222),
                FakeProcess(name=VRCHAT_PROCESS_NAME, pid=333),
            ],
        )

        exit_code = main(["terminate"])

        assert exit_code == 0
        assert capsys.readouterr().out.splitlines() == ["111", "222", "333"]
