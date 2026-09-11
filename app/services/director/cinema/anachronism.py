"""Anachronism blocking — flag wardrobe / props that don't match the era."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from .era import Era


@dataclass(frozen=True)
class AnachronismHit:
    prop: str
    category: str  # short kebab-case id used in rule_id (e.g. "modern-phone")
    scope: str  # "wardrobe" or "props" or "environment"
    reason: str
    suggestion: str


# Each tuple is (era, prop_keyword_regex, reason_template, suggestion).
# We match against the lowercase wardrobe string and against each
# prop keyword. We deliberately keep this small and conservative —
# we want false negatives over false positives. Operators can
# disable per-shot via the ShotPlan warnings list anyway.
#
# Tuple shape extended to 5 elements: (era, regex, category, reason,
# suggestion). The category is a short kebab-case string used as
# the rule_id in CinemaRuleHit (cleaner than the regex itself
# showing up in the UI).
_ANACHRONISMS: list[tuple[Era, str, str, str, str]] = [
    # Medieval scenes should not have modern technology
    (Era.MEDIEVAL, r"\bsmartphone\b|\biphone\b|\bandroid phone\b|\bcell phone\b",
     "modern-phone",
     "medieval scene references a modern smartphone",
     "swap for a hand-written letter, messenger, or period-appropriate signaling device"),
    (Era.MEDIEVAL, r"\bcar\b|\bautomobile\b|\btruck\b|\belectric car\b|\btesla\b",
     "modern-vehicle",
     "medieval scene references a modern vehicle",
     "swap for a horse, cart, or period-appropriate transport"),
    (Era.MEDIEVAL, r"\bgoggles\b|\baviator\b|\bsunglasses\b|\bray-?ban\b",
     "modern-eyewear",
     "medieval scene references modern eyewear",
     "swap for a hood, veil, or remove the reference"),
    (Era.MEDIEVAL, r"\baztec print\b|\bdesigner\b|\bhaute couture\b|\brandom brand\b",
     "modern-fashion-brand",
     "medieval scene references modern fashion branding",
     "use period-appropriate fabrics and silhouettes; drop brand references"),
    # Medieval scenes should not be set in future-tech environments
    (Era.MEDIEVAL, r"\bcyberpunk\b|\bdystopian\b|\bhologram\b|\brobot\b|\bcyborg\b|\bwarp drive\b|\bspace station\b|\binterstellar\b",
     "future-tech-environment",
     "medieval scene set in a future-tech environment",
     "move the action to a period-appropriate setting (village, castle, forest)"),
    (Era.MEDIEVAL, r"\bneon\b|\bblinking\b|\bskyscraper\b|\bskyscrapers\b",
     "modern-urban-environment",
     "medieval scene set in a modern urban environment",
     "swap the urban/electric setting for a period-appropriate one (castle, village, marketplace)"),
    # Modern scenes should not have explicit medieval weaponry
    (Era.MODERN, r"\bcrossbow\b|\bjoust(?:ing)?\b|\bdungeon\b",
     "medieval-prop-in-modern",
     "modern scene references medieval prop",
     "swap for the modern analog (firearm, sports field, prison, etc.)"),
    (Era.CONTEMPORARY, r"\bcrossbow\b|\bjoust(?:ing)?\b|\bdungeon\b",
     "medieval-prop-in-contemporary",
     "contemporary scene references medieval prop",
     "swap for the contemporary analog"),
    # Industrial scenes should not have modern technology
    (Era.INDUSTRIAL, r"\bsmartphone\b|\bcell phone\b|\biphone\b|\binternet\b|\bwifi\b",
     "modern-tech-in-industrial",
     "industrial-era scene references modern technology",
     "swap for a telegraph, written note, or messenger"),
    (Era.INDUSTRIAL, r"\belectric car\b|\btesla\b|\bhybrid\b",
     "modern-vehicle-in-industrial",
     "industrial-era scene references modern vehicle",
     "swap for a steam train, horse carriage, or period transport"),
    # Future scenes should not reference very-specific historical items
    # (intentionally lax — future scenes can have anachronistic
    # callbacks; we don't want to over-flag).
]


def check_anachronism(
    *, era: Era, wardrobe: str = "", props: Iterable[str] = (),
    environment: str = "",
) -> Tuple[AnachronismHit, ...]:
    """Return all anachronism hits found in the wardrobe string,
    prop list, and environment description. An empty tuple means
    the shot is era-consistent.

    The `era` argument is what the era detector inferred; we treat
    it as ground truth for this rule. If the user wants to override
    (e.g. a deliberately anachronistic short film), they can mark
    the era as UNKNOWN upstream and the rule becomes a no-op.

    Scope precedence: wardrobe > props > environment. A wardrobe
    hit wins over a prop hit wins over an environment hit for the
    same keyword, because a costume mismatch is the loudest
    inconsistency. We dedupe by (scope, pattern) so the same
    signal doesn't fire three times.
    """
    if era == Era.UNKNOWN or era == Era.FUTURE:
        # No anachronism rule applies to unknown-era or future scenes
        # (future is explicitly exempted — see comment in _ANACHRONISMS).
        return ()

    hits: list[AnachronismHit] = []
    wardrobe_lc = (wardrobe or "").lower()
    environment_lc = (environment or "").lower()
    for rule_era, pattern, category, reason, suggestion in _ANACHRONISMS:
        if rule_era != era:
            continue
        import re
        # Wardrobe wins — emit and skip the other scopes for this
        # pattern. This keeps the warning list short.
        if wardrobe_lc and re.search(pattern, wardrobe_lc):
            hits.append(AnachronismHit(
                prop=pattern,
                category=category,
                scope="wardrobe",
                reason=reason,
                suggestion=suggestion,
            ))
            continue
        # Props: emit one hit per matching prop (multiple distinct
        # props is a real signal — three anachronistic props in one
        # shot is three times the warning, not one).
        prop_emitted = False
        for prop in props:
            if prop and re.search(pattern, prop.lower()):
                hits.append(AnachronismHit(
                    prop=prop,
                    category=category,
                    scope="props",
                    reason=reason,
                    suggestion=suggestion,
                ))
                prop_emitted = True
        if prop_emitted:
            continue
        # Environment is the last-resort scope: a medieval scene
        # whose environment string is "neon cyberpunk city" is
        # anachronistic, but this is the noisiest signal (people
        # often describe a setting with mixed cues), so we treat
        # it as one hit per pattern regardless of how many times
        # the keyword appears in the environment string.
        if environment_lc and re.search(pattern, environment_lc):
            hits.append(AnachronismHit(
                prop=pattern,
                category=category,
                scope="environment",
                reason=reason,
                suggestion=suggestion,
            ))
    return tuple(hits)


__all__ = ["AnachronismHit", "check_anachronism"]
