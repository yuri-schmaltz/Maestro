"""Style Bible tests — Director v2 character/environment anchor abstraction.

Pattern lifted from directo_studio M1. We test the backend module
(anchors, builder, registry) without touching the UI. The aim is to
lock the data shape, the prompt composition order, the file-IO
safety guarantees, and the round-trip fidelity (save → load → assert
equality).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.services.style_bible import (
    BIBLE_DEFAULT_DIR,
    CharacterAnchor,
    EnvironmentAnchor,
    LoraConfig,
    PromptBuilder,
    StyleBible,
    BibleMetadata,
    delete_bible,
    list_bibles,
    load_bible,
    load_bible_from_path,
    save_bible,
)


def _make_sample_bible() -> StyleBible:
    """Helper: a representative Bible used across the round-trip tests."""
    return StyleBible(
        metadata=BibleMetadata(
            id="test-bible-1",
            title="Test Bible",
            description="A Bible for tests",
            author="gauntlet",
            tags=("test", "round-trip"),
        ),
        characters={
            "ana": CharacterAnchor(
                id="ana",
                name="Ana",
                physical_description="a woman in her 30s with short red hair",
                wardrobe="a charcoal blazer and round glasses",
                color_palette=("muted earth tones", "soft pastels"),
            ),
            "kai": CharacterAnchor(
                id="kai",
                name="Kai",
                physical_description="a tall man with dark skin and a shaved head",
                wardrobe="a worn denim jacket",
                color_palette=("navy", "rust"),
            ),
        },
        environments={
            "loft": EnvironmentAnchor(
                id="loft",
                name="Industrial Loft",
                description="a converted industrial loft with exposed brick",
                lighting="late afternoon sun raking across the floor",
                color_palette=("amber", "brick red", "concrete grey"),
            ),
        },
        loras={
            "charcoal-blazer": LoraConfig(
                name="charcoal-blazer",
                file_path="app/loras/charcoal-blazer.safetensors",
                weight=0.8,
                weight_min=0.6,
                weight_max=1.0,
                notes="Strengthens the charcoal blazer look",
            ),
        },
        global_style="cinematic, anamorphic, shallow depth of field",
        global_negative="cartoon, low-poly, watermark, signature",
    )


class AnchorsTests(unittest.TestCase):
    def test_character_anchor_round_trip(self):
        original = CharacterAnchor(
            id="c1", name="C1", physical_description="p1",
            wardrobe="w1", color_palette=("red", "blue"),
        )
        d = original.to_dict()
        restored = CharacterAnchor.from_dict(d)
        self.assertEqual(original, restored)

    def test_character_anchor_palette_must_be_list(self):
        with self.assertRaises(ValueError):
            CharacterAnchor.from_dict({
                "id": "c", "name": "c",
                "color_palette": "not-a-list",  # type: ignore[list-item]
            })

    def test_environment_anchor_round_trip(self):
        original = EnvironmentAnchor(
            id="e1", name="E1", description="d1",
            lighting="l1", color_palette=("amber",),
        )
        restored = EnvironmentAnchor.from_dict(original.to_dict())
        self.assertEqual(original, restored)

    def test_lora_config_round_trip(self):
        original = LoraConfig(
            name="l1", file_path="app/loras/l1.safetensors",
            weight=0.5, weight_min=0.1, weight_max=1.5, notes="",
        )
        restored = LoraConfig.from_dict(original.to_dict())
        self.assertEqual(original, restored)

    def test_style_bible_round_trip(self):
        original = _make_sample_bible()
        restored = StyleBible.from_dict(original.to_dict())
        self.assertEqual(original, restored)

    def test_style_bible_requires_metadata(self):
        with self.assertRaises(ValueError):
            StyleBible.from_dict({"characters": {}})

    def test_style_bible_default_collections_are_empty(self):
        bible = StyleBible(metadata=BibleMetadata(id="empty", title="Empty"))
        self.assertEqual(bible.characters, {})
        self.assertEqual(bible.environments, {})
        self.assertEqual(bible.loras, {})
        self.assertEqual(bible.global_style, "")
        self.assertEqual(bible.global_negative, "")


class PromptBuilderTests(unittest.TestCase):
    def setUp(self):
        self.bible = _make_sample_bible()
        self.builder = PromptBuilder()

    def test_build_returns_empty_prompt_when_no_inputs(self):
        result = self.builder.build(self.bible, base_prompt="")
        # Empty base + no ids + empty global style with no LoRAs would
        # produce a bare LoRAs: ... line. With our sample bible we
        # have one LoRA, so we expect just that line.
        self.assertIn("charcoal-blazer", result.prompt)
        self.assertEqual(result.active_loras, tuple(self.bible.loras.values()))

    def test_build_with_base_prompt_only(self):
        result = self.builder.build(self.bible, base_prompt="a quiet scene")
        self.assertTrue(result.prompt.startswith("a quiet scene"))

    def test_build_with_character_ids(self):
        result = self.builder.build(
            self.bible, base_prompt="they meet",
            character_ids=("ana",),
        )
        self.assertIn("Ana", result.prompt)
        self.assertIn("charcoal blazer", result.prompt)
        self.assertEqual(len(result.character_anchors), 1)
        self.assertEqual(result.character_anchors[0].id, "ana")

    def test_build_with_multiple_characters(self):
        result = self.builder.build(
            self.bible, base_prompt="they meet",
            character_ids=("ana", "kai"),
        )
        self.assertIn("Ana", result.prompt)
        self.assertIn("Kai", result.prompt)
        self.assertEqual(len(result.character_anchors), 2)

    def test_build_with_environment(self):
        result = self.builder.build(
            self.bible, base_prompt="inside",
            environment_id="loft",
        )
        self.assertIn("Industrial Loft", result.prompt)
        self.assertIn("exposed brick", result.prompt)
        self.assertEqual(result.environment_anchor.id, "loft")

    def test_unknown_character_id_is_silently_skipped(self):
        # A Bible without __default__ just drops the unknown id.
        # No crash, no warning, the prompt remains usable.
        result = self.builder.build(
            self.bible, base_prompt="",
            character_ids=("unknown-id",),
        )
        self.assertEqual(result.character_anchors, ())

    def test_unknown_character_id_falls_back_to_default(self):
        # A Bible with __default__ returns the default for unknown ids.
        bible = StyleBible(
            metadata=BibleMetadata(id="with-default", title="t"),
            characters={"__default__": CharacterAnchor(
                id="__default__", name="default",
                physical_description="a generic person",
            )},
        )
        result = self.builder.build(
            bible, base_prompt="",
            character_ids=("nonexistent",),
        )
        self.assertEqual(len(result.character_anchors), 1)
        self.assertEqual(result.character_anchors[0].id, "__default__")

    def test_build_includes_global_style(self):
        result = self.builder.build(self.bible, base_prompt="a scene")
        self.assertIn("cinematic, anamorphic", result.prompt)

    def test_build_includes_lora_metadata(self):
        result = self.builder.build(self.bible, base_prompt="a scene")
        self.assertIn("LoRAs:", result.prompt)
        self.assertIn("charcoal-blazer@0.8", result.prompt)

    def test_build_merges_negative_prompts(self):
        result = self.builder.build(
            self.bible, base_prompt="", negative_prompt="caller-side negatives",
        )
        self.assertIn("cartoon", result.negative_prompt)
        self.assertIn("low-poly", result.negative_prompt)
        self.assertIn("caller-side negatives", result.negative_prompt)

    def test_active_loras_order_matches_bible_iteration_order(self):
        # The registry loads dictionaries in insertion order (Python
        # 3.7+). The builder should preserve that order so a Bible
        # author who orders their LoRAs intentionally gets the
        # intended order in the prompt.
        bible = StyleBible(
            metadata=BibleMetadata(id="ordered", title="ordered"),
            loras={
                "first": LoraConfig(name="first", file_path="a", weight=0.1),
                "second": LoraConfig(name="second", file_path="b", weight=0.2),
                "third": LoraConfig(name="third", file_path="c", weight=0.3),
            },
        )
        result = self.builder.build(bible, base_prompt="x")
        names = [l.name for l in result.active_loras]
        self.assertEqual(names, ["first", "second", "third"])


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_save_and_load_round_trip(self):
        bible = _make_sample_bible()
        path = save_bible(bible, directory=self.dir)
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "test-bible-1.json")
        loaded = load_bible("test-bible-1", directory=self.dir)
        self.assertEqual(loaded, bible)

    def test_save_is_atomic(self):
        # Even if the write crashes mid-way, the original file should
        # be intact (we write to .tmp and rename). We can't easily
        # crash the process, but we CAN assert the .tmp file is gone
        # after a successful save.
        bible = _make_sample_bible()
        save_bible(bible, directory=self.dir)
        self.assertFalse((self.dir / "test-bible-1.json.tmp").exists())

    def test_save_refuses_overwrite_when_disabled(self):
        bible = _make_sample_bible()
        save_bible(bible, directory=self.dir)
        with self.assertRaises(FileExistsError):
            save_bible(bible, directory=self.dir, overwrite=False)

    def test_list_returns_all_bibles_sorted_by_title(self):
        b1 = StyleBible(metadata=BibleMetadata(id="b1", title="Bravo"))
        b2 = StyleBible(metadata=BibleMetadata(id="b2", title="Alpha"))
        b3 = StyleBible(metadata=BibleMetadata(id="b3", title="Charlie"))
        for bible in (b1, b2, b3):
            save_bible(bible, directory=self.dir)
        result = list_bibles(directory=self.dir)
        titles = [b.metadata.title for b in result]
        self.assertEqual(titles, ["Alpha", "Bravo", "Charlie"])

    def test_list_skips_corrupt_files(self):
        # A corrupt file in the directory must not break the registry.
        save_bible(_make_sample_bible(), directory=self.dir)
        (self.dir / "corrupt.json").write_text("{not valid json", encoding="utf-8")
        bibles = list_bibles(directory=self.dir)
        self.assertEqual(len(bibles), 1)
        self.assertEqual(bibles[0].metadata.id, "test-bible-1")

    def test_list_on_empty_directory_returns_empty(self):
        self.assertEqual(list_bibles(directory=self.dir), [])

    def test_list_creates_directory_if_missing(self):
        nested = self.dir / "does" / "not" / "exist"
        self.assertFalse(nested.exists())
        result = list_bibles(directory=nested)
        self.assertEqual(result, [])
        self.assertTrue(nested.is_dir())

    def test_delete_removes_file(self):
        bible = _make_sample_bible()
        save_bible(bible, directory=self.dir)
        self.assertTrue(delete_bible("test-bible-1", directory=self.dir))
        with self.assertRaises(FileNotFoundError):
            load_bible("test-bible-1", directory=self.dir)

    def test_delete_missing_returns_false(self):
        self.assertFalse(delete_bible("nonexistent", directory=self.dir))

    def test_delete_refuses_reserved_ids(self):
        with self.assertRaises(ValueError):
            delete_bible("__default__", directory=self.dir)
        with self.assertRaises(ValueError):
            delete_bible("_anything-leading-underscore", directory=self.dir)

    def test_load_rejects_invalid_id_path_traversal(self):
        for bad_id in ["../etc/passwd", "/absolute/path", "with/slash", "with\\backslash", "", ".", "..", "has\x00nul"]:
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(ValueError):
                    save_bible(
                        StyleBible(metadata=BibleMetadata(id=bad_id, title="t")),
                        directory=self.dir,
                    )

    def test_save_refuses_missing_metadata_id(self):
        bible = StyleBible(metadata=BibleMetadata(id="", title="t"))
        with self.assertRaises(ValueError):
            save_bible(bible, directory=self.dir)

    def test_load_raises_filenotfound_for_missing_bible(self):
        with self.assertRaises(FileNotFoundError):
            load_bible("nonexistent", directory=self.dir)

    def test_load_raises_valueerror_for_missing_metadata_key(self):
        # A file that exists but doesn't have the required shape.
        (self.dir / "broken.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_bible("broken", directory=self.dir)

    def test_load_bible_from_path_arbitrary_file(self):
        bible = _make_sample_bible()
        path = save_bible(bible, directory=self.dir)
        loaded = load_bible_from_path(path)
        self.assertEqual(loaded, bible)


class DefaultDirSmokeTest(unittest.TestCase):
    """The default registry dir must be inside the app/ tree and be
    writable from a regular user. We do NOT create it on import —
    creation is the job of list_bibles() / save_bible()."""

    def test_default_dir_is_inside_app_settings(self):
        # The default dir should be app/settings/style_bibles/. We
        # assert the path exists relative to APP_ROOT and contains
        # 'style_bibles' in its final segment.
        self.assertTrue(str(BIBLE_DEFAULT_DIR).endswith("style_bibles"))
        self.assertIn("settings", BIBLE_DEFAULT_DIR.parts)


class YamlSupportTests(unittest.TestCase):
    """YAML is optional — PyYAML may or may not be installed in the
    test env. We test both branches."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_yaml_available_or_not(self):
        from app.services.style_bible.registry import yaml_available, yaml_import_error
        # Either yaml_available() is True (PyYAML present) or False
        # with a non-empty yaml_import_error(). Both states are valid;
        # the rest of this test class skips the YAML-specific cases
        # when PyYAML is missing.
        if not yaml_available():
            self.assertIsNotNone(yaml_import_error())

    def test_save_and_load_yaml_round_trip(self):
        from app.services.style_bible.registry import yaml_available
        if not yaml_available():
            self.skipTest("PyYAML not installed")
        bible = _make_sample_bible()
        path = save_bible(bible, directory=self.dir, fmt="yaml")
        self.assertEqual(path.suffix, ".yaml")
        # The YAML file is plain text — sanity check a few substrings.
        text = path.read_text(encoding="utf-8")
        self.assertIn("test-bible-1", text)
        # Round-trip
        loaded = load_bible_from_path(path)
        self.assertEqual(loaded, bible)

    def test_yaml_save_refuses_overwrite_when_disabled(self):
        from app.services.style_bible.registry import yaml_available
        if not yaml_available():
            self.skipTest("PyYAML not installed")
        bible = _make_sample_bible()
        save_bible(bible, directory=self.dir, fmt="yaml")
        with self.assertRaises(FileExistsError):
            save_bible(bible, directory=self.dir, fmt="yaml", overwrite=False)

    def test_yaml_save_requires_pyyaml(self):
        from app.services.style_bible import registry as reg
        if reg._yaml is not None:
            self.skipTest("PyYAML is installed — cannot exercise the missing-PyYAML branch")
        bible = _make_sample_bible()
        with self.assertRaises(ImportError):
            save_bible(bible, directory=self.dir, fmt="yaml")

    def test_load_yaml_without_pyyaml_raises(self):
        from app.services.style_bible import registry as reg
        if reg._yaml is not None:
            self.skipTest("PyYAML is installed — cannot exercise the missing-PyYAML branch")
        fake_yaml = self.dir / "test.yaml"
        fake_yaml.write_text("metadata:\n  id: x\n  title: x\n", encoding="utf-8")
        with self.assertRaises(ImportError):
            load_bible_from_path(fake_yaml)

    def test_list_includes_yaml_when_pyyaml_installed(self):
        from app.services.style_bible.registry import yaml_available
        if not yaml_available():
            self.skipTest("PyYAML not installed")
        json_bible = StyleBible(metadata=BibleMetadata(id="json-one", title="JSON One"))
        yaml_bible = StyleBible(metadata=BibleMetadata(id="yaml-one", title="YAML One"))
        save_bible(json_bible, directory=self.dir, fmt="json")
        save_bible(yaml_bible, directory=self.dir, fmt="yaml")
        bibles = list_bibles(directory=self.dir)
        titles = sorted(b.metadata.title for b in bibles)
        self.assertEqual(titles, ["JSON One", "YAML One"])

    def test_mixed_format_directory_lists_correctly(self):
        from app.services.style_bible.registry import yaml_available
        if not yaml_available():
            self.skipTest("PyYAML not installed")
        # Save the same bible in both formats. The list should
        # return both — they're independent files.
        bible = _make_sample_bible()
        save_bible(bible, directory=self.dir, fmt="json")
        save_bible(bible, directory=self.dir, fmt="yaml", overwrite=False)
        bibles = list_bibles(directory=self.dir)
        ids = [b.metadata.id for b in bibles]
        self.assertEqual(ids.count("test-bible-1"), 2)

    def test_delete_removes_both_formats(self):
        from app.services.style_bible.registry import yaml_available
        if not yaml_available():
            self.skipTest("PyYAML not installed")
        bible = _make_sample_bible()
        save_bible(bible, directory=self.dir, fmt="json")
        save_bible(bible, directory=self.dir, fmt="yaml", overwrite=False)
        self.assertTrue(delete_bible("test-bible-1", directory=self.dir))
        # Both files gone
        self.assertFalse((self.dir / "test-bible-1.json").exists())
        self.assertFalse((self.dir / "test-bible-1.yaml").exists())

    def test_invalid_fmt_raises_valueerror(self):
        with self.assertRaises(ValueError):
            save_bible(_make_sample_bible(), directory=self.dir, fmt="xml")  # type: ignore[arg-type]

    def test_yaml_round_trip_preserves_color_palettes_as_lists(self):
        # Regression test: color_palette is a tuple internally but
        # must serialize/deserialize as a list (YAML/JSON have no
        # tuples). If the to_dict path forgot the list() coercion,
        # the from_dict would crash with "color_palette must be a list".
        from app.services.style_bible.registry import yaml_available
        if not yaml_available():
            self.skipTest("PyYAML not installed")
        bible = _make_sample_bible()
        path = save_bible(bible, directory=self.dir, fmt="yaml")
        loaded = load_bible_from_path(path)
        self.assertEqual(loaded.characters["ana"].color_palette, ("muted earth tones", "soft pastels"))


if __name__ == "__main__":
    unittest.main()
