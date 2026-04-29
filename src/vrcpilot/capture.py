"""VRChat window capture API.

Public entry point for grabbing a screenshot of the running VRChat
window as a :class:`PIL.Image.Image`. Capture is **focus-free** on both
platforms: Linux reads the off-screen pixmap via the X11 Composite
extension, and Windows uses the Windows.Graphics.Capture API (the same
backend OBS's "Window Capture (Windows 10 1903+)" mode is built on).
The window is not raised to the foreground, so callers avoid the side
effect (and settle delay) of invoking :func:`focus` before each shot.

Companion to :mod:`vrcpilot.window` (z-order control) and
:mod:`vrcpilot.process` (lifecycle). Native Wayland sessions are not
supported (warns and returns ``None``).
"""

from __future__ import annotations

import sys
import threading
import warnings

from PIL import Image

from vrcpilot._x11 import find_vrchat_window, is_wayland_native, x11_display
from vrcpilot.process import find_pid

if sys.platform == "linux":
    import Xlib.error
    from Xlib import X
    from Xlib.ext import composite

if sys.platform == "win32":
    # ``windows_capture`` ships no type stubs (it's a thin wrapper over a
    # PyO3 native module), so the import trips ``reportMissingTypeStubs``
    # and downstream attribute reads come back as ``Unknown``. We narrow
    # with isinstance / asserts at use sites.
    from windows_capture import (  # pyright: ignore[reportMissingTypeStubs]
        WindowsCapture,
    )

    from vrcpilot._win32 import find_vrchat_hwnd

#: Maximum seconds to wait for the first WGC frame before giving up.
#: WGC normally delivers a frame within ~33 ms; 2 s is a generous
#: watchdog for cases where the HWND vanishes between lookup and
#: capture, or the session never delivers a frame.
_WIN32_FRAME_TIMEOUT_SEC: float = 2.0


def _take_screenshot_win32() -> Image.Image | None:
    """Win32 implementation of :func:`take_screenshot`.

    Captures the VRChat window via the same WGC API that OBS's
    "Window Capture (Windows 10 1903+)" mode uses, so the window
    can be captured without being raised to the foreground and even
    when occluded. Returns ``None`` for any recoverable failure mode.
    """
    if sys.platform != "win32":
        # Defensive narrow for pyright on non-Windows runs.
        raise RuntimeError("unreachable")

    pid = find_pid()
    if pid is None:
        return None

    hwnd = find_vrchat_hwnd(pid)
    if hwnd is None:
        return None

    captured_data: list[bytes] = []
    captured_size: list[tuple[int, int]] = []

    capture = WindowsCapture(  # pyright: ignore[reportUnknownVariableType]
        cursor_capture=False,
        draw_border=False,
        window_hwnd=hwnd,
    )

    @capture.event  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator, reportArgumentType]
    def on_frame_arrived(frame: object, control: object) -> None:  # pyright: ignore[reportUnusedFunction]
        # ``frame.frame_buffer`` is a row-tight ``(H, W, 4)`` BGRA ndarray;
        # the library has already collapsed the GPU stride for us. Copy
        # out as bytes so the buffer is safe to use after capture stops.
        buf = frame.frame_buffer.tobytes()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue, reportUnknownVariableType]
        width = int(frame.width)  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue, reportUnknownMemberType]
        height = int(frame.height)  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue, reportUnknownMemberType]
        assert isinstance(buf, bytes)
        captured_data.append(buf)
        captured_size.append((width, height))
        control.stop()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    @capture.event  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator, reportArgumentType]
    def on_closed() -> None:  # pyright: ignore[reportUnusedFunction]
        pass

    try:
        control = capture.start_free_threaded()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    except OSError:
        return None

    watchdog = threading.Timer(_WIN32_FRAME_TIMEOUT_SEC, control.stop)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    watchdog.start()
    try:
        control.wait()  # pyright: ignore[reportUnknownMemberType]
    finally:
        watchdog.cancel()

    if not captured_data:
        return None

    width, height = captured_size[0]
    if width <= 0 or height <= 0:
        return None
    return Image.frombytes("RGB", (width, height), captured_data[0], "raw", "BGRX")


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

    Use this from automation to read VRChat's pixels without disturbing
    the user. The capture is **focus-free**: the window is not raised
    to the foreground and the call succeeds even when VRChat is fully
    occluded by other windows. On Linux this is done via the X11
    Composite extension; on Windows via the Windows.Graphics.Capture
    API (the same backend OBS's "Window Capture (Windows 10 1903+)"
    mode uses).

    Failure is signalled by returning ``None`` rather than by raising —
    automation callers that poll for VRChat readiness can simply retry.
    ``None`` is returned when VRChat is not running, its top-level
    window cannot be located yet, the window is minimized, the
    underlying capture path fails, or the session is native Wayland (a
    ``RuntimeWarning`` is also emitted in that case).

    Supported on Windows 10 1903+ and Linux (X11 / XWayland). Native
    Wayland sessions are not supported because neither capture path
    can reach the compositor's surface.

    Raises:
        NotImplementedError: When called on a platform other than
            Windows or Linux.

    Returns:
        A ``PIL.Image.Image`` of the VRChat window's contents in RGB
        mode, or ``None`` when the window could not be captured.
    """
    if sys.platform == "win32":
        return _take_screenshot_win32()
    if sys.platform == "linux":
        return _take_screenshot_x11()
    raise NotImplementedError(f"take_screenshot() is not supported on {sys.platform}")
