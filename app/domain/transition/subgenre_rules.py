"""Subgenre-specific transition rules for techno pair classification.

Reduced post Neural Mix refactor: the legacy ``preferred_type_for_pair``
table is gone — the picker (``app/domain/transition/picker.py``)
encodes pair-aware preferences inline against the seven Neural Mix
transitions. ``classify_pair`` + ``clamp_bars`` remain as pure helpers.
"""

from __future__ import annotations

from enum import StrEnum

from app.shared.constants import TechnoSubgenre

_AMBIENT = frozenset({TechnoSubgenre.AMBIENT_DUB, TechnoSubgenre.DUB_TECHNO})
_HARD = frozenset({TechnoSubgenre.INDUSTRIAL, TechnoSubgenre.HARD_TECHNO, TechnoSubgenre.RAW})
_MELODIC = frozenset(
    {TechnoSubgenre.MELODIC_DEEP, TechnoSubgenre.PROGRESSIVE, TechnoSubgenre.DETROIT}
)
_HYPNOTIC = frozenset({TechnoSubgenre.HYPNOTIC, TechnoSubgenre.MINIMAL})


class SubgenrePairType(StrEnum):
    AMBIENT_PAIR = "ambient_pair"
    HARD_PAIR = "hard_pair"
    ACID_PAIR = "acid_pair"
    MELODIC_PAIR = "melodic_pair"
    HYPNOTIC_PAIR = "hypnotic_pair"
    MIXED_PAIR = "mixed_pair"


def classify_pair(
    mood_a: TechnoSubgenre | str | None,
    mood_b: TechnoSubgenre | str | None,
) -> SubgenrePairType:
    """Classify a pair of tracks by their combined subgenre context."""
    if mood_a is None or mood_b is None:
        return SubgenrePairType.MIXED_PAIR

    try:
        a = TechnoSubgenre(mood_a) if isinstance(mood_a, str) else mood_a
    except ValueError:
        return SubgenrePairType.MIXED_PAIR
    try:
        b = TechnoSubgenre(mood_b) if isinstance(mood_b, str) else mood_b
    except ValueError:
        return SubgenrePairType.MIXED_PAIR

    if a in _AMBIENT and b in _AMBIENT:
        return SubgenrePairType.AMBIENT_PAIR
    if a in _HARD and b in _HARD:
        return SubgenrePairType.HARD_PAIR
    if a == TechnoSubgenre.ACID or b == TechnoSubgenre.ACID:
        return SubgenrePairType.ACID_PAIR
    if a in _MELODIC and b in _MELODIC:
        return SubgenrePairType.MELODIC_PAIR
    if a in _HYPNOTIC and b in _HYPNOTIC:
        return SubgenrePairType.HYPNOTIC_PAIR
    return SubgenrePairType.MIXED_PAIR


# Per-pair bar clamps used by templates to scale the default 32-bar
# Neural Mix transition window. AMBIENT pairs want long blends; HARD
# pairs want short stabs.
_BAR_CLAMPS: dict[SubgenrePairType, tuple[int, int]] = {
    SubgenrePairType.AMBIENT_PAIR: (32, 128),
    SubgenrePairType.HARD_PAIR: (4, 16),
    SubgenrePairType.HYPNOTIC_PAIR: (16, 64),
    SubgenrePairType.ACID_PAIR: (8, 32),
    SubgenrePairType.MELODIC_PAIR: (16, 64),
    SubgenrePairType.MIXED_PAIR: (8, 64),
}


def clamp_bars(bars: int, pair_type: SubgenrePairType) -> int:
    """Clamp transition bar count based on subgenre pair rules."""
    lo, hi = _BAR_CLAMPS.get(pair_type, (8, 64))
    return max(lo, min(bars, hi))
