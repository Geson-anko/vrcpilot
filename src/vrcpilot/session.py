"""Cross-platform session-type detection."""

from __future__ import annotations

import os


def is_wayland_native() -> bool:
    """Return ``True`` when the session is Wayland with no XWayland.

    XWayland exposes a usable ``DISPLAY`` to X11 clients, so the
    detection requires both ``XDG_SESSION_TYPE == "wayland"`` AND no
    ``DISPLAY``. Otherwise our X11 operations would still be reachable.
    """
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" and not os.environ.get(
        "DISPLAY"
    )
