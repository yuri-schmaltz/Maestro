"""Era detection — given a scene's textual cues, infer the era."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional


class Era(str, Enum):
    """Coarse-grained era buckets. Order matters: PREHISTORIC is the
    earliest; FUTURE is the latest. The detector picks the first era
    that matches in priority order."""
    PREHISTORIC = "prehistoric"
    MEDIEVAL = "medieval"   # ~500–1500 CE
    EARLY_MODERN = "early_modern"  # 1500–1800
    INDUSTRIAL = "industrial"  # 1800–1900
    MODERN = "modern"      # 1900–2000
    CONTEMPORARY = "contemporary"  # 2000–present
    FUTURE = "future"
    UNKNOWN = "unknown"


# Each era maps to a list of regex patterns. The first era with any
# match wins. Patterns are case-insensitive.
_ERA_PATTERNS: list[tuple[Era, tuple[str, ...]]] = [
    (Era.PREHISTORIC, (
        r"\bcaveman\b", r"\bdinosaur\b", r"\bcavemen\b",
        r"\bstone age\b", r"\bmammoth\b", r"\bice age\b",
    )),
    (Era.MEDIEVAL, (
        r"\bmedieval\b", r"\bknight\b", r"\bcastle\b", r"\bcastle walls\b",
        r"\bkingdom\b", r"\bqueen\b", r"\bpeasant\b", r"\bsword\b",
        r"\bcrossbow\b", r"\bcrown\b", r"\bdungeon\b", r"\bjoust\b",
        r"\bcourt jester\b", r"\bplague doctor\b", r"\bcrusade\b",
    )),
    (Era.EARLY_MODERN, (
        r"\bcolony\b", r"\bcolonial\b", r"\bpirate\b", r"\bmerchant ship\b",
        r"\bcorsair\b", r"\b16th century\b", r"\b17th century\b",
        r"\b18th century\b", r"\bhorse-drawn\b", r"\bgaslight\b",
    )),
    (Era.INDUSTRIAL, (
        r"\bindustrial revolution\b", r"\bfactory\b", r"\bsteam engine\b",
        r"\bsteam train\b", r"\bloom\b", r"\b19th century\b",
        r"\bcotton mill\b", r"\bgas lamp\b", r"\bVictorian\b",
    )),
    (Era.FUTURE, (
        r"\bcyberpunk\b", r"\bdystopian\b", r"\brobot\b", r"\brobotics\b",
        r"\bhologram\b", r"\bwarp drive\b", r"\bspace station\b",
        r"\bartificial intelligence\b", r"\bcyborg\b", r"\binterstellar\b",
        r"\btime travel\b", r"\b22nd century\b", r"\b23rd century\b",
    )),
    (Era.CONTEMPORARY, (
        r"\bsmartphone\b", r"\biphone\b", r"\bandroid\b", r"\bcell phone\b",
        r"\bmobile phone\b", r"\bwifi\b", r"\bwireless\b",
        r"\binternet\b", r"\bstreaming\b", r"\binfluencer\b",
        r"\buber\b", r"\bairpods\b", r"\b21st century\b",
    )),
    (Era.MODERN, (
        r"\bmodern\b", r"\b20th century\b", r"\b1950s\b", r"\b1960s\b",
        r"\b1970s\b", r"\b1980s\b", r"\b1990s\b", r"\bcold war\b",
        r"\bvhs\b", r"\bwalkman\b", r"\bcassette\b",
    )),
]


@dataclass(frozen=True)
class EraDetection:
    era: Era
    matched_pattern: str
    matched_field: str  # which field produced the match (scene_goal/environment)


def detect_era(*, scene_goal: str = "", environment: str = "") -> EraDetection:
    """Scan scene_goal then environment for era markers. The first
    era in priority order with any match wins; we don't try to
    reconcile conflicting signals across fields — a scene where the
    environment says medieval and the goal says 'the protagonist
    uses their smartphone' is exactly the anachronism we want the
    next rule to flag, not something the era detector should paper
    over by picking 'modern' for the whole shot."""
    combined = f"{scene_goal}\n{environment}".lower()
    if not combined.strip():
        return EraDetection(era=Era.UNKNOWN, matched_pattern="", matched_field="")
    for era, patterns in _ERA_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, combined):
                field = "scene_goal" if re.search(pattern, scene_goal.lower()) else "environment"
                return EraDetection(era=era, matched_pattern=pattern, matched_field=field)
    return EraDetection(era=Era.UNKNOWN, matched_pattern="", matched_field="")


__all__ = ["Era", "EraDetection", "detect_era"]
