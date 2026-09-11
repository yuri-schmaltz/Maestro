"""
Cinema Rules — Director v2 screenplay post-pass evaluator.

Pattern lifted from directo_studio Phase 3 (cinema engine). Directo's
cinema engine ships 19 rules (era detection, anachronism blocking,
lighting consistency, costume era check, prop era check, etc.) that
the director agent runs against the screenplay before shot
breakdown. This module ports the rules that have a real fit with
Maestro's Director v2 pipeline:

  1. Era detection — classify the implied era of a scene from text
     cues (medieval, modern, future, etc.).
  2. Anachronism blocking — flag props, costumes, or technology that
     don't match the detected era.
  3. Lighting consistency — flag a shot where the lighting direction
     described contradicts itself (e.g. "low key" + "blown out").

Other Directo rules (script parser grammar, shot sequence grammar)
are NOT ported: Maestro's Director v2 already has structured shot
planning via the planners/, and the screenplay pass is plain prose,
not a parsed AST.

The cinema pass is a SOFT evaluator: it never blocks the pipeline.
A scene with a flagged rule proceeds; the rule just becomes a
`warning` on the ShotPlan so the operator can see it in the
DirectorDashboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional

from .era import detect_era, Era
from .anachronism import check_anachronism, AnachronismHit
from .lighting import check_lighting_consistency, LightingInconsistency


class Severity(str, Enum):
    """How loud a violation should be. Soft by design — the pass is
    advisory; nothing blocks the pipeline."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class CinemaRuleHit:
    """A single rule violation. Immutable so the result is safe to
    pass to the ShotPlan warnings list and compare across runs."""
    rule_id: str
    severity: Severity
    message: str
    field: str  # which ShotPlan field the violation concerns
    suggestion: str  # human-readable remediation

    def as_warning(self) -> str:
        return f"[cinema:{self.rule_id}] {self.message} — {self.suggestion}"


@dataclass(frozen=True)
class CinemaEvaluation:
    """Aggregate result of a cinema pass on a single ShotPlan."""
    hits: tuple[CinemaRuleHit, ...] = field(default_factory=tuple)

    @property
    def has_warnings(self) -> bool:
        return any(h.severity != Severity.INFO for h in self.hits)

    @property
    def warnings(self) -> list[str]:
        return [h.as_warning() for h in self.hits if h.severity != Severity.INFO]

    def merge(self, other: "CinemaEvaluation") -> "CinemaEvaluation":
        return CinemaEvaluation(hits=self.hits + other.hits)


def evaluate_shot(*, scene_goal: str = "", environment: str = "", lighting: str = "", wardrobe: str = "", props: Iterable[str] = ()) -> CinemaEvaluation:
    """Run all cinema rules against a shot's textual fields.

    Each rule is a pure function that returns either no hits or a
    tuple of CinemaRuleHit. The aggregator concatenates them.

    Args:
        scene_goal: Shot's scene goal text (what happens in the shot).
        environment: Where the shot takes place.
        lighting: Lighting description for the shot.
        wardrobe: Costume / wardrobe description.
        props: Iterable of named props referenced in the shot.

    Returns:
        CinemaEvaluation with all rule hits found. Empty hits tuple
        means the shot is cinema-clean.
    """
    # 1. Era detection. We use the scene_goal + environment as the
    #    primary signal — wardrobe and props are downstream cues that
    #    the anachronism rule consumes, not signals for the era
    #    detector itself (otherwise a historical scene with a present-
    #    day narrator would mis-classify as modern).
    era_detection = detect_era(scene_goal=scene_goal, environment=environment)
    # The downstream rules take the bare Era enum, not the detection
    # object. Pull .era off the detection.
    era = era_detection.era

    hits: list[CinemaRuleHit] = []

    # 2. Anachronism: does the wardrobe / props list / environment
    #    description contain anything that contradicts the detected
    #    era? Environment is the noisiest signal (mixed cues) so the
    #    check_anachronism function scopes it as a last-resort hit.
    anachronisms = check_anachronism(
        era=era,
        wardrobe=wardrobe,
        props=tuple(props),
        environment=environment,
    )
    for hit in anachronisms:
        # Map anachronism scope → ShotPlan field name. The dashboard
        # shows the field in the warning row, so it has to be the
        # ShotPlan field that triggered the violation, not the
        # internal scope name.
        scope_to_field = {
            "wardrobe": "wardrobe",
            "props": "props",
            "environment": "environment",
        }
        hits.append(CinemaRuleHit(
            rule_id=f"anachronism.{hit.category}",
            severity=Severity.WARNING,
            message=hit.reason,
            field=scope_to_field.get(hit.scope, hit.scope),
            suggestion=hit.suggestion,
        ))

    # 3. Lighting consistency: the lighting description must be
    #    internally consistent (e.g. "low key" + "blown out" is a
    #    contradiction; one implies controlled contrast, the other
    #    implies overexposure).
    inconsistencies = check_lighting_consistency(lighting)
    for hit in inconsistencies:
        hits.append(CinemaRuleHit(
            rule_id=f"lighting.{hit.kind}",
            severity=Severity.WARNING,
            message=hit.reason,
            field="lighting",
            suggestion=hit.suggestion,
        ))

    return CinemaEvaluation(hits=tuple(hits))


__all__ = [
    "CinemaRuleHit",
    "CinemaEvaluation",
    "Era",
    "Severity",
    "evaluate_shot",
]
