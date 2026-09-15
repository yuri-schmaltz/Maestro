"""Director HTTP extraction contract.

Locks the contract that ``services.director.http.build_skills_router()``
exposes the same catalog endpoint that was previously inline in
launch.py. Asserts:
  * The router mounts at the same path (``/api/v1/director/skills``).
  * The endpoint returns the live skills catalog from the registry.
  * The catalog matches the format the UI consumes
    (``{"skills": [...]}"`` with each entry carrying the ``id``/``label``
    /``desc``/``icon``/``active``/``aliases`` fields).

This is the only Director endpoint extracted in the first cut — see
services/director/http.py for the rationale. Future cuts can be
exercised by adding similar sub-routers + contract tests rather than
moving the whole Director surface at once.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# launch.py lives in app/. Tests run with conftest.py on sys.path, so
# app/ is importable directly.
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


@pytest.fixture(scope="module")
def skills_router():
    # Ensure ``app/`` is on sys.path. conftest.py adds the repo root, but
    # services lives inside app/, so we have to add it explicitly here.
    if str(_APP_DIR) not in sys.path:
        sys.path.insert(0, str(_APP_DIR))
    from services.director.http import build_skills_router
    return build_skills_router()


def test_skills_router_mount_path(skills_router):
    """The catalog endpoint stays at the URL the UI already consumes."""
    paths = [route.path for route in skills_router.routes]
    # FastAPI stores the full path (prefix + route) on the router, so the
    # assertion lives on the post-prefix path rather than the bare suffix.
    assert "/api/v1/director/skills" in paths


def test_skills_router_method(skills_router):
    """Only GET is supported on the catalog endpoint."""
    methods = [route.methods for route in skills_router.routes if route.path == "/api/v1/director/skills"]
    # FastAPI exposes the allowed methods as a frozenset on each route.
    assert any("GET" in m for m in methods)
    assert all("POST" not in m for m in methods)


def test_skills_response_shape(monkeypatch, skills_router):
    """The endpoint returns the documented {"skills": [...]} shape.

    Stub the registry so the test doesn't depend on the live plugin
    discovery machinery; we only care about the wire contract.
    """

    fake_catalog = [
        {
            "id": "music_video",
            "label": "Music Video",
            "desc": "From audio",
            "icon": "music",
            "active": True,
            "aliases": [],
        },
        {
            "id": "short_film",
            "label": "Short Film",
            "desc": "Dialogue scenes",
            "icon": "film",
            "active": True,
            "aliases": [],
        },
    ]

    import services.director.registry as registry_module

    monkeypatch.setattr(registry_module, "list_skills", lambda: fake_catalog)

    # Find the route handler and invoke it directly. Starlette routes
    # expose ``endpoint`` for the underlying async function.
    skills_route = next(r for r in skills_router.routes if r.path == "/api/v1/director/skills")
    import asyncio
    response = asyncio.run(skills_route.endpoint())
    assert "skills" in response
    assert isinstance(response["skills"], list)
    assert len(response["skills"]) == 2
    sample = response["skills"][0]
    for key in ("id", "label", "desc", "icon", "active", "aliases"):
        assert key in sample, f"skill entry missing {key}"
    assert sample["id"] == "music_video"
    assert sample["active"] is True
