"""Style Bible data classes.

These are the core types lifted from directo_studio M1 (style_bible).
The shapes are deliberately close to Directo's so a future port of
the Directo UI could consume them without translation.

Each anchor is a plain dataclass with `to_dict` / `from_dict` for
serialization. We avoid Pydantic here to keep the module import-light
(no extra dependency for a setting that just needs JSON round-trip).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class CharacterAnchor:
    """Stable visual + wardrobe description for a character.

    Differs from `services.director.schema.CharacterProfile` in that
    this is a pure style anchor (no voice, no narrative role); the
    Director CharacterProfile is a production character, and a Style
    Bible CharacterAnchor is the visual recipe that anchors production
    characters to a consistent look. A production can reference a
    Style Bible character by id and the renderer will pick up the
    anchor text.
    """
    id: str
    name: str
    physical_description: str
    wardrobe: str = ""
    color_palette: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "physical_description": self.physical_description,
            "wardrobe": self.wardrobe,
            "color_palette": list(self.color_palette),
        }

    @staticmethod
    def from_dict(d: dict) -> "CharacterAnchor":
        palette = d.get("color_palette", [])
        if not isinstance(palette, list):
            raise ValueError(f"color_palette must be a list, got {type(palette).__name__}")
        return CharacterAnchor(
            id=d["id"],
            name=d["name"],
            physical_description=d.get("physical_description", ""),
            wardrobe=d.get("wardrobe", ""),
            color_palette=tuple(palette),
        )


@dataclass(frozen=True)
class EnvironmentAnchor:
    """Stable visual description for a recurring location."""
    id: str
    name: str
    description: str
    lighting: str = ""
    color_palette: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "lighting": self.lighting,
            "color_palette": list(self.color_palette),
        }

    @staticmethod
    def from_dict(d: dict) -> "EnvironmentAnchor":
        palette = d.get("color_palette", [])
        if not isinstance(palette, list):
            raise ValueError(f"color_palette must be a list, got {type(palette).__name__}")
        return EnvironmentAnchor(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            lighting=d.get("lighting", ""),
            color_palette=tuple(palette),
        )


@dataclass(frozen=True)
class LoraConfig:
    """Pointer to a LoRA file on disk + recommended weight range.

    Maestro stores LoRAs in app/loras/ as .safetensors files. A Style
    Bible binds a subset of LoRAs to recommended weights so the
    PromptBuilder can include them in the prompt metadata.
    """
    name: str
    file_path: str  # absolute or app-relative path under app/loras/
    weight: float = 1.0
    weight_min: float = 0.0
    weight_max: float = 1.0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "LoraConfig":
        return LoraConfig(
            name=d["name"],
            file_path=d["file_path"],
            weight=float(d.get("weight", 1.0)),
            weight_min=float(d.get("weight_min", 0.0)),
            weight_max=float(d.get("weight_max", 1.0)),
            notes=d.get("notes", ""),
        )


@dataclass(frozen=True)
class BibleMetadata:
    """Identifying + descriptive metadata for a Style Bible."""
    id: str
    title: str
    description: str = ""
    author: str = ""
    created_at: str = ""
    updated_at: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": list(self.tags),
        }

    @staticmethod
    def from_dict(d: dict) -> "BibleMetadata":
        tags = d.get("tags", [])
        if not isinstance(tags, list):
            raise ValueError(f"tags must be a list, got {type(tags).__name__}")
        return BibleMetadata(
            id=d["id"],
            title=d["title"],
            description=d.get("description", ""),
            author=d.get("author", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            tags=tuple(tags),
        )


@dataclass(frozen=True)
class StyleBible:
    """A complete Style Bible. Characters, environments, and LoRA
    configs are referenced by id; the renderer resolves them at
    prompt-build time.

    Two reserved ids:
      - characters["__default__"] is the fallback when a character
        referenced from a Director v2 production is not in the Bible.
      - environments["__default__"] is the fallback for locations.
    """
    metadata: BibleMetadata
    characters: dict[str, CharacterAnchor] = field(default_factory=dict)
    environments: dict[str, EnvironmentAnchor] = field(default_factory=dict)
    loras: dict[str, LoraConfig] = field(default_factory=dict)
    global_style: str = ""
    global_negative: str = ""

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "characters": {k: v.to_dict() for k, v in self.characters.items()},
            "environments": {k: v.to_dict() for k, v in self.environments.items()},
            "loras": {k: v.to_dict() for k, v in self.loras.items()},
            "global_style": self.global_style,
            "global_negative": self.global_negative,
        }

    @staticmethod
    def from_dict(d: dict) -> "StyleBible":
        if "metadata" not in d:
            raise ValueError("StyleBible dict must contain 'metadata' key")
        return StyleBible(
            metadata=BibleMetadata.from_dict(d["metadata"]),
            characters={k: CharacterAnchor.from_dict(v) for k, v in d.get("characters", {}).items()},
            environments={k: EnvironmentAnchor.from_dict(v) for k, v in d.get("environments", {}).items()},
            loras={k: LoraConfig.from_dict(v) for k, v in d.get("loras", {}).items()},
            global_style=d.get("global_style", ""),
            global_negative=d.get("global_negative", ""),
        )
