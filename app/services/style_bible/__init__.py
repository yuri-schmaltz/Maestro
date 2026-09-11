"""
Style Bible — Director v2 character/environment anchor abstraction.

Pattern lifted from directo_studio M1 (style_bible). Directo's Style
Bible is a structured set of:
  - CharacterAnchor: stable visual + wardrobe description for a
    character across shots.
  - EnvironmentAnchor: stable visual description for a recurring
    location.
  - LoraConfig: pointer to a LoRA file on disk + recommended weight
    range. Different from Directo's: Maestro has its own LoRA system
    under app/loras/, so LoraConfig points to a local file path
    instead of an external provider.
  - PromptBuilder: takes the anchors + a base prompt and returns a
    fully-formed prompt with the anchors injected as natural-language
    descriptions. This is the integration point with Director v2:
    planners/renderers can call PromptBuilder.build() to enrich a
    ShotPlan's prompt with the active Style Bible before sending it
    to the model.

Differences from Directo (deliberate, documented):
  - Directo stores Bibles in SQLite via the `vault` module. Maestro
    has no SQLite today. We store as JSON files in
    app/settings/style_bibles/ (same pattern as the existing
    app/settings/web_push.json).
  - Directo has LoRA configs that point to provider names (ComfyUI,
    A1111, etc.). Maestro has local file paths under app/loras/,
    so LoraConfig uses absolute file paths.
  - Directo also supports YAML; we do too via PyYAML if available,
    but fall back to JSON-only when PyYAML is missing (so the module
    works on minimal installs).

This is a backend-only module: the load/save/build API is complete
and stable, but the UI is out of scope for this slice (a follow-up
slice would add a Configurations tab section that creates/edits
Bibles and binds them to a Director v2 run).
"""
from __future__ import annotations

from .anchors import (
    CharacterAnchor,
    EnvironmentAnchor,
    LoraConfig,
    StyleBible,
    BibleMetadata,
)
from .builder import PromptBuilder, PromptBuildResult
from .registry import (
    list_bibles,
    load_bible,
    load_bible_from_path,
    save_bible,
    delete_bible,
    BIBLE_DEFAULT_DIR,
)

__all__ = [
    "CharacterAnchor",
    "EnvironmentAnchor",
    "LoraConfig",
    "StyleBible",
    "BibleMetadata",
    "PromptBuilder",
    "PromptBuildResult",
    "list_bibles",
    "load_bible",
    "load_bible_from_path",
    "save_bible",
    "delete_bible",
    "BIBLE_DEFAULT_DIR",
]
