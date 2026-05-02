"""Tests for :mod:`vrcpilot.controls.guard`.

``ensure_target`` is the only safety check between user code and the
synthetic-input backends, so every branch is exercised. The autouse
``_no_real_vrchat`` fixture pins ``find_pid()`` to ``None`` by default;
each test that needs the "VRChat is running" branch overrides the
``vrcpilot.controls.guard.find_pid`` symbol the module imported.

``vrcpilot.window`` functions are patched via attribute access on the
guard module (the implementation does ``from vrcpilot import window``)
rather than at their canonical paths -- patching via the bound name is
the only way to intercept calls the module already resolved at import
time.
"""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from vrcpilot.controls.errors import VRChatNotFocusedError, VRChatNotRunningError
from vrcpilot.controls.guard import ensure_target


class TestEnsureTarget:
    def test_raises_not_implemented_on_wayland_native(self, mocker: MockerFixture):
        # Wayland native sessions cannot satisfy is_foreground(), so
        # the focus loop would never converge. Surface a clear
        # NotImplementedError before any side effect.
        mocker.patch("vrcpilot.controls.guard.is_wayland_native", return_value=True)
        with pytest.raises(NotImplementedError, match="X11 or XWayland"):
            ensure_target()

    def test_raises_when_vrchat_not_running(self, mocker: MockerFixture):
        # Autouse _no_real_vrchat fixture already pins find_pid to
        # None, but patching the local import is explicit and lets the
        # other branch tests override it without ambiguity.
        mocker.patch("vrcpilot.controls.guard.is_wayland_native", return_value=False)
        mocker.patch("vrcpilot.controls.guard.find_pid", return_value=None)
        with pytest.raises(VRChatNotRunningError, match="not running"):
            ensure_target()

    def test_no_op_when_already_foreground(self, mocker: MockerFixture):
        # Happy path: VRChat is running and is_foreground() is True
        # on the first probe -- focus() must not be called at all.
        mocker.patch("vrcpilot.controls.guard.is_wayland_native", return_value=False)
        mocker.patch("vrcpilot.controls.guard.find_pid", return_value=4242)
        is_fg = mocker.patch(
            "vrcpilot.controls.guard.window.is_foreground", return_value=True
        )
        focus = mocker.patch("vrcpilot.controls.guard.window.focus")

        ensure_target()  # no exception expected

        is_fg.assert_called_once()
        focus.assert_not_called()

    def test_focuses_then_returns_when_focus_succeeds(self, mocker: MockerFixture):
        # First is_foreground() call drives the focus path; the second
        # confirms VRChat surfaced on the first poll iteration.
        mocker.patch("vrcpilot.controls.guard.is_wayland_native", return_value=False)
        mocker.patch("vrcpilot.controls.guard.find_pid", return_value=4242)
        is_fg = mocker.patch(
            "vrcpilot.controls.guard.window.is_foreground",
            side_effect=[False, True],
        )
        focus = mocker.patch("vrcpilot.controls.guard.window.focus", return_value=True)

        ensure_target()  # no exception expected

        assert is_fg.call_count == 2
        focus.assert_called_once()

    def test_polls_until_foreground_after_focus(self, mocker: MockerFixture):
        # The WM applies _NET_ACTIVE_WINDOW asynchronously, so the
        # first probe after focus() can still see the old foreground.
        # Guard must keep polling until the window catches up rather
        # than failing on the first stale reading.
        mocker.patch("vrcpilot.controls.guard.is_wayland_native", return_value=False)
        mocker.patch("vrcpilot.controls.guard.find_pid", return_value=4242)
        is_fg = mocker.patch(
            "vrcpilot.controls.guard.window.is_foreground",
            side_effect=[False, False, False, True],
        )
        mocker.patch("vrcpilot.controls.guard.window.focus", return_value=True)
        sleep = mocker.patch("vrcpilot.controls.guard.time.sleep")

        ensure_target()  # no exception expected

        assert is_fg.call_count == 4
        # 2 sleeps between the 2nd, 3rd, 4th is_foreground probes
        # (the first probe runs before the loop, the success exits it).
        assert sleep.call_count == 2

    def test_raises_when_focus_returns_false(self, mocker: MockerFixture):
        # Native call to bring the window forward failed (e.g. another
        # app stole foreground or X11 returned an XError) -- the guard
        # must propagate as VRChatNotFocusedError.
        mocker.patch("vrcpilot.controls.guard.is_wayland_native", return_value=False)
        mocker.patch("vrcpilot.controls.guard.find_pid", return_value=4242)
        mocker.patch("vrcpilot.controls.guard.window.is_foreground", return_value=False)
        mocker.patch("vrcpilot.controls.guard.window.focus", return_value=False)
        with pytest.raises(VRChatNotFocusedError, match=r"focus\(\) failed"):
            ensure_target()

    def test_raises_when_still_not_foreground_after_focus(self, mocker: MockerFixture):
        # focus() reported success but the window never surfaced even
        # after the polling window expired (e.g. WM ignored
        # _NET_ACTIVE_WINDOW). Guard must not silently continue. The
        # time monotonic patch makes the polling loop give up
        # immediately so the test stays fast.
        mocker.patch("vrcpilot.controls.guard.is_wayland_native", return_value=False)
        mocker.patch("vrcpilot.controls.guard.find_pid", return_value=4242)
        mocker.patch("vrcpilot.controls.guard.window.is_foreground", return_value=False)
        mocker.patch("vrcpilot.controls.guard.window.focus", return_value=True)
        # Force the deadline to be already past on the first check.
        mocker.patch("vrcpilot.controls.guard.time.monotonic", side_effect=[0.0, 999.0])
        mocker.patch("vrcpilot.controls.guard.time.sleep")
        with pytest.raises(VRChatNotFocusedError, match="after focus"):
            ensure_target()
