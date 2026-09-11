import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / 'app'
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from services.director.registry import get_skill_planner_class, list_skills


def test_demo_skill_is_registered_and_plan_builds():
    skill_ids = {entry['id'] for entry in list_skills()}
    assert 'demo_skill' in skill_ids

    planner_cls = get_skill_planner_class('demo_skill')
    planner = planner_cls()
    plan = planner.plan(scene_description='A single subject in a clean studio environment.')

    assert plan.skill_type == 'demo_skill'
    assert len(plan.shots) == 1
    assert plan.shots[0].scene_goal


def test_plugin_manifest_can_be_discovered_and_loaded():
    skill_id = f'demo_local_skill_{uuid.uuid4().hex[:8]}'
    manifest_dir = Path(__file__).resolve().parents[1] / 'app' / 'services' / 'director' / 'plugins'
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / skill_id / 'skill_manifest.json'
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        f'''{{
  "id": "{skill_id}",
  "label": "Demo Local Skill",
  "desc": "Local plugin skill used for manifest discovery tests.",
  "icon": "film",
  "active": true,
  "aliases": ["local_demo"],
  "module": "services.director.plugins.{skill_id}.plugin",
  "planner_class": "DemoLocalSkillPlanner"
}}
''',
        encoding='utf-8',
    )

    plugin_file = manifest_path.parent / 'plugin.py'
    plugin_file.write_text(
        f'''from services.director.planners.base import BasePlanner
from services.director.schema import AudioPlan, CameraPlan, ProductionPlan, ShotPlan, SubjectRef


class DemoLocalSkillPlanner(BasePlanner):
    skill_type = "{skill_id}"

    def plan(self, scene_description: str = "Local plugin skill", **kwargs):
        subject = SubjectRef(visual_description=scene_description)
        shot = ShotPlan(
            shot_id="{skill_id}_001",
            index=0,
            duration_sec=4.0,
            skill_type=self.skill_type,
            scene_goal="Introduce the subject clearly.",
            subjects_on_screen=[subject],
            spatial_setup="Single subject framing.",
            environment="Local plugin scene.",
            visual_style="Clean and direct.",
            lighting="Soft studio light.",
            mood="Focused.",
            action_beats=["Set the subject in frame."],
            camera_plan=CameraPlan(framing="medium shot", movement="static", movement_intensity="subtle"),
            audio_plan=AudioPlan(mode="ambient_only", ambience="Minimal tone", timing_anchor="balanced"),
            ending_beat="Hold on the frame.",
        )
        return ProductionPlan(skill_type=self.skill_type, shots=[shot], title="Local plugin demo", global_style="Focused", total_duration_sec=4.0)
''',
        encoding='utf-8',
    )

    try:
        from services.director.registry import discover_local_skill_manifests, get_skill_planner_class

        discovered = discover_local_skill_manifests()
        assert any(item.get('id') == skill_id for item in discovered)

        planner_cls = get_skill_planner_class(skill_id)
        assert planner_cls.__name__ == 'DemoLocalSkillPlanner'
        plan = planner_cls().plan(scene_description='A plugin skill found from a manifest file.')
        assert plan.skill_type == skill_id
    finally:
        for path in [manifest_path, plugin_file]:
            if path.exists():
                path.unlink()
        if manifest_path.parent.exists() and not any(manifest_path.parent.iterdir()):
            manifest_path.parent.rmdir()
