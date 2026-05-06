# vrcpilot

**English** | [日本語](README.ja.md)

[![PyPI](https://img.shields.io/pypi/v/vrcpilot?color=blue)](https://pypi.org/project/vrcpilot/)
[![Python](https://img.shields.io/pypi/pyversions/vrcpilot)](https://pypi.org/project/vrcpilot/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test](https://github.com/MLShukai/vrcpilot/actions/workflows/test.yml/badge.svg)](https://github.com/MLShukai/vrcpilot/actions/workflows/test.yml)
[![Type Check](https://github.com/MLShukai/vrcpilot/actions/workflows/type-check.yaml/badge.svg)](https://github.com/MLShukai/vrcpilot/actions/workflows/type-check.yaml)
[![Format & Lint](https://github.com/MLShukai/vrcpilot/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/MLShukai/vrcpilot/actions/workflows/pre-commit.yml)

Python automation toolkit for VRChat (Windows / Linux). Drives the desktop client end-to-end — launch, focus, capture, OCR, image-template detection, and synthetic input — through both a typed Python API and a `vrcpilot` CLI.

## Features

- **Process control** — launch VRChat through Steam (`vrcpilot.launch`), find PIDs, terminate cleanly.
- **Window control** — focus / unfocus / foreground checks on Win32 and X11 / XWayland.
- **Screen capture** — `Capture` for streaming (mp4 / y4m sinks), `take_screenshot` for one-off shots that round-trip through YAML.
- **OCR** — pluggable `OCREngine` ABC with a default `RapidOCREngine`; `ocr()` returns word-level results in both window-local and desktop-absolute coordinates.
- **Image-template detection** — `TemplateDetectEngine` (OpenCV `TM_CCOEFF_NORMED`) returns coordinate-bearing detections matching the OCR coordinate schema.
- **Synthetic input** — keyboard / mouse via [`pydirectinput`](https://github.com/learncodebygaming/pydirectinput) on Windows and [`inputtino`](https://github.com/games-on-whales/inputtino) (`/dev/uinput`) on Linux, with VRChat focus-guarding.
- **Non-ASCII text injection** — `vrcpilot.clipboard` sends arbitrary Unicode through clipboard + Ctrl+V.
- **CLI front-end** — `vrcpilot launch / screenshot / ocr / detect / mouse / keyboard / paste / capture / ...` with shell completion via `argcomplete`.

## Installation

```bash
# Library + CLI (alpha — needs --pre)
pip install --pre vrcpilot

# With OCR extras
pip install --pre "vrcpilot[ocr]"

# As an isolated CLI tool
uv tool install --prerelease=allow vrcpilot

# Development install
git clone https://github.com/MLShukai/vrcpilot
cd vrcpilot
uv sync --all-extras
```

Python `>= 3.12` is required.

## Platform requirements

### Windows

No additional system packages — `pywin32` and `pydirectinput` are pulled in automatically.

### Linux

An X11 or XWayland session is required. Wayland-native sessions are not supported (`focus()` / `unfocus()` warn and return `False`).

[`inputtino-python`](https://github.com/games-on-whales/inputtino/tree/stable/bindings/python) is built natively from git, so the following system packages are needed before `pip install`:

```bash
sudo apt-get install -y cmake build-essential pkg-config libevdev-dev
sudo usermod -aG input "$USER"   # for /dev/uinput; log out and back in
```

### macOS

Not supported.

## Quick Start (CLI)

The CLI is the fastest way to drive VRChat. The pipeline is: `screenshot` produces a `Screenshot` YAML, and `ocr` / `detect` consume it from stdin or `--screenshot`. Use the `display_pos.bbox` of an OCR/detect result as the click target — never the window-local `pos`.

```bash
# Launch VRChat in desktop mode and wait until it's up
vrcpilot launch --no-vr --screen-width 1280 --screen-height 720 --wait-timeout 60

# Capture a screenshot, run OCR, and save a visualization
vrcpilot screenshot | vrcpilot ocr --viz /tmp/viz.png > /tmp/ocr.yaml

# Or pipe straight into image-template detection
vrcpilot screenshot | vrcpilot detect -q assets/button.png > /tmp/det.yaml

# Move the mouse and click (display-absolute coordinates)
vrcpilot mouse move 1183 514
vrcpilot mouse click left

# Press a key (default duration is 0.1s, the lower bound VRChat reliably accepts)
vrcpilot keyboard press w --duration 1.0

# Paste non-ASCII text (clipboard + Ctrl+V)
vrcpilot paste "こんにちは、VRChat！"

# Shut down (idempotent)
vrcpilot terminate
```

`vrcpilot --help` and `vrcpilot <subcommand> --help` show every flag.

## Quick Start (Python API)

```python
from time import sleep

import vrcpilot

# launch() waits for VRChat's PID (up to wait_timeout, default 30s) and
# returns it. None means the timeout expired before VRChat appeared.
pid = vrcpilot.launch(no_vr=True, screen_width=1280, screen_height=720)
if pid is None:
    raise RuntimeError("VRChat did not start before launch() timed out")
sleep(45)  # extra warm up: shaders, avatar load, network sync

try:
    # One-off screenshot (returns None on a recoverable failure)
    shot = vrcpilot.take_screenshot()
    if shot is None:
        raise RuntimeError("could not capture VRChat")

    # OCR all visible words (uses a cached RapidOCREngine by default)
    result = vrcpilot.ocr(shot)
    for word in result.words:
        print(word.text, result.display_bbox(word))

    # Move the mouse to the first word's centre and click
    if result.words:
        x, y, w, h = result.display_bbox(result.words[0])
        vrcpilot.mouse.move(int(x + w / 2), int(y + h / 2))
        vrcpilot.mouse.click(vrcpilot.MouseButton.LEFT)

    # Press a key
    vrcpilot.keyboard.press(vrcpilot.Key.W, duration=1.0)
finally:
    vrcpilot.terminate()
```

## CLI subcommands

| Subcommand   | Purpose                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------ |
| `launch`     | Start VRChat through Steam. `--no-vr`, `--screen-{width,height}`, `--wait-timeout`.        |
| `pid`        | List running VRChat PIDs (one per line).                                                   |
| `terminate`  | Kill VRChat. Idempotent.                                                                   |
| `focus`      | Bring the VRChat window to the foreground.                                                 |
| `unfocus`    | Send the VRChat window to the bottom of the z-order.                                       |
| `screenshot` | One-shot capture. Emits a `Screenshot` YAML on stdout (PNG file path or inline base64).    |
| `capture`    | Record at a fixed FPS. `-o file.mp4`, or y4m on stdout if no file.                         |
| `mouse`      | `move` / `click` / `scroll` (display-absolute coordinates).                                |
| `keyboard`   | `press` (default `--duration 0.1`).                                                        |
| `paste`      | Inject text via clipboard + Ctrl+V (non-ASCII safe).                                       |
| `ocr`        | Run OCR on a `Screenshot` YAML (stdin pipe or `--screenshot <path>`).                      |
| `detect`     | Image-template detection on a `Screenshot` YAML. `-q query.png`, `--threshold`, `--top-k`. |

## Shell completion

The CLI ships with [`argcomplete`](https://pypi.org/project/argcomplete/) hooks for subcommands, options, and file-path arguments.

For a one-line setup in the development repo, source the bundled bootstrap script:

- bash / Git Bash: `. ./clicomp.sh`
- PowerShell: `. .\CliComp.ps1`

For a manual / system-wide install:

```bash
# bash, Git Bash
eval "$(register-python-argcomplete vrcpilot)"

# PowerShell
register-python-argcomplete --shell powershell vrcpilot | Out-String | Invoke-Expression
```

Add the line above to your `~/.bashrc` or `$PROFILE` to persist it. See [README.ja.md](README.ja.md#shell-completion) for the full breakdown.

## Documentation

- **Tutorial / playbook**: [`docs/usage.md`](docs/usage.md) — task-oriented walkthrough (launch → observe → click → teardown).
- **CLI reference**: [`docs/cli.md`](docs/cli.md) — every subcommand, flag, and exit code. `vrcpilot --help` and `vrcpilot <subcommand> --help` print the same content.
- **Python API reference**: [`docs/python-api.md`](docs/python-api.md) — every symbol exposed at `vrcpilot.<name>`.
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md)
- **Contributing**: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **Japanese README** (legacy, more historical notes): [`README.ja.md`](README.ja.md)

## License

[MIT](LICENSE)
