"""Tests for :mod:`vrcpilot.controls.mouse`.

The test file is organised around the three layers the module exposes:

* :class:`Mouse` ABC template-method wiring -- runs on every platform
  via :class:`tests.helpers.ImplMouse` so the guard plumbing is
  verified independently of any backend.
* :class:`vrcpilot.controls.mouse.LinuxMouse` -- the inputtino-backed
  concrete class. Linux-only, with the real ``inputtino.Mouse`` and
  ``mss.mss`` swapped out via ``mocker.patch`` so no uinput device is
  ever opened during testing.
* The lazy-singleton ``_get`` and the ``move`` / ``click`` / ``press``
  / ``release`` / ``scroll`` module functions, which simply forward to
  the backend.

The autouse ``_reset_mouse_singleton`` fixture clears
``vrcpilot.controls.mouse._instance`` between tests so backend
construction order does not leak between cases.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import override

import pytest
from pytest_mock import MockerFixture

from tests.fakes import FakeInputtinoMouse
from tests.helpers import ImplMouse, only_linux
from vrcpilot.controls import mouse as mouse_mod
from vrcpilot.controls.mouse import Mouse


@pytest.fixture(autouse=True)
def _reset_mouse_singleton() -> Iterator[None]:
    """Clear the module-level lazy backend before and after each test."""
    mouse_mod._instance = None
    yield
    mouse_mod._instance = None


# --- ABC template-method tests (cross-platform) ---------------------------


class TestMouseGuardWiring:
    """Verify the ABC runs ``ensure_target`` exactly when ``focus`` allows.

    Uses the real :class:`ImplMouse` (not a mock) so the abstract
    method dispatch and kwarg forwarding are exercised; only
    ``ensure_target`` is patched.
    """

    def test_focus_true_calls_ensure_target_for_every_method(
        self, mocker: MockerFixture
    ):
        guard = mocker.patch("vrcpilot.controls.mouse.ensure_target")
        impl = ImplMouse()

        impl.move(1, 2)
        impl.click()
        impl.press()
        impl.release()
        impl.scroll(1)

        assert guard.call_count == 5

    def test_focus_false_skips_ensure_target(self, mocker: MockerFixture):
        guard = mocker.patch("vrcpilot.controls.mouse.ensure_target")
        impl = ImplMouse()

        impl.move(1, 2, focus=False)
        impl.click(focus=False)
        impl.press(focus=False)
        impl.release(focus=False)
        impl.scroll(1, focus=False)

        guard.assert_not_called()

    def test_move_forwards_arguments(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.controls.mouse.ensure_target")
        impl = ImplMouse()

        impl.move(10, 20, relative=True)
        impl.move(30, 40)  # default relative=False

        assert impl.calls == [
            ("_do_move", {"x": 10, "y": 20, "relative": True}),
            ("_do_move", {"x": 30, "y": 40, "relative": False}),
        ]

    def test_click_forwards_arguments(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.controls.mouse.ensure_target")
        impl = ImplMouse()

        impl.click("right", count=2, duration=0.05)

        assert impl.calls == [
            (
                "_do_click",
                {"button": "right", "count": 2, "duration": 0.05},
            )
        ]

    def test_press_release_forward_button(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.controls.mouse.ensure_target")
        impl = ImplMouse()

        impl.press("middle")
        impl.release("middle")

        assert impl.calls == [
            ("_do_press", {"button": "middle"}),
            ("_do_release", {"button": "middle"}),
        ]

    def test_scroll_forwards_amount(self, mocker: MockerFixture):
        mocker.patch("vrcpilot.controls.mouse.ensure_target")
        impl = ImplMouse()

        impl.scroll(-3)

        assert impl.calls == [("_do_scroll", {"amount": -3})]


# --- LinuxMouse tests (Linux-only) ----------------------------------------


@pytest.fixture
def fake_inputtino_mouse(mocker: MockerFixture) -> FakeInputtinoMouse:
    """Patch ``inputtino.Mouse`` with a recording fake.

    Linux-only fixture: imports ``inputtino`` to satisfy pyright at
    test discovery time but is gated by the ``only_linux`` mark on
    test classes that use it. The fake instance is also returned so
    tests can read ``.calls`` directly.
    """
    fake = FakeInputtinoMouse()
    mocker.patch("vrcpilot.controls.mouse.inputtino.Mouse", return_value=fake)
    # Pin screen size so move_abs assertions are deterministic. The
    # production code calls mss.mss() / .monitors / .close() directly
    # (no context manager), so a plain mock instance is enough.
    fake_sct = mocker.MagicMock()
    fake_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
    mocker.patch("vrcpilot.controls.mouse.mss.mss", return_value=fake_sct)
    return fake


@only_linux
class TestLinuxMouse:
    """Exercise the inputtino backend without touching ``/dev/uinput``.

    The Linux-only mark prevents collection on Windows; the
    ``fake_inputtino_mouse`` fixture replaces ``inputtino.Mouse`` and
    ``mss.mss`` so the production code runs end-to-end against a
    fake.
    """

    def test_move_relative_calls_move(self, fake_inputtino_mouse: FakeInputtinoMouse):
        from vrcpilot.controls.mouse import LinuxMouse

        m = LinuxMouse()
        m._do_move(15, -7, relative=True)

        assert fake_inputtino_mouse.move_calls == [{"delta_x": 15, "delta_y": -7}]
        assert fake_inputtino_mouse.move_abs_calls == []

    def test_move_absolute_uses_screen_size_from_mss(
        self, fake_inputtino_mouse: FakeInputtinoMouse
    ):
        from vrcpilot.controls.mouse import LinuxMouse

        m = LinuxMouse()
        m._do_move(960, 540, relative=False)

        assert fake_inputtino_mouse.move_abs_calls == [
            {
                "x": 960,
                "y": 540,
                "screen_width": 1920,
                "screen_height": 1080,
            }
        ]
        assert fake_inputtino_mouse.move_calls == []

    @pytest.mark.parametrize(
        "name,expected_value",
        [("left", 0), ("middle", 1), ("right", 2)],
    )
    def test_click_maps_button_and_repeats_count(
        self,
        fake_inputtino_mouse: FakeInputtinoMouse,
        name: str,
        expected_value: int,
    ):
        from vrcpilot.controls.mouse import LinuxMouse

        m = LinuxMouse()
        m._do_click(name, count=3, duration=0.05)  # type: ignore[arg-type]

        assert len(fake_inputtino_mouse.click_calls) == 3
        for call in fake_inputtino_mouse.click_calls:
            # button is the real inputtino.MouseButton enum -- compare
            # by the IntEnum value to stay decoupled from the binding.
            assert int(call["button"]) == expected_value  # type: ignore[arg-type]
            assert call["duration"] == 0.05

    def test_click_count_zero_emits_nothing(
        self, fake_inputtino_mouse: FakeInputtinoMouse
    ):
        from vrcpilot.controls.mouse import LinuxMouse

        m = LinuxMouse()
        m._do_click("left", count=0, duration=0.0)

        assert fake_inputtino_mouse.click_calls == []

    def test_press_maps_right_button(self, fake_inputtino_mouse: FakeInputtinoMouse):
        from vrcpilot.controls.mouse import LinuxMouse

        m = LinuxMouse()
        m._do_press("right")

        assert len(fake_inputtino_mouse.press_calls) == 1
        assert int(fake_inputtino_mouse.press_calls[0]["button"]) == 2  # type: ignore[arg-type]

    def test_release_maps_middle_button(self, fake_inputtino_mouse: FakeInputtinoMouse):
        from vrcpilot.controls.mouse import LinuxMouse

        m = LinuxMouse()
        m._do_release("middle")

        assert len(fake_inputtino_mouse.release_calls) == 1
        assert int(fake_inputtino_mouse.release_calls[0]["button"]) == 1  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "amount,expected_distance",
        [(2, 240), (-1, -120), (0, 0)],
    )
    def test_scroll_converts_notches_to_high_resolution_units(
        self,
        fake_inputtino_mouse: FakeInputtinoMouse,
        amount: int,
        expected_distance: int,
    ):
        from vrcpilot.controls.mouse import LinuxMouse

        m = LinuxMouse()
        m._do_scroll(amount)

        assert fake_inputtino_mouse.scroll_vertical_calls == [
            {"distance": expected_distance}
        ]


# --- _get() lazy-init tests ----------------------------------------------


class TestGetLazyInit:
    """The backend should be created on first access and reused after."""

    def test_returns_same_instance_on_repeated_calls(self, mocker: MockerFixture):
        # Replace the backend with a recording impl so the test runs
        # on every platform without needing inputtino or pydirectinput.
        mocker.patch("vrcpilot.controls.mouse.ensure_target")
        instance = ImplMouse()
        mouse_mod._instance = instance

        assert mouse_mod._get() is instance
        assert mouse_mod._get() is instance

    def test_unsupported_platform_raises_not_implemented(self, mocker: MockerFixture):
        # Force the "neither linux nor win32" branch by patching the
        # module-level sys.platform reference. Singleton has been
        # cleared by the autouse fixture, so the branch is reached.
        mocker.patch.object(sys, "platform", "darwin")

        with pytest.raises(NotImplementedError, match="darwin"):
            mouse_mod._get()


# --- Module function delegation tests -------------------------------------


class _SpyMouse(Mouse):
    """Backend that records the public-API call it received.

    Distinct from :class:`ImplMouse` because we want to assert which
    *public* method on the backend was called -- the module functions
    forward through the public method (which then runs the guard and
    delegates to ``_do_*``), not directly to ``_do_*``.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    @override
    def move(
        self, x: int, y: int, *, relative: bool = False, focus: bool = True
    ) -> None:
        self.calls.append(
            (
                "move",
                {"x": x, "y": y, "relative": relative, "focus": focus},
            )
        )

    @override
    def click(
        self,
        button: str = "left",  # type: ignore[override]
        *,
        count: int = 1,
        duration: float = 0.0,
        focus: bool = True,
    ) -> None:
        self.calls.append(
            (
                "click",
                {
                    "button": button,
                    "count": count,
                    "duration": duration,
                    "focus": focus,
                },
            )
        )

    @override
    def press(
        self,
        button: str = "left",  # type: ignore[override]
        *,
        focus: bool = True,
    ) -> None:
        self.calls.append(("press", {"button": button, "focus": focus}))

    @override
    def release(
        self,
        button: str = "left",  # type: ignore[override]
        *,
        focus: bool = True,
    ) -> None:
        self.calls.append(("release", {"button": button, "focus": focus}))

    @override
    def scroll(self, amount: int, *, focus: bool = True) -> None:
        self.calls.append(("scroll", {"amount": amount, "focus": focus}))

    @override
    def _do_move(self, x: int, y: int, *, relative: bool) -> None:
        # Not exercised; the spy overrides the public methods directly.
        ...

    @override
    def _do_click(self, button: str, *, count: int, duration: float) -> None: ...

    @override
    def _do_press(self, button: str) -> None: ...

    @override
    def _do_release(self, button: str) -> None: ...

    @override
    def _do_scroll(self, amount: int) -> None: ...


