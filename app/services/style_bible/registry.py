"""Style Bible registry — file-based load/save/list/delete.

Each Bible is stored as a JSON file at
{app/settings/style_bibles}/{bible_id}.json. We chose JSON over SQLite
because Maestro doesn't have a SQLite store yet, and the Style Bible
set is small (a handful of files per user) so filesystem round-trips
are cheap. This matches the pattern used by app/settings/web_push.json
and other Maestro settings files.

The directory is created on first access by list_bibles() and
save_bible(). Both functions are safe to call before any Bible exists.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional

from .anchors import StyleBible

# Default storage location: app/settings/style_bibles/, next to the
# other settings files. BIBLE_DEFAULT_DIR is exported so tests can
# point it at a tempdir.
APP_ROOT = Path(__file__).resolve().parents[3]  # .../app/services/style_bible/registry.py -> app/
BIBLE_DEFAULT_DIR = APP_ROOT / "settings" / "style_bibles"


def _ensure_dir(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def list_bibles(directory: Path = BIBLE_DEFAULT_DIR) -> list[StyleBible]:
    """Return all Bibles in `directory`, sorted by metadata.title.

    Files that fail to parse (corrupt JSON, missing fields) are
    silently skipped — we never want a corrupt file to break the
    whole registry. The user's ability to fix it (delete the file,
    re-save the Bible) is preserved."""
    _ensure_dir(directory)
    bibles: list[StyleBible] = []
    for path in sorted(directory.glob("*.json")):
        try:
            bibles.append(load_bible_from_path(path))
        except (OSError, ValueError, json.JSONDecodeError):
            # Defensive: a corrupt file should not break the whole
            # registry. The user can delete the file and re-save.
            continue
    bibles.sort(key=lambda b: (b.metadata.title or b.metadata.id).lower())
    return bibles


def load_bible(bible_id: str, directory: Path = BIBLE_DEFAULT_DIR) -> StyleBible:
    """Load a Bible by id. Raises FileNotFoundError if missing, ValueError
    if the file is corrupt."""
    path = _path_for(bible_id, directory)
    if not path.is_file():
        raise FileNotFoundError(f"Style Bible not found: {bible_id} (looked at {path})")
    return load_bible_from_path(path)


def load_bible_from_path(path: Path) -> StyleBible:
    """Load a Bible from an arbitrary file path. Useful for tests and
    for import flows that pass a file the user picked."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return StyleBible.from_dict(data)


def save_bible(
    bible: StyleBible,
    directory: Path = BIBLE_DEFAULT_DIR,
    *,
    overwrite: bool = True,
) -> Path:
    """Persist `bible` to {directory}/{bible.metadata.id}.json.

    By default, overwrites an existing file with the same id. Set
    overwrite=False to refuse to clobber (raises FileExistsError).
    The file is written atomically (write to .tmp, then rename) so
    a crash mid-write does not leave a half-written Bible on disk."""
    if not bible.metadata.id:
        raise ValueError("StyleBible.metadata.id is required to save")
    _ensure_dir(directory)
    target = _path_for(bible.metadata.id, directory)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Style Bible already exists: {target}")
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = bible.to_dict()
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, target)
    return target


def delete_bible(bible_id: str, directory: Path = BIBLE_DEFAULT_DIR) -> bool:
    """Delete the file backing `bible_id`. Returns True if a file was
    removed, False if no such file existed. Refuses to delete a
    Bible whose id starts with a leading underscore (reserved ids
    like __default__)."""
    if bible_id.startswith("_"):
        raise ValueError(f"Refusing to delete reserved Bible id: {bible_id!r}")
    path = _path_for(bible_id, directory)
    if not path.is_file():
        return False
    path.unlink()
    return True


def _path_for(bible_id: str, directory: Path) -> Path:
    # Defense in depth: bible_id becomes part of a filesystem path.
    # Reject anything that could escape the directory (path traversal,
    # absolute paths, NUL bytes, etc.). Valid ids are URL-safe-ish:
    # letters, digits, dash, underscore, dot.
    if not bible_id or "/" in bible_id or "\\" in bible_id or "\x00" in bible_id:
        raise ValueError(f"Invalid Bible id: {bible_id!r}")
    if bible_id in {".", ".."}:
        raise ValueError(f"Invalid Bible id: {bible_id!r}")
    if not all(c.isalnum() or c in "-_." for c in bible_id):
        raise ValueError(
            f"Invalid Bible id: {bible_id!r} (only letters, digits, dash, underscore, dot allowed)"
        )
    return directory / f"{bible_id}.json"


__all__ = [
    "list_bibles",
    "load_bible",
    "load_bible_from_path",
    "save_bible",
    "delete_bible",
    "BIBLE_DEFAULT_DIR",
]
