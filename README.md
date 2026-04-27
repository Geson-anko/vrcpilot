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

## Shell completion

`vrcpilot` は [`argcomplete`](https://pypi.org/project/argcomplete/) を利用して、サブコマンド (`launch` / `terminate`)、オプション (`--steam-path` など)、および `--steam-path` に渡す `.exe` ファイルパスの Tab 補完を提供する。

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
vrcpilot <TAB><TAB>           # → launch terminate
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
