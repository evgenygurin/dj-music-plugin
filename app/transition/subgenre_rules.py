# app/transition/subgenre_rules.py
"""Subgenre-specific transition rules for techno pair classification."""

from __future__ import annotations

from enum import StrEnum

from app.core.constants import TechnoSubgenre
from app.transition.recipe import TransitionType

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


# Bar clamps per subgenre pair. Research-calibrated:
# - Hard: minimum 8 (not 0) — hard cuts without micro-ramp cause clicks
# - Ambient: max 64 (not 128) — ultra-long blends lose listener attention
# - Hypnotic: max 32 (Ben Klock style: long but not infinite)
# - Sources: Kim ISMIR 2020 (transition length histogram peaks at 8/16/32),
#   professional DJ practice, Mosaikbox 2024 (16 bars standard)
_BAR_CLAMPS: dict[SubgenrePairType, tuple[int, int]] = {
    SubgenrePairType.AMBIENT_PAIR: (32, 64),  # was (32, 128)
    SubgenrePairType.HARD_PAIR: (4, 16),  # was (0, 8) — need micro-ramp
    SubgenrePairType.HYPNOTIC_PAIR: (16, 32),  # was (16, 64)
    SubgenrePairType.ACID_PAIR: (8, 32),  # unchanged — matches research
    SubgenrePairType.MELODIC_PAIR: (16, 48),  # was (16, 64)
    SubgenrePairType.MIXED_PAIR: (8, 48),  # was (0, 64)
}


def clamp_bars(bars: int, pair_type: SubgenrePairType) -> int:
    """Clamp transition bar count based on subgenre pair rules."""
    lo, hi = _BAR_CLAMPS.get(pair_type, (0, 64))
    return max(lo, min(bars, hi))


_PREFERRED_TYPES: dict[SubgenrePairType, tuple[TransitionType, ...]] = {
    SubgenrePairType.AMBIENT_PAIR: (TransitionType.DISSOLVE, TransitionType.LONG_BLEND),
    SubgenrePairType.HARD_PAIR: (
        TransitionType.CUT,
        TransitionType.DROP_SWAP,
        TransitionType.FILTER_SWEEP,
    ),
    SubgenrePairType.ACID_PAIR: (TransitionType.FILTER_SWEEP,),
    SubgenrePairType.MELODIC_PAIR: (TransitionType.EQ_BLEND, TransitionType.LONG_BLEND),
    SubgenrePairType.HYPNOTIC_PAIR: (TransitionType.NEURAL_MIX_BLEND, TransitionType.EQ_BLEND),
    SubgenrePairType.MIXED_PAIR: (TransitionType.EQ_BLEND, TransitionType.FILTER_SWEEP),
}


def preferred_type_for_pair(pair_type: SubgenrePairType) -> tuple[TransitionType, ...]:
    """Return preferred transition types for a subgenre pair."""
    return _PREFERRED_TYPES.get(pair_type, (TransitionType.EQ_BLEND,))
