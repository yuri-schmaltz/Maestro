"""Cinema rules tests — Director v2 screenplay post-pass.

Covers:
  - Era detection across prehistoric / medieval / industrial / modern /
    contemporary / future / unknown.
  - Anachronism blocking per era.
  - Lighting consistency for known contradictions.
  - End-to-end: validate_shot_plan appends cinema warnings but never
    fails the validation (cinema is advisory, not blocking).
"""
from __future__ import annotations

import unittest

from app.services.director.cinema import (
    CinemaEvaluation,
    CinemaRuleHit,
    Era,
    Severity,
    evaluate_shot,
)
from app.services.director.cinema.era import detect_era
from app.services.director.cinema.anachronism import check_anachronism
from app.services.director.cinema.lighting import check_lighting_consistency
from app.services.director.cinema.integration import run_cinema_pass, collect_shot_text
from app.services.director.schema import (
    AudioPlan,
    CameraPlan,
    CharacterProfile,
    ProductionPlan,
    ShotPlan,
    SubjectRef,
)
from app.services.director.validators import validate_shot_plan


class EraDetectionTests(unittest.TestCase):
    def test_prehistoric_era(self):
        result = detect_era(scene_goal="a caveman hunts a mammoth")
        self.assertEqual(result.era, Era.PREHISTORIC)

    def test_medieval_era(self):
        result = detect_era(scene_goal="a knight rides toward the castle")
        self.assertEqual(result.era, Era.MEDIEVAL)

    def test_industrial_era(self):
        result = detect_era(scene_goal="workers leave the factory at dusk")
        self.assertEqual(result.era, Era.INDUSTRIAL)

    def test_modern_era(self):
        result = detect_era(scene_goal="a 1980s walkman plays on the bus")
        self.assertEqual(result.era, Era.MODERN)

    def test_contemporary_era(self):
        result = detect_era(scene_goal="the influencer checks her iphone")
        self.assertEqual(result.era, Era.CONTEMPORARY)

    def test_future_era(self):
        result = detect_era(scene_goal="the cyborg walks through the space station")
        self.assertEqual(result.era, Era.FUTURE)

    def test_unknown_when_no_signals(self):
        result = detect_era(scene_goal="a quiet morning in an empty room")
        self.assertEqual(result.era, Era.UNKNOWN)

    def test_unknown_when_only_environment_is_blank(self):
        result = detect_era(scene_goal="", environment="")
        self.assertEqual(result.era, Era.UNKNOWN)


