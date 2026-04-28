"""Automation toolkit for VRChat.

``vrcpilot`` exposes building blocks for driving VRChat from Python: from
launching the client through Steam to higher-level UI / in-game automation
that will be layered on top. The top-level namespace re-exports the stable
entry points; lower-level helpers live under private submodules and are not
part of the public API.

Typical use::

    import vrcpilot

    vrcpilot.launch()
"""

from importlib import metadata

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.launcher import (
    VRCHAT_PROCESS_NAME,
    VRCHAT_STEAM_APP_ID,
    OscConfig,
    build_launch_command,
    build_vrchat_launch_args,
    find_pid,
    launch,
    terminate,
)

#: Installed package version, resolved from distribution metadata so it stays
#: in sync with ``pyproject.toml`` without being hard-coded here.
__version__ = metadata.version(__name__.replace("_", "-"))

__all__ = [
    "__version__",
    "build_launch_command",
    "build_vrchat_launch_args",
    "find_pid",
    "launch",
    "OscConfig",
    "SteamNotFoundError",
    "terminate",
    "VRCHAT_PROCESS_NAME",
    "VRCHAT_STEAM_APP_ID",
]
