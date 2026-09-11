"""Prompt Builder — assembles a prompt from a Style Bible + base prompt.

This is the integration point with Director v2 planners/renderers.
A renderer calls PromptBuilder.build(bible, base_prompt, character_ids=...,
environment_id=...) to get a fully-formed prompt that includes the
character's anchor text, the environment's anchor text, the global
style block, and metadata about the LoRAs that should be active.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from .anchors import (
    CharacterAnchor,
    EnvironmentAnchor,
    LoraConfig,
    StyleBible,
)


@dataclass(frozen=True)
class PromptBuildResult:
    """The output of PromptBuilder.build.

    - prompt: the final prompt text to send to the model.
    - negative_prompt: optional negative prompt (combines bible.global_negative
      with anything the caller passed in).
    - active_loras: the LoRAs that should be loaded for this prompt,
      in the order they appear in the Bible.
    - character_anchors: the CharacterAnchor objects that were injected.
    - environment_anchor: the EnvironmentAnchor that was injected (if any).
    """
    prompt: str
    negative_prompt: str = ""
    active_loras: tuple[LoraConfig, ...] = ()
    character_anchors: tuple[CharacterAnchor, ...] = ()
    environment_anchor: Optional[EnvironmentAnchor] = None


class PromptBuilder:
    """Stateless builder. Call .build() to compose a prompt.

    Composition order in the output:
      1. Base prompt (caller-provided)
      2. Character descriptions (one per character_id, in order)
      3. Environment description (if environment_id provided)
      4. Global style block (bible.global_style)
      5. LoRA metadata (appended as a "LoRAs: ..." line so the
         renderer can see at a glance which LoRAs to load; not all
         models consume this — image models with Civitai metadata
         do, video models typically ignore the textual form but
         still need the structured metadata for the pipeline).
    """

    def build(
        self,
        bible: StyleBible,
        base_prompt: str = "",
        *,
        character_ids: Sequence[str] = (),
        environment_id: Optional[str] = None,
        negative_prompt: str = "",
    ) -> PromptBuildResult:
        """Compose a prompt from the bible and the caller's inputs.

        Missing character_ids fall back to "__default__" if the
        Bible defines one, otherwise they are silently skipped
        (the caller is responsible for the prompt being usable
        without those anchors). The same rule applies to
        environment_id.
        """
        # 1. Resolve characters
        anchors: list[CharacterAnchor] = []
        for char_id in character_ids:
            anchor = bible.characters.get(char_id)
            if anchor is None:
                anchor = bible.characters.get("__default__")
            if anchor is not None:
                anchors.append(anchor)

        # 2. Resolve environment
        env_anchor: Optional[EnvironmentAnchor] = None
        if environment_id:
            env_anchor = bible.environments.get(environment_id)
            if env_anchor is None:
                env_anchor = bible.environments.get("__default__")

        # 3. Build the prompt text
        parts: list[str] = []
        if base_prompt:
            parts.append(base_prompt.strip())
        for anchor in anchors:
            anchor_text = self._format_character(anchor)
            if anchor_text:
                parts.append(anchor_text)
        if env_anchor is not None:
            env_text = self._format_environment(env_anchor)
            if env_text:
                parts.append(env_text)
        if bible.global_style:
            parts.append(bible.global_style.strip())

        # 4. Append LoRA metadata line
        active_loras = tuple(bible.loras.values())
        if active_loras:
            lora_line = self._format_lora_metadata(active_loras)
            parts.append(lora_line)

        prompt = "\n".join(p for p in parts if p)
        negative = "\n".join(p for p in (bible.global_negative.strip(), negative_prompt.strip()) if p)

        return PromptBuildResult(
            prompt=prompt,
            negative_prompt=negative,
            active_loras=active_loras,
            character_anchors=tuple(anchors),
            environment_anchor=env_anchor,
        )

    @staticmethod
    def _format_character(anchor: CharacterAnchor) -> str:
        """Format a CharacterAnchor as natural-language prose.

        Example output:
          "Character: a woman in her 30s with short red hair, wearing
          a charcoal blazer and round glasses, palette: muted earth
          tones, soft pastels"
        """
        pieces: list[str] = []
        head = anchor.name or anchor.id
        if head:
            pieces.append(f"Character ({head}):")
        if anchor.physical_description:
            pieces.append(anchor.physical_description.strip())
        if anchor.wardrobe:
            pieces.append(f"wearing {anchor.wardrobe.strip()}")
        if anchor.color_palette:
            palette = ", ".join(anchor.color_palette)
            pieces.append(f"palette: {palette}")
        return ", ".join(p if p.endswith(",") or "," in p else p for p in pieces)

    @staticmethod
    def _format_environment(anchor: EnvironmentAnchor) -> str:
        pieces: list[str] = []
        head = anchor.name or anchor.id
        if head:
            pieces.append(f"Environment ({head}):")
        if anchor.description:
            pieces.append(anchor.description.strip())
        if anchor.lighting:
            pieces.append(f"lighting: {anchor.lighting.strip()}")
        if anchor.color_palette:
            palette = ", ".join(anchor.color_palette)
            pieces.append(f"palette: {palette}")
        return ", ".join(pieces)

    @staticmethod
    def _format_lora_metadata(loras: Sequence[LoraConfig]) -> str:
        names = [f"{l.name}@{l.weight:g}" for l in loras]
        return "LoRAs: " + ", ".join(names)


__all__ = ["PromptBuilder", "PromptBuildResult"]
