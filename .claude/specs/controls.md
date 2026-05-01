# Spec: VRChat 向け mouse / keyboard 入力機能（`vrcpilot.controls`）

VRChat の自動操作のため、起動中の VRChat ウィンドウに対して合成 mouse / keyboard 入力を送る API を `vrcpilot.controls` サブパッケージとして追加する。

## 1. 目的とスコープ

- 公開: VRChat 向けの mouse / keyboard 入力（移動、クリック、押下、スクロール、文字入力）
- 安全条件: 入力送出時、VRChat が **起動済 かつ 最前面** であることをデフォルトで保証する。ホットループ向けに opt-out も用意
- スコープ外: VR コントローラ入力、OSC、ゲームパッド、グローバルホットキー受信

## 2. モジュールレイアウト

```
src/vrcpilot/controls/
├── __init__.py     # ensure_target / errors の再公開
├── errors.py       # VRChatNotRunningError, VRChatNotFocusedError
├── guard.py        # ensure_target() 実装
├── mouse.py        # Mouse ABC + Win32Mouse + LinuxMouse + モジュール関数
└── keyboard.py     # Keyboard ABC + Win32Keyboard + LinuxKeyboard + モジュール関数
```

`window/` と `capture/` の踏襲。テストするので backend にも `_` prefix なし（[private モジュール規約](../memory/feedback_private_module_convention.md)）。

ABC を機能ファイルに同居させる（`base.py` は作らない）。1 ファイルが 1 機能のすべて（インターフェース・両 backend 実装・公開関数）を持つ。

## 3. アーキテクチャ

### 3.1 ABC は template-method で guard を内蔵

`Mouse` / `Keyboard` の **公開メソッドは ABC に実装** され、ガード処理を一箇所で扱う。具象クラスは副作用のみを `_do_*` 抽象メソッドで実装する。

```python
class Mouse(ABC):
    def click(
        self,
        button: Literal["left", "right", "middle"] = "left",
        *,
        count: int = 1,
        ensure_target: bool = True,
    ) -> None:
        if ensure_target:
            from .guard import ensure_target as _ensure
            _ensure()
        self._do_click(button, count=count)

    @abstractmethod
    def _do_click(self, button: str, *, count: int) -> None: ...
```

### 3.2 Backend インスタンスは遅延生成

各機能モジュールは backend インスタンスを **最初の関数呼出時に一度だけ** 作る。`import vrcpilot.controls` 自体は副作用無し（特に Linux inputtino の uinput device オープンを遅らせる）。

```python
_instance: Mouse | None = None

def _get() -> Mouse:
    global _instance
    if _instance is None:
        if sys.platform == "win32":
            _instance = Win32Mouse()
        elif sys.platform == "linux":
            _instance = LinuxMouse()
        else:
            raise NotImplementedError(
                f"controls.mouse is not supported on {sys.platform}"
            )
    return _instance
```

### 3.3 ユーザー向け公開はモジュール関数

利用側は **インスタンスではなくモジュール関数** を呼ぶ。サブモジュール `mouse` / `keyboard` の名前と衝突しない。

```python
# controls/mouse.py
def click(button="left", *, count=1, ensure_target=True) -> None:
    _get().click(button, count=count, ensure_target=ensure_target)
```

```python
# 利用例
from vrcpilot.controls import mouse, keyboard
mouse.click()
keyboard.press("a")
mouse.move(100, 200, ensure_target=False)  # ホットループで guard skip

import vrcpilot.controls as ctl
ctl.ensure_target()  # ループ前に明示的に検証
```

テスト側は具象クラスを直接インスタンス化できる:

```python
from vrcpilot.controls.mouse import Win32Mouse
m = Win32Mouse()
m.click()
```

## 4. 公開 API

### 4.1 mouse (`vrcpilot.controls.mouse`)

