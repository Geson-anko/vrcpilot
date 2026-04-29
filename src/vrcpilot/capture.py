"""VRChat window capture API.

Public entry point for grabbing a screenshot of the running VRChat
window as a :class:`PIL.Image.Image`. On Linux the X11 Composite
extension is used to read the window's off-screen pixmap directly, so
the window can be captured **without being raised to the foreground**
and even when it is fully occluded by other windows. This avoids the
side effect (and the settle delay) of having to call :func:`focus`
before each capture.

Companion to :mod:`vrcpilot.window` (z-order control) and
:mod:`vrcpilot.process` (lifecycle). Wayland native sessions are not
supported (warns and returns ``None``); Windows support is not yet
implemented.
"""

from __future__ import annotations

import sys
import warnings

from PIL import Image

from vrcpilot._x11 import find_vrchat_window, is_wayland_native, x11_display
from vrcpilot.process import find_pid

if sys.platform == "linux":
    import Xlib.error
    from Xlib import X
    from Xlib.ext import composite


def _take_screenshot_win32() -> Image.Image | None:
    """Win32 implementation of :func:`take_screenshot` (not yet
    implemented)."""
    # TODO: Win32 サポートを実装する。`PrintWindow(hwnd, hdc,
    # PW_RENDERFULLCONTENT)` で hidden / occluded window でも撮れる
    # ため、Linux Composite 同様 focus 不要で実装可能。
    raise NotImplementedError("take_screenshot() on Windows is not implemented yet")


def _take_screenshot_x11() -> Image.Image | None:
    """X11/XWayland implementation of :func:`take_screenshot`.

    Uses the Composite extension to read the VRChat window's off-screen
    pixmap, so the window need not be visible or focused. Returns
    ``None`` for any failure mode the caller can recover from by
    retrying (VRChat not running, window not yet mapped, server lacks
    Composite, etc.).
    """
    if sys.platform != "linux":
        # Defensive narrow for pyright on non-Linux runs.
        raise RuntimeError("unreachable")

    if is_wayland_native():
        warnings.warn(
            "Wayland native session detected; "
            "take_screenshot() requires X11 or XWayland.",
            RuntimeWarning,
            stacklevel=2,
        )
        return None

    pid = find_pid()
    if pid is None:
        return None

    with x11_display() as display:
        if display is None:
            return None
        window = find_vrchat_window(display, pid)
        if window is None:
            return None
        try:
            # Verify the server speaks Composite — raises XError when
            # the extension isn't loaded so we can degrade to None.
            composite.query_version(display)
            # Redirect the window to off-screen storage so we can read
            # its pixels regardless of stacking order. Idempotent when
            # a compositor (picom, mutter, kwin…) already redirects.
            # python-xlib stubs declare ``update`` as a callable but
            # the protocol value is the int constant ``RedirectAutomatic``.
            composite.redirect_window(window, composite.RedirectAutomatic)  # pyright: ignore[reportArgumentType]
            pixmap = composite.name_window_pixmap(window)
            geom = window.get_geometry()
            width, height = int(geom.width), int(geom.height)
            if width <= 0 or height <= 0:
                pixmap.free()
                return None
            reply = pixmap.get_image(0, 0, width, height, X.ZPixmap, 0xFFFFFFFF)
            pixmap.free()
        except Xlib.error.XError:
            return None
    return Image.frombytes("RGB", (width, height), reply.data, "raw", "BGRX")


def take_screenshot() -> Image.Image | None:
    """Capture the running VRChat window and return it as a PIL image.

    On Linux the X11 Composite extension is used to read the window's
    off-screen pixmap, so the capture works even when the VRChat window
    is occluded or running in VR exclusive mode. The window is **not**
    raised to the foreground, so calling this from automation does not
    disturb the user's z-order.

    Failure is signalled by returning ``None`` rather than by raising —
    automation callers that poll for VRChat readiness can simply retry.
    Conditions that yield ``None`` include: VRChat is not running, its
    top-level window cannot be located yet, the window is minimized
    (zero-size geometry), the X11 display cannot be opened, the server
    does not speak the Composite extension, an X11 request fails, or
    the session is native Wayland (a ``RuntimeWarning`` is also
    emitted in that case).

    Currently implemented for Linux (X11 / XWayland). Calling on
    Windows raises ``NotImplementedError`` until the Win32 backend is
    written.

    Raises:
        NotImplementedError: When called on Windows (not yet
            implemented) or any platform other than Windows or Linux.

    Returns:
        A ``PIL.Image.Image`` of the VRChat window's contents in RGB
        mode, or ``None`` when the window could not be captured.
    """
    if sys.platform == "win32":
        return _take_screenshot_win32()
    if sys.platform == "linux":
        return _take_screenshot_x11()
    raise NotImplementedError(f"take_screenshot() is not supported on {sys.platform}")
