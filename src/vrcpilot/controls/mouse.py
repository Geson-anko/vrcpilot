"""Synthetic mouse input for VRChat (Linux backend).

The :class:`Mouse` ABC owns a template-method that runs
:func:`vrcpilot.controls.guard.ensure_target` before delegating the
actual side-effects to ``_do_*`` abstract methods. Concrete backends
implement only the side-effect half so the safety check cannot be
forgotten.

This iteration ships :class:`LinuxMouse` (backed by ``inputtino``).
The Win32 backend is not yet implemented; calling :func:`_get` on a
non-Linux platform raises :class:`NotImplementedError`. Backend
instantiation is deferred to the first module-function call so that
``import vrcpilot.controls`` itself stays free of side effects (in
particular, opening ``/dev/uinput`` is delayed until actually needed).

Module functions ``move`` / ``click`` / ``press`` / ``release`` /
``scroll`` are the public surface; tests can also instantiate
:class:`LinuxMouse` directly.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Literal, override

from .guard import ensure_target

ButtonName = Literal["left", "right", "middle"]


class Mouse(ABC):
    """Template-method base: applies the focus guard, then delegates.

    Public methods ``move`` / ``click`` / ``press`` / ``release`` /
    ``scroll`` call :func:`ensure_target` when ``focus=True`` (the
    default) and then forward to the matching ``_do_*`` abstract method.
    Concrete subclasses only implement the ``_do_*`` half so the guard
    is centralised and cannot be skipped accidentally.
    """

    def move(
        self, x: int, y: int, *, relative: bool = False, focus: bool = True
    ) -> None:
        """Move the cursor to ``(x, y)`` (absolute) or by ``(x, y)``
        (relative).

        Args:
            x: Target X (absolute) or delta X (relative), in pixels.
            y: Target Y (absolute) or delta Y (relative), in pixels.
            relative: Treat ``(x, y)`` as a delta from the current
                cursor position.
            focus: Run :func:`ensure_target` first. Set ``False`` in
                hot loops where the caller has already verified focus.
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
        """Click ``button`` ``count`` times, holding ``duration`` seconds each.

        ``duration`` is forwarded to the backend (inputtino implements
        the press/release hold internally), and the loop runs
        ``count`` clicks back-to-back without an inter-click sleep.

        Args:
            button: ``"left"`` / ``"right"`` / ``"middle"``.
            count: Number of clicks to perform; must be ``>= 0``.
            duration: Hold time per click, in seconds.
            focus: Run :func:`ensure_target` first.
        """
        if focus:
            ensure_target()
        self._do_click(button, count=count, duration=duration)

    def press(self, button: ButtonName = "left", *, focus: bool = True) -> None:
        """Press and hold ``button`` until a matching :meth:`release`.

        Args:
            button: ``"left"`` / ``"right"`` / ``"middle"``.
            focus: Run :func:`ensure_target` first.
        """
        if focus:
            ensure_target()
        self._do_press(button)

    def release(self, button: ButtonName = "left", *, focus: bool = True) -> None:
        """Release ``button`` previously pressed with :meth:`press`.

        Args:
            button: ``"left"`` / ``"right"`` / ``"middle"``.
            focus: Run :func:`ensure_target` first.
        """
        if focus:
            ensure_target()
        self._do_release(button)

    def scroll(self, amount: int, *, focus: bool = True) -> None:
        """Scroll vertically by ``amount`` notches.

        Positive values scroll *down*, negative values scroll *up*,
        matching the inputtino convention. The Linux backend converts
        each notch to 120 high-resolution units before forwarding.

        Args:
            amount: Number of notches; sign determines direction.
            focus: Run :func:`ensure_target` first.
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

#: Notch size in inputtino's high-resolution scroll units.
#:
#: ``scroll_vertical`` and ``scroll_horizontal`` accept distance in
#: 120-per-notch units; we expose ``scroll(amount)`` in user-friendly
#: notches and multiply on the way down.
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
        """``inputtino``-backed :class:`Mouse` for Linux.

        The screen size used for absolute moves is read once from
        :func:`mss.mss` at construction time -- mss returns the union
        bounding box of every monitor at index 0, which is what
        inputtino's ``move_abs`` expects when the user passes
        whole-desktop coordinates.

        Construction opens a uinput device via inputtino and will raise
        :class:`RuntimeError` from inputtino if the calling process
        lacks permission on ``/dev/uinput``.
        """

        def __init__(self) -> None:
            self._imp = inputtino.Mouse()
            # mss is untyped; mss.monitors[0] is the union bounding
            # box of all monitors, which is what inputtino's move_abs
            # expects for whole-desktop coordinates.
            sct = mss.mss()
            try:
                bbox: dict[str, int] = sct.monitors[0]  # type: ignore[assignment]
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
    """Return the platform backend, creating it on the first call.

    Deferring construction means ``import vrcpilot.controls.mouse`` has
    no side effects (no uinput device, no X server connection) until
    the user actually sends an input event.

    Raises:
        NotImplementedError: Current platform has no backend.
    """
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
    """Move the cursor; see :meth:`Mouse.move`."""
    _get().move(x, y, relative=relative, focus=focus)


def click(
    button: ButtonName = "left",
    *,
    count: int = 1,
    duration: float = 0.0,
    focus: bool = True,
) -> None:
    """Click ``button``; see :meth:`Mouse.click`."""
    _get().click(button, count=count, duration=duration, focus=focus)


def press(button: ButtonName = "left", *, focus: bool = True) -> None:
    """Press ``button`` and hold; see :meth:`Mouse.press`."""
    _get().press(button, focus=focus)


def release(button: ButtonName = "left", *, focus: bool = True) -> None:
    """Release ``button``; see :meth:`Mouse.release`."""
    _get().release(button, focus=focus)


def scroll(amount: int, *, focus: bool = True) -> None:
    """Scroll vertically by ``amount`` notches; see :meth:`Mouse.scroll`."""
    _get().scroll(amount, focus=focus)
