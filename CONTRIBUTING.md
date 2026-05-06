# Contributing to vrcpilot

Thanks for your interest in contributing! `vrcpilot` automates the desktop client and in-world interactions of VRChat from Python. This document covers what we expect from a pull request and how to set up a development environment.

## Scope

`vrcpilot` is intentionally narrow:

- **In scope**: launching / terminating VRChat, window focus, screen capture, OCR, image-template detection, synthetic keyboard / mouse input, clipboard-based text injection.
- **Out of scope**: anything that requires reverse-engineering the VRChat network protocol, modifying the VRChat client binary, distributing client assets, or automating account-level destructive actions (logout, friend management, avatar uploads, purchases). Please do not file PRs in those directions.

When automating gameplay, **be considerate of other players**. Public instances are shared spaces. The `tests/e2e/` scenarios deliberately stay within non-destructive operations and we expect contributions to follow the same posture.

## Development setup

We use [uv](https://docs.astral.sh/uv/) for environment and dependency management, and [just](https://just.systems/) as a task runner. Python 3.12 or later is required.

```bash
just setup       # uv venv + uv sync --all-extras + pre-commit install
```

If you are not using `just`, the equivalent is:

```bash
uv venv
uv sync --all-extras
uv run pre-commit install
```

### Platform notes

- **Windows**: no extra system packages; `pywin32` and `pydirectinput` are installed automatically.

- **Linux**: `inputtino-python` is built natively from git. Install build prerequisites first:

  ```bash
  sudo apt-get install -y cmake build-essential pkg-config libevdev-dev
  sudo usermod -aG input "$USER"   # for /dev/uinput access; log out and back in
  ```

  An X11 or XWayland session is required for window-related code. Wayland-native sessions are not supported.

- **macOS**: not supported.

## Project layout

- Source: [`src/vrcpilot/`](src/vrcpilot/) — a typed package (`py.typed`).
- Tests: [`tests/`](tests/) mirror `src/vrcpilot/` one-to-one (`src/vrcpilot/foo.py` ↔ `tests/vrcpilot/test_foo.py`). End-to-end scenarios live in [`tests/e2e/`](tests/e2e/).
- CLI entry point: `vrcpilot.cli:main`, dispatched through [`src/vrcpilot/cli/__init__.py`](src/vrcpilot/cli/__init__.py).

## Branching and commits

- Branch off `main` using `<type>/<YYYYMMDD>/<topic>`, for example `feat/20260506/world-search` or `fix/20260506/launch-timeout`.
- Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Commit messages follow `<type>(<scope>): <subject>` (Conventional Commits flavor). Keep one logical change per commit.
- Do not commit directly to `main`; merging is done through pull requests.

## Verifying changes

Every PR is expected to pass:

```bash
just run         # format + test + type check (alias for the three below)
```

If you prefer to run them individually:

```bash
just format      # pre-commit (ruff fix + format, mdformat, codespell, ...)
just test        # pytest -v --cov
just type        # pyright (strict on src/, tests/ excluded)
```

The CI matrix runs on Linux and Windows across Python 3.12 / 3.13 / 3.14. New code must work on both platforms or be guarded with a clear `sys.platform` check.

### Tests

- Mirror the source layout: `src/vrcpilot/foo.py` ↔ `tests/vrcpilot/test_foo.py`. Backend-split modules (`window/win32.py`, `window/x11.py`) get split tests too.
- Prefer real objects and real I/O; reach for mocks only at true external boundaries (network APIs, hard-to-reproduce kernel features). For ABC-only modules, define a tiny concrete `Impl` in `tests/helpers.py` rather than mocking.
- For tests that depend on a platform or display, `pytest.skip(..., allow_module_level=True)` at the top of the file (before any imports that would fail at collection time).

### End-to-end scenarios

Files under [`tests/e2e/`](tests/e2e/) are scenario scripts that drive a real VRChat instance. They are excluded from `pytest` collection. Run them via:

```bash
just e2e-test <NAME>   # e.g. just e2e-test focus_unfocus
```

Requirements: Steam must already be running, VRChat must be installed, and on Linux the desktop session must be X11 or XWayland.

## Pull requests

- Title: `<type>(<scope>): <subject>` mirroring the commit convention.
- Description: follow [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).
- One PR per concern — please do not bundle unrelated changes.
- Confirm `just run` passes locally before requesting review.

## Reporting issues

- Bug reports and feature requests: open an issue using the templates under [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/).
- Security vulnerabilities: please use [GitHub Security Advisories](https://github.com/MLShukai/vrcpilot/security/advisories/new) instead of a public issue.

## License

By contributing, you agree that your contributions will be licensed under the MIT License (see [`LICENSE`](LICENSE)).
