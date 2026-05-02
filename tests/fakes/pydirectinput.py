"""Test double for the ``pydirectinput`` Win32 input backend.

:class:`FakePyDirectInput` records every call the production code makes
against the ``pydirectinput`` module, so tests can assert on the
synthesized event sequence without touching real ``SendInput``. The
fake mirrors the function names actually invoked by
:mod:`vrcpilot.controls.mouse` (and, in a later step,
``...controls.keyboard``), so swapping the module-level symbol via
``mocker.patch.object`` is sufficient.

The :attr:`FAILSAFE` and :attr:`MINIMUM_DURATION` attributes exist so
production code that assigns to them at import time does not fail when
the real module has been substituted with a fake instance.
"""

from __future__ import annotations


class FakePyDirectInput:
    """Stand-in for the ``pydirectinput`` module, recording every call.

    Each call is appended to :attr:`calls` as a ``(name, args)`` tuple
    where ``args`` is a dict of the keyword names used at the call
    site. Tests can inspect the list directly, or use the
    ``move_to_calls`` / ``click_calls`` / etc. convenience properties
    when only one method's history matters.
    """

    # Module-level attribute parity. Production assigns
    # ``pydirectinput.FAILSAFE = False`` at import; the fake just needs
    # the slot to exist.
    FAILSAFE: bool = False
    MINIMUM_DURATION: float = 0.0

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    # --- pydirectinput surface (mouse subset) ---------------------------

    def moveTo(self, x: int, y: int) -> None:
        self.calls.append(("moveTo", {"x": x, "y": y}))

    def moveRel(self, x: int, y: int) -> None:
        self.calls.append(("moveRel", {"x": x, "y": y}))

    def click(self, *, button: str) -> None:
        self.calls.append(("click", {"button": button}))

    def mouseDown(self, *, button: str) -> None:
        self.calls.append(("mouseDown", {"button": button}))

    def mouseUp(self, *, button: str) -> None:
        self.calls.append(("mouseUp", {"button": button}))

    # --- convenience views ---------------------------------------------

    @property
    def move_to_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "moveTo"]

    @property
    def move_rel_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "moveRel"]

    @property
    def click_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "click"]

    @property
    def mouse_down_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "mouseDown"]

    @property
    def mouse_up_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "mouseUp"]
