"""Focused tests for the standalone workspace setup service."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.workspace_setup import (
    DEFAULT_PROJECT_SETUP,
    WorkspaceSetupError,
    load_setup,
    persist_setup,
    setup_path,
)


class WorkspaceSetupServiceTests(unittest.TestCase):
    def test_default_workspace_has_no_setup_path(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(setup_path(root, "default"))

    def test_round_trip_is_independent_of_fastapi(self):
        with tempfile.TemporaryDirectory() as root:
            stored = persist_setup(root, "project_1", {
                "music_source": "generate",
                "music_model": "ace_step_v1_5",
                "advanced": {"film_grain": True},
            })
            self.assertEqual(stored["music_source"], "generate")
            loaded = load_setup(root, "project_1")
            self.assertEqual(loaded["music_model"], "ace_step_v1_5")
            self.assertEqual(loaded["advanced"], {"film_grain": True})
            self.assertEqual(loaded["resolution"], DEFAULT_PROJECT_SETUP["resolution"])

    def test_unknown_fields_are_not_persisted(self):
        with tempfile.TemporaryDirectory() as root:
            persist_setup(root, "project_1", {"unknown": True})
            path = Path(root) / "project_1" / "setup.json"
            self.assertNotIn("unknown", path.read_text(encoding="utf-8"))

    def test_metadata_fields_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            stored = persist_setup(root, "project_1", {
                "description": "My short film",
                "tags": ["film", "draft"],
                "pinned": True,
            })
            self.assertEqual(stored["description"], "My short film")
            self.assertEqual(stored["tags"], ["film", "draft"])
            self.assertTrue(stored["pinned"])
            loaded = load_setup(root, "project_1")
            self.assertEqual(loaded["description"], "My short film")
            self.assertEqual(loaded["tags"], ["film", "draft"])
            self.assertTrue(loaded["pinned"])

    def test_invalid_tags_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(WorkspaceSetupError) as context:
                persist_setup(root, "project_1", {"tags": "not-a-list"})
            self.assertEqual(context.exception.status_code, 400)

    def test_invalid_payload_has_http_compatible_error(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(WorkspaceSetupError) as context:
                persist_setup(root, "project_1", {"seamless": "yes"})
            self.assertEqual(context.exception.status_code, 400)

    def test_invalid_workspace_name_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(WorkspaceSetupError) as context:
                persist_setup(root, "../escape", {})
            self.assertEqual(context.exception.status_code, 400)
            self.assertFalse((Path(root).parent / "escape").exists())


if __name__ == "__main__":
    unittest.main()
