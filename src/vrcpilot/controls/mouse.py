"""Synthetic mouse input for VRChat."""

from __future__ import annotations

import ctypes
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Literal, override

from .guard import ensure_target

ButtonName = Literal["left", "right", "middle"]


class Mouse(ABC):
    """Mouse ABC: runs :func:`ensure_target`, then delegates to ``_do_*``."""

    def move(
        self, x: int, y: int, *, relative: bool = False, focus: bool = True
    ) -> None:
        """Move the cursor.

        With ``relative=False`` (default), ``(x, y)`` are pixels in the
        union bounding box of all monitors (``mss.monitors[0]``);
        ``(0, 0)`` is the top-left of the leftmost / topmost monitor.
        """
        if focus:
            ensure_target()
        self._do_move(x, y, relative=relative)

    def click(
        self,
        button: ButtonName = "left",
        *,
        count: int = 1,
        duration: float = 0.0,
        focus: bool = True,
    ) -> None:
        """Click ``button`` ``count`` times.

        ``duration`` is the down-to-up hold per click, in seconds;
        use ``0.02``-``0.05`` when VRChat / Unity drops zero-length
        presses. Clicks run back-to-back with no inter-click delay.
        """
        if focus:
            ensure_target()
        self._do_click(button, count=count, duration=duration)

    def press(self, button: ButtonName = "left", *, focus: bool = True) -> None:
        """Press and hold ``button`` until a matching :meth:`release`."""
        if focus:
            ensure_target()
        self._do_press(button)

    def release(self, button: ButtonName = "left", *, focus: bool = True) -> None:
        """Release ``button`` previously pressed with :meth:`press`."""
        if focus:
            ensure_target()
        self._do_release(button)

    def scroll(self, amount: int, *, focus: bool = True) -> None:
        """Scroll vertically by ``amount`` notches (positive = down)."""
        if focus:
            ensure_target()
        self._do_scroll(amount)

    @abstractmethod
    def _do_move(self, x: int, y: int, *, relative: bool) -> None: ...

    @abstractmethod
    def _do_click(self, button: ButtonName, *, count: int, duration: float) -> None: ...

    @abstractmethod
    def _do_press(self, button: ButtonName) -> None: ...

    @abstractmethod
    def _do_release(self, button: ButtonName) -> None: ...

    @abstractmethod
    def _do_scroll(self, amount: int) -> None: ...


# Linux backend ------------------------------------------------------------

# inputtino's scroll API takes distance in 120-per-notch high-resolution
# units; we expose plain notches and multiply on the way down.
_SCROLL_NOTCH = 120

if sys.platform == "linux":
    import inputtino
    import mss

    _BUTTON_MAP: dict[ButtonName, inputtino.MouseButton] = {
        "left": inputtino.MouseButton.LEFT,
        "middle": inputtino.MouseButton.MIDDLE,
        "right": inputtino.MouseButton.RIGHT,
    }

    class LinuxMouse(Mouse):
        """``inputtino``-backed :class:`Mouse`.

        Opens ``/dev/uinput`` at construction; inputtino raises
        :class:`RuntimeError` if the caller lacks permission. Screen
        size for absolute moves is captured once from ``mss.monitors[0]``
        (whole-desktop bounding box).
        """

        def __init__(self) -> None:
            self._imp = inputtino.Mouse()
            # Match screenshot.py: explicit instantiate / close (not
            # the context manager) so test fakes can be plain mocks
            # without implementing __enter__ / __exit__.
            sct = mss.MSS()
            try:
                bbox = sct.monitors[0]
                self._screen_w = int(bbox["width"])
                self._screen_h = int(bbox["height"])
            finally:
                sct.close()

        @override
        def _do_move(self, x: int, y: int, *, relative: bool) -> None:
            if relative:
                self._imp.move(x, y)
            else:
                self._imp.move_abs(x, y, self._screen_w, self._screen_h)

        @override
        def _do_click(self, button: ButtonName, *, count: int, duration: float) -> None:
            btn = _BUTTON_MAP[button]
            for _ in range(count):
                self._imp.click(btn, duration=duration)

        @override
        def _do_press(self, button: ButtonName) -> None:
            self._imp.press(_BUTTON_MAP[button])

        @override
        def _do_release(self, button: ButtonName) -> None:
            self._imp.release(_BUTTON_MAP[button])

        @override
        def _do_scroll(self, amount: int) -> None:
            self._imp.scroll_vertical(amount * _SCROLL_NOTCH)


