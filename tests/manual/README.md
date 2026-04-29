# tests/manual

実 VRChat を起動して end-to-end の振る舞いを確認するためのスクリプト群。

## 目的

`tests/` 配下の通常のユニットテストは `pytest` で完結する高速・自動な検証だが、
`vrcpilot` は最終的に Steam 経由で実 VRChat プロセスを起動・終了する必要があ
り、その経路はモックでは検証しきれない。本ディレクトリのスクリプトは、実機で
VRChat を起こして PID を確認し、`terminate` まで通すことで、ライブラリ全体が
本物の環境で期待通り動くことを人間または Claude Code が確かめるための入口で
ある。

各スクリプトは終了時に必ず以下のいずれかを標準出力へ出す。

- `PASS: <name>` (exit code 0)
- `FAIL: <name>: <reason>` (exit code 1)

これにより、自走中の Claude Code でもユーザーでも、出力 1 行で成否を判別でき
る。

## 前提条件

- Windows 環境を想定（launcher が動作すれば Linux でも実行可能）。
- VRChat と Steam がインストール済みで、Steam にログイン済みであること。
- `just setup` 済みで `uv` 環境が整っていること。

## 警告

スクリプトを実行すると、その時点で起動している VRChat セッションが pre-cleanup
で強制終了される。VRChat を使った作業中には実行しないこと。各シナリオは
post-cleanup でも VRChat を落とすため、終了後の環境はクリーンな状態に戻る。

## 実行方法

`just` レシピを使うのが標準。

```sh
just manual launch_terminate
just manual cli_launch_terminate
just manual launch_no_vr
just manual focus_unfocus
```

直接実行も可能。

```sh
uv run python tests/manual/launch_terminate.py
```

## シナリオ一覧

| 名前                   | 内容                                                                                                                                                                 |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `launch_terminate`     | API (`vrcpilot.launch` / `find_pid` / `terminate`) のハッピーパス。                                                                                                  |
| `cli_launch_terminate` | `uv run vrcpilot` の `launch` / `status` / `terminate` を subprocess で叩く CLI 経路の検証。                                                                         |
| `launch_no_vr`         | `vrcpilot.launch(no_vr=True)` でデスクトップモード起動を確認。HMD 非装着のマシンでも動く想定。                                                                       |
| `focus_unfocus`        | `vrcpilot.focus()` で最前面化、`vrcpilot.unfocus()` で z-order 最下層化。各操作後に `_manual_artifacts/` へスクリーンショットを保存し、Claude / 人間が目視確認する。 |

## 実行時間の目安

各シナリオおよそ 30 秒前後。内訳は PID 検出 (~数秒) + warmup (15-20 秒) +
terminate / cleanup (数秒) 程度。

## CI への影響

`pyproject.toml` の pytest 設定で `--ignore=tests/manual` を指定しているため、
`just test` および CI の pytest 収集対象から除外される。手動でのみ走る、明示的
な動作確認スクリプトという位置付け。
