---
name: Pyright baseline tracking
description: This repo runs pyright strict but ships with a small set of pre-existing errors from untyped third-party libs (Xlib, etc.). New work must not increase the count.
type: project
---

`just type` produces a non-zero baseline of pyright strict errors that cannot
trivially be eliminated because the offending third-party libraries have no
type stubs. As of 2026-04-29 the baseline is **12 errors**, all in `_x11.py`,
`capture.py` (the `find_vrchat_window` re-export), and `window.py` (same).

**Why:** the user's quality bar is "don't make it worse" — adding new errors is
a regression even when the errors are about an untyped lib. Adding stubs is out
of scope for most feature work.

**How to apply:**

- Before adding new code that touches an untyped library (e.g. `windows_capture`),
  capture the baseline count with `just type 2>&1 | tail -3` on a clean tree
  (or `git stash && just type; git stash pop`).
- After your change, the count must equal the baseline. Use targeted
  `# pyright: ignore[<rule>]` comments at the specific lines that trip,
  not blanket `# type: ignore` (the `check blanket type ignore` pre-commit
  hook will reject those).
- For an import line that exceeds 88 chars with the trailing
  `# pyright: ignore[...]` comment, ruff-format will wrap the import to
  multi-line which moves the comment off the offending line. Workaround:
  `import foo as _foo` on one line, then alias the symbol on the next
  (`Bar = _foo.Bar`) so each line stays short enough to keep its ignore.