| 関数      | シグネチャ                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------------ |
| `move`    | `(x: int, y: int, *, relative: bool = False, ensure_target: bool = True) -> None`                            |
| `click`   | `(button: Literal["left","right","middle"] = "left", *, count: int = 1, ensure_target: bool = True) -> None` |
| `press`   | `(button: Literal["left","right","middle"] = "left", *, ensure_target: bool = True) -> None`                 |
| `release` | `(button: Literal["left","right","middle"] = "left", *, ensure_target: bool = True) -> None`                 |
| `scroll`  | `(amount: int, *, ensure_target: bool = True) -> None`                                                       |

### 4.2 keyboard (`vrcpilot.controls.keyboard`)

| 関数        | シグネチャ                                                                  |
| ----------- | --------------------------------------------------------------------------- |
| `press`     | `(key: str, *, ensure_target: bool = True) -> None` — down→up タップ        |
| `down`      | `(key: str, *, ensure_target: bool = True) -> None`                         |
| `up`        | `(key: str, *, ensure_target: bool = True) -> None`                         |
| `type_text` | `(text: str, *, interval: float = 0.0, ensure_target: bool = True) -> None` |

キー名は両 backend 共通の正規化文字列（例: `"a"`, `"space"`, `"f1"`, `"shift"`）。マッピングが必要なら `controls/_keymap.py` を実装フェーズで追加する（規模次第）。

### 4.3 guard / errors (`vrcpilot.controls`)

```python
from vrcpilot.controls import (
    ensure_target,           # 関数
    VRChatNotRunningError,   # RuntimeError サブクラス
    VRChatNotFocusedError,   # RuntimeError サブクラス
)
```

`controls/__init__.py` は上記 3 つのみ再公開する（`mouse` / `keyboard` はサブモジュールなので import 経由で取得）:

```python
from .errors import VRChatNotRunningError, VRChatNotFocusedError
from .guard import ensure_target

__all__ = ["ensure_target", "VRChatNotRunningError", "VRChatNotFocusedError"]
```

トップ `vrcpilot/__init__.py` でも上記 3 つを再公開する（既存 `focus` / `unfocus` 等と同パターン）。

### 4.4 `ensure_target()` の振る舞い

```python
def ensure_target() -> None:
    """VRChat が起動 & 最前面であることを保証する。

    未起動なら VRChatNotRunningError。最前面でなければ window.focus()
    を 1 回試行し、それでも前面に来なければ VRChatNotFocusedError。
    """
    if process.find_pid() is None:
        raise VRChatNotRunningError(...)
    if not window.is_foreground():
        if not window.focus():
            raise VRChatNotFocusedError(...)
        if not window.is_foreground():
            raise VRChatNotFocusedError(...)
```

## 5. `window/` への追加（前提）

`controls.guard` が呼ぶため、`window` に最前面判定 API を新設する。

- `vrcpilot.window.is_foreground() -> bool` — VRChat ウィンドウが最前面か（既存 `focus` / `unfocus` と同型 dispatch）
- `window/win32.py` に `is_window_foreground()`（`GetForegroundWindow` 比較）
- `window/x11.py` に `is_window_foreground()`（`_NET_ACTIVE_WINDOW` 比較。Wayland では既存どおり `RuntimeWarning` + `False`）
- `window/__init__.py` の `__all__` と トップ `vrcpilot/__init__.py` で `is_foreground` を公開

## 6. 依存関係

### 6.1 `pyproject.toml`

```toml
[project]
dependencies = [
    # ... 既存 deps ...
    "pydirectinput>=1.0.4 ; sys_platform == 'win32'",
    "inputtino ; sys_platform == 'linux'",
]

[tool.uv.sources]
inputtino = { git = "https://github.com/games-on-whales/inputtino.git", subdirectory = "bindings/python", branch = "stable" }
```

### 6.2 含意

- **uv ユーザー**: `uv sync` 一発で git からビルド・インストールされる

- **pip ユーザー**: `[tool.uv.sources]` を読まないため `inputtino` を PyPI に探しに行って失敗する。Linux 環境で pip install したい場合は事前に手動で:

  ```sh
  pip install "git+https://github.com/games-on-whales/inputtino.git@stable#subdirectory=bindings/python"
  ```

- **将来の PyPI アップロード**: `[project.dependencies]` に direct URL が無いのでブロックされない

### 6.3 README Installation 追記

