from __future__ import annotations

from services.director.planners.base import BasePlanner
from services.director.schema import AudioPlan, CameraPlan, ProductionPlan, ShotPlan, SubjectRef


class DemoLocalSkillPlanner(BasePlanner):
    skill_type = "demo_local_skill"

    def plan(self, scene_description: str = "Local plugin skill", **kwargs) -> ProductionPlan:
        subject = SubjectRef(visual_description=(scene_description or "A clean local install scene").strip())
        shot = ShotPlan(
            shot_id="demo_local_001",
            index=0,
            duration_sec=5.0,
            skill_type=self.skill_type,
            scene_goal="Set up the scene with a clear subject and stable framing.",
            subjects_on_screen=[subject],
            spatial_setup="Centered composition with moderate headroom.",
            environment="A clean local plugin setup ready for runtime discovery.",
            visual_style="Minimal and polished.",
            lighting="Soft key light and restrained contrast.",
            mood="Focused and calm.",
            action_beats=["Establish the subject.", "Hold a stable frame."],
            camera_plan=CameraPlan(framing="medium shot", movement="static", movement_intensity="subtle"),
            audio_plan=AudioPlan(mode="ambient_only", ambience="Subtle room tone", timing_anchor="balanced"),
            ending_beat="Hold the scene long enough to confirm framing and mood.",
        )
        return ProductionPlan(
            skill_type=self.skill_type,
            shots=[shot],
            title="Demo Local Skill",
            global_style="Focused and premium",
            total_duration_sec=5.0,
        )
