"""Focused tests for the standalone workspace setup service."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.workspace_setup import (
    DEFAULT_PROJECT_SETUP,
    WorkspaceSetupError,
    cover_image_path,
    delete_cover_image,
    load_setup,
    persist_setup,
    save_cover_image,
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
                "director_skill": "short_film",
            })
            self.assertEqual(stored["description"], "My short film")
            self.assertEqual(stored["tags"], ["film", "draft"])
            self.assertTrue(stored["pinned"])
            self.assertEqual(stored["director_skill"], "short_film")
            loaded = load_setup(root, "project_1")
            self.assertEqual(loaded["description"], "My short film")
            self.assertEqual(loaded["tags"], ["film", "draft"])
            self.assertTrue(loaded["pinned"])
            self.assertEqual(loaded["director_skill"], "short_film")

    def test_legacy_setup_without_skill_defaults_to_music_video(self):
        with tempfile.TemporaryDirectory() as root:
            stored = persist_setup(root, "project_1", {"resolution": "1080p"})
            self.assertEqual(stored.get("director_skill", "music_video"), "music_video")
            loaded = load_setup(root, "project_1")
            self.assertEqual(loaded["director_skill"], DEFAULT_PROJECT_SETUP["director_skill"])

    def test_invalid_skill_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(WorkspaceSetupError) as context:
                persist_setup(root, "project_1", {"director_skill": "podcast"})
            self.assertEqual(context.exception.status_code, 400)

    def test_cover_image_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            stored = persist_setup(root, "project_1", {"cover_image": "cover_abc123.png"})
            self.assertEqual(stored["cover_image"], "cover_abc123.png")
            loaded = load_setup(root, "project_1")
            self.assertEqual(loaded["cover_image"], "cover_abc123.png")

    def test_invalid_cover_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for bad in ("../escape.png", "cover.png/", "cover.exe", "cover svg.png", ""):
                if bad == "":
                    continue
                with self.assertRaises(WorkspaceSetupError, msg=bad) as context:
                    persist_setup(root, "project_1", {"cover_image": bad})
                self.assertEqual(context.exception.status_code, 400)

    def test_cover_upload_store_and_delete(self):
        with tempfile.TemporaryDirectory() as root:
            png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
            first = save_cover_image(root, "project_1", png, "My Cover.PNG")
            second = save_cover_image(root, "project_1", png, "other.jpg")
            self.assertNotEqual(first, second)
            self.assertTrue(first.endswith(".png"))
            self.assertIsNotNone(cover_image_path(root, "project_1", first))
            self.assertIsNone(cover_image_path(root, "project_1", "missing.png"))
            self.assertTrue(delete_cover_image(root, "project_1", first))
            self.assertIsNone(cover_image_path(root, "project_1", first))
            self.assertTrue(delete_cover_image(root, "project_1"))
            self.assertFalse(delete_cover_image(root, "project_1"))

    def test_cover_upload_rejects_bad_input(self):
        with tempfile.TemporaryDirectory() as root:
            png = b"\x89PNG\r\n\x1a\n"
            with self.assertRaises(WorkspaceSetupError) as context:
                save_cover_image(root, "project_1", png, "cover.gif")
            self.assertEqual(context.exception.status_code, 415)
            with self.assertRaises(WorkspaceSetupError) as context:
                save_cover_image(root, "project_1", b"", "cover.png")
            self.assertEqual(context.exception.status_code, 400)
            with self.assertRaises(WorkspaceSetupError) as context:
                save_cover_image(root, "default", png, "cover.png")
            self.assertEqual(context.exception.status_code, 400)
            with self.assertRaises(WorkspaceSetupError):
                save_cover_image(root, "../escape", png, "cover.png")

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
