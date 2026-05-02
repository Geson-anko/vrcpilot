"""Synthetic mouse input for VRChat (Linux backend, inputtino)."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Literal, override

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
        """Scroll vertically by ``amount`` notches (positive = down).

        Each notch is multiplied by 120 inside the Linux backend before
        being forwarded to inputtino's high-resolution scroll API.
        """
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


# Lazy singleton -----------------------------------------------------------

_instance: Mouse | None = None


def _get() -> Mouse:
    """Return the lazily-built platform backend (deferred uinput open)."""
    global _instance
    if _instance is None:
        if sys.platform == "linux":
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
