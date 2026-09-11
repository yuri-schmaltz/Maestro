"""Anachronism blocking — flag wardrobe / props that don't match the era."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from .era import Era


@dataclass(frozen=True)
class AnachronismHit:
    prop: str
    scope: str  # "wardrobe" or "props"
    reason: str
    suggestion: str


# Each tuple is (era, prop_keyword_regex, reason_template, suggestion).
# We match against the lowercase wardrobe string and against each
# prop keyword. We deliberately keep this small and conservative —
# we want false negatives over false positives. Operators can
# disable per-shot via the ShotPlan warnings list anyway.
_ANACHRONISMS: list[tuple[Era, str, str, str]] = [
    # Medieval scenes should not have modern technology
    (Era.MEDIEVAL, r"\bsmartphone\b|\biphone\b|\bandroid phone\b|\bcell phone\b",
     "medieval scene references a modern smartphone",
     "swap for a hand-written letter, messenger, or period-appropriate signaling device"),
    (Era.MEDIEVAL, r"\bcar\b|\bautomobile\b|\btruck\b|\belectric car\b|\btesla\b",
     "medieval scene references a modern vehicle",
     "swap for a horse, cart, or period-appropriate transport"),
    (Era.MEDIEVAL, r"\bgoggles\b|\baviator\b|\bsunglasses\b|\bray-?ban\b",
     "medieval scene references modern eyewear",
     "swap for a hood, veil, or remove the reference"),
    (Era.MEDIEVAL, r"\baztec print\b|\bdesigner\b|\bhaute couture\b|\brandom brand\b",
     "medieval scene references modern fashion branding",
     "use period-appropriate fabrics and silhouettes; drop brand references"),
    # Modern scenes should not have explicit medieval weaponry
    (Era.MODERN, r"\bcrossbow\b|\bjoust(?:ing)?\b|\bdungeon\b",
     "modern scene references medieval prop",
     "swap for the modern analog (firearm, sports field, prison, etc.)"),
    (Era.CONTEMPORARY, r"\bcrossbow\b|\bjoust(?:ing)?\b|\bdungeon\b",
     "contemporary scene references medieval prop",
     "swap for the contemporary analog"),
    # Industrial scenes should not have modern technology
    (Era.INDUSTRIAL, r"\bsmartphone\b|\bcell phone\b|\biphone\b|\binternet\b|\bwifi\b",
     "industrial-era scene references modern technology",
     "swap for a telegraph, written note, or messenger"),
    (Era.INDUSTRIAL, r"\belectric car\b|\btesla\b|\bhybrid\b",
     "industrial-era scene references modern vehicle",
     "swap for a steam train, horse carriage, or period transport"),
    # Future scenes should not reference very-specific historical items
    # (intentionally lax — future scenes can have anachronistic
    # callbacks; we don't want to over-flag).
]


def check_anachronism(
    *, era: Era, wardrobe: str = "", props: Iterable[str] = (),
) -> Tuple[AnachronismHit, ...]:
    """Return all anachronism hits found in the wardrobe string and
    prop list. An empty tuple means the shot is era-consistent.

    The `era` argument is what the era detector inferred; we treat
    it as ground truth for this rule. If the user wants to override
    (e.g. a deliberately anachronistic short film), they can mark
    the era as UNKNOWN upstream and the rule becomes a no-op.
    """
    if era == Era.UNKNOWN or era == Era.FUTURE:
        # No anachronism rule applies to unknown-era or future scenes
        # (future is explicitly exempted — see comment in _ANACHRONISMS).
        return ()

    hits: list[AnachronismHit] = []
    wardrobe_lc = (wardrobe or "").lower()
    for rule_era, pattern, reason, suggestion in _ANACHRONISMS:
        if rule_era != era:
            continue
        import re
        if wardrobe_lc and re.search(pattern, wardrobe_lc):
            hits.append(AnachronismHit(
                prop=pattern,
                scope="wardrobe",
                reason=reason,
                suggestion=suggestion,
            ))
        for prop in props:
            if prop and re.search(pattern, prop.lower()):
                hits.append(AnachronismHit(
                    prop=prop,
                    scope="props",
                    reason=reason,
                    suggestion=suggestion,
                ))
    return tuple(hits)


__all__ = ["AnachronismHit", "check_anachronism"]
