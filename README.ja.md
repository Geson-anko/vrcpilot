# vrcpilot

[English](README.md) | **日本語**

[![PyPI](https://img.shields.io/pypi/v/vrcpilot?color=blue)](https://pypi.org/project/vrcpilot/)
[![Python](https://img.shields.io/pypi/pyversions/vrcpilot)](https://pypi.org/project/vrcpilot/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test](https://github.com/MLShukai/vrcpilot/actions/workflows/test.yml/badge.svg)](https://github.com/MLShukai/vrcpilot/actions/workflows/test.yml)
[![Type Check](https://github.com/MLShukai/vrcpilot/actions/workflows/type-check.yaml/badge.svg)](https://github.com/MLShukai/vrcpilot/actions/workflows/type-check.yaml)
[![Format & Lint](https://github.com/MLShukai/vrcpilot/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/MLShukai/vrcpilot/actions/workflows/pre-commit.yml)

VRChat を Python から自動操作するツールキット (Windows / Linux 対応)。デスクトップクライアントの起動・フォーカス・キャプチャ・OCR・テンプレート検出・合成入力までを、型付きの Python API と `vrcpilot` CLI の両方で提供する。

## 機能

- **プロセス制御** — Steam 経由で VRChat を起動 (`vrcpilot.launch`)、PID 検出、安全な終了
- **ウィンドウ制御** — Win32 と X11 / XWayland での focus / unfocus / 前面確認
- **画面キャプチャ** — ストリーミング用 `Capture` (mp4 / y4m sink)、YAML を介して保存・復元できる 1 枚撮り `take_screenshot`
- **OCR** — 差し替え可能な `OCREngine` ABC とデフォルトの `RapidOCREngine`。`recognize()` は単語単位の結果をウィンドウローカルとデスクトップ絶対の両座標で返す
- **画像テンプレート検出** — OpenCV `TM_CCOEFF_NORMED` を使う `TemplateDetectEngine`。OCR と同じ座標スキーマで結果を返す
- **合成入力** — keyboard / mouse は Windows で [`pydirectinput`](https://github.com/learncodebygaming/pydirectinput)、Linux で [`inputtino`](https://github.com/games-on-whales/inputtino) (`/dev/uinput`) を経由。VRChat フォーカスのガード付き
- **非 ASCII テキスト入力** — `vrcpilot.clipboard` がクリップボード + Ctrl+V で任意の Unicode を投入
- **CLI フロントエンド** — `vrcpilot launch / screenshot / ocr / detect / mouse / keyboard / paste / capture / ...` を提供。`argcomplete` による Tab 補完あり

## インストール

```bash
# ライブラリ + CLI (alpha のため --pre が必要)
pip install --pre vrcpilot

# OCR extras 付き
pip install --pre "vrcpilot[ocr]"

# CLI ツールとしてのみ隔離インストール
uv tool install --prerelease=allow vrcpilot

# 開発インストール
git clone https://github.com/MLShukai/vrcpilot
cd vrcpilot
uv sync --all-extras
```

Python `>= 3.12` 必須。

## プラットフォーム別前提条件

### Windows

追加のシステムパッケージは不要。`pywin32` および `pydirectinput` が依存として自動で入る。

### Linux

X11 もしくは XWayland セッションが必須。Wayland ネイティブセッションは非対応で、`focus()` / `unfocus()` は `RuntimeWarning` を出して `False` を返す。

セッション種別の確認:

```bash
echo $XDG_SESSION_TYPE   # x11 または wayland
echo $DISPLAY            # XWayland 経由でもセットされていれば OK
```

[`inputtino-python`](https://github.com/games-on-whales/inputtino/tree/stable/bindings/python) は git からネイティブビルドされるため、`pip install` 前に以下のシステムパッケージが必要:

```bash
sudo apt-get install -y cmake build-essential pkg-config libevdev-dev
sudo usermod -aG input "$USER"   # /dev/uinput への書き込み権限。ログインし直して反映
```

`uinput` カーネルモジュールが無効な場合は `sudo modprobe uinput` で読み込む。

distribution name と import 名がずれている点に注意: PyPI 上は `inputtino-python`、Python の import 名は `inputtino`。

### macOS

非対応。

## Quick Start (CLI)

CLI が VRChat を駆動する一番手早い手段。パイプラインの基本形は「`screenshot` が `Screenshot` YAML を吐き、`ocr` / `detect` が stdin もしくは `--screenshot` でそれを受け取る」。OCR / detect 結果のクリック先には**必ず `display_pos.bbox`** を使う (ウィンドウローカルの `pos` ではない)。

```bash
# VRChat をデスクトップモードで起動し、立ち上がるまで待機
vrcpilot launch --no-vr --screen-width 1280 --screen-height 720 --wait-timeout 60

# screenshot → OCR → 可視化 PNG までを一度に
vrcpilot screenshot | vrcpilot ocr --viz /tmp/viz.png > /tmp/ocr.yaml

# 同じパイプを画像テンプレート検出に流す
vrcpilot screenshot | vrcpilot detect -q assets/button.png > /tmp/det.yaml

# マウス移動 + クリック (デスクトップ絶対座標)
vrcpilot mouse move 1183 514
vrcpilot mouse click left

# キー押下 (デフォルト duration は 0.1s。VRChat が確実に拾う下限)
vrcpilot keyboard press w --duration 1.0

# 非 ASCII テキストを投入 (clipboard + Ctrl+V)
vrcpilot paste "こんにちは、VRChat！"

# 終了 (idempotent)
vrcpilot terminate
```

すべてのフラグは `vrcpilot --help` と `vrcpilot <subcommand> --help` で確認できる。

## Quick Start (Python API)

```python
from time import sleep

import vrcpilot

# launch() は VRChat の PID を最大 wait_timeout 秒 (default 30s) 待って
# 返す。None はその時間内に VRChat が観測できなかったことを意味する。
pid = vrcpilot.launch(no_vr=True, screen_width=1280, screen_height=720)
if pid is None:
    raise RuntimeError("launch() のタイムアウト前に VRChat が起動しなかった")
sleep(45)  # 追加のウォームアップ: シェーダ / avatar ロード / ネットワーク同期

try:
    # 1 枚撮り (回復可能な失敗時は None)
    shot = vrcpilot.take_screenshot()
    if shot is None:
        raise RuntimeError("could not capture VRChat")

    # 全単語を OCR (engine 未指定時は cache された RapidOCREngine を使う)
    result = vrcpilot.recognize(shot)
    for word in result.words:
        print(word.text, result.display_bbox(word))

    # 最初の単語の中心へカーソル移動 + クリック
    if result.words:
        x, y, w, h = result.display_bbox(result.words[0])
        vrcpilot.mouse.move(int(x + w / 2), int(y + h / 2))
        vrcpilot.mouse.click(vrcpilot.MouseButton.LEFT)

    # キー押下
    vrcpilot.keyboard.press(vrcpilot.Key.W, duration=1.0)
finally:
    vrcpilot.terminate()
```

## CLI サブコマンド一覧

| サブコマンド | 用途                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------- |
| `launch`     | Steam 経由で VRChat を起動。`--no-vr` / `--screen-{width,height}` / `--wait-timeout` 等      |
| `pid`        | 動作中 VRChat の PID 一覧 (1 行 1 PID)                                                       |
| `terminate`  | VRChat を強制終了。idempotent                                                                |
| `focus`      | VRChat ウィンドウを前面に                                                                    |
| `unfocus`    | VRChat ウィンドウを z-order 末尾に                                                           |
| `screenshot` | 1 枚撮って `Screenshot` を YAML で吐く (PNG パスかインライン base64)                         |
| `capture`    | 一定 FPS で録画。`-o file.mp4` か、未指定で y4m を stdout                                    |
| `mouse`      | `move` / `click` / `scroll` (デスクトップ絶対座標)                                           |
| `keyboard`   | `press` (デフォルト `--duration 0.1`)                                                        |
| `paste`      | クリップボード + Ctrl+V でテキスト投入 (非 ASCII 対応)                                       |
| `ocr`        | `Screenshot` YAML に対して OCR (stdin pipe か `--screenshot <path>`)                         |
| `detect`     | `Screenshot` YAML 内をクエリ画像でテンプレート検索。`-q query.png`、`--threshold`、`--top-k` |

## Shell completion

`vrcpilot` は [`argcomplete`](https://pypi.org/project/argcomplete/) を利用して、サブコマンド (`launch` / `pid` / `terminate` / `focus` / `unfocus` / `screenshot` / `capture` / `mouse` / `keyboard` / `paste` / `ocr` / `detect`)、オプション (`--steam-path` など)、`--steam-path` に渡す `.exe` や `--query` に渡す `.png` のファイルパスの Tab 補完を提供する。

### 前提条件

- `uv sync` で開発インストールするか `uv tool install --prerelease=allow vrcpilot` で取得して、`register-python-argcomplete` が PATH に通っていること
- PATH を汚したくない場合は、以下のコマンドを `uv run register-python-argcomplete ...` に置き換えても代替できる

### ワンショットセットアップ (開発リポジトリ向け)

クローン直後に「venv 作成 → activate → 補完登録」までを 1 行で済ませたい場合、リポジトリ同梱のブートストラップスクリプトを **source / dot-source** する。

- bash: `. ./clicomp.sh`
- pwsh: `. .\CliComp.ps1`

スクリプトは以下を順に行う:

1. `.venv` が存在すれば activate する
2. `vrcpilot` がまだ PATH に無ければ `just setup` を実行し、再 activate する
3. `register-python-argcomplete` で現セッションに `vrcpilot` の補完を登録する

サブシェル (`bash clicomp.sh` や `.\CliComp.ps1` のような実行) では venv も補完も親シェルに残らないため、必ず source / dot-source すること (実行された場合はスクリプト側で拒否する)。永続化したい場合は起動 rc ファイルに以下を追記する。

```bash
# ~/.bashrc
. /path/to/vrcpilot/clicomp.sh
```

```powershell
# $PROFILE
. C:\path\to\vrcpilot\CliComp.ps1
```

### Bash / Git Bash

現セッションのみで一時的に有効化する場合:

```bash
eval "$(register-python-argcomplete vrcpilot)"
```

永続化するには上記 1 行を `~/.bashrc` (Git Bash 環境では `~/.bash_profile` でも可) に追記する。

### PowerShell

Windows PowerShell 5.1 / pwsh 7.x のいずれでも動作する想定だが、開発時は pwsh 7.x を推奨。

現セッションのみで一時的に有効化する場合:

```powershell
register-python-argcomplete --shell powershell vrcpilot | Out-String | Invoke-Expression
```

永続化するには PowerShell プロファイルに上記の `Invoke-Expression` 行を追記する。

```powershell
code $PROFILE   # または notepad $PROFILE
# 上記 Invoke-Expression 行を末尾に追記して保存
# 新しいセッションを開くか、`. $PROFILE` で再読込
```

### トラブルシュート

補完が効かない場合は、argcomplete の公式ドキュメント <https://kislyuk.github.io/argcomplete/> を参照。

## ドキュメント

- **チュートリアル / playbook**: [`docs/usage.md`](docs/usage.md) — タスク指向の解説 (launch → 観測 → クリック → 後片付け)
- **CLI リファレンス**: [`docs/cli.md`](docs/cli.md) — 全サブコマンドのフラグ・exit code。`vrcpilot --help` / `vrcpilot <subcommand> --help` と同等
- **Python API リファレンス**: [`docs/python-api.md`](docs/python-api.md) — `vrcpilot.<name>` で公開している全シンボル
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md)
- **Contributing**: [`CONTRIBUTING.md`](CONTRIBUTING.md) (英語)

## ライセンス

[MIT](LICENSE)
