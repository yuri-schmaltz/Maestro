"""Director HTTP endpoint surface — first cut of the Director HTTP extraction.

This module owns the Director endpoints that don't depend on per-request
generation state in launch.py. The first cut is intentionally narrow:

  * GET  /api/v1/director/skills              — registry catalog

The other ~39 Director endpoints (v2 plan + cancel, pipeline lifecycle,
queue, repair, rerun, take selection, cinema evaluation, script reading,
dialogue scene planning, etc.) still live in launch.py because each
depends on the global ``api`` router plus the per-request LLM/GPU state
hooks (``_ensure_llm_loaded``, ``_generation_request_uses_serial_auto_planner``,
the ``_jobs`` registry, the cancellation event bus, the request-scoped
model def cache, etc.). Moving them all at once risks breaking the
request lifecycle; the rest is left for incremental follow-up PRs.

Mounting pattern in launch.py::

    from services.director.http import build_skills_router
    api.include_router(build_skills_router())
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)


def build_skills_router() -> APIRouter:
    """Build a Director sub-router with the registry catalog surface only."""
    router = APIRouter(prefix="/api/v1/director", tags=["director"])

    @router.get("/skills")
    async def director_skills() -> dict:
        """Expose the Director skill catalog from a single registry."""
        from services.director.registry import list_skills
        return {"skills": list_skills()}

    return router
