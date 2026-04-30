"""X11 / Composite backend for :class:`vrcpilot.Capture`.

Wraps the python-xlib Composite extension behind a
:class:`~vrcpilot._backends.capture_base.CaptureBackend` so the public
:class:`vrcpilot.Capture` wrapper does not have to know anything about
X11. The session keeps a single display connection alive across calls
to :meth:`read` and re-grabs the off-screen pixmap on demand: callers
get the live state of the window without forcing it to the foreground.
"""

from __future__ import annotations

import sys
import warnings
from typing import TYPE_CHECKING, override

import numpy as np

from vrcpilot._backends.capture_base import CaptureBackend
from vrcpilot._x11 import (
    find_vrchat_window,
    is_wayland_native,
    open_x11_display,
)
from vrcpilot.process import find_pid

if TYPE_CHECKING or sys.platform == "linux":
    import Xlib.display
    import Xlib.error
    from Xlib import X
    from Xlib.ext import composite
    from Xlib.xobject.drawable import Window as _XWindow


class X11CaptureBackend(CaptureBackend):
    """X11 Composite-backed capture session for the VRChat window.

    Holds the display connection and the redirected window; each
    :meth:`read` re-fetches the off-screen pixmap so the returned frame
    reflects the window's current state even when occluded.
    """

    _display: Xlib.display.Display
    _window: _XWindow

    def __init__(self) -> None:
        if sys.platform != "linux":
            # Defensive narrow for pyright on non-Linux runs.
            raise RuntimeError("unreachable")

        if is_wayland_native():
            raise RuntimeError(
                "Capture requires X11 or XWayland; native Wayland is not supported",
            )

        pid = find_pid()
        if pid is None:
            raise RuntimeError("VRChat is not running")

        display = open_x11_display()
        if display is None:
            raise RuntimeError("X11 display unavailable")

        try:
            window = find_vrchat_window(display, pid)
            if window is None:
                raise RuntimeError("VRChat top-level window is not yet mapped")

            # Verify the server speaks Composite -- raises XError when
            # the extension isn't loaded so we can fail fast.
            try:
                composite.query_version(display)
            except Xlib.error.XError as exc:
                raise RuntimeError(
                    f"X11 Composite extension not available: {exc}",
                ) from exc

            try:
                # Redirect the window to off-screen storage so we can read
                # its pixels regardless of stacking order. Idempotent when
                # a compositor (picom, mutter, kwin...) already redirects.
                # python-xlib stubs declare ``update`` as a callable but
                # the protocol value is the int constant
                # ``RedirectAutomatic``.
                composite.redirect_window(window, composite.RedirectAutomatic)  # pyright: ignore[reportArgumentType]
            except Xlib.error.XError as exc:
                raise RuntimeError(f"Failed to redirect window: {exc}") from exc
        except BaseException:
            # Any failure between display open and successful redirect must
            # release the connection; otherwise an exception during init
            # leaks the X server socket.
            try:
                display.close()
            except Exception:  # noqa: BLE001 - cleanup must not mask the cause
                pass
            raise

        self._display = display
        self._window = window

    @override
    def read(self) -> np.ndarray:
        """Re-grab the window pixmap through Composite and return RGB
        ndarray."""
        if sys.platform != "linux":
            # Defensive narrow for pyright on non-Linux runs.
            raise RuntimeError("unreachable")

        try:
            geom = self._window.get_geometry()
            width = int(geom.width)
            height = int(geom.height)
            if width <= 0 or height <= 0:
                raise RuntimeError("Window has invalid geometry")
            pixmap = composite.name_window_pixmap(self._window)
            try:
                reply = pixmap.get_image(0, 0, width, height, X.ZPixmap, 0xFFFFFFFF)
            finally:
                pixmap.free()
        except Xlib.error.XError as exc:
            raise RuntimeError(f"X11 capture failed: {exc}") from exc

        bgra = np.frombuffer(reply.data, dtype=np.uint8).reshape(height, width, 4)
        return np.ascontiguousarray(bgra[..., 2::-1])

    @override
    def close(self) -> None:
        """Close the held X display connection (no unredirect, no pixmap)."""
        try:
            self._display.close()
        except Exception as exc:  # noqa: BLE001 - close() must not raise
            warnings.warn(
                f"X11 display close failed: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