# Win32 backend ------------------------------------------------------------

if sys.platform == "win32":
    # pydirectinput ships no stubs; alias to Any once so call sites stay
    # clean instead of needing reportUnknownMemberType ignores per call.
    import pydirectinput as _pydirectinput_module  # pyright: ignore[reportMissingTypeStubs]

    pydirectinput: Any = _pydirectinput_module

    # Disable pydirectinput's "cursor at (0, 0) panic" — VRChat workflows
    # legitimately move the cursor to corners and we do not want a hard
    # exit from a synthetic input call.
    pydirectinput.FAILSAFE = False

    # MOUSEEVENTF_WHEEL is the SendInput flag for vertical wheel events.
    # pydirectinput 1.0.4 does not ship a scroll() helper, so we
    # synthesize the event using its already-imported ctypes structures.
    _MOUSEEVENTF_WHEEL = 0x0800
    _WHEEL_DELTA = 120

    def _scroll_wheel(amount: int) -> None:
        """Synthesize a vertical wheel event via ``SendInput``.

        Win32 wheel sign convention: positive = up. Caller is expected
        to have already sign-flipped to match the public API
        (positive = down).
        """
        extra = ctypes.c_ulong(0)
        ii = pydirectinput.Input_I()
        ii.mi = pydirectinput.MouseInput(
            0,
            0,
            ctypes.c_ulong(amount * _WHEEL_DELTA).value,
            _MOUSEEVENTF_WHEEL,
            0,
            ctypes.pointer(extra),
        )
        inp = pydirectinput.Input(ctypes.c_ulong(0), ii)
        pydirectinput.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))

    class Win32Mouse(Mouse):
        """``pydirectinput``-backed :class:`Mouse`.

        Uses Windows screen coordinates directly (no mss capture).
        """

        @override
        def _do_move(self, x: int, y: int, *, relative: bool) -> None:
            if relative:
                pydirectinput.moveRel(x, y)
            else:
                pydirectinput.moveTo(x, y)

        @override
        def _do_click(self, button: ButtonName, *, count: int, duration: float) -> None:
            for _ in range(count):
                if duration > 0:
                    # Older pydirectinput versions inject MINIMUM_DURATION
                    # sleeps when click() is called with duration=0, so
                    # split the down/up path manually instead of passing
                    # duration through.
                    pydirectinput.mouseDown(button=button)
                    time.sleep(duration)
                    pydirectinput.mouseUp(button=button)
                else:
                    pydirectinput.click(button=button)

        @override
        def _do_press(self, button: ButtonName) -> None:
            pydirectinput.mouseDown(button=button)

        @override
        def _do_release(self, button: ButtonName) -> None:
            pydirectinput.mouseUp(button=button)

        @override
        def _do_scroll(self, amount: int) -> None:
            # Public API: positive = down. Win32: positive = up. Flip.
            _scroll_wheel(-amount)


# Lazy singleton -----------------------------------------------------------

_instance: Mouse | None = None


def _get() -> Mouse:
    """Return the platform backend, constructing it on first call.

    Deferred so import does not eagerly open ``/dev/uinput`` (Linux).
    """
    global _instance
    if _instance is None:
        if sys.platform == "win32":
            _instance = Win32Mouse()
        elif sys.platform == "linux":
            _instance = LinuxMouse()
        else:
            raise NotImplementedError(
                f"controls.mouse is not supported on {sys.platform}"
            )
    return _instance


# Module functions ---------------------------------------------------------


def move(x: int, y: int, *, relative: bool = False, focus: bool = True) -> None:
    """See :meth:`Mouse.move`."""
    _get().move(x, y, relative=relative, focus=focus)


def click(
    button: ButtonName = "left",
    *,
    count: int = 1,
    duration: float = 0.0,
    focus: bool = True,
) -> None:
    """See :meth:`Mouse.click`."""
    _get().click(button, count=count, duration=duration, focus=focus)


def press(button: ButtonName = "left", *, focus: bool = True) -> None:
    """See :meth:`Mouse.press`."""
    _get().press(button, focus=focus)


def release(button: ButtonName = "left", *, focus: bool = True) -> None:
    """See :meth:`Mouse.release`."""
    _get().release(button, focus=focus)


def scroll(amount: int, *, focus: bool = True) -> None:
    """See :meth:`Mouse.scroll`."""
    _get().scroll(amount, focus=focus)
