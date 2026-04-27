# CLAUDE.md

このファイルは Claude Code (claude.ai/code) がこのリポジトリを扱う際のガイダンスを提供する。

## プロジェクト概要

`vrcpilot` は VRChat の操作を自動化するための Python ライブラリ。VRChat クライアントの UI 操作からゲーム内操作までを対象とする。

## プロジェクト状況

このリポジトリは Python の `uv` テンプレートから初期化された直後で、`vrcpilot` パッケージ自体は現状空のスケルトン（`src/vrcpilot/__init__.py` に `__version__` のみ）。ドメインコードやアーキテクチャはまだ存在しないため、ゼロから構築する想定。最初の実モジュールを追加するタイミングで、出現したアーキテクチャに合わせてこのファイルを更新すること。

## ツーリング

- パッケージ・環境管理: `uv`（ロックファイル `uv.lock` をコミット済み）
- Python: `>=3.12` 必須。CI は Linux / Windows × 3.12 / 3.13 / 3.14 のマトリクス
- タスクランナー: `just`（`justfile`）。Windows でも `just` は Git Bash を呼び出す設定なのでレシピは Unix シェル前提で書く
- 型チェッカー: `pyright` を `./src/` に対し **strict** モードで実行（`tests/` は除外）。`reportImplicitOverride` 有効、`reportPrivateUsage` は警告
- リンター/フォーマッター: `ruff`（line-length 88、ダブルクォート、isort + `combine-as-imports`）
- pre-commit: ruff、pyupgrade（`--py312-plus`）、docformatter、mdformat、codespell、`uv-lock`（lockfile 鮮度）、pygrep checks（`python-check-blanket-noqa`、`python-no-log-warn` 等）を実行

## コマンド

`just` レシピを使う（`uv run` をラップしているので venv が常に尊重される）:

- `just setup` - 開発環境のセットアップ（`uv venv` + `uv sync --all-extras` + `pre-commit install`）
- `just format` - pre-commit フックを実行（ruff fix + format、mdformat、codespell など）
- `just test` - `uv run pytest -v --cov`
- `just type` - `uv run pyright`
- `just run` - format → test → type を順に実行
- `just clean` - `dist/`、`__pycache__`、`.pytest_cache`、`.coverage` 等を削除

細かい制御が必要な場合の直接呼び出し:

- 単一テスト: `uv run pytest tests/test_package.py::test_version -v`
- キーワードフィルタ: `uv run pytest -v -k "<expr>"`
- 単一パスへの pyright: `uv run pyright src/vrcpilot/<file>.py`
- 単一の pre-commit フック: `uv run pre-commit run ruff -a`

## pytest 設定の注意点

`pyproject.toml` で `addopts = ["--strict-markers", "--doctest-modules", ...]` が設定されている。コードを書く際の含意:

- `--doctest-modules` により `testpaths = "tests/"` 配下および import される source の全モジュールから doctest が収集される。docstring 内の `>>>` 例は実行されるため、確実にパスするよう書くか、プロンプトを省くこと
- `--strict-markers` のため、`@pytest.mark.<name>` は事前に `pyproject.toml` の `[tool.pytest.ini_options] markers` に登録する必要がある。未登録だとテストはエラーになる

`asyncio_default_fixture_loop_scope = "function"` は `pytest-asyncio` 想定で設定されているが、当該プラグインは現状 `dev` deps に含まれていない。async テストを書く前に追加すること。

## テスト方針

### 基本原則

- 必要十分なテストのみを記述する。過剰なテストは避ける
- 内部実装の詳細はテストしない。公開インターフェースと振る舞いをテストする
- テスト関数に戻り値の型アノテーションは不要

### 実践的なテスト

- 実際のオブジェクトを生成し、実際の入出力で振る舞いを検証する
- できる限りモックを使わない。外部依存であっても、テスト用の実データ（一時ファイル等）を生成して回避できる場合は実データを使う
- モックは最小限にとどめる。モックを使ってよいのは以下の場合のみ:
  - 外部 API（VRChat API などネットワーク通信を伴うもの）
  - ファイルシステムや DB など、テスト環境で再現が困難な外部依存
- 内部モジュール同士の結合はモックせず、実際に結合してテストする
- 複数のパラメータをテストする場合は `@pytest.mark.parametrize` を使用する
- ABC のみで具象クラスが存在しない場合、テスト用のシンプルな Impl 具象クラスを `tests/helpers.py` に定義する（モックは使わない）

### モック（使用する場合）