class AnachronismTests(unittest.TestCase):
    def test_medieval_wardrobe_with_smartphone_is_flagged(self):
        hits = check_anachronism(
            era=Era.MEDIEVAL,
            wardrobe="a tunic, leather boots, a smartphone in the belt pouch",
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("smartphone", hits[0].reason)

    def test_medieval_wardrobe_with_car_is_flagged(self):
        hits = check_anachronism(
            era=Era.MEDIEVAL,
            wardrobe="a cape, an electric car parked behind the castle",
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("vehicle", hits[0].reason)

    def test_modern_wardrobe_with_crossbow_is_flagged(self):
        hits = check_anachronism(
            era=Era.MODERN,
            wardrobe="jeans, a t-shirt, a crossbow slung over the shoulder",
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("medieval", hits[0].reason)

    def test_industrial_wardrobe_with_smartphone_is_flagged(self):
        hits = check_anachronism(
            era=Era.INDUSTRIAL,
            wardrobe="factory worker in a flat cap, using a smartphone",
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("modern technology", hits[0].reason)

    def test_unknown_era_is_a_noop(self):
        # The anachronism rule is meaningless without a detected era —
        # it would generate noise on every unspecified shot. We
        # explicitly short-circuit.
        hits = check_anachronism(
            era=Era.UNKNOWN,
            wardrobe="anything goes here: smartphone, car, crossbow, etc.",
        )
        self.assertEqual(hits, ())

    def test_future_era_is_exempt(self):
        # Future scenes can reference anything; the rule is exempt by
        # design (see comment in anachronism.py).
        hits = check_anachronism(
            era=Era.FUTURE,
            wardrobe="the cyborg plugs into a smartphone, then drives a car",
        )
        self.assertEqual(hits, ())

    def test_props_list_is_also_scanned(self):
        hits = check_anachronism(
            era=Era.MEDIEVAL,
            wardrobe="simple wool tunic",
            props=("the knight draws a smartphone",),
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].scope, "props")


class LightingConsistencyTests(unittest.TestCase):
    def test_low_key_and_blown_out_contradicts(self):
        hits = check_lighting_consistency("low key lighting, blown out windows")
        self.assertEqual(len(hits), 1)
        self.assertIn("contradicts", hits[0].reason)

    def test_hard_light_and_soft_diffusion_contradicts(self):
        hits = check_lighting_consistency("hard light from a single source, soft box diffused")
        self.assertEqual(len(hits), 1)
        self.assertIn("hard light", hits[0].reason)

    def test_high_key_and_heavy_shadow_contradicts(self):
        hits = check_lighting_consistency("high key even lighting, deep shadow on the face")
        self.assertEqual(len(hits), 1)

    def test_noon_and_twilight_contradicts(self):
        hits = check_lighting_consistency("noon overhead sun, then blue hour twilight")
        self.assertEqual(len(hits), 1)

    def test_clean_lighting_passes(self):
        hits = check_lighting_consistency("low key with a single hard light source")
        self.assertEqual(hits, ())

    def test_empty_lighting_passes(self):
        hits = check_lighting_consistency("")
        self.assertEqual(hits, ())


class EvaluateShotIntegrationTests(unittest.TestCase):
    """End-to-end: evaluate_shot pulls era + anachronism + lighting
    into a single CinemaEvaluation."""

    def test_clean_shot_returns_no_hits(self):
        result = evaluate_shot(
            scene_goal="a knight rides through the forest at dawn",
            environment="ancient forest path",
            lighting="dappled golden hour",
            wardrobe="chainmail, wool cloak",
        )
        self.assertEqual(result.hits, ())
        self.assertFalse(result.has_warnings)

    def test_medieval_shot_with_smartphone_is_warned(self):
        result = evaluate_shot(
            scene_goal="a knight checks his phone before the joust",
            environment="castle courtyard",
            lighting="low key",
            wardrobe="chainmail with a smartphone in his pocket",
        )
        self.assertTrue(result.has_warnings)
        # At least one hit should be the anachronism one
        anachronism_hits = [h for h in result.hits if h.rule_id.startswith("anachronism")]
        self.assertGreaterEqual(len(anachronism_hits), 1)

    def test_lighting_contradiction_is_warned(self):
        result = evaluate_shot(
            scene_goal="a noir interrogation",
            environment="sparse room",
            lighting="low key, hard shadow, blown out window",
            wardrobe="trench coat",
        )
        lighting_hits = [h for h in result.hits if h.rule_id.startswith("lighting")]
        self.assertGreaterEqual(len(lighting_hits), 1)

    def test_warnings_property_only_includes_non_info(self):
        # Manually craft a hit with INFO severity
        result = CinemaEvaluation(hits=(
            CinemaRuleHit(
                rule_id="test.info",
                severity=Severity.INFO,
                message="info",
                field="x",
                suggestion="y",
            ),
            CinemaRuleHit(
                rule_id="test.warning",
                severity=Severity.WARNING,
                message="warning",
                field="x",
                suggestion="y",
            ),
        ))
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("test.warning", result.warnings[0])


class ShotValidatorIntegrationTests(unittest.TestCase):
    """The cinema pass must be wired into validate_shot_plan and
    surface as warnings (never as errors)."""

    def _make_shot(self, **overrides) -> ShotPlan:
        defaults = dict(
            shot_id="shot-test-1",
            index=0,
            duration_sec=8.0,
            skill_type="short_film",
            scene_goal="a knight checks his phone before the joust",
            subjects_on_screen=[],
            spatial_setup="open courtyard",
            environment="castle courtyard",
            visual_style="cinematic",
            lighting="low key, blown out windows",
            mood="tense",
            action_beats=["the knight stands", "checks his phone"],
            camera_plan=CameraPlan(
                framing="medium shot",
                angle="eye level",
                movement="static",
                movement_intensity="static",
                lens_feel="35mm",
            ),
            audio_plan=AudioPlan(mode="ambient_only"),
            ending_beat="the knight pockets the phone",
        )
        defaults.update(overrides)
        return ShotPlan(**defaults)

    def test_validate_appends_cinema_warnings_without_failing(self):
        shot = self._make_shot()
        result = validate_shot_plan(shot)
        # The shot is structurally valid (no errors) — cinema pass must
        # not flip it to invalid.
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])
        # The cinema pass must have flagged at least one warning
        # (smartphone in medieval era + lighting contradiction).
        cinema_warnings = [w for w in result.warnings if w.startswith("[cinema:")]
        self.assertGreaterEqual(len(cinema_warnings), 1)

    def test_validate_clean_shot_has_no_cinema_warnings(self):
        shot = self._make_shot(
            shot_id="shot-clean",
            scene_goal="a quiet morning in the field",
            environment="rural pasture",
            lighting="soft golden hour",
            subjects_on_screen=[
                SubjectRef(
                    visual_description="a farmer in a linen shirt and wool vest",
                    wardrobe="linen shirt, wool vest",
                ),
            ],
            action_beats=["a farmer walks to the gate"],
        )
        result = validate_shot_plan(shot)
        self.assertTrue(result.valid)
        cinema_warnings = [w for w in result.warnings if w.startswith("[cinema:")]
        self.assertEqual(cinema_warnings, [])

    def test_cinema_pass_does_not_mutate_shot(self):
        # Defensive: the cinema pass must be read-only on the shot.
        shot = self._make_shot()
        before = repr(shot)
        run_cinema_pass(shot)
        self.assertEqual(repr(shot), before)

    def test_cinema_pass_uses_plan_character_wardrobe(self):
        # When a subject references a character by id, the cinema
        # pass should pick up that character's wardrobe for the
        # anachronism check — not just the per-subject wardrobe.
        char = CharacterProfile(
            id="knight-1",
            physical_description="a tall knight in shining armor",
            wardrobe="chainmail, wool cloak, smartphone",
        )
        shot = self._make_shot(
            scene_goal="the knight prepares for battle",
            subjects_on_screen=[
                SubjectRef(
                    visual_description="a tall knight in shining armor",
                    character_id="knight-1",
                ),
            ],
        )
        plan = ProductionPlan(
            skill_type="short_film",
            shots=[shot],
            title="Test",
            characters=[char],
        )
        result = validate_shot_plan(shot, plan)
        cinema_warnings = [w for w in result.warnings if w.startswith("[cinema:anachronism")]
        self.assertGreaterEqual(len(cinema_warnings), 1)


if __name__ == "__main__":
    unittest.main()
