"""Pytest configuration — adds app/ to sys.path so absolute imports
like `from services.director.cinema import ...` resolve.

Why this lives at the repo root and not in tests/: pytest's
sys.path manipulation order is rootdir-first; a tests/conftest.py
runs AFTER the rootdir conftest has already been processed, which
is too late to influence collection of tests/ siblings. By sitting
at the repo root, this conftest hooks the sys.path before any test
module gets imported.

Maestro's standalone launcher (start_local.sh) `cd`s into app/
and runs `python launch.py`, so its absolute imports (e.g. `from
services import safe_download`) resolve relative to that cwd. We
mirror that behaviour here: any test that needs `launch.py` (or
modules that import it directly) gets `app/` on sys.path so the
same absolute imports keep working.

We also prepend the repo root so `import maestro_cli` (the
pip-installed console-script shim) is importable from the
test-suite.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_APP_DIR = _REPO_ROOT / "app"

for _path in (str(_APP_DIR), str(_REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# Opt-in tests (browser regression, smoke-import subprocess) declare
# heavy dependencies (playwright, a full venv) that are NOT default
# installs. Pytest's ``-m`` filter is applied AFTER collection, so
# the import-time error from a missing module would still abort the
# suite. Detect the missing modules here and drop those test files
# from collection via the standard ``collect_ignore`` hook so
# ``pytest tests/`` works on a fresh checkout.
_OPT_IN_MODULES = {
    "test_application_shell.py": "playwright",
}
for _test_filename, _required_module in _OPT_IN_MODULES.items():
    if importlib.util.find_spec(_required_module) is None:
        _candidate = _REPO_ROOT / "tests" / _test_filename
        if _candidate.exists():
            # Mutating the module-level collect_ignore at import time
            # is the documented way to drop a test from discovery.
            collect_ignore = list(getattr(sys.modules[__name__], "collect_ignore", []))
            if str(_candidate) not in collect_ignore:
                collect_ignore.append(str(_candidate))
            sys.modules[__name__].collect_ignore = collect_ignore
