"""Top-level entry point shim for the `maestro` console script.

Why this exists: pip-generated console scripts do a literal
``from <module> import <attr>`` at the top of the wrapper. With
``app.cli:main`` as the entry point, the wrapper does
``from app.cli import main``, which fails because the repo root
isn't on sys.path when the wrapper runs.

We can't fix this by adding app/__init__.py — Maestro's standalone
launcher (start_local.sh) imports ``launch`` (not ``app.launch``)
from the ``app/`` cwd, and adding ``__init__.py`` breaks that
because Python then refuses to import a top-level module named
``launch`` when a package named ``app`` is on the path.

The fix: put the entry point module at the REPO ROOT, where it can
do ``from app.cli import main`` itself with the repo root already
on sys.path (because the wrapper script is at the repo root). This
file is small and exists only to bridge the pip console-script
contract to the real CLI module.

Run directly: ``python maestro_cli.py status``
Via pip console script: ``maestro status`` (after `pip install -e .`)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path (it normally is — this file lives
# at maestro_cli/__init__.py, so .parent.parent is the repo root).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.cli import main  # noqa: E402 — sys.path injection above


if __name__ == "__main__":
    sys.exit(main())
