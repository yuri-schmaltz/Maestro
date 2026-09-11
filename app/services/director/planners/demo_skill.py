"""Demo Director skill used to validate the importable planner flow.

This keeps the architecture honest: a new skill can be added as a regular module
and registered in the catalog without touching the main orchestrator or UI list.
"""

from __future__ import annotations

from typing import Optional

from ..schema import (
    AudioPlan,
    CameraPlan,
    ProductionPlan,
    ReferenceAssets,
    ShotPlan,
    SubjectRef,
)
from .base import BasePlanner


class DemoSkillPlanner(BasePlanner):
    skill_type = 'demo_skill'

    def plan(
        self,
        scene_description: str,
        audio_path: Optional[str] = None,
        reference_image_path: Optional[str] = None,
        **kwargs,
    ) -> ProductionPlan:
        subject = SubjectRef(
            visual_description=(scene_description or 'A clean composition with one focused subject').strip(),
        )
        shot = ShotPlan(
            shot_id='shot_001',
            index=0,
            duration_sec=6.0,
            skill_type=self.skill_type,
            scene_goal='Introduce the subject in a clear, focused frame.',
            subjects_on_screen=[subject],
            spatial_setup='Centered composition with generous negative space.',
            environment='Studio-like environment with subtle detail.',
            visual_style='Minimal cinematic polish.',
            lighting='Soft directional lighting with a clean background.',
            mood='Calm and confident.',
            action_beats=['Frame the subject clearly.', 'Hold a simple and stable motion profile.'],
            camera_plan=CameraPlan(framing='medium shot', movement='static', movement_intensity='subtle'),
            audio_plan=AudioPlan(mode='ambient_only', ambience='Light ambient texture', timing_anchor='balanced'),
            ending_beat='Hold the frame long enough to establish presence.',
        )

        return ProductionPlan(
            skill_type=self.skill_type,
            shots=[shot],
            title='Demo Director skill',
            global_style='Simple, premium, focused',
            total_duration_sec=6.0,
            reference_assets=ReferenceAssets(
                start_image=None,
                audio=None,
            ),
            continuity_notes=['Demo skill validates the importable planner contract.'],
        )
