"""Automation toolkit for VRChat.

``vrcpilot`` exposes building blocks for driving VRChat from Python: from
launching the client through Steam to higher-level UI / in-game automation
layered on top. The top-level namespace re-exports the stable entry points;
lower-level helpers live under private submodules and are not part of the
public API.

The pixel-capture surface is split into two complementary entry points; pick
based on workload:

- :class:`Capture` — long-lived session that yields successive frames as
  RGB ``ndarray`` instances. Focus-free (the window is not raised) and
  designed for video-rate streaming where the latest frame matters more
  than every frame. Use this for recording, ML inference loops, or any
  consumer that calls into the capture in a tight loop.
- :func:`take_screenshot` — single-shot grab that focuses the window
  first and returns a :class:`Screenshot` carrying both the pixels and
  the on-screen geometry. Use this for GUI automation steps that need
  to compute click coordinates, drive OCR over a region, or diff a
  static UI state.

Typical use::

    import vrcpilot

    vrcpilot.launch()
    shot = vrcpilot.take_screenshot()  # one-shot + metadata
    with vrcpilot.Capture() as cap:    # streaming frames
        frame = cap.read()
"""

from importlib import metadata

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.capture import Capture
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
from vrcpilot.window import focus, unfocus

#: Installed package version, resolved from distribution metadata so it stays
#: in sync with ``pyproject.toml`` without being hard-coded here.
__version__ = metadata.version(__name__.replace("_", "-"))

__all__ = [
    "__version__",
    "build_launch_command",
    "build_vrchat_launch_args",
    "Capture",
    "find_pid",
    "focus",
    "launch",
    "OscConfig",
    "Screenshot",
    "SteamNotFoundError",
    "take_screenshot",
    "terminate",
    "unfocus",
    "VRCHAT_PROCESS_NAME",
    "VRCHAT_STEAM_APP_ID",
]
