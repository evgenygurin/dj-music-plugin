"""KeyInterchange — advanced Camelot wheel key compatibility for techno DJs.

Extends the basic ±1 rule on the Camelot wheel with:
- Modal interchange (relative major/minor = ±3 on wheel)
- Energy boost (+2, +7 on wheel = rising energy)
- Energy release (-2, -5 on wheel = tension release)
- Perfect fourth/fifth (musically consonant, ±1 or ±5)
- Chromatic mediant (bold, ±4 — used in peak-time techno)
- Tritone (dark, ±6 — used in industrial/raw techno)

Also handles key detection confidence weighting:
- L5 keys (essentia Krumhansl-Kessler) have higher confidence
- Keys with low confidence get wider tolerance in compatibility checks
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KeyRelation(Enum):
    SAME = "same"  # identical key — safest, seamless
    PERFECT = "perfect"  # ±1 on wheel — smooth, no energy change
    ENERGY_UP = "energy_up"  # +2, +7 — rising energy feeling
    ENERGY_DOWN = "energy_down"  # -2, -5 — releasing tension
    MODAL = "modal"  # relative major/minor (±3) — modal shift
    CHROMATIC = "chromatic"  # ±4 — bold, attention-grabbing
    TRITONE = "tritone"  # ±6 — dark, industrial, risky
    CLASH = "clash"  # avoid unless intentional dissonance


CAMELOT_NAMES: list[str] = [
    "8B",
    "7B",
    "7A",
    "8A",
    "9A",
    "9B",
    "10B",
    "10A",
    "11A",
    "11B",
    "12B",
    "12A",
    "1A",
    "1B",
    "2B",
    "2A",
    "3A",
    "3B",
    "4B",
    "4A",
    "5A",
    "5B",
    "6B",
    "6A",
]


def key_to_camelot(key_code: int) -> str:
    """Convert 0-23 key code to Camelot notation (e.g. 13 → '1B')."""
    if 0 <= key_code < 24:
        return CAMELOT_NAMES[key_code]
    return "?"


def camelot_distance(a: int, b: int) -> int:
    """Distance on the 24-position Camelot wheel."""
    diff = abs(a - b)
    return min(diff, 24 - diff)


@dataclass(frozen=True, slots=True)
class KeyRelationResult:
    """Analysis of the harmonic relationship between two keys."""

    from_key: int
    to_key: int
    from_camelot: str
    to_camelot: str
    distance: int
    relation: KeyRelation
    compatibility_score: float  # 0.0 = clash, 1.0 = perfect
    description: str


def analyze_key_relation(
    from_key: int,
    to_key: int,
    from_confidence: float = 1.0,
    to_confidence: float = 1.0,
) -> KeyRelationResult:
    """Analyze the harmonic relationship between two keys."""
    dist = camelot_distance(from_key, to_key)

    if dist == 0:
        relation = KeyRelation.SAME
        score = 1.0
        desc = "Same key — seamless, zero harmonic tension"
    elif dist == 1:
        relation = KeyRelation.PERFECT
        score = 0.95
        desc = "Adjacent on Camelot — smooth, minimal energy change"
    elif dist in (2, 10):
        relation = KeyRelation.ENERGY_UP
        score = 0.85
        desc = "Energy boost (+2/+7) — felt as rising intensity"
    elif dist in (5, 7):
        relation = KeyRelation.ENERGY_DOWN
        score = 0.80
        desc = "Energy release (-2/-5) — felt as tension releasing"
    elif dist == 3:
        relation = KeyRelation.MODAL
        score = 0.75
        desc = "Modal interchange (relative major/minor) — mood shift"
    elif dist == 4 or dist == 8:
        relation = KeyRelation.CHROMATIC
        score = 0.55
        desc = "Chromatic mediant — bold, dramatic shift"
    elif dist == 6:
        relation = KeyRelation.TRITONE
        score = 0.35
        desc = "Tritone — dark, industrial character"
    else:
        relation = KeyRelation.CLASH
        score = 0.20
        desc = f"Harsh dissonance ({dist} steps) — avoid unless intentional"

    # Confidence weighting: low-confidence keys get higher tolerance
    confidence_factor = min(from_confidence, to_confidence)
    if confidence_factor < 0.5:
        score = max(score, 0.5)  # don't be too harsh when detection is uncertain

    return KeyRelationResult(
        from_key=from_key,
        to_key=to_key,
        from_camelot=key_to_camelot(from_key),
        to_camelot=key_to_camelot(to_key),
        distance=dist,
        relation=relation,
        compatibility_score=score,
        description=desc,
    )


# ── Subgenre-specific key preferences ──────────────────────

SUBGENRE_KEY_PREFERENCES: dict[str, dict[str, float]] = {
    "dub_techno": {
        "same": 1.0,
        "perfect": 0.9,
        "modal": 0.8,
        "energy_up": 0.4,
        "energy_down": 0.7,
        "chromatic": 0.2,
        "tritone": 0.1,
    },
    "industrial_techno": {
        "same": 0.5,
        "perfect": 0.6,
        "modal": 0.5,
        "energy_up": 0.8,
        "energy_down": 0.6,
        "chromatic": 0.7,
        "tritone": 0.6,  # industrial LOVES dissonance
    },
    "hard_techno": {
        "same": 0.6,
        "perfect": 0.7,
        "modal": 0.5,
        "energy_up": 0.9,
        "energy_down": 0.5,
        "chromatic": 0.6,
        "tritone": 0.4,
    },
    "hypnotic_techno": {
        "same": 0.9,
        "perfect": 0.95,
        "modal": 0.85,
        "energy_up": 0.5,
        "energy_down": 0.6,
        "chromatic": 0.3,
        "tritone": 0.1,
    },
    "peak_time_techno": {
        "same": 0.7,
        "perfect": 0.8,
        "modal": 0.6,
        "energy_up": 0.85,
        "energy_down": 0.55,
        "chromatic": 0.5,
        "tritone": 0.3,
    },
    "acid_techno": {
        "same": 0.5,
        "perfect": 0.6,
        "modal": 0.5,
        "energy_up": 0.7,
        "energy_down": 0.5,
        "chromatic": 0.7,
        "tritone": 0.5,  # acid = weird is good
    },
    "driving_techno": {
        "same": 0.7,
        "perfect": 0.8,
        "modal": 0.6,
        "energy_up": 0.85,
        "energy_down": 0.5,
        "chromatic": 0.4,
        "tritone": 0.2,
    },
    "raw_techno": {
        "same": 0.4,
        "perfect": 0.5,
        "modal": 0.4,
        "energy_up": 0.7,
        "energy_down": 0.5,
        "chromatic": 0.7,
        "tritone": 0.7,  # raw = embrace the noise
    },
}


def subgenre_key_score(
    from_key: int,
    to_key: int,
    subgenre: str | None = None,
) -> float:
    """Key compatibility weighted by subgenre preferences.

    Industrial/raw gets higher scores for dissonant relations.
    Dub/hypnotic gets penalized for harsh key changes.
    """
    result = analyze_key_relation(from_key, to_key)
    base_score = result.compatibility_score

    if subgenre:
        prefs = SUBGENRE_KEY_PREFERENCES.get(subgenre.lower().replace(" ", "_"))
        if prefs:
            relation_key = result.relation.value
            weight = prefs.get(relation_key, 0.5)
            base_score = base_score * 0.3 + weight * 0.7

    return base_score
