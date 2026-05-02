"""Run every e2e scenario in this directory and aggregate the results.

Discovers sibling ``*.py`` files (excluding underscore-prefixed helpers
and this script itself), launches each as a subprocess, and prints a
final ``PASS: all`` / ``FAIL: all: <names>`` line plus a non-zero exit
code if any scenario failed. Invoked by ``just e2e-test`` when no
scenario name is given.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_NAME = "all"


def _discover() -> list[Path]:
    self_name = Path(__file__).name
    return [
        path
        for path in sorted(_HERE.glob("*.py"))
        if not path.name.startswith("_") and path.name != self_name
    ]


def main() -> int:
    scripts = _discover()
    if not scripts:
        print(f"FAIL: {_NAME}: no scenarios found in {_HERE}", flush=True)
        return 1

    print(f"=== running {len(scripts)} scenarios ===", flush=True)
    failures: list[str] = []
    for path in scripts:
        name = path.stem
        print(f"\n--- {name} ---", flush=True)
        result = subprocess.run([sys.executable, str(path)], check=False)
        if result.returncode != 0:
            failures.append(name)

    print("\n=== summary ===", flush=True)
    print(f"total: {len(scripts)}", flush=True)
    print(f"failed: {len(failures)}", flush=True)
    if failures:
        print(f"FAIL: {_NAME}: {', '.join(failures)}", flush=True)
        return 1
    print(f"PASS: {_NAME}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
