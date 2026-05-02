# vrcpilot

VRChat の操作を自動化するための Python ライブラリ。VRChat クライアントの UI 操作からゲーム内操作までを対象とする。

## Installation

開発環境のセットアップは `uv` を利用する。

```bash
# このリポジトリ内で開発インストール
uv sync --all-extras
```

将来の利用者向けには、配布された `vrcpilot` を CLI ツールとしてインストールする想定。

```bash
uv tool install vrcpilot
```

## プラットフォーム別前提条件

### Windows

追加インストールは不要。`pywin32` が依存として自動で入る。

### Linux (X11 / XWayland)

`vrcpilot.focus()` / `vrcpilot.unfocus()` は X11 EWMH 経由で VRChat ウィンドウの z-order を操作する。`python-xlib` は依存として自動で入るので、Linux パッケージを別途インストールする必要はないが、X11 が動作するセッションが必要。

- **X11 セッション**: そのまま動作する。
- **XWayland**: Wayland コンポジタ上でも `DISPLAY` が設定されていれば X11 アプリ（VRChat / Proton）として動作する。GNOME / KDE / Sway 等の主要コンポジタはデフォルトで XWayland 有効。
- **Wayland ネイティブ（XWayland 無効）**: 非対応。`focus()` / `unfocus()` は `RuntimeWarning` を出して `False` を返す。XWayland を有効にするか X11 セッションでログインし直すこと。

セッション種別の確認:

```bash
echo $XDG_SESSION_TYPE   # x11 または wayland
echo $DISPLAY            # XWayland 経由時もセットされていれば OK
```

### vrcpilot.controls (合成入力) の追加要件

`vrcpilot.controls` は VRChat への合成 mouse / keyboard 入力を Linux 上で
[inputtino](https://github.com/games-on-whales/inputtino) (`/dev/uinput`
経由) で送出する。`uv sync` 時に inputtino が git ソースからネイティブ
ビルドされるため、以下のシステム依存とランタイム要件が必要になる。

- **ビルド依存** (Ubuntu / Debian の例。他ディストリは
  [inputtino bindings/python](https://github.com/games-on-whales/inputtino/tree/stable/bindings/python)
  を参照):

  ```bash
  sudo apt-get install -y cmake build-essential pkg-config libevdev-dev
  ```

- **`/dev/uinput` への書き込み権限**: 通常は `input` グループに所属するか、
  udev rule で許可する。

  ```bash
  sudo usermod -aG input $USER
  # ログインし直してグループ反映
  ```

- **`uinput` カーネルモジュール**: 多くのディストリでは標準で有効。
  無効な場合 `sudo modprobe uinput` で読み込む。

- **distribution name vs import name**: PyPI 上は `inputtino-python`、
  Python の import 名は `inputtino`。`pyproject.toml` の依存名は前者。

### macOS

サポート対象外。

## Shell completion

`vrcpilot` は [`argcomplete`](https://pypi.org/project/argcomplete/) を利用して、サブコマンド (`launch` / `status` / `terminate` / `focus` / `unfocus`)、オプション (`--steam-path` など)、および `--steam-path` に渡す `.exe` ファイルパスの Tab 補完を提供する。

### 前提条件

- `uv sync` で開発インストール、または `uv tool install vrcpilot` を済ませて、`register-python-argcomplete` が PATH に通っていること。
- PATH を汚したくない場合は、以下のコマンドを `uv run register-python-argcomplete ...` に置き換えても代替できる。

### Bash / Git Bash

現セッションのみで一時的に有効化する場合。

```bash
eval "$(register-python-argcomplete vrcpilot)"
```

永続化するには、上記の 1 行を `~/.bashrc`（Git Bash 環境では `~/.bash_profile` でも可）に追記する。

動作確認の例。

```bash
vrcpilot <TAB><TAB>           # → focus launch status terminate unfocus
vrcpilot launch --<TAB><TAB>  # → --app-id --steam-path --no-vr ...
vrcpilot launch --steam-path <TAB>  # → カレントの .exe / ディレクトリ
```

### PowerShell

Windows PowerShell 5.1 / pwsh 7.x のいずれでも動作する想定だが、開発時は pwsh 7.x を推奨する。

現セッションのみで一時的に有効化する場合。

```powershell
register-python-argcomplete --shell powershell vrcpilot | Out-String | Invoke-Expression
```

永続化するには、PowerShell プロファイルに上記の `Invoke-Expression` 行を追記する。

```powershell
# PowerShell プロファイルを開く
code $PROFILE   # または notepad $PROFILE
# 上記 Invoke-Expression 行を末尾に追記して保存
# 新しいセッションを開くか、`. $PROFILE` で再読込
```

`register-python-argcomplete --shell powershell vrcpilot` を実行すると、`Register-ArgumentCompleter -Native -CommandName vrcpilot -ScriptBlock { ... }` 形式の補完スクリプトが標準出力に書き出される。これをそのままプロファイル内で評価すれば、新しいセッションから補完が有効になる。

### トラブルシュート

補完が効かない場合は、argcomplete の公式ドキュメント <https://kislyuk.github.io/argcomplete/> を参照。
