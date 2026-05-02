---
name: submodule attribute collision in cli package
description: Re-exports on cli/__init__.py that share names with subcommand submodules get clobbered by submodule load; rebind explicitly after _main import
type: feedback
---

When `vrcpilot/cli/__init__.py` re-exports a symbol whose name matches a submodule (e.g. window's `focus`/`unfocus` functions vs `cli/focus.py` / `cli/unfocus.py` subcommand modules), CPython's import machinery silently overwrites the parent's attribute with the submodule object during `import vrcpilot.cli.focus`. After `_main.py` loads (which imports every subcommand submodule), `vrcpilot.cli.focus` will be the submodule, not the function — even if `__init__.py` did `from vrcpilot.window import focus` first.

**Why:** CPython's `_find_and_load` calls `setattr(parent, child, module)` unconditionally after loading a submodule. The order in `__init__.py` does not matter — what matters is whether anything runs `import vrcpilot.cli.<name>` (or `from . import <name>`) AFTER the re-export.

**How to apply:** In `cli/__init__.py`, re-bind clashing names AFTER `from ._main import main` using a private alias + assignment:

```python
from vrcpilot.window import focus as _window_focus, unfocus as _window_unfocus
from ._main import main as main  # triggers submodule loads that clobber cli.focus/cli.unfocus
focus = _window_focus
unfocus = _window_unfocus
```

The plain `from X import focus` re-export pattern at the top of `__init__.py` does NOT survive `_main.py` loading — ruff/isort will reorder it and even if it stays put, the submodule import overwrites it. Tests that only `mocker.patch("vrcpilot.cli.focus")` will still pass either way (the patch overwrites whatever's there) but real `vrcpilot focus` invocation will crash with TypeError trying to call the submodule.
