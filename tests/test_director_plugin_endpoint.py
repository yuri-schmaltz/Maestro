"""Exercise discovery, runtime planner selection and rendering through the real API."""
import json
import uuid

from fastapi.testclient import TestClient


def test_local_skill_is_planned_after_orchestrator_import(tmp_path, monkeypatch):
    import launch
    from services.director import registry
    # Import before installing the manifest: cached built-in maps must not hide it.
    import services.director.orchestrator  # noqa: F401 — freeze-time regression

    skill_id = 'fixture_' + uuid.uuid4().hex
    folder = tmp_path / skill_id
    folder.mkdir()
    (folder / '__init__.py').write_text('')
    (folder / 'plugin.py').write_text(
        'from services.director.planners.demo_skill import DemoSkillPlanner\n'
        f'class FixturePlanner(DemoSkillPlanner):\n    skill_type = {skill_id!r}\n'
    )
    (folder / 'skill_manifest.json').write_text(json.dumps({
        'id': skill_id, 'label': 'Fixture skill', 'active': True,
        'module': skill_id + '.plugin', 'planner_class': 'FixturePlanner',
    }))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, '_local_skill_manifest_dirs', lambda: [tmp_path])
    monkeypatch.setattr(registry, '_SKILL_FACTORIES', dict(registry._SKILL_FACTORIES))
    monkeypatch.setattr(registry, 'DIRECTOR_SKILL_CATALOG', dict(registry.DIRECTOR_SKILL_CATALOG))
    monkeypatch.setattr(registry, 'DIRECTOR_SKILL_ALIASES', dict(registry.DIRECTOR_SKILL_ALIASES))
    monkeypatch.setattr(registry, 'DIRECTOR_SKILL_ORDER', list(registry.DIRECTOR_SKILL_ORDER))
    monkeypatch.setattr(launch, '_ensure_llm_loaded', lambda: None)
    monkeypatch.setitem(launch.wgp.server_config, 'services', {'director_prompt_polish': 'off'})
    with TestClient(launch.api) as client:
        catalog = client.get('/api/v1/director/skills').json()['skills']
        assert any(item['id'] == skill_id and item['active'] for item in catalog)
        response = client.post('/api/v1/director/v2/plan', json={
            'skill_type': skill_id, 'scene_description': 'A ceramic vase in a quiet studio.',
            'director_flags': {'use_llm_refinement': False},
        })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['skill_type'] == skill_id
    assert payload['production_plan']['skill_type'] == skill_id
    assert payload['production_plan']['shots'][0]['skill_type'] == skill_id
    assert len(payload['clip_plans']) == 1
    assert payload['clip_plans'][0]['video_prompt']
