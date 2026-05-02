"""Automation toolkit for VRChat.

Pixel capture is split between :class:`Capture` (focus-free streaming for
video / ML) and :func:`take_screenshot` (one focused shot with on-screen
geometry, for GUI automation).
"""

from importlib import metadata

from vrcpilot.capture import Capture, CaptureLoop
from vrcpilot.controls import (
    Key,
    VRChatNotFocusedError,
    VRChatNotRunningError,
    ensure_target,
)
from vrcpilot.process import (
    VRCHAT_PROCESS_NAME,
    VRCHAT_STEAM_APP_ID,
    OscConfig,
    build_launch_command,
    build_vrchat_launch_args,
    find_pid,
    launch,
    terminate,
)
from vrcpilot.screenshot import Screenshot, take_screenshot
from vrcpilot.steam import SteamNotFoundError
from vrcpilot.window import focus, is_foreground, unfocus

#: Resolved from distribution metadata so it stays in sync with
#: ``pyproject.toml`` without being hard-coded here.
__version__ = metadata.version(__name__.replace("_", "-"))

__all__ = [
    "__version__",
    "build_launch_command",
    "build_vrchat_launch_args",
    "Capture",
    "CaptureLoop",
    "ensure_target",
    "find_pid",
    "focus",
    "is_foreground",
    "Key",
    "launch",
    "OscConfig",
    "Screenshot",
    "SteamNotFoundError",
    "take_screenshot",
    "terminate",
    "unfocus",
    "VRChatNotFocusedError",
    "VRChatNotRunningError",
    "VRCHAT_PROCESS_NAME",
    "VRCHAT_STEAM_APP_ID",
]
