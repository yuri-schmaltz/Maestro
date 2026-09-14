"""Director skill registry and importable planner loader.

This keeps the project on a simple plugin-like pattern without introducing a
new package manager or external database. Skills remain Python modules that
inherit BasePlanner, but they are discovered through a single registry instead
of being hard-coded in multiple layers.
"""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Iterable

from .schema import DIRECTOR_SKILL_ALIASES, DIRECTOR_SKILL_CATALOG, DIRECTOR_SKILL_ORDER, RETIRED_DIRECTOR_SKILL_TYPES, canonical_skill_type

_SKILL_MODULES = {
    "music_video": ".planners.music_video",
    "short_film": ".planners.short_film",
    "podcast": ".planners.podcast",
    "viral_video": ".planners.viral_video",
    "demo_skill": ".planners.demo_skill",
}

_SKILL_FACTORIES: dict[str, Callable[[], Any]] = {}


def _local_skill_manifest_dirs() -> list[Path]:
    root = Path(__file__).resolve().parent
    candidates = [root / 'plugins', root.parent / 'plugins']
    return [path for path in candidates if path.exists()]


def discover_local_skill_manifests() -> list[dict[str, Any]]:
    """Discover local skill manifests in plugin folders.

    Manifest format example:
    {
      "id": "demo_local_skill",
      "label": "Demo Local Skill",
      "desc": "Description",
      "icon": "film",
      "active": true,
      "aliases": ["local_demo"],
      "module": "services.director.plugins.demo_local_skill",
      "planner_class": "DemoLocalSkillPlanner"
    }
    """
    manifests: list[dict[str, Any]] = []
    for base_dir in _local_skill_manifest_dirs():
        if not base_dir.is_dir():
            continue
        for child in sorted(base_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest_path = child / 'skill_manifest.json'
            if not manifest_path.is_file():
                continue
            try:
                payload = json.loads(manifest_path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            skill_id = str(payload.get('id') or child.name).strip()
            if not skill_id:
                continue
            canonical = canonical_skill_type(skill_id)
            manifest = {
                'id': canonical,
                'label': str(payload.get('label') or canonical.replace('_', ' ').title()),
                'desc': str(payload.get('desc') or ''),
                'icon': str(payload.get('icon') or 'film'),
                'active': bool(payload.get('active', True)),
                'aliases': [str(alias) for alias in payload.get('aliases', []) if isinstance(alias, str)],
                'module': str(payload.get('module') or ''),
                'planner_class': str(payload.get('planner_class') or ''),
            }
            manifests.append(manifest)
    return manifests


def register_skill(skill_type: str, planner_factory: Callable[[], Any], *, label: str | None = None, active: bool = True, aliases: Iterable[str] = ()) -> None:
    """Register a concrete planner factory for a skill.

    The factory is intentionally lightweight: it can return a planner class or
    a planner instance. The registry resolves to the class by convention when it
    is a class object; otherwise, it returns the object itself.
    """
    canonical = canonical_skill_type(skill_type)
    _SKILL_FACTORIES[canonical] = planner_factory
    for alias in aliases:
        _SKILL_FACTORIES[canonical_skill_type(alias)] = planner_factory
    if canonical not in DIRECTOR_SKILL_CATALOG:
        DIRECTOR_SKILL_CATALOG[canonical] = {
            "label": label or canonical.replace("_", " ").title(),
            "desc": "",
            "icon": "music",
            "active": active,
        }


def _resolve_planner_module(skill_type: str) -> Any:
    canonical = canonical_skill_type(skill_type)
    module_path = _SKILL_MODULES.get(canonical)
    if module_path is None:
        raise KeyError(f"Unknown skill type: {skill_type}")
    return import_module(module_path, __package__ or "app.services.director")


def list_skill_types() -> list[str]:
    """Return the public skill order as a stable list."""
    return list(DIRECTOR_SKILL_ORDER)


def _merge_manifest_into_catalog(manifest: dict[str, Any]) -> None:
    skill_id = canonical_skill_type(str(manifest.get('id') or ''))
    if not skill_id:
        return
    # Retired skills are never advertised: a stale manifest with one of
    # these ids must not re-add it to the order or the catalog.
    if skill_id in RETIRED_DIRECTOR_SKILL_TYPES:
        return

    catalog_entry = DIRECTOR_SKILL_CATALOG.setdefault(skill_id, {
        'label': skill_id.replace('_', ' ').title(),
        'desc': '',
        'icon': 'film',
        'active': True,
    })
    catalog_entry.update({
        'label': str(manifest.get('label') or catalog_entry.get('label') or skill_id.replace('_', ' ').title()),
        'desc': str(manifest.get('desc') or catalog_entry.get('desc') or ''),
        'icon': str(manifest.get('icon') or catalog_entry.get('icon') or 'film'),
        'active': bool(manifest.get('active', catalog_entry.get('active', True))),
    })
    if skill_id not in DIRECTOR_SKILL_ORDER:
        DIRECTOR_SKILL_ORDER.append(skill_id)
    for alias in manifest.get('aliases', []):
        alias_name = str(alias).strip()
        if alias_name and alias_name not in DIRECTOR_SKILL_ALIASES:
            DIRECTOR_SKILL_ALIASES[alias_name] = skill_id


def _load_local_skill_manifests() -> None:
    for manifest in discover_local_skill_manifests():
        _merge_manifest_into_catalog(manifest)


def list_skills() -> list[dict[str, Any]]:
    """Return metadata for all skills in the catalog.

    Retired ids (podcast, viral_video, demo skills) are skipped even if a
    stale manifest or a previous merge put them in the order — the picker
    only ever sees music_video + short_film.
    """
    _load_local_skill_manifests()
    items: list[dict[str, Any]] = []
    for skill_type in list_skill_types():
        if skill_type in RETIRED_DIRECTOR_SKILL_TYPES:
            continue
        entry = dict(DIRECTOR_SKILL_CATALOG.get(skill_type, {"label": skill_type.replace("_", " ").title(), "desc": "", "icon": "music", "active": False}))
        entry["id"] = skill_type
        entry["aliases"] = [alias for alias, canonical in DIRECTOR_SKILL_ALIASES.items() if canonical == skill_type]
        items.append(entry)
    return items


def get_skill_manifest(skill_type: str) -> dict[str, Any]:
    canonical = canonical_skill_type(skill_type)
    manifest = dict(DIRECTOR_SKILL_CATALOG.get(canonical, {"label": canonical.replace("_", " ").title(), "desc": "", "icon": "music", "active": False}))
    manifest["id"] = canonical
    manifest["aliases"] = [alias for alias, value in DIRECTOR_SKILL_ALIASES.items() if value == canonical]
    return manifest


def get_skill_planner_class(skill_type: str) -> type:
    """Return the planner class for a given skill type."""
    canonical = canonical_skill_type(skill_type)
    factory = _SKILL_FACTORIES.get(canonical)
    if factory is not None:
        planner = factory()
        return planner if isinstance(planner, type) else planner.__class__

    manifests = discover_local_skill_manifests()
    for manifest in manifests:
        manifest_id = canonical_skill_type(str(manifest.get('id') or ''))
        if manifest_id != canonical:
            continue
        module_name = str(manifest.get('module') or '').strip()
        planner_name = str(manifest.get('planner_class') or '').strip()
        if not module_name or not planner_name:
            raise KeyError(f"Local skill manifest missing module or planner_class for: {canonical}")
        module = import_module(module_name)
        planner_cls = getattr(module, planner_name)
        register_skill(canonical, lambda: planner_cls, label=manifest.get('label'), active=bool(manifest.get('active', True)), aliases=manifest.get('aliases', ()))
        return planner_cls

    module = _resolve_planner_module(canonical)
    planner_name = {
        "music_video": "MusicVideoPlanner",
        "short_film": "ShortFilmPlanner",
        "podcast": "PodcastPlanner",
        "viral_video": "ViralVideoPlanner",
        "demo_skill": "DemoSkillPlanner",
    }.get(canonical)
    if planner_name is None:
        raise KeyError(f"No planner class defined for skill type: {canonical}")
    planner_cls = getattr(module, planner_name)
    register_skill(canonical, lambda: planner_cls, label=get_skill_manifest(canonical)["label"], active=get_skill_manifest(canonical)["active"])
    return planner_cls


def get_skill_planner(skill_type: str, **kwargs: Any):
    """Instantiate the planner for a skill type using the canonical registry."""
    planner_cls = get_skill_planner_class(skill_type)
    return planner_cls(**kwargs)


__all__ = [
    "DIRECTOR_SKILL_ALIASES",
    "DIRECTOR_SKILL_CATALOG",
    "DIRECTOR_SKILL_ORDER",
    "canonical_skill_type",
    "discover_local_skill_manifests",
    "get_skill_manifest",
    "get_skill_planner",
    "get_skill_planner_class",
    "list_skill_types",
    "list_skills",
    "register_skill",
]
