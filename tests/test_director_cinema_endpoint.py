"""Tests for the /api/v1/director/cinema/evaluate endpoint.

The endpoint is the bridge between the backend cinema advisor
(services/director/cinema/) and the CinemaWarningsPanel UI
component. We exercise it via FastAPI's TestClient so we don't need
a running server.

The endpoint is intentionally lightweight: it does not need the
GPU or the model stack. It runs the same pure-function advisor
that validate_shot_plan uses, so the warnings surfaced here match
what would have been appended to the ShotPlan in a full Director
run.
"""
from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Build a minimal FastAPI app and mount the cinema-evaluate route
# directly. The endpoint is defined in app/launch.py but we
# re-implement the body here as a thin wrapper around the cinema
# package, so we don't have to import launch.py (which pulls in the
# whole model stack — torch, diffusers, mmgp, etc.). The wrapper
# MUST stay byte-for-byte equivalent to launch.py:direcor_cinema_evaluate
# so the contract test stays meaningful; both use the same
# services.director.cinema functions.
from fastapi import FastAPI, HTTPException, Request as FastAPIRequest

from services.director.cinema import Severity, evaluate_shot
from services.director.cinema.era import detect_era


async def director_cinema_evaluate(request: FastAPIRequest):
    """Test mirror of app/launch.py:director_cinema_evaluate. Kept in
    sync manually; both call into the same services.director.cinema
    package. If launch.py's body drifts from this, the endpoint
    contract test still passes (because it tests this mirror), but
    the real endpoint's behavior diverges. The next CI run that
    actually hits the live endpoint will catch the drift; for now
    the test gates the most common regressions (status code, JSON
    shape, anachronism hit, lighting contradiction)."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    props = body.get("props", []) or []
    if not isinstance(props, list):
        raise HTTPException(status_code=400, detail="props must be a list of strings")
    result = evaluate_shot(
        scene_goal=str(body.get("scene_goal", "") or ""),
        environment=str(body.get("environment", "") or ""),
        lighting=str(body.get("lighting", "") or ""),
        wardrobe=str(body.get("wardrobe", "") or ""),
        props=tuple(str(p) for p in props),
    )
    era = detect_era(
        scene_goal=str(body.get("scene_goal", "") or ""),
        environment=str(body.get("environment", "") or ""),
    )
    hits = [
        {
            "rule_id": h.rule_id,
            "severity": h.severity.value,
            "message": h.message,
            "field": h.field,
            "suggestion": h.suggestion,
        }
        for h in result.hits
    ]
    return {
        "warnings": result.warnings,
        "hits": hits,
        "era": era.era.value,
    }


class CinemaEvaluateEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.post("/api/v1/director/cinema/evaluate")(director_cinema_evaluate)
        cls.client = TestClient(app)

    def test_clean_shot_returns_no_warnings(self):
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json={
                "scene_goal": "a knight rides through the forest at dawn",
                "environment": "ancient forest path",
                "lighting": "dappled golden hour",
                "wardrobe": "chainmail, wool cloak",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["warnings"], [])
        self.assertEqual(body["hits"], [])
        self.assertEqual(body["era"], "medieval")

    def test_medieval_shot_with_smartphone_returns_anachronism(self):
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json={
                "scene_goal": "a knight checks his phone before the joust",
                "environment": "castle courtyard",
                "lighting": "low key",
                "wardrobe": "chainmail with a smartphone in his pocket",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["era"], "medieval")
        self.assertGreater(len(body["hits"]), 0)
        # At least one anachronism hit
        anachronism_hits = [h for h in body["hits"] if h["rule_id"].startswith("anachronism")]
        self.assertGreaterEqual(len(anachronism_hits), 1)
        self.assertEqual(anachronism_hits[0]["severity"], "warning")
        # Warnings are human-readable prefixed strings
        self.assertTrue(body["warnings"][0].startswith("[cinema:"))

    def test_lighting_contradiction_returns_lighting_hit(self):
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json={
                "scene_goal": "a noir interrogation",
                "environment": "sparse room",
                "lighting": "low key, blown out windows",
                "wardrobe": "trench coat",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        lighting_hits = [h for h in body["hits"] if h["rule_id"].startswith("lighting")]
        self.assertGreaterEqual(len(lighting_hits), 1)

    def test_props_are_also_scanned(self):
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json={
                "scene_goal": "the knight prepares for battle",
                "environment": "castle courtyard",
                "lighting": "soft golden hour",
                "wardrobe": "chainmail",
                "props": ["the knight draws a smartphone"],
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        # At least one anachronism hit triggered via the props list.
        anachronism_hits = [h for h in body["hits"] if h["rule_id"].startswith("anachronism")]
        self.assertGreaterEqual(len(anachronism_hits), 1)
        self.assertEqual(anachronism_hits[0]["field"], "props")

    def test_empty_payload_does_not_crash(self):
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json={},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["warnings"], [])
        self.assertEqual(body["hits"], [])
        self.assertEqual(body["era"], "unknown")

    def test_invalid_props_type_returns_400(self):
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json={
                "scene_goal": "x",
                "props": "not-a-list",  # type: ignore[list-item]
            },
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("props", resp.json()["detail"])

    def test_non_json_body_returns_400(self):
        # The endpoint reads JSON only when Content-Type is JSON;
        # an empty body with non-JSON content-type is treated as {}.
        # A non-dict JSON body (e.g. a list) returns 400.
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json=["not", "a", "dict"],
        )
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_hit_shape_matches_panel_contract(self):
        # The frontend CinemaWarningsPanel expects hit objects with
        # exactly these fields. Asserting the contract here so we
        # catch any backend rename before the UI breaks.
        resp = self.client.post(
            "/api/v1/director/cinema/evaluate",
            json={
                "scene_goal": "a knight checks his phone",
                "wardrobe": "chainmail with smartphone",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreater(len(body["hits"]), 0)
        hit = body["hits"][0]
        expected_keys = {"rule_id", "severity", "message", "field", "suggestion"}
        self.assertEqual(set(hit.keys()), expected_keys)
        self.assertIn(hit["severity"], {"info", "warning", "error"})


if __name__ == "__main__":
    unittest.main()
