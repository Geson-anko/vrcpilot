"""Test doubles for the ``inputtino`` Linux input backend.

:class:`FakeInputtinoMouse` and :class:`FakeInputtinoKeyboard` record
every call the production code makes against
``inputtino.Mouse`` / ``inputtino.Keyboard``, so tests can assert on
the synthesized event sequence without ever opening ``/dev/uinput``.
The fakes mirror the real method signatures (verified against the
installed inputtino binding) so swapping the class via
``mocker.patch`` is sufficient.

:class:`FakeMouseButton` is intentionally separate even though
production code can use the real ``inputtino.MouseButton`` enum -- the
fake exists for tests that want to drive the backend without importing
inputtino at all (i.e. on a non-Linux runner). Tests that *do* run on
Linux can simply use the real enum.
"""

from __future__ import annotations

from enum import IntEnum


class FakeMouseButton(IntEnum):
    """Standalone stand-in for :class:`inputtino.MouseButton`.

    Values match the real binding (verified via ``dir(inputtino)``).
    """

    LEFT = 0
    MIDDLE = 1
    RIGHT = 2
    SIDE = 3
    EXTRA = 4


class FakeInputtinoMouse:
    """Stand-in for ``inputtino.Mouse`` that records every call.

    Each call is appended to :attr:`calls` as a ``(method, args)``
    tuple where ``args`` is a dict of the keyword names used in the
    real binding. Tests can inspect the list directly, or use the
    ``move_calls`` / ``click_calls`` / etc. convenience properties
    when only one method's history matters.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    # --- inputtino.Mouse surface (mirrored exactly) ---------------------

    def move(self, delta_x: int, delta_y: int) -> None:
        self.calls.append(("move", {"delta_x": delta_x, "delta_y": delta_y}))

    def move_abs(self, x: int, y: int, screen_width: int, screen_height: int) -> None:
        self.calls.append(
            (
                "move_abs",
                {
                    "x": x,
                    "y": y,
                    "screen_width": screen_width,
                    "screen_height": screen_height,
                },
            )
        )

    def click(self, button: object, duration: float = 0.0) -> None:
        self.calls.append(("click", {"button": button, "duration": duration}))

    def press(self, button: object) -> None:
        self.calls.append(("press", {"button": button}))

    def release(self, button: object) -> None:
        self.calls.append(("release", {"button": button}))

    def scroll_vertical(self, distance: int) -> None:
        self.calls.append(("scroll_vertical", {"distance": distance}))

    def scroll_horizontal(self, distance: int) -> None:
        self.calls.append(("scroll_horizontal", {"distance": distance}))

    # --- convenience views ---------------------------------------------

    @property
    def move_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "move"]

    @property
    def move_abs_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "move_abs"]

    @property
    def click_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "click"]

    @property
    def press_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "press"]

    @property
    def release_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "release"]

    @property
    def scroll_vertical_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "scroll_vertical"]


class FakeInputtinoKeyboard:
    """Stand-in for ``inputtino.Keyboard`` that records every call.

    Each call is appended to :attr:`calls` as a ``(method, args)``
    tuple where ``args`` is a dict of the keyword names used in the
    real binding. Tests can inspect the list directly, or use the
    ``press_calls`` / ``release_calls`` / ``type_calls`` convenience
    properties when only one method's history matters.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    # --- inputtino.Keyboard surface (mirrored exactly) ------------------

    def press(self, key_code: object) -> None:
        self.calls.append(("press", {"key_code": key_code}))

    def release(self, key_code: object) -> None:
        self.calls.append(("release", {"key_code": key_code}))

    def type(self, key_code: object, duration: float = 0.1) -> None:
        self.calls.append(("type", {"key_code": key_code, "duration": duration}))

    # --- convenience views ---------------------------------------------

    @property
    def press_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "press"]

    @property
    def release_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "release"]

    @property
    def type_calls(self) -> list[dict[str, object]]:
        return [args for name, args in self.calls if name == "type"]
