---
name: private モジュール規約
description: src/vrcpilot/ における `_` prefix モジュール命名規約 — テスト有無で prefix を決める
type: feedback
---

`src/vrcpilot/` 配下のモジュールは **テストの有無** で `_` prefix の有無を決める:

- テストを書かない（真に private な実装）→ ファイル名に `_` prefix を付ける（例: `_session.py`）
- テストを書く / 書かれている → `_` prefix を **付けない**（例: `steam.py`, `win32.py`, `x11.py`, `capture/sinks.py`）
- 外部公開は `__init__.py` の `__all__` で別途集約管理する。モジュール名の `_` 有無と「公開 API」は独立した軸として扱う

**Why:** `tests/` から `_`-prefixed モジュールを import するのは「テストする = 外部からも触り得る」ことを意味し、prefix の本来の意図（"do not test, do not touch"）と矛盾する。命名規約として一貫させ、誤誘導を防ぐ。`__all__` で公開面を制御していれば、内部モジュール名から `_` を外しても外部に漏れることはない。

**How to apply:** モジュールを新設する時、テストを書くか即決する。テストを書くつもりなら `_` 無しの名前にする。逆に誰にも触らせたくない実装は `_` を付けてテストも書かない。既存ファイルでテストを追加する場合は、リネーム + importer 修正をセットで行う（公開 API として `__init__.py` の `__all__` に足すかは別判断）。

## tests/ 配下では適用しない

この規約は `src/vrcpilot/` 専用。`tests/` には「外部公開」の概念が無いので `_` prefix は基本的に**付けない**:

- `tests/helpers.py` / `tests/fakes/` / `tests/conftest.py` — prefix 無しで揃える
- 例外: `tests/manual/_helpers.py` は **`just manual <NAME>`** が `tests/manual/<NAME>.py` を直接実行する仕組みになっており、prefix 無しだと `just manual helpers` が誤実行されうる。同階層の `all.py` / `focus_unfocus.py` 等の **実行可能シナリオ** と区別する語彙として `_` を残す

**判断基準:** `tests/` 内で `_` を付けるのは「機能的に prefix が役立つ場合」(例: 直接 script 実行されるディレクトリ内でのヘルパー識別) のみ。「外部から触らせない」目的で `_` を付けない。
