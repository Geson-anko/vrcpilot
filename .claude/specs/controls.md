# Spec: VRChat 向け mouse / keyboard 入力機能（`vrcpilot.controls`）

VRChat の自動操作のため、起動中の VRChat ウィンドウに対して合成 mouse / keyboard 入力を送る API を `vrcpilot.controls` サブパッケージとして追加する。

## 1. 目的とスコープ

- 公開: VRChat 向けの mouse / keyboard 入力（移動、クリック、押下、修飾子コンボ、スクロール）
- 安全条件: 入力送出時、VRChat が **起動済 かつ 最前面** であることをデフォルトで保証する。ホットループ向けに opt-out も用意
- スコープ外: VR コントローラ入力、OSC、ゲームパッド、グローバルホットキー受信、**文字列入力**（任意のテキスト送出は将来追加する `controls.clipboard` モジュール経由とする方針）

## 2. モジュールレイアウト

```
src/vrcpilot/controls/
├── __init__.py     # ensure_target / errors / Key の再公開
├── errors.py       # VRChatNotRunningError, VRChatNotFocusedError
├── guard.py        # ensure_target() 実装
├── mouse.py        # Mouse ABC + Win32Mouse + LinuxMouse + モジュール関数
└── keyboard.py     # Key StrEnum + Keyboard ABC + Win32Keyboard + LinuxKeyboard + モジュール関数
```

`window/` と `capture/` の踏襲。テストするので backend にも `_` prefix なし（[private モジュール規約](../memory/feedback_private_module_convention.md)）。

ABC を機能ファイルに同居させる（`base.py` は作らない）。1 ファイルが 1 機能のすべて（インターフェース・両 backend 実装・公開関数）を持つ。

## 3. アーキテクチャ

### 3.1 ABC は template-method で guard を内蔵

`Mouse` / `Keyboard` の **公開メソッドは ABC に実装** され、ガード処理を一箇所で扱う。具象クラスは副作用のみを `_do_*` 抽象メソッドで実装する。

```python
from .guard import ensure_target

class Mouse(ABC):
    def click(
        self,
        button: Literal["left", "right", "middle"] = "left",
        *,
        count: int = 1,
        duration: float = 0.0,
        focus: bool = True,
    ) -> None:
        if focus:
            ensure_target()
        self._do_click(button, count=count, duration=duration)

    @abstractmethod
    def _do_click(self, button: str, *, count: int, duration: float) -> None: ...
```

`duration` は backend 内で down → `time.sleep(duration)` → up の挟み込みに使う（`0.0` の場合 sleep を呼ばない）。`Keyboard.press` も同型で `_do_press(key, *, duration)` を持つ。

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
def click(button="left", *, count=1, duration=0.0, focus=True) -> None:
    _get().click(button, count=count, duration=duration, focus=focus)
```

```python
# 利用例
from vrcpilot.controls import mouse, keyboard, Key
mouse.click()
mouse.click(duration=0.05)            # 50ms ホールドしてから release
keyboard.press(Key.SPACE)             # 即座に down→up
keyboard.press(Key.SPACE, duration=0.1)  # 100ms ホールド
mouse.move(100, 200, focus=False)     # ホットループで guard skip

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

| 関数      | シグネチャ                                                                                                                  |
| --------- | --------------------------------------------------------------------------------------------------------------------------- |
| `move`    | `(x: int, y: int, *, relative: bool = False, focus: bool = True) -> None`                                                   |
| `click`   | `(button: Literal["left","right","middle"] = "left", *, count: int = 1, duration: float = 0.0, focus: bool = True) -> None` |
| `press`   | `(button: Literal["left","right","middle"] = "left", *, focus: bool = True) -> None`                                        |
| `release` | `(button: Literal["left","right","middle"] = "left", *, focus: bool = True) -> None`                                        |
| `scroll`  | `(amount: int, *, focus: bool = True) -> None`                                                                              |

### 4.2 keyboard (`vrcpilot.controls.keyboard`)

| 関数    | シグネチャ                                                                          |
| ------- | ----------------------------------------------------------------------------------- |
| `press` | `(key: Key, *, duration: float = 0.0, focus: bool = True) -> None` — down→up タップ |
| `down`  | `(key: Key, *, focus: bool = True) -> None`                                         |
| `up`    | `(key: Key, *, focus: bool = True) -> None`                                         |

すべて **`Key` enum** で受ける（IDE 補完・型チェックで typo を弾く）。任意文字列の入力は本モジュールでは扱わない（後述 §11.3 参照、`controls.clipboard` で対応する方針）。

