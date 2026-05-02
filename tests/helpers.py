"""Shared test helpers.

Skip markers, environment probes, and lightweight polling utilities
shared between the automated test suite and the e2e scenarios under
``tests/e2e/``. Anything platform- or display-specific lives here so
that individual test modules can decide at file scope whether to run.
"""

from __future__ import annotations

import functools
import sys
import time
from typing import override

import pytest

import vrcpilot
from vrcpilot.controls.keyboard import Key, Keyboard
from vrcpilot.controls.mouse import ButtonName, Mouse

#: Skip a test on non-Windows platforms.
#:
#: Use for tests whose body touches Windows-only APIs (e.g.
#: ``subprocess.CREATE_NEW_PROCESS_GROUP``) that are absent on POSIX runners,
#: even when ``sys.platform`` itself is monkey-patched.
only_windows = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows-only behaviour"
)

#: Skip a test on non-Linux platforms.
#:
#: Use for tests that exercise Linux-specific behaviour and would fail on
#: Windows runners regardless of ``sys.platform`` patching.
only_linux = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="Linux-only behaviour"
)


@functools.lru_cache(maxsize=1)
def has_x11_display() -> bool:
    """Return ``True`` when an X11 display is reachable on this host.

    Probes by opening and immediately closing a connection via
    ``Xlib.display.Display()``. Cached because the underlying state
    cannot change during a pytest run, and probing repeatedly would
    leak X server file descriptors on Linux CI.

    Returns ``False`` on non-Linux platforms unconditionally; ``Xlib``
    is a Linux-only dependency in this project.
    """
    if not sys.platform.startswith("linux"):
        return False
    try:
        import Xlib.display

        display = Xlib.display.Display()
    except Exception:
        return False
    try:
        display.close()
    except Exception:
        pass
    return True


#: Skip a test when the Linux X11 display is unavailable.
#:
#: Use this on tests that exercise the real ``Xlib`` paths (window
#: lookup, focus, capture). Tests that purely simulate X11 with the
#: ``tests.fakes.x11`` doubles do not need this marker.
requires_x11_display = pytest.mark.skipif(
    not has_x11_display(), reason="X11 display unavailable"
)

_PID_WAIT_TIMEOUT: float = 30.0
_PID_WAIT_INTERVAL: float = 1.0


def wait_for_pid(
    timeout: float = _PID_WAIT_TIMEOUT,
    interval: float = _PID_WAIT_INTERVAL,
) -> int | None:
    """Poll for a VRChat PID until one appears or ``timeout`` elapses.

    Returns the observed PID, or ``None`` if the deadline expires
    first. Suitable for both e2e scenarios (waiting for VRChat to
    finish launching) and automated tests that drive a real launcher.
    """
    deadline = time.monotonic() + timeout
    while True:
        pid = vrcpilot.find_pid()
        if pid is not None:
            return pid
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)


def wait_for_no_pid(
    timeout: float = _PID_WAIT_TIMEOUT,
    interval: float = _PID_WAIT_INTERVAL,
) -> bool:
    """Poll until VRChat is no longer running, or ``timeout`` elapses.

    Returns ``True`` once the process is gone; ``False`` if the
    deadline expired with the process still present.
    """
    deadline = time.monotonic() + timeout
    while True:
        if vrcpilot.find_pid() is None:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


class ImplMouse(Mouse):
    """Concrete :class:`Mouse` for ABC template-method tests.

    Records every ``_do_*`` invocation in :attr:`calls` as
    ``(method_name, kwargs_dict)`` tuples. Tests use this in place of
    a mock so the real ABC plumbing (focus guard, kwarg forwarding) is
    exercised end-to-end -- per the project rule that ABC wiring tests
    use a real impl rather than ``mocker.Mock``.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    @override
    def _do_move(self, x: int, y: int, *, relative: bool) -> None:
        self.calls.append(("_do_move", {"x": x, "y": y, "relative": relative}))

    @override
    def _do_click(self, button: ButtonName, *, count: int, duration: float) -> None:
        self.calls.append(
            (
                "_do_click",
                {"button": button, "count": count, "duration": duration},
            )
        )

    @override
    def _do_press(self, button: ButtonName) -> None:
        self.calls.append(("_do_press", {"button": button}))

    @override
    def _do_release(self, button: ButtonName) -> None:
        self.calls.append(("_do_release", {"button": button}))

    @override
    def _do_scroll(self, amount: int) -> None:
        self.calls.append(("_do_scroll", {"amount": amount}))


class ImplKeyboard(Keyboard):
    """Concrete :class:`Keyboard` for ABC template-method tests.

    Records every ``_do_*`` invocation in :attr:`calls` as
    ``(method_name, kwargs_dict)`` tuples. Mirrors :class:`ImplMouse`
    so the keyboard ABC plumbing (focus guard, kwarg forwarding) can
    be exercised end-to-end without the inputtino backend.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    @override
    def _do_press(self, key: Key, *, duration: float) -> None:
        self.calls.append(("_do_press", {"key": key, "duration": duration}))

    @override
    def _do_down(self, key: Key) -> None:
        self.calls.append(("_do_down", {"key": key}))

    @override
    def _do_up(self, key: Key) -> None:
        self.calls.append(("_do_up", {"key": key}))
