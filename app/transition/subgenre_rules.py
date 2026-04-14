"""Subgenre-specific transition rules — pair classification and bar clamping.

``SubgenrePairType`` lives in ``types.py``; this module provides the
classification and clamping functions used by ``recipe_decision.py``
and ``selector.py``.
"""

from __future__ import annotations

from app.core.constants import TechnoSubgenre
from app.transition.types import SubgenrePairType

_AMBIENT = frozenset({TechnoSubgenre.AMBIENT_DUB, TechnoSubgenre.DUB_TECHNO})
_HARD = frozenset({TechnoSubgenre.INDUSTRIAL, TechnoSubgenre.HARD_TECHNO, TechnoSubgenre.RAW})
_MELODIC = frozenset(
    {TechnoSubgenre.MELODIC_DEEP, TechnoSubgenre.PROGRESSIVE, TechnoSubgenre.DETROIT}
)
_HYPNOTIC = frozenset({TechnoSubgenre.HYPNOTIC, TechnoSubgenre.MINIMAL})


def classify_pair(
    mood_a: TechnoSubgenre | str | None,
    mood_b: TechnoSubgenre | str | None,
) -> SubgenrePairType:
    """Classify a track pair by combined subgenre context."""
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


# Bar clamps per subgenre pair (Kim et al. ISMIR 2020, Mosaikbox 2024, professional DJ practice).
_BAR_CLAMPS: dict[SubgenrePairType, tuple[int, int]] = {
    SubgenrePairType.AMBIENT_PAIR: (32, 64),
    SubgenrePairType.HARD_PAIR: (4, 16),
    SubgenrePairType.HYPNOTIC_PAIR: (16, 32),
    SubgenrePairType.ACID_PAIR: (8, 32),
    SubgenrePairType.MELODIC_PAIR: (16, 48),
    SubgenrePairType.MIXED_PAIR: (8, 48),
}


def clamp_bars(bars: int, pair_type: SubgenrePairType) -> int:
    """Clamp transition bar count to subgenre-appropriate range."""
    lo, hi = _BAR_CLAMPS.get(pair_type, (0, 64))
    return max(lo, min(bars, hi))
