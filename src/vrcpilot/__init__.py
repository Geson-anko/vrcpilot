from importlib import metadata

from vrcpilot._steam import SteamNotFoundError
from vrcpilot.launcher import VRCHAT_STEAM_APP_ID, build_launch_command, launch_vrchat

__version__ = metadata.version(__name__.replace("_", "-"))

__all__ = [
    "VRCHAT_STEAM_APP_ID",
    "SteamNotFoundError",
    "__version__",
    "build_launch_command",
    "launch_vrchat",
]
