"""X11 helpers shared between window control and screen capture.

Both :mod:`vrcpilot.window` (focus / unfocus) and
:mod:`vrcpilot.capture` (take_screenshot) need to open an X11 display,
detect Wayland native sessions, and locate the VRChat top-level window
by PID. Centralising those primitives here keeps the two modules from
duplicating Xlib boilerplate.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING or sys.platform == "linux":
    import Xlib.display
    import Xlib.error
    from Xlib import X
    from Xlib.xobject.drawable import Window as _XWindow


def is_wayland_native() -> bool:
    """Return ``True`` if running under a Wayland compositor without XWayland.

    XWayland exposes a usable ``DISPLAY`` to X11 clients; only when both
    ``XDG_SESSION_TYPE == "wayland"`` AND ``DISPLAY`` is unset do we
    consider the session native Wayland — in that case our X11-based
    operations cannot work.
    """
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" and not os.environ.get(
        "DISPLAY"
    )


def open_x11_display() -> Xlib.display.Display | None:
    """Open an X11 display without wrapping it in a context manager.

    Use this for long-lived connections that span many operations — for
    instance :class:`vrcpilot.capture.Capture` keeps a single connection
    alive for the whole capture session. The caller MUST eventually call
    :meth:`Xlib.display.Display.close` (typically from a ``close()`` /
    ``__exit__`` path).

    For one-shot scripts that only need the connection inside a single
    block, prefer :func:`x11_display` — it handles cleanup automatically.

    Returns ``None`` on connection failure (X server unreachable,
    ``DISPLAY`` unset, missing or stale ``XAUTHORITY``, etc.); see
    :func:`x11_display` for the same failure surface.
    """
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")

    try:
        return Xlib.display.Display()
    except (
        Xlib.error.DisplayError,
        Xlib.error.XauthError,
        Xlib.error.ConnectionClosedError,
        OSError,
    ):
        return None


@contextmanager
def x11_display() -> Iterator[Xlib.display.Display | None]:
    """Open an X11 display for the duration of a ``with`` block.

    Yields ``None`` when the connection fails — typical when the X
    server is unreachable, ``DISPLAY`` is unset, or the X authority
    file (``XAUTHORITY``) is missing or stale (common SSH symptoms
    documented in CLAUDE.md). The display is always closed on exit.
    """
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")

    display = open_x11_display()
    if display is None:
        yield None
        return
    try:
        yield display
    finally:
        display.close()


def find_vrchat_window(display: Xlib.display.Display, pid: int) -> _XWindow | None:
    """Return the X11 window owned by *pid*, or ``None`` if not found.

    Reads ``_NET_CLIENT_LIST`` from the root window (an EWMH property
    listing every managed top-level window) and matches each entry's
    ``_NET_WM_PID`` property against *pid*. The first match wins.
    Windows that disappear mid-iteration (``BadWindow``) are skipped.

    Args:
        display: Open X11 display connection.
        pid: Target process id to match.

    Returns:
        The matching X11 ``Window`` resource, or ``None`` if no managed
        window owned by *pid* is currently mapped.
    """
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")

    root = display.screen().root
    net_client_list = display.intern_atom("_NET_CLIENT_LIST")
    net_wm_pid = display.intern_atom("_NET_WM_PID")

    client_list_prop = root.get_full_property(net_client_list, X.AnyPropertyType)
    if client_list_prop is None:
        return None

    for wid in client_list_prop.value:
        try:
            window = display.create_resource_object("window", int(wid))
            pid_prop = window.get_full_property(net_wm_pid, X.AnyPropertyType)
        except Xlib.error.BadWindow:
            # Window disappeared between _NET_CLIENT_LIST snapshot and the
            # property read — skip and continue scanning.
            continue
        if pid_prop is None:
            continue
        values = pid_prop.value
        if len(values) > 0 and int(values[0]) == pid:
            return window
    return None


def get_window_rect(
    display: Xlib.display.Display, window: _XWindow
) -> tuple[int, int, int, int] | None:
    """Return ``(x, y, width, height)`` of *window* in root screen coords.

    Combines ``window.translate_coords(root, 0, 0)`` for the origin with
    ``window.get_geometry()`` for the size. Empirically the
    ``translate_coords`` reply's ``x`` / ``y`` are the negative of the
    window's screen-space origin under python-xlib, so the sign is
    inverted here — this mirrors the behaviour confirmed in the prior
    mss-based implementation (see commit ``77a6422``).

    Args:
        display: Open X11 display connection.
        window: Target X11 window resource.

    Returns:
        ``(x, y, width, height)`` on success, or ``None`` when the
        window has disappeared (``XError``) or has degenerate geometry
        (non-positive width or height).
    """
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")

    try:
        coords = window.translate_coords(display.screen().root, 0, 0)
        geom = window.get_geometry()
    except Xlib.error.XError:
        return None
    width = int(geom.width)
    height = int(geom.height)
    if width <= 0 or height <= 0:
        return None
    return (-int(coords.x), -int(coords.y), width, height)