`duration` は down と up の間隔（秒）。`0.0` で即座に up（VRChat や Unity が即押しを取りこぼす場合に `0.02` ～ `0.05` 程度を渡すユースケース）。`mouse.click` も同じ意味のパラメータを持つ。

#### `Key` enum

`enum.StrEnum`（Python 3.11+）として `controls/keyboard.py` に定義する。値は pydirectinput の慣習名と揃え、`StrEnum` なので backend 側で `key.value` をそのまま渡せる。

```python
from enum import StrEnum

class Key(StrEnum):
    """Normalized key identifiers."""

    # 英字
    A = "a"
    # ... B ～ Z
    # 数字（識別子に "0" は使えないので NUM_ プレフィックス）
    NUM_0 = "0"
    # ... NUM_1 ～ NUM_9
    # ファンクション
    F1 = "f1"
    # ... F2 ～ F12（必要なら F24 まで）
    # 修飾子（左右別 + generic は左にマップ）
    SHIFT = "shift"
    SHIFT_LEFT = "shiftleft"
    SHIFT_RIGHT = "shiftright"
    CTRL = "ctrl"
    CTRL_LEFT = "ctrlleft"
    CTRL_RIGHT = "ctrlright"
    ALT = "alt"
    ALT_LEFT = "altleft"
    ALT_RIGHT = "altright"   # AltGr 含む
    WIN = "win"
    WIN_LEFT = "winleft"
    WIN_RIGHT = "winright"
    # ナビゲーション・矢印
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    HOME = "home"
    END = "end"
    PAGE_UP = "pageup"
    PAGE_DOWN = "pagedown"
    # 編集
    BACKSPACE = "backspace"
    DELETE = "delete"
    INSERT = "insert"
    TAB = "tab"
    ENTER = "enter"
    ESCAPE = "escape"
    SPACE = "space"
    # 記号（識別子化）
    MINUS = "-"
    EQUALS = "="
    LBRACKET = "["
    RBRACKET = "]"
    BACKSLASH = "\\"
    SEMICOLON = ";"
    QUOTE = "'"
    COMMA = ","
    PERIOD = "."
    SLASH = "/"
    BACKTICK = "`"
```

`Key` は `controls/__init__.py` で再公開し、トップ `vrcpilot/__init__.py` でも公開する。エイリアス（`"esc"` → `ESCAPE` 等）は enum 採用に伴い不要（呼び出し側は `Key.ESCAPE` を書く）。

#### 両 backend への翻訳

inputtino の API は Windows DirectInput 系の流儀を踏襲しており、左右の修飾子・矢印・ファンクションキー等が L/R 別の scan code として揃っている。両 backend で 1:1 マッピングが取れる見込み。

- **Win32 / pydirectinput**: `key.value` をそのまま `pydirectinput.press(...)` に渡す（StrEnum の値が pydirectinput 慣習名と一致。`"shift"` は左、`"shiftright"` は右、と両方が KEYBOARD_MAPPING にある）

- **Linux / inputtino**: `Key` → inputtino のキー識別子への dict を `keyboard.py` 内で持つ。`LinuxKeyboard.__init__` で inputtino import 後にテーブルを構築（lazy）。下記は **暫定スケッチ**（実 API は §11 参照、install 後に確認すること）:

  ```python
  _INPUTTINO_CODES: dict[Key, int] = {
      Key.SHIFT:       inputtino.KEY_LEFTSHIFT,   # generic は左にマップ
      Key.SHIFT_LEFT:  inputtino.KEY_LEFTSHIFT,
      Key.SHIFT_RIGHT: inputtino.KEY_RIGHTSHIFT,
      # ... 同様に CTRL / ALT / WIN
  }
  ```

翻訳テーブルは `keyboard.py` 内に閉じるので **`_keymap.py` は不要**。

#### 修飾子コンボ

`down` → `press` → `up` の明示的な組み合わせで扱う。`press("ctrl+c")` のような string-parsing は導入しない。

```python
from vrcpilot.controls import keyboard, Key

keyboard.down(Key.CTRL)
keyboard.press(Key.C)
keyboard.up(Key.CTRL)
```

将来コンボ用の薄いヘルパ（例: `keyboard.combo(Key.CTRL, Key.C)` や `with keyboard.held(Key.CTRL):`）が必要になったら追加する。初版スコープには含めない。

### 4.3 guard / errors / Key (`vrcpilot.controls`)

```python
from vrcpilot.controls import (
    ensure_target,           # 関数
    VRChatNotRunningError,   # RuntimeError サブクラス
    VRChatNotFocusedError,   # RuntimeError サブクラス
    Key,                     # StrEnum
)
```

`controls/__init__.py`:

```python
from .errors import VRChatNotRunningError, VRChatNotFocusedError
from .guard import ensure_target
from .keyboard import Key

