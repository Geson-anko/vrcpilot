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
    """Send arbitrary Unicode ``text`` to VRChat via clipboard + Ctrl+V.

    The brief sleep between copy and paste is load-bearing: on Linux,
    xclip / xsel take selection ownership asynchronously, so an
    immediate Ctrl+V can paste the *previous* clipboard contents.
    ``focus`` is forwarded to :func:`vrcpilot.controls.keyboard.press`;
    pass ``False`` only inside loops that have already verified the
    target window is foreground. Raises
    :class:`pyperclip.PyperclipException` when the clipboard backend is
    missing (e.g. no ``xclip`` / ``xsel`` on Linux) -- CLI callers wrap
    this for user-facing reporting.
    """
    pyperclip.copy(text)
    time.sleep(_CLIPBOARD_SETTLE)
    keyboard.press(Key.CTRL, Key.V, focus=focus)
