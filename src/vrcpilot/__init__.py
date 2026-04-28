"""Automation toolkit for VRChat.

``vrcpilot`` exposes building blocks for driving VRChat from Python: from
launching the client through Steam to higher-level UI / in-game automation
that will be layered on top. The top-level namespace re-exports the stable
entry points; lower-level helpers live under private submodules and are not
part of the public API.

Typical use::

    import vrcpilot

    process = vrcpilot.launch_vrchat()
"""

from importlib import metadata

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.launcher import (
    VRCHAT_PROCESS_NAME,
    VRCHAT_STEAM_APP_ID,
    OscConfig,
    build_launch_command,
    build_vrchat_launch_args,
    find_vrchat_pid,
    launch_vrchat,
    terminate_vrchat,
)

#: Installed package version, resolved from distribution metadata so it stays
#: in sync with ``pyproject.toml`` without being hard-coded here.
__version__ = metadata.version(__name__.replace("_", "-"))

__all__ = [
    "__version__",
    "build_launch_command",
    "build_vrchat_launch_args",
    "find_vrchat_pid",
    "launch_vrchat",
    "OscConfig",
    "SteamNotFoundError",
    "terminate_vrchat",
    "VRCHAT_PROCESS_NAME",
    "VRCHAT_STEAM_APP_ID",
]
