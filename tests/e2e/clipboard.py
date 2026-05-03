"""E2E scenario: 日本語テキストを VRChat の chat 入力欄に貼り付ける.

`vrcpilot.clipboard.paste` は pyperclip でクリップボードに文字列を置き、
直後に Ctrl+V を叩くことで scancode ベースの keyboard では入力できない
非 ASCII 文字を VRChat に送る経路を提供する。本シナリオは:

* VRChat を Desktop モードで起動し、warmup 後に Y キーで chat 入力欄を開く
* `clipboard.paste("こんにちは VRChat")` を呼ぶ
* スクリーンショットを保存して目視確認できるようにする
* 最後に ESC で chat を閉じ、起動直後と同じ tidy 状態に戻して post-cleanup
  に渡す

Run with::

    just e2e-test clipboard

Prerequisites:

* デスクトップセッション (X11 / XWayland) が到達可能であること。native
  Wayland は ``ensure_target`` で弾かれる
* Steam が起動済みであること (``vrcpilot.launch()`` が timeout する)
* Linux では ``/dev/uinput`` への書き込み権限 (input グループ所属) が
  必要 — ``tests/e2e/keyboard.py`` の説明を参照
* Linux では ``xclip`` または ``xsel`` がインストール済みであること。
  pyperclip は内部でこれらを fork して selection 所有権を保持する
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
