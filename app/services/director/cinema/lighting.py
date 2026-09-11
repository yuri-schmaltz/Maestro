"""Lighting consistency — flag a shot whose lighting description contradicts itself."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Tuple


@dataclass(frozen=True)
class LightingInconsistency:
    kind: str
    reason: str
    suggestion: str


# Pairs that contradict. Each tuple is (left_keywords, right_keywords,
# reason, suggestion). We flag if BOTH left and right keywords are
# present in the lighting description.
_INCONSISTENCIES: list[tuple[tuple[str, ...], tuple[str, ...], str, str]] = [
    # Low-key lighting implies controlled shadow contrast; blown out
    # implies overexposure. They cannot both describe the same shot.
    (
        ("low key", "low-key", "chiaroscuro", "deep shadow", "hard shadow"),
        ("blown out", "blown-out", "overexposed", "white-out", "white out"),
        "low-key lighting contradicts blown-out exposure",
        "pick one direction: either deepen the shadow OR add fill light, but not both",
    ),
    # Hard light + soft diffusion is a contradiction
    (
        ("hard light", "harsh light", "direct sunlight", "single-source"),
        ("soft box", "diffused", "soft fill", "silk diffusion", "soft bounce"),
        "hard light contradicts soft diffusion in the same shot",
        "either commit to hard light for contrast OR add diffusion for softness, not both",
    ),
    # High-key + heavy shadow is contradictory
    (
        ("high key", "high-key", "even lighting", "flat lighting"),
        ("deep shadow", "heavy shadow", "dramatic shadow", "noir shadow"),
        "high-key lighting contradicts heavy shadow",
        "high-key means low contrast; deep shadow is high contrast. Pick one mood.",
    ),
    # Noon sun + moody twilight
    (
        ("noon", "midday sun", "overhead sun", "high sun"),
        ("twilight", "blue hour", "dusk", "moonlight"),
        "lighting description spans noon and twilight in the same shot",
        "decide a single time-of-day; the shot can't be noon and dusk simultaneously",
    ),
]


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    for keyword in keywords:
        # word-boundary-ish match: keyword surrounded by start/end or
        # non-letter characters. This avoids 'sun' matching inside
        # 'sunset' while still allowing 'noon sun' as a phrase.
        if re.search(r"(^|[^a-z0-9])" + re.escape(keyword) + r"(?=$|[^a-z0-9])", text):
            return True
    return False


def check_lighting_consistency(lighting: str) -> Tuple[LightingInconsistency, ...]:
    """Return all lighting-inconsistency hits found in the description.

    An empty tuple means the lighting is self-consistent. We do not
    flag single-keyword descriptions (a shot described as just 'low
    key' is fine) — only descriptions that include BOTH sides of a
    contradiction.
    """
    if not lighting:
        return ()
    text = lighting.lower()
    hits: list[LightingInconsistency] = []
    for left, right, reason, suggestion in _INCONSISTENCIES:
        if _has_any(text, left) and _has_any(text, right):
            # Pick a stable kind string from the first matching left
            # keyword. We use the rule-pair index for stability.
            hits.append(LightingInconsistency(
                kind=f"contradicts_{left[0].replace(' ', '_')}_vs_{right[0].replace(' ', '_')}",
                reason=reason,
                suggestion=suggestion,
            ))
    return tuple(hits)


__all__ = ["LightingInconsistency", "check_lighting_consistency"]
