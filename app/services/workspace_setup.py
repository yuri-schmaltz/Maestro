"""Persistence and validation for per-workspace Project Setup defaults.

This module deliberately has no FastAPI or WanGP dependency. The launch
module supplies the configured output root and maps ``WorkspaceSetupError``
to HTTP responses at the API boundary. Keeping the file contract here makes
it possible to test setup persistence without importing the full generation
server in future callers.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


class WorkspaceSetupError(Exception):
    """Validation or persistence failure with an HTTP-compatible status."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


DEFAULT_PROJECT_SETUP: dict[str, Any] = {
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "seamless": False,
    "auto_mode": False,
    "video_model": "",
    "image_model": "",
    "music_source": "upload",
    "music_model": "",
    "default_image_loras": {},
    "default_video_loras": {},
    "advanced": {},
    "description": "",
    "tags": [],
    "pinned": False,
    "director_skill": "music_video",
    "schema_version": 1,
}

_WORKSPACE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
_STRING_FIELDS = {"aspect_ratio", "resolution", "video_model", "image_model", "music_model", "description"}
_BOOL_FIELDS = {"seamless", "auto_mode", "pinned"}
_LIST_STRING_FIELDS = {"tags"}
_OBJECT_FIELDS = {"default_image_loras", "default_video_loras", "advanced"}


def _safe_join(base: str, name: str) -> str | None:
    """Join one workspace segment without allowing traversal."""
    base_real = os.path.realpath(base)
    candidate = os.path.realpath(os.path.join(base_real, name))
    try:
        if os.path.commonpath((base_real, candidate)) != base_real:
            return None
    except ValueError:
        return None
    return candidate


def setup_path(save_path: str, name: str) -> str | None:
    """Resolve ``<save_path>/<name>/setup.json`` for a valid workspace."""
    if name == "default":
        return None
    if not _WORKSPACE_NAME_RE.match(str(name or "")):
        return None
    workspace_dir = _safe_join(save_path, name)
    if workspace_dir is None:
        return None
    return os.path.join(workspace_dir, "setup.json")


def load_setup(save_path: str, name: str) -> dict[str, Any]:
    """Read and merge setup defaults; malformed or missing files use defaults."""
    path = setup_path(save_path, name)
    if path is None or not os.path.isfile(path):
        return dict(DEFAULT_PROJECT_SETUP)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.loads(handle.read() or "{}")
    except (OSError, ValueError):
        return dict(DEFAULT_PROJECT_SETUP)
    if not isinstance(raw, dict):
        return dict(DEFAULT_PROJECT_SETUP)
    merged = dict(DEFAULT_PROJECT_SETUP)
    for key, value in raw.items():
        if key in merged:
            merged[key] = value
    return merged


def _validate_setup(name: str, setup: dict[str, Any]) -> dict[str, Any]:
    if name == "default":
        raise WorkspaceSetupError(400, "The default workspace cannot hold a custom project setup.")
    if not _WORKSPACE_NAME_RE.match(str(name or "")):
        raise WorkspaceSetupError(400, "Invalid workspace name.")
    if not isinstance(setup, dict):
        raise WorkspaceSetupError(400, "Setup payload must be a JSON object.")

    sanitized: dict[str, Any] = {}
    for key in DEFAULT_PROJECT_SETUP:
        if key not in setup:
            continue
        value = setup[key]
        if key in _STRING_FIELDS:
            if value is None or isinstance(value, str):
                sanitized[key] = value if value is not None else ""
            else:
                raise WorkspaceSetupError(400, f"{key} must be a string or null.")
        elif key in _BOOL_FIELDS:
            if not isinstance(value, bool):
                raise WorkspaceSetupError(400, f"{key} must be a boolean.")
            sanitized[key] = value
        elif key == "music_source":
            if value not in {"upload", "generate"}:
                raise WorkspaceSetupError(400, "music_source must be 'upload' or 'generate'.")
            sanitized[key] = value
        elif key == "director_skill":
            if value not in {"music_video", "short_film"}:
                raise WorkspaceSetupError(400, "director_skill must be 'music_video' or 'short_film'.")
            sanitized[key] = value
        elif key in _LIST_STRING_FIELDS:
            if not isinstance(value, list) or not all(isinstance(tag, str) for tag in value):
                raise WorkspaceSetupError(400, f"{key} must be an array of strings.")
            sanitized[key] = value
        elif key in _OBJECT_FIELDS:
            if value is None or isinstance(value, dict):
                sanitized[key] = value if value is not None else {}
            else:
                raise WorkspaceSetupError(400, f"{key} must be an object.")
        elif key == "schema_version":
            if not isinstance(value, int):
                raise WorkspaceSetupError(400, "schema_version must be an integer.")
            sanitized[key] = value
    sanitized.setdefault("schema_version", DEFAULT_PROJECT_SETUP["schema_version"])
    return sanitized


def persist_setup(save_path: str, name: str, setup: dict[str, Any]) -> dict[str, Any]:
    """Validate and atomically persist one workspace setup."""
    sanitized = _validate_setup(name, setup)
    path = setup_path(save_path, name)
    if path is None:
        raise WorkspaceSetupError(400, "Invalid workspace path.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary_path = path + ".tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(sanitized, handle, indent=2)
        os.replace(temporary_path, path)
    except OSError as exc:
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass
        raise WorkspaceSetupError(500, f"Could not persist setup: {exc}") from exc
    return sanitized
