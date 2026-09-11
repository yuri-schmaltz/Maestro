"""Tests for the /api/v1/style-bibles endpoints.

The endpoints are the bridge between the backend Style Bible
package (services/style_bible/) and the Configurations UI panel
that the operator uses to manage their Bibles.

We mount the routes on a fresh FastAPI app via TestClient. The
endpoints themselves are defined in app/launch.py, but we can't
import launch.py in a test (it pulls in torch / diffusers / etc.).
Instead, we re-implement each handler as a thin wrapper around the
style_bible package, mirroring the launch.py body. The wrappers
MUST stay byte-for-byte equivalent so the contract test stays
meaningful; both call the same services, so the structural
assertions still gate the most common regressions.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request as FastAPIRequest

# Use the package directly — the style_bible registry is pure-Python
# and does not require the model stack.
from app.services.style_bible import (
    PromptBuilder,
    StyleBible,
    delete_bible,
    list_bibles,
    load_bible,
    save_bible,
)


def _bible_payload(id: str, title: str = "Test Bible") -> dict:
    """Return a minimal valid Bible payload."""
    return {
        "metadata": {
            "id": id,
            "title": title,
            "description": "",
            "author": "",
            "created_at": "",
            "updated_at": "",
            "tags": [],
        },
        "characters": {
            "ana": {
                "id": "ana",
                "name": "Ana",
                "physical_description": "a woman in her 30s",
                "wardrobe": "charcoal blazer",
                "color_palette": ["muted"],
            },
        },
        "environments": {},
        "loras": {},
        "global_style": "",
        "global_negative": "",
    }


# --- Mirror handlers (sync with app/launch.py:list_style_bibles, etc.) ---


def _list_style_bibles():
    out = []
    for bible in list_bibles():
        out.append({
            "id": bible.metadata.id,
            "title": bible.metadata.title,
            "description": bible.metadata.description,
            "author": bible.metadata.author,
            "tags": list(bible.metadata.tags),
            "characters_count": len(bible.characters),
            "environments_count": len(bible.environments),
            "loras_count": len(bible.loras),
            "global_style": bible.global_style,
            "global_negative": bible.global_negative,
        })
    return {"bibles": out}


def _get_style_bible(bible_id: str):
    try:
        bible = load_bible(bible_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return bible.to_dict()


async def _put_style_bible(bible_id: str, request: FastAPIRequest):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    if "metadata" not in body or not isinstance(body["metadata"], dict):
        raise HTTPException(status_code=400, detail="metadata key is required")
    if body["metadata"].get("id") != bible_id:
        raise HTTPException(
            status_code=400,
            detail=f"body metadata.id ({body['metadata'].get('id')!r}) does not match path bible_id ({bible_id!r})",
        )
    try:
        bible = StyleBible.from_dict(body)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid bible: {exc}") from exc
    try:
        path = save_bible(bible)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": bible.metadata.id, "path": str(path)}


async def _create_style_bible(request: FastAPIRequest):
    from app.services.style_bible.registry import BIBLE_DEFAULT_DIR
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        bible = StyleBible.from_dict(body)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid bible: {exc}") from exc
    # Mirror launch.py: refuse before calling save_bible (save_bible
    # default-overwrites, which is the opposite of what POST means).
    target = BIBLE_DEFAULT_DIR / f"{bible.metadata.id}.json"
    yaml_target = BIBLE_DEFAULT_DIR / f"{bible.metadata.id}.yaml"
    yml_target = BIBLE_DEFAULT_DIR / f"{bible.metadata.id}.yml"
    if target.exists() or yaml_target.exists() or yml_target.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Style Bible already exists: {bible.metadata.id}",
        )
    try:
        path = save_bible(bible, overwrite=False)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": bible.metadata.id, "path": str(path)}


def _delete_style_bible(bible_id: str):
    try:
        removed = delete_bible(bible_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail=f"Style Bible not found: {bible_id}")
    return {"deleted": bible_id}


async def _build_style_bible_prompt(bible_id: str, request: FastAPIRequest):
    try:
        bible = load_bible(bible_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    result = PromptBuilder().build(
        bible,
        base_prompt=str(body.get("base_prompt", "") or ""),
        character_ids=tuple(body.get("character_ids", []) or []),
        environment_id=body.get("environment_id"),
        negative_prompt=str(body.get("negative_prompt", "") or ""),
    )
    return {
        "prompt": result.prompt,
        "negative_prompt": result.negative_prompt,
        "active_loras": [],
        "character_anchors": [{"id": c.id, "name": c.name} for c in result.character_anchors],
        "environment_anchor": (
            {"id": result.environment_anchor.id, "name": result.environment_anchor.name}
            if result.environment_anchor is not None else None
        ),
    }


class StyleBibleEndpointTests(unittest.TestCase):
    """Each test runs against a tempdir pointed at BIBLE_DEFAULT_DIR."""

    def setUp(self):
        from fastapi.testclient import TestClient

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

        # Patch both the package re-export and the registry module
        # so all registry calls (including the lazy imports inside
        # the handlers) hit our tempdir.
        import app.services.style_bible as sb_pkg
        import app.services.style_bible.registry as reg
        self._patches = (
            patch.object(reg, "BIBLE_DEFAULT_DIR", self.dir),
            patch.object(sb_pkg, "BIBLE_DEFAULT_DIR", self.dir),
        )
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])

        app = FastAPI()
        app.get("/api/v1/style-bibles")(_list_style_bibles)
        app.get("/api/v1/style-bibles/{bible_id}")(_get_style_bible)
        app.put("/api/v1/style-bibles/{bible_id}")(_put_style_bible)
        app.post("/api/v1/style-bibles")(_create_style_bible)
        app.delete("/api/v1/style-bibles/{bible_id}")(_delete_style_bible)
        app.post("/api/v1/style-bibles/{bible_id}/build")(_build_style_bible_prompt)
        self.client = TestClient(app)

    def test_list_empty(self):
        resp = self.client.get("/api/v1/style-bibles")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"bibles": []})

    def test_list_after_create(self):
        self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha", "Alpha"))
        self.client.post("/api/v1/style-bibles", json=_bible_payload("beta", "Beta"))
        resp = self.client.get("/api/v1/style-bibles")
        self.assertEqual(resp.status_code, 200)
        bodies = resp.json()["bibles"]
        ids = [b["id"] for b in bodies]
        # Sort order is by title, not id
        self.assertEqual(ids, ["alpha", "beta"])
        alpha = next(b for b in bodies if b["id"] == "alpha")
        self.assertEqual(alpha["characters_count"], 1)
        self.assertEqual(alpha["environments_count"], 0)

    def test_get_returns_full_bible(self):
        self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha"))
        resp = self.client.get("/api/v1/style-bibles/alpha")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["metadata"]["id"], "alpha")
        self.assertIn("ana", body["characters"])
        self.assertEqual(body["characters"]["ana"]["name"], "Ana")

    def test_get_missing_returns_404(self):
        resp = self.client.get("/api/v1/style-bibles/nonexistent")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"])

    def test_create_persists_file(self):
        resp = self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["id"], "alpha")
        self.assertTrue((self.dir / "alpha.json").exists())

    def test_create_duplicate_returns_409(self):
        self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha"))
        resp = self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha"))
        self.assertEqual(resp.status_code, 409)

    def test_create_invalid_bible_returns_400(self):
        # Missing metadata
        resp = self.client.post("/api/v1/style-bibles", json={"characters": {}})
        self.assertEqual(resp.status_code, 400)

    def test_put_updates_existing_bible(self):
        self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha"))
        payload = _bible_payload("alpha", title="Updated Title")
        resp = self.client.put("/api/v1/style-bibles/alpha", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        # Verify the file now has the new title
        get_resp = self.client.get("/api/v1/style-bibles/alpha")
        self.assertEqual(get_resp.json()["metadata"]["title"], "Updated Title")

    def test_put_path_id_mismatch_returns_400(self):
        payload = _bible_payload("alpha")
        resp = self.client.put("/api/v1/style-bibles/different-id", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("does not match", resp.json()["detail"])

    def test_delete_removes_file(self):
        self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha"))
        resp = self.client.delete("/api/v1/style-bibles/alpha")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], "alpha")
        self.assertFalse((self.dir / "alpha.json").exists())

    def test_delete_missing_returns_404(self):
        resp = self.client.delete("/api/v1/style-bibles/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_delete_reserved_id_returns_400(self):
        resp = self.client.delete("/api/v1/style-bibles/__default__")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("reserved", resp.json()["detail"])

    def test_build_prompt_endpoint(self):
        self.client.post("/api/v1/style-bibles", json=_bible_payload("alpha"))
        resp = self.client.post(
            "/api/v1/style-bibles/alpha/build",
            json={
                "base_prompt": "a quiet scene",
                "character_ids": ["ana"],
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("Ana", body["prompt"])
        self.assertIn("a quiet scene", body["prompt"])
        self.assertEqual(len(body["character_anchors"]), 1)
        self.assertEqual(body["character_anchors"][0]["id"], "ana")
        self.assertIsNone(body["environment_anchor"])

    def test_build_prompt_unknown_bible_returns_404(self):
        resp = self.client.post(
            "/api/v1/style-bibles/nonexistent/build",
            json={"base_prompt": "x"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_full_crud_lifecycle(self):
        # Create
        create_resp = self.client.post("/api/v1/style-bibles", json=_bible_payload("lifecycle"))
        self.assertEqual(create_resp.status_code, 200)
        # Read (list)
        list_resp = self.client.get("/api/v1/style-bibles")
        self.assertEqual(len(list_resp.json()["bibles"]), 1)
        # Read (single)
        get_resp = self.client.get("/api/v1/style-bibles/lifecycle")
        self.assertEqual(get_resp.status_code, 200)
        # Update
        update_payload = get_resp.json()
        update_payload["metadata"]["description"] = "now with more info"
        update_resp = self.client.put("/api/v1/style-bibles/lifecycle", json=update_payload)
        self.assertEqual(update_resp.status_code, 200)
        # Verify update
        verify_resp = self.client.get("/api/v1/style-bibles/lifecycle")
        self.assertEqual(verify_resp.json()["metadata"]["description"], "now with more info")
        # Delete
        del_resp = self.client.delete("/api/v1/style-bibles/lifecycle")
        self.assertEqual(del_resp.status_code, 200)
        # Confirm gone
        self.assertEqual(self.client.get("/api/v1/style-bibles/lifecycle").status_code, 404)


if __name__ == "__main__":
    unittest.main()
