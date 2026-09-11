"""Integration hook: run the cinema pass inside validate_shot_plan.

Pattern: validate_shot_plan is the canonical pre-render validator.
We add a cinema pass as a soft post-step that appends warnings to
the ValidationResult.warnings list. We never add errors — the cinema
pass is advisory by design (a Director v2 user can see the warnings
in the dashboard and decide whether to revise the shot).
"""
from __future__ import annotations

from typing import Optional

from ..schema import ProductionPlan, ShotPlan
from . import CinemaEvaluation, evaluate_shot


def collect_shot_text(shot: ShotPlan, plan: Optional[ProductionPlan] = None) -> dict[str, object]:
    """Extract the textual fields a cinema pass needs from a ShotPlan.

    Returns a dict with scene_goal, environment, lighting, wardrobe, props.
    The wardrobe is taken from subjects_on_screen (the per-shot
    wardrobe) and falls back to the production's character wardrobe
    if the shot references a character by id and no per-shot wardrobe
    is set. Props are extracted from action_beats + dialogue_beats
    by simple keyword matching (we don't have a structured props
    field on ShotPlan today).
    """
    wardrobe_parts: list[str] = []
    for subj in shot.subjects_on_screen or []:
        if subj.wardrobe:
            wardrobe_parts.append(subj.wardrobe)
        elif subj.character_id and plan is not None:
            char = plan.get_character(subj.character_id)
            if char and char.wardrobe:
                wardrobe_parts.append(char.wardrobe)

    # No structured props field on ShotPlan today. Treat action_beats
    # as the best proxy — props usually appear in the action line.
    props = tuple(beat for beat in (shot.action_beats or []) if beat)

    return {
        "scene_goal": shot.scene_goal or "",
        "environment": shot.environment or "",
        "lighting": shot.lighting or "",
        "wardrobe": " ".join(wardrobe_parts),
        "props": props,
    }


def run_cinema_pass(shot: ShotPlan, plan: Optional[ProductionPlan] = None) -> CinemaEvaluation:
    """Run the cinema pass on a ShotPlan. Returns the full evaluation
    including info-level hits; the integration in shot_validator
    filters to warnings only when appending to ValidationResult."""
    text = collect_shot_text(shot, plan)
    return evaluate_shot(
        scene_goal=str(text["scene_goal"]),
        environment=str(text["environment"]),
        lighting=str(text["lighting"]),
        wardrobe=str(text["wardrobe"]),
        props=text["props"],  # type: ignore[arg-type]
    )


__all__ = ["collect_shot_text", "run_cinema_pass"]
