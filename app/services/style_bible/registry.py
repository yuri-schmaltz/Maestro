"""Style Bible registry — file-based load/save/list/delete.

Each Bible is stored as a JSON file at
{app/settings/style_bibles}/{bible_id}.json (or .yaml / .yml if the
caller asks). We chose JSON over SQLite because Maestro doesn't have
a SQLite store yet, and the Style Bible set is small (a handful of
files per user) so filesystem round-trips are cheap. This matches
the pattern used by app/settings/web_push.json and other Maestro
settings files.

YAML support is optional: when PyYAML is installed we round-trip
through it; when it isn't, list_bibles/load_bible_from_path still
work on JSON files (and silently skip YAML ones). save_bible with
fmt="yaml" raises ImportError if PyYAML is missing — callers that
care about YAML should declare the dependency.

The directory is created on first access by list_bibles() and
save_bible(). Both functions are safe to call before any Bible exists.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Literal, Optional

from .anchors import StyleBible

# Default storage location: app/settings/style_bibles/, next to the
# other settings files. BIBLE_DEFAULT_DIR is exported so tests can
# point it at a tempdir.
APP_ROOT = Path(__file__).resolve().parents[3]  # .../app/services/style_bible/registry.py -> app/
BIBLE_DEFAULT_DIR = APP_ROOT / "settings" / "style_bibles"

# Format literals. ``json`` is the default and always available;
# ``yaml`` requires PyYAML at runtime.
Format = Literal["json", "yaml"]

# Optional PyYAML import. We try once at module import and cache the
# result so we don't pay the import cost on every load. When PyYAML
# is missing, YAML support is disabled and only JSON works.
_yaml = None
_yaml_import_error: Optional[str] = None
try:
    import yaml as _yaml  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover — exercised only without PyYAML
    _yaml_import_error = repr(exc)


def _ensure_dir(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def yaml_available() -> bool:
    """True if PyYAML is installed and YAML load/save will work."""
    return _yaml is not None


def yaml_import_error() -> Optional[str]:
    """If PyYAML is missing, return the import error string so callers
    can surface a useful message. None when YAML is available."""
    return _yaml_import_error


def list_bibles(directory: Path = BIBLE_DEFAULT_DIR) -> list[StyleBible]:
    """Return all Bibles in `directory`, sorted by metadata.title.

    Globs for both .json and (if PyYAML is installed) .yaml/.yml.
    Files that fail to parse (corrupt JSON/YAML, missing fields) are
    silently skipped — we never want a corrupt file to break the
    whole registry. The user's ability to fix it (delete the file,
    re-save the Bible) is preserved."""
    _ensure_dir(directory)
    bibles: list[StyleBible] = []
    patterns = ["*.json"]
    if _yaml is not None:
        patterns.extend(["*.yaml", "*.yml"])
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(directory.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            try:
                bibles.append(load_bible_from_path(path))
            except (OSError, ValueError, json.JSONDecodeError):
                # Defensive: a corrupt file should not break the whole
                # registry. The user can delete the file and re-save.
                continue
            except Exception:
                # PyYAML raises its own exception type for malformed YAML;
                # catch the base Exception to be safe (we don't want to
                # import yaml just to catch yaml.YAMLError here).
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
    for import flows that pass a file the user picked. The file
    extension selects the parser: .yaml/.yml need PyYAML; .json always
    works."""
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in (".yaml", ".yml"):
        if _yaml is None:
            raise ImportError(
                f"PyYAML is required to load {path} but is not installed"
                + (f" ({_yaml_import_error})" if _yaml_import_error else "")
            )
        data = _yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level, got {type(data).__name__}")
    return StyleBible.from_dict(data)


def save_bible(
    bible: StyleBible,
    directory: Path = BIBLE_DEFAULT_DIR,
    *,
    overwrite: bool = True,
    fmt: Format = "json",
) -> Path:
    """Persist `bible` to {directory}/{bible.metadata.id}.{fmt}.

    By default, overwrites an existing file with the same id. Set
    overwrite=False to refuse to clobber (raises FileExistsError).
    The file is written atomically (write to .tmp, then rename) so
    a crash mid-write does not leave a half-written Bible on disk.

    When fmt='yaml' the file extension is .yaml; when fmt='json' it
    is .json. Mixed-format directories are fine (list_bibles picks
    up both). YAML requires PyYAML — calling with fmt='yaml' when
    PyYAML is missing raises ImportError."""
    if not bible.metadata.id:
        raise ValueError("StyleBible.metadata.id is required to save")
    if fmt not in ("json", "yaml"):
        raise ValueError(f"Unknown fmt: {fmt!r} (expected 'json' or 'yaml')")
    if fmt == "yaml" and _yaml is None:
        raise ImportError(
            "PyYAML is required to save Bibles as YAML but is not installed."
            f" {_yaml_import_error or 'pip install pyyaml'}."
        )
    _ensure_dir(directory)
    extension = "yaml" if fmt == "yaml" else "json"
    target = _path_for(bible.metadata.id, directory, extension=extension)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Style Bible already exists: {target}")
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = bible.to_dict()
    if fmt == "yaml":
        assert _yaml is not None
        with open(tmp, "w", encoding="utf-8") as fh:
            _yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    else:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    os.replace(tmp, target)
    return target


def delete_bible(bible_id: str, directory: Path = BIBLE_DEFAULT_DIR) -> bool:
    """Delete the file backing `bible_id` (any supported extension).

    Returns True if a file was removed, False if no such file existed.
    Refuses to delete a Bible whose id starts with a leading underscore
    (reserved ids like __default__)."""
    if bible_id.startswith("_"):
        raise ValueError(f"Refusing to delete reserved Bible id: {bible_id!r}")
    removed = False
    for extension in ("json", "yaml", "yml"):
        path = _path_for(bible_id, directory, extension=extension)
        if path.is_file():
            path.unlink()
            removed = True
    return removed


def _path_for(bible_id: str, directory: Path, *, extension: str = "json") -> Path:
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
    return directory / f"{bible_id}.{extension}"


__all__ = [
    "list_bibles",
    "load_bible",
    "load_bible_from_path",
    "save_bible",
    "delete_bible",
    "yaml_available",
    "yaml_import_error",
    "BIBLE_DEFAULT_DIR",
]