__all__ = [
    "ensure_target",
    "VRChatNotRunningError",
    "VRChatNotFocusedError",
    "Key",
]
```

トップ `vrcpilot/__init__.py` でも `ensure_target` / 2 エラー型 / `Key` を再公開する（既存 `focus` / `unfocus` 等と同パターン）。`mouse` / `keyboard` 自体はサブモジュールなので `from vrcpilot.controls import mouse, keyboard` で取得する。

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
└── controls_keyboard_combo.py  # Step 3 検証用（修飾子コンボの down→press→up）
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

- 追加: `controls/keyboard.py`（`Key` StrEnum + Keyboard ABC + Win32Keyboard + LinuxKeyboard + inputtino スキャンコード dict + モジュール関数 press/down/up）
- 更新: `controls/__init__.py` で `Key` を再公開
- 更新: トップ `vrcpilot/__init__.py` で `Key` 等を再公開
- 追加: `tests/vrcpilot/controls/test_keyboard.py`
- 追加: `tests/manual/controls_keyboard_combo.py`（修飾子コンボの down→press→up を VRChat 上で目視確認、例: `Ctrl+Tab` で UI 切替など）
- 検証: `just manual controls_keyboard_combo` を Win / Linux 双方で実機通し

## 10. 検証手順

- 各ステップで `just run`（format + test + type）が green
- Step 2 / Step 3 の手動シナリオが Win / Linux 双方で目視成功

## 11. 実装前に確認すべき事項

本仕様書中の **inputtino API は推測ベース**（Windows DirectInput 系の流儀という公開情報からの類推）。Step 2 着手前に必ず実物を確認し、ズレていれば本仕様書を更新してから実装する。

### 11.1 inputtino インストール直後の確認手順

```sh
uv add "git+https://github.com/games-on-whales/inputtino.git#subdirectory=bindings/python&branch=stable"
uv run python -c "import inputtino; help(inputtino)"
uv run python -c "import inputtino; print([n for n in dir(inputtino) if not n.startswith('_')])"
```

確認したい点:

- **Mouse class**: コンストラクタ引数（device 名・vendor / product id 等の必須項目）、メソッド名（`move(x, y)` か `move_rel(dx, dy)` か、`button_press` / `press_button` 等）、戻り値、例外型
- **Keyboard class**: 同上。`press(key) / release(key)` のシグネチャ、key 引数の型（int scan code か enum か文字列か）
- **キー定数**: `KEY_A`, `KEY_LEFTSHIFT`, `KEY_RIGHTSHIFT` 等のモジュールレベル定数の有無と命名規約。無ければ `linux/input-event-codes.h` の値（int 直書き or `evdev.ecodes` 経由）に変更
- **スクロール**: マウススクロールの API（`scroll(dy)` か `scroll_vertical(amount)` か）と方向の正負規約
- **絶対座標 vs 相対座標**: `Mouse.move()` がデフォルトで absolute か relative か。VRChat 操作では absolute を期待
- **権限エラー時の例外型**: uinput アクセス失敗時に inputtino が投げる例外を catch して有用なメッセージにできるか

### 11.2 確認後に本仕様書を更新する箇所

- §4.2 翻訳セクションのコード例
- §3 `LinuxMouse` / `LinuxKeyboard` の `__init__` / `_do_*` の具体実装スケッチ
- §7 エラー方針（必要なら inputtino 例外の扱いを追記）

### 11.3 文字列入力の方針（参考）

任意文字列の入力（特に日本語等の非 ASCII）は `controls` 本体では扱わず、将来 **`vrcpilot.controls.clipboard` モジュール** を追加して対応する方針。

理由:

- pydirectinput / inputtino はどちらも scan code ベース。Unicode 文字イベントを直接送れない（`KEYEVENTF_UNICODE` を使う Win32 SendInput への自前差し替えは可能だが、Linux 側に対応が無いのでクロスプラットフォーム性が崩れる）
- ASCII 限定の `type_text` を入れても VRChat の主用途（日本語チャット）に応えられず、API として中途半端になる
- clipboard 経由なら **Unicode 全般を確実に入れられる**（`pyperclip` 等で text をクリップボードに入れて `Ctrl+V` を送出するだけ）。本仕様の `keyboard.down(Key.CTRL) → press(Key.V) → up(Key.CTRL)` を組み合わせて使える

`controls.clipboard` の仕様は需要が出てから別途切る。本仕様書のスコープ外。
