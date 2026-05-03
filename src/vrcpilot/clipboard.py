"""Clipboard helper for non-ASCII text input into VRChat.

`vrcpilot.controls.keyboard` は scancode ベースで動作するため、日本語のような
非 ASCII 文字列は直接入力できない。本モジュールはこの制限を回避するため、
文字列を OS のクリップボードに書き込み、VRChat へ ``Ctrl+V`` を送る経路を
提供する。pyperclip 1 つに依存する薄いラッパで、プラットフォーム分岐は
pyperclip 内部に委ねている。
"""

from __future__ import annotations

import time

import pyperclip

from vrcpilot.controls import Key, keyboard

#: xclip / xsel が selection の所有権を取得するまでの猶予 (秒)。
#: Linux で copy 直後に paste すると selection 反映前に Ctrl+V が走り、
#: 直前の clipboard 内容が貼られる事故が起きるため明示的に待つ。
_CLIPBOARD_SETTLE: float = 0.05


def paste(text: str, *, focus: bool = True) -> None:
    """Copy ``text`` to the clipboard and send ``Ctrl+V`` to VRChat.

    The function performs three steps in order:

    1. ``pyperclip.copy(text)`` — write ``text`` to the OS clipboard.
    2. ``time.sleep(_CLIPBOARD_SETTLE)`` — let the clipboard backend
       settle (xclip / xsel acquire selection ownership asynchronously).
    3. ``keyboard.press(Key.CTRL, Key.V, focus=focus)`` — drive the
       paste shortcut. ``focus`` is forwarded to
       :func:`vrcpilot.controls.keyboard.press`, which runs
       :func:`vrcpilot.controls.guard.ensure_target` when ``True``.

    Args:
        text: String to paste. May contain any Unicode characters that
            the clipboard backend supports.
        focus: When ``True`` (default), ``ensure_target`` is invoked
            before the keystroke so VRChat is guaranteed to receive
            the paste. Set to ``False`` inside loops that have already
            verified focus.

    Raises:
        pyperclip.PyperclipException: The clipboard backend is missing
            (e.g. neither ``xclip`` nor ``xsel`` is installed on Linux)
            or otherwise failed. The exception propagates unmodified;
            CLI callers wrap it for user-facing reporting.
    """
    pyperclip.copy(text)
    time.sleep(_CLIPBOARD_SETTLE)
    keyboard.press(Key.CTRL, Key.V, focus=focus)