- Linux システム依存: `uinput` カーネルモジュール、`libudev`、`libevdev`、ネイティブビルドツール
- `uinput` への書き込み権限（udev rule、もしくは権限を持つグループでの実行）。inputtino のネイティブ初期化失敗時の対処として記述
- pip ユーザー向けの手動 install 手順（上記コマンド）
- Windows: `pydirectinput` は通常の pip 依存なので追加手順不要

## 7. エラー方針

- `VRChatNotRunningError(RuntimeError)`
- `VRChatNotFocusedError(RuntimeError)`

inputtino のネイティブ初期化（uinput オープン）失敗時は inputtino 側の例外をそのまま伝播させる（独自ラッパは置かない）。

## 8. テストレイアウト

[ミラー規約](../memory/feedback_test_layout_mirror.md) に従い `src` と 1:1 ミラー。

```
tests/vrcpilot/controls/
├── __init__.py
├── test_init.py        # ensure_target / errors の再公開確認
├── test_errors.py      # 継承関係の確認
├── test_guard.py       # ensure_target の各分岐（process.find_pid / window.is_foreground を mocker で差替）
├── test_mouse.py       # Mouse ABC + Win32Mouse + LinuxMouse + モジュール関数
└── test_keyboard.py    # Keyboard ABC + Win32Keyboard + LinuxKeyboard + モジュール関数
```

`window/` 側にも追加:

- `tests/vrcpilot/window/test_init.py` に `is_foreground` のテスト追加
- `tests/vrcpilot/window/test_win32.py` / `test_x11.py` に `is_window_foreground` テスト追加

`mouse.py` / `keyboard.py` は Win32 / Linux 両具象が同居するので、テストファイルも分割せず `test_mouse.py` / `test_keyboard.py` で扱う。Win32 部・Linux 部はそれぞれ `pytest.mark.skipif(sys.platform != ...)` で振り分ける。

ABC の template-method（guard 配線）テストは `tests/helpers.py` に `Impl` 具象を定義し（モックではなく実体）、`test_mouse.py` / `test_keyboard.py` から共有する。

手動シナリオ:

```
tests/manual/
├── controls_mouse_click.py     # Step 2 検証用
└── controls_keyboard_type.py   # Step 3 検証用
```

## 9. 実装ステップ

各ステップ完了時に `just run` をパスさせ独立にコミットする。

### Step 1: core

- 追加: `controls/__init__.py`、`controls/errors.py`、`controls/guard.py`
- 追加: `window/win32.py`・`window/x11.py` の `is_window_foreground()`、`window/__init__.py` の `is_foreground()` dispatch、トップ `vrcpilot/__init__.py` の再公開
- 更新: `pyproject.toml` の `[project.dependencies]` と `[tool.uv.sources]`
- 更新: `README.md` Installation の Linux 用節
- 追加: `tests/vrcpilot/controls/test_init.py` / `test_errors.py` / `test_guard.py`
- 更新: `tests/vrcpilot/window/test_init.py` 等に `is_foreground` テスト追加
- このステップ単体では mouse / keyboard 操作 API は公開されない

### Step 2: mouse

- 追加: `controls/mouse.py`（Mouse ABC + Win32Mouse + LinuxMouse + モジュール関数 click/move/press/release/scroll、lazy `_get()` 含む）
- 追加: `tests/vrcpilot/controls/test_mouse.py`
- 追加: `tests/manual/controls_mouse_click.py`
- 検証: `just manual controls_mouse_click` を Win / Linux 双方で実機通し

### Step 3: keyboard

- 追加: `controls/keyboard.py`（Keyboard ABC + Win32Keyboard + LinuxKeyboard + モジュール関数 press/down/up/type_text）
- 必要なら追加: `controls/_keymap.py`
- 追加: `tests/vrcpilot/controls/test_keyboard.py`
- 追加: `tests/manual/controls_keyboard_type.py`
- 検証: `just manual controls_keyboard_type` を Win / Linux 双方で実機通し

## 10. 検証手順

- 各ステップで `just run`（format + test + type）が green
- Step 2 / Step 3 の手動シナリオが Win / Linux 双方で目視成功
