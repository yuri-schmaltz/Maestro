"""Regression tests for the LLM JSON-grammar helpers.

Covers three layers:

1. ``services.text_integrity.repair_text`` — conservative mojibake
   repair used to fix UTF-8 bytes that crossed a Latin-1 / cp1252
   boundary (older Maestro projects, Windows HTTP responses).
2. ``services.text_integrity.repair_payload`` — the same repair
   applied recursively to dicts / lists returned from the LLM.
3. ``Director.planners.base.BasePlanner._parse_json_response`` — the
   strict → regex → json_repair fallback chain that powers every
   ``_call_llm_json`` consumer (music video, short film, podcast,
   viral video, demo skill).

These tests are intentionally self-contained: no LLM weights, no GPU,
no network. They run under both ``python -m unittest`` (which is what
CI uses) and ``pytest`` (which the local gauntlet uses).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Import path setup — same trick as the other tests/ modules so the suite
# can be run from the repo root OR from inside tests/.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = REPO_ROOT / "app"
# Mirror the layout other tests/ modules use: prepend app/ so the
# absolute ``services.X`` imports (Maestro's runtime layout) resolve
# the same way they do inside the launcher.
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


from services.text_integrity import repair_payload, repair_text  # noqa: E402


# ---------------------------------------------------------------------------
# repair_text
# ---------------------------------------------------------------------------


class RepairTextTests(unittest.TestCase):
    """Validate the conservative mojibake repair surface."""

    def test_passes_through_clean_unicode(self):
        # Valid international text must NOT be rewritten, otherwise a
        # German "Wörter" or Portuguese "não" gets mangled the moment
        # we touch it. This is the regression that broke an earlier
        # "always re-decode" implementation.
        original = "Wörter, não, señor — résumé."
        self.assertEqual(repair_text(original), original)

    def test_repairs_curly_quotes_double_encoded(self):
        # The U+2019 right single quote was stored as the cp1252
        # representation of the UTF-8 bytes, which renders as "â€™".
        self.assertEqual(repair_text("â€™"), "\u2019")

    def test_repairs_known_em_dash_pair(self):
        self.assertEqual(repair_text("â€“"), "\u2013")
        self.assertEqual(repair_text("â€”"), "\u2014")

    def test_repairs_ellipsis(self):
        self.assertEqual(repair_text("â€¦"), "\u2026")

    def test_handles_empty_input(self):
        self.assertEqual(repair_text(""), "")
        self.assertEqual(repair_text(None), "")

    def test_handles_bytes_input(self):
        # Bytes flow in from older saved projects. Decode as UTF-8 with
        # replacement; the resulting string is then passed through the
        # same mojibake gate as a normal string.
        sample = "Hello".encode("utf-8")
        self.assertEqual(repair_text(sample), "Hello")

    def test_does_not_introduce_replacement_char(self):
        # A well-formed Unicode string contains no U+FFFD; the
        # repair must not inject one when validating input.
        self.assertNotIn("\ufffd", repair_text("café — déjà vu"))


# ---------------------------------------------------------------------------
# repair_payload
# ---------------------------------------------------------------------------


class RepairPayloadTests(unittest.TestCase):
    """Recursive variant — the LLM sometimes mojibakes inside JSON
    values rather than the raw text, so we re-run the gate on the
    parsed payload."""

    def test_dict_recurses_into_values(self):
        broken = {"title": "â€™Helloâ€™", "nested": {"name": "WÃ¶rter"}}
        repaired = repair_payload(broken)
        self.assertEqual(repaired["title"], "\u2019Hello\u2019")
        self.assertEqual(repaired["nested"]["name"], "Wörter")

    def test_list_recurses_into_items(self):
        broken = ["â€˜", "â€™", "ok"]
        repaired = repair_payload(broken)
        self.assertEqual(repaired[0], "\u2018")
        self.assertEqual(repaired[1], "\u2019")
        self.assertEqual(repaired[2], "ok")

    def test_preserves_non_string_primitives(self):
        # Numbers, booleans and None must survive a no-op pass. An
        # earlier version that called str() on every primitive caused
        # integer keys to render as strings and broke schema
        # validation downstream.
        payload = {"count": 42, "ratio": 0.5, "flag": True, "empty": None}
        self.assertEqual(repair_payload(payload), payload)

    def test_preserves_clean_unicode_strings(self):
        payload = {"name": "café", "city": "São Paulo"}
        self.assertEqual(repair_payload(payload), payload)


# ---------------------------------------------------------------------------
# BasePlanner._parse_json_response
# ---------------------------------------------------------------------------


class _ConcreteParserProbe:
    """Lightweight stand-in for the parts of BasePlanner that
    ``_parse_json_response`` depends on, so we can exercise the JSON
    grammar pipeline without instantiating a full skill planner.

    ``_parse_json_response`` only reads / writes ``self`` attributes
    implicitly through the ``normalized_items`` closure; inlining the
    method against a stub is enough to cover the grammar path."""

    _parse_json_response = None  # patched in setUp


class ParseJsonResponseTests(unittest.TestCase):
    """Direct unit tests against ``BasePlanner._parse_json_response``.

    Uses ``DemoSkillPlanner`` (the simplest concrete subclass) so we
    exercise the real implementation, not a re-implementation."""

    def setUp(self):
        # Defer the import until path setup has run. Avoids a hard
        # dependency order that would break standalone runs.
        from services.director.planners.demo_skill import DemoSkillPlanner

        # No LLM wired in — _parse_json_response does not call the
        # backend; it only operates on the text passed in.
        self._planner = DemoSkillPlanner(llm_generate=None, llm_generate_streaming=None)

    # ----- direct parse ----------------------------------------------------

    def test_parses_clean_array(self):
        text = json.dumps([{"shot_id": "shot_001", "duration_sec": 4.0}])
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["shot_id"], "shot_001")

    def test_parses_object_with_shots_key(self):
        # Some prompts encourage the LLM to wrap the array in an
        # object — accept that shape too.
        text = json.dumps({"shots": [{"shot_id": "shot_002"}, {"shot_id": "shot_003"}]})
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual([item["shot_id"] for item in result], ["shot_002", "shot_003"])

    def test_parses_single_object_as_one_item(self):
        text = json.dumps({"shot_id": "shot_only", "duration_sec": 2.0})
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["shot_id"], "shot_only")

    # ----- markdown fences -------------------------------------------------

    def test_strips_json_fence(self):
        text = (
            "Here is the JSON you asked for:\n"
            "```json\n"
            + json.dumps([{"shot_id": "shot_fenced"}])
            + "\n```\n"
            "Cheers."
        )
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["shot_id"], "shot_fenced")

    def test_strips_plain_fence(self):
        # Some models emit ``` without the "json" hint. The regex
        # covers both flavours; both must round-trip.
        text = "```\n" + json.dumps([{"shot_id": "shot_plain"}]) + "\n```"
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["shot_id"], "shot_plain")

    # ----- thinking tags --------------------------------------------------

    def test_strips_thinking_tag(self):
        # Qwen emits <think>...</think>; Gemma emits
        # <|channel>thought\n...<channel|>. Both should be removed
        # before JSON extraction so the user-visible payload is the
        # structured output, not the model's scratchpad.
        text = (
            "<think>The user wants a list.</think>"
            + json.dumps([{"shot_id": "shot_after_think"}])
        )
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["shot_id"], "shot_after_think")

    def test_strips_unclosed_thinking_tag(self):
        # A streaming truncation can leave the closing tag missing.
        # The greedy unanchored regex removes everything after the
        # open tag (the rest is treated as leaked reasoning), so the
        # parser surfaces None — callers know to retry / surface an
        # error. The contract here is "unclosed thinking => no
        # JSON extracted", NOT "unclosed thinking => JSON survives".
        # Documenting it as a test so a future refactor doesn't
        # silently flip the contract.
        text = (
            "<reasoning>I should output JSON now..."
            + json.dumps([{"shot_id": "shot_unclosed_thinking"}])
        )
        self.assertIsNone(self._planner._parse_json_response(text))

    def test_strips_thinking_then_parses_following_json(self):
        # Closed thinking block followed by JSON on its own line is
        # the well-behaved streaming case: drop the scratchpad, keep
        # the structured payload.
        text = (
            "<reasoning>Let me think...</reasoning>\n"
            + json.dumps([{"shot_id": "shot_after_reasoning"}])
        )
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["shot_id"], "shot_after_reasoning")

    # ----- recovery paths -------------------------------------------------

    def test_extracts_json_array_embedded_in_prose(self):
        # Some responses surround the array with chatty prose. The
        # regex fallback (\[[\s\S]*\]) must still find it.
        text = (
            "Sure! Here you go:\n"
            + json.dumps([{"shot_id": "shot_in_prose"}])
            + "\nLet me know if you need anything else."
        )
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["shot_id"], "shot_in_prose")

    def test_returns_none_for_garbage(self):
        # If we genuinely can't find JSON, surface None — callers
        # already know how to retry / surface a user-visible error.
        self.assertIsNone(self._planner._parse_json_response("not json at all"))

    def test_handles_empty_string(self):
        self.assertIsNone(self._planner._parse_json_response(""))
        self.assertIsNone(self._planner._parse_json_response(None))

    # ----- mojibake repair ------------------------------------------------

    def test_repairs_mojibake_in_payload_values(self):
        # UTF-8 bytes that crossed a cp1252 boundary land as "WÃ¶rter"
        # in the raw text; the repair gate runs before parse and the
        # parser should surface the corrected payload.
        text = '[{"title": "WÃ¶rter"}]'
        result = self._planner._parse_json_response(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["title"], "Wörter")


# ---------------------------------------------------------------------------
# Backwards-compat shim — the CI job historically ran this file as a
# standalone script ("python tests/test_call_llm_json_grammar.py") rather
# than via unittest discovery. Keep that working so anyone reproducing an
# older bug report can still execute the suite with python directly.
# ---------------------------------------------------------------------------


def _run_all() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite([
        loader.loadTestsFromTestCase(RepairTextTests),
        loader.loadTestsFromTestCase(RepairPayloadTests),
        loader.loadTestsFromTestCase(ParseJsonResponseTests),
    ])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(_run_all())