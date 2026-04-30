"""Abstract base class for VRChat window capture backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class CaptureBackend(ABC):
    """Platform-specific frame source for :class:`vrcpilot.Capture`.

    Implementations own a single open session against the platform's
    window-capture API (WGC on Windows, X11 Composite on Linux). They
    must be safe to construct in ``__init__`` and tear down in
    :meth:`close`; the public :class:`vrcpilot.Capture` wrapper handles
    closed-state checks and context-manager protocol.
    """

    @abstractmethod
    def read(self) -> np.ndarray:
        """Return the latest captured frame as an ``(H, W, 3)`` uint8 RGB
        ndarray.

        Implementations may block (Win32 / WGC delivers asynchronously)
        or be synchronous (X11 / Composite re-reads the pixmap on
        demand).
        """

    @abstractmethod
    def close(self) -> None:
        """Release platform resources.

        Must be idempotent and not raise.
        """