- `pytest_mock` を使用する（unittest の mock は使わない。`mocker.Mock` を使う）
- 複数のテストで共有するモックは `tests/conftest.py` にフィクスチャとして定義する
- 特定のテストでのみモックの振る舞いを変更する場合、フィクスチャの戻り値を使って設定を上書きする

### 何をテストするか

- 正常系: 期待通りの入力に対する出力
- 異常系: エラー発生時の例外やメッセージ
- 警告: 設定失敗時などの `RuntimeWarning`
- エッジケース: 境界値やサイズ違いの入力

### 何をテストしないか

- 内部実装の詳細（例: 特定のメソッドが呼ばれたか）
- 初期化時のプロパティ設定などの内部動作

## コーディング規約

### ソースレイアウト

- `src/vrcpilot/`（PEP 561 typed、`py.typed` 同梱）。インポート名は `vrcpilot`（distribution 名からのアンダースコアマッピングは `__init__.py` の `metadata.version` ルックアップで処理）
- テストは `tests/` 配下に置き、pyright strict チェックからは除外されるが、ruff と pre-commit は通る
- バージョンは単一の真実: `pyproject.toml` の `[project].version` が真値で、`vrcpilot.__version__` は `importlib.metadata` 経由で読む。既存の `tests/test_package.py::test_version` がこれを強制しているため、他の場所にバージョンをハードコードしないこと

### カプセル化

- クラスの内部実装の詳細や属性は、基本的にすべて private（`_` prefix）にする
- 外部から参照する必要がある属性のみ public にする
- `__init__` で設定される属性は原則として private とする

例:

```python
class Example:
    def __init__(self, dim: int):
        self._dim = dim  # private
        self._client = SomeClient(dim)  # private
```

## Git 運用

### ブランチ

- `main`: 開発の主軸
- 作業用ブランチの命名規則: `<種別>/<日付>/<内容>`
  - 例: `feature/20260427/auth-flow`、`fix/20260427/version-lookup`
  - 種別: `feature`, `fix`, `refactor`, `docs`, `chore`
- 必ずブランチ上でのみ commit する（`main` に直接 commit しない）
- 作業ブランチは `main` ブランチから分岐する
- `main` へのマージはユーザーが判断・実行する

### コミットメッセージ

`<種別>(<スコープ>): <内容>` の形式に従う。

- 種別: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- スコープ: モジュール名、機能名、ファイル等の単位
- 例: `feat(client): VRChat OAuth クライアントを追加`

## 自走開発フロー

Claude Code が自律的に実装・検証・コミットを行うためのフロー。

### 基本サイクル

1. **要件確認**: 要件定義ドキュメントがあれば読み、実装対象を把握する
2. **作業ブランチ作成**: `main` ブランチから `<種別>/<日付>/<内容>` で作業ブランチを切る
3. **実装**: コードを書く
4. **検証**: `just run`（`just format && just test && just type` 相当）を実行し、すべてパスすることを確認する
5. **コミット**: 検証が通ったらコミットする。細かい単位でコミットし、1 コミットに複数の関心事を混ぜない
6. **繰り返し**: 3-5 を機能単位で繰り返す

### 検証の原則

- **コミット前に必ず検証する**: `just run` がすべてパスすること
- テストが失敗した場合はコミットせず、修正してから再検証する
- 新しいモジュールを追加した場合はテストも書く
- 型チェックエラーを放置しない

### 判断基準

- 要件定義に明記されている内容はそのまま実装する
- 要件定義に記載がない実装の詳細（アルゴリズムの選択、内部設計等）は自分で判断してよい
- 要件定義の未決事項に関わる部分は、合理的なデフォルトで実装し、コミットメッセージに判断理由を記載する
- スコープ外の機能は実装しない

## エージェントチーム戦略

「エージェントチームで行う」という指示があり、具体的な手順が示されていない場合、以下のサイクルに従う。利用可能なエージェントは `.claude/agents/` および本リポジトリで定義されているものを使う。

### 実装サイクル

1. **spec-planner**: 要件を分析し、インターフェース設計と実装計画を策定する（コードは書かない）
2. **spec-driven-implementer → code-quality-reviewer**: 計画に基づき実装し、リファクタリングする。品質が十分になるまで繰り返す
3. **docstring-author**: 最後にコメントやドキュメントの追加・更新が必要か確認する

### 並列化

- 変更規模に応じて並列に動作するエージェント数を増やす
- 並列化の対象: spec-driven-implementer、code-quality-reviewer
- 分割可能なタスク数だけ並列に実行する（独立したモジュールや機能ごとに分割）
