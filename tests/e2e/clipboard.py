"""E2E scenario: paste Japanese text into VRChat's chat input box.

:func:`vrcpilot.clipboard.paste` writes a string to the clipboard via
pyperclip and immediately issues ``Ctrl+V``, providing a path to send
non-ASCII characters that the scancode-based keyboard cannot type. This
scenario:

* Launches VRChat in Desktop mode, warms up, then opens the chat input
  with the ``Y`` key.
* Calls ``clipboard.paste("Hello VRChat")`` (with a Japanese sample) so
  the resulting screenshot can be verified by eye.
* Closes chat with ``ESC`` so VRChat returns to the same tidy state as
  immediately after launch, ready for post-cleanup.

Run with::

    just e2e-test clipboard

Prerequisites:

* A desktop session (X11 / XWayland) must be reachable. Native Wayland
  is rejected by ``ensure_target``.
* Steam must already be running (``vrcpilot.launch()`` will time out
  otherwise).
* On Linux, write access to ``/dev/uinput`` (membership in the ``input``
  group) is required -- see ``tests/e2e/keyboard.py`` for details.
* On Linux, ``xclip`` or ``xsel`` must be installed. pyperclip forks
  one of them internally to hold selection ownership.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import vrcpilot
from vrcpilot import Key, clipboard, keyboard

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _helpers  # noqa: E402

_PASTE_TEXT = "こんにちは VRChat"


def _scenario() -> None:
    _helpers.log("calling vrcpilot.launch(no_vr=True)")
    vrcpilot.launch(no_vr=True)

    _helpers.log("waiting for VRChat PID")
    pid = _helpers.wait_for_pid()
    assert pid is not None, "VRChat PID was not observed before timeout"
    _helpers.log(f"VRChat started (pid={pid})")

    _helpers.warmup()

    # Step 1: open chat. Y is the VRChat Desktop shortcut for the chat
    # input box. After this press, focus should be inside the chatbox so
    # the subsequent Ctrl+V lands as text.
    _helpers.log("keyboard.press(Key.Y) (open chat input)")
    keyboard.press(Key.Y)
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("clipboard", "1_chat_open")

    # Step 2: paste the Japanese sample. The clipboard helper sets the
    # selection via pyperclip, sleeps briefly so xclip can take ownership
    # on Linux, then issues Ctrl+V via the keyboard backend with
    # focus=True (default), so the focus guard re-checks VRChat is still
    # foreground.
    _helpers.log(f"clipboard.paste({_PASTE_TEXT!r})")
    clipboard.paste(_PASTE_TEXT)
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("clipboard", "2_pasted")

    # Step 3: close the chat box with ESC so VRChat is left in the
    # natural post-launch state for post-cleanup. Also acts as a
    # smoke-check that no modifier was left stuck (a stuck CTRL would
    # make ESC behave differently or stick the menu).
    _helpers.log("keyboard.press(Key.ESCAPE) (close chat / tidy)")
    keyboard.press(Key.ESCAPE)
    time.sleep(0.5)
    _helpers.save_monitor_screenshot("clipboard", "3_closed")


def main() -> int:
    return _helpers.run_scenario("clipboard", _scenario)


if __name__ == "__main__":
    raise SystemExit(main())