class TestModuleFunctions:
    """``move`` / ``click`` / ...

    must forward through ``_get()``.
    """

    def test_move_forwards(self):
        spy = _SpyMouse()
        mouse_mod._instance = spy

        mouse_mod.move(100, 200, relative=True, focus=False)

        assert spy.calls == [
            (
                "move",
                {"x": 100, "y": 200, "relative": True, "focus": False},
            )
        ]

    def test_click_forwards(self):
        spy = _SpyMouse()
        mouse_mod._instance = spy

        mouse_mod.click("right", count=2, duration=0.1, focus=False)

        assert spy.calls == [
            (
                "click",
                {
                    "button": "right",
                    "count": 2,
                    "duration": 0.1,
                    "focus": False,
                },
            )
        ]

    def test_press_release_forward(self):
        spy = _SpyMouse()
        mouse_mod._instance = spy

        mouse_mod.press("middle")
        mouse_mod.release("middle", focus=False)

        assert spy.calls == [
            ("press", {"button": "middle", "focus": True}),
            ("release", {"button": "middle", "focus": False}),
        ]

    def test_scroll_forwards(self):
        spy = _SpyMouse()
        mouse_mod._instance = spy

        mouse_mod.scroll(-2, focus=False)

        assert spy.calls == [("scroll", {"amount": -2, "focus": False})]
