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

from tests.fakes import FakeInputtinoMouse, FakePyDirectInput
from tests.helpers import ImplMouse, only_linux, only_windows
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
    # production code calls mss.MSS() / .monitors / .close() directly
    # (no context manager), so a plain mock instance is enough.
    fake_sct = mocker.MagicMock()
    fake_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
    mocker.patch("vrcpilot.controls.mouse.mss.MSS", return_value=fake_sct)
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


# --- Win32Mouse tests (Windows-only) --------------------------------------


@pytest.fixture
def fake_pydirectinput(mocker: MockerFixture) -> FakePyDirectInput:
    """Patch the module-level ``pydirectinput`` symbol with a fake.

    Windows-only fixture: substituted via ``mocker.patch.object`` so the
    fake intercepts the same call sites the production code uses (the
    ``import pydirectinput`` is wrapped in ``if sys.platform == 'win32'``,
    so it is only present on Windows runners).
    """
    fake = FakePyDirectInput()
    mocker.patch.object(mouse_mod, "pydirectinput", fake)
    return fake


@only_windows
class TestWin32Mouse:
    """Exercise the pydirectinput backend without touching real ``SendInput``.

    The Windows-only mark prevents collection on Linux; the
    ``fake_pydirectinput`` fixture replaces the module-level
    ``pydirectinput`` symbol so the production code runs end-to-end
    against a fake.
    """

    def test_move_absolute_calls_move_to(self, fake_pydirectinput: FakePyDirectInput):
        from vrcpilot.controls.mouse import Win32Mouse

        m = Win32Mouse()
        m._do_move(100, 200, relative=False)

        assert fake_pydirectinput.move_to_calls == [{"x": 100, "y": 200}]
        assert fake_pydirectinput.move_rel_calls == []

    def test_move_relative_calls_move_rel(self, fake_pydirectinput: FakePyDirectInput):
        from vrcpilot.controls.mouse import Win32Mouse

        m = Win32Mouse()
        m._do_move(15, -7, relative=True)

        assert fake_pydirectinput.move_rel_calls == [{"x": 15, "y": -7}]
        assert fake_pydirectinput.move_to_calls == []

    @pytest.mark.parametrize("button", ["left", "right", "middle"])
    @pytest.mark.parametrize("count", [1, 3])
    def test_click_zero_duration_uses_click_helper(
        self,
        fake_pydirectinput: FakePyDirectInput,
        mocker: MockerFixture,
        button: str,
        count: int,
    ):
        from vrcpilot.controls.mouse import Win32Mouse

        # Spy on time.sleep to confirm the zero-duration path skips it.
        sleep_spy = mocker.patch.object(mouse_mod.time, "sleep")

        m = Win32Mouse()
        m._do_click(button, count=count, duration=0.0)  # type: ignore[arg-type]

        assert fake_pydirectinput.click_calls == [{"button": button}] * count
        assert fake_pydirectinput.mouse_down_calls == []
        assert fake_pydirectinput.mouse_up_calls == []
        sleep_spy.assert_not_called()

    def test_click_with_duration_decomposes_to_down_sleep_up(
        self,
        fake_pydirectinput: FakePyDirectInput,
        mocker: MockerFixture,
    ):
        from vrcpilot.controls.mouse import Win32Mouse

        sleep_spy = mocker.patch.object(mouse_mod.time, "sleep")

        m = Win32Mouse()
        m._do_click("left", count=2, duration=0.05)

        # The click() helper must NOT be used when duration > 0, to
        # avoid pydirectinput's MINIMUM_DURATION sleep injection.
        assert fake_pydirectinput.click_calls == []
        assert fake_pydirectinput.mouse_down_calls == [{"button": "left"}] * 2
        assert fake_pydirectinput.mouse_up_calls == [{"button": "left"}] * 2
        # Interleaved: down -> sleep -> up -> down -> sleep -> up.
        assert [name for name, _ in fake_pydirectinput.calls] == [
            "mouseDown",
            "mouseUp",
            "mouseDown",
            "mouseUp",
        ]
        assert sleep_spy.call_count == 2
        for call in sleep_spy.call_args_list:
            assert call.args == (0.05,)

    def test_click_count_zero_emits_nothing(
        self, fake_pydirectinput: FakePyDirectInput
    ):
        from vrcpilot.controls.mouse import Win32Mouse

        m = Win32Mouse()
        m._do_click("left", count=0, duration=0.0)

        assert fake_pydirectinput.calls == []

    @pytest.mark.parametrize("button", ["left", "right", "middle"])
    def test_press_routes_to_mouse_down(
        self, fake_pydirectinput: FakePyDirectInput, button: str
    ):
        from vrcpilot.controls.mouse import Win32Mouse

        m = Win32Mouse()
        m._do_press(button)  # type: ignore[arg-type]

        assert fake_pydirectinput.mouse_down_calls == [{"button": button}]
        assert fake_pydirectinput.mouse_up_calls == []

    @pytest.mark.parametrize("button", ["left", "right", "middle"])
    def test_release_routes_to_mouse_up(
        self, fake_pydirectinput: FakePyDirectInput, button: str
    ):
        from vrcpilot.controls.mouse import Win32Mouse

        m = Win32Mouse()
        m._do_release(button)  # type: ignore[arg-type]

        assert fake_pydirectinput.mouse_up_calls == [{"button": button}]
        assert fake_pydirectinput.mouse_down_calls == []

    @pytest.mark.parametrize(
        "amount,expected_wheel_arg",
        [(2, -2), (-3, 3), (0, 0)],
    )
    def test_scroll_sign_flips_for_win32_wheel_convention(
        self,
        mocker: MockerFixture,
        amount: int,
        expected_wheel_arg: int,
    ):
        from vrcpilot.controls.mouse import Win32Mouse

        # Patch the helper directly: Win32Mouse._do_scroll's sole
        # responsibility is the sign flip. The helper itself wraps
        # SendInput, which is verified separately by exercising the
        # real Win32 path in the e2e scenario.
        scroll_spy = mocker.patch.object(mouse_mod, "_scroll_wheel")

        m = Win32Mouse()
        m._do_scroll(amount)

        scroll_spy.assert_called_once_with(expected_wheel_arg)


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
