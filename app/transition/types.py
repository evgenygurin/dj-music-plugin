"""Shared enums for the transition subsystem.

Single source of truth for all transition-related enum types.
Imported by recipe.py, subgenre_rules.py, selector.py, and consumers.
No dependencies on other app.transition modules.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class Stem(StrEnum):
    """djay Pro AI Neural Mix stem lanes."""

    DRUMS = "drums"
    BASS = "bass"
    HARMONICS = "harmonics"
    VOCALS = "vocals"


class StemAction(StrEnum):
    """Automation action applied to a stem lane."""

    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CUT = "cut"
    SWAP = "swap"
    MUTE = "mute"
    SOLO = "solo"


class SubgenrePairType(StrEnum):
    """Techno subgenre classification for a track pair."""

    AMBIENT_PAIR = "ambient_pair"
    HARD_PAIR = "hard_pair"
    ACID_PAIR = "acid_pair"
    MELODIC_PAIR = "melodic_pair"
    HYPNOTIC_PAIR = "hypnotic_pair"
    MIXED_PAIR = "mixed_pair"


class TransitionIntent(IntEnum):
    """Context-aware intent for the transition (set position + energy arc)."""

    MAINTAIN = 0
    RAMP_UP = 1
    COOL_DOWN = 2
    CONTRAST = 3
