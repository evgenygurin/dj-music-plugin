"""Pydantic domain models for the transition subsystem.

All value objects in one place — no scattered single-class files.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.constants import NeuralMixCrossfaderFX, SectionType
from app.transition.types import StemAction  # noqa: F401 — re-exported for convenience

# Section types where percussion dominates and harmonic scoring is relaxed.
# (Pioneer DJ blog; Vande Veire & De Bie, JASMP 2018)
_DRUM_ONLY_SECTIONS: frozenset[SectionType] = frozenset(
    {SectionType.INTRO, SectionType.OUTRO, SectionType.SUSTAIN, SectionType.AMBIENT}
)


class TransitionScore(BaseModel):
    """6-component quality score for a track-to-track transition."""

    model_config = ConfigDict(frozen=True)

    bpm: float = 0.0
    harmonic: float = 0.0
    energy: float = 0.0
    spectral: float = 0.0
    groove: float = 0.0
    timbral: float = 0.0
    overall: float = 0.0
    hard_reject: bool = False
    reject_reason: str | None = None
    vocal_conflict: bool = False  # both tracks have vocals → mute outgoing
    drum_conflict: bool = False  # drum patterns differ → attenuate incoming drums


class SectionContext(BaseModel):
    """Structural context for the mix-out / mix-in windows of a transition.

    None fields mean "no section data" — scoring falls back to full-track formula.
    """

    model_config = ConfigDict(frozen=True)

    from_section: SectionType | None = None
    to_section: SectionType | None = None

    @property
    def is_drum_only_pair(self) -> bool:
        """True when both sides are percussion-only sections."""
        if self.from_section is None or self.to_section is None:
            return False
        return self.from_section in _DRUM_ONLY_SECTIONS and self.to_section in _DRUM_ONLY_SECTIONS


class ConstraintResult(BaseModel):
    """Result of hard-constraint and soft-conflict checks."""

    model_config = ConfigDict(frozen=True)

    rejection: TransitionScore | None = None  # non-None → hard reject
    vocal_conflict: bool = False
    drum_conflict: bool = False


class TransitionRecommendation(BaseModel):
    """djay Pro AI Neural Mix FX recommendation for a track pair.

    We recommend WHICH crossfader preset to use — djay Pro AI handles
    the actual stem automation automatically.
    """

    model_config = ConfigDict(frozen=True)

    fx_type: NeuralMixCrossfaderFX
    confidence: float = 0.75
    reason: str = ""
    alt_fx_type: NeuralMixCrossfaderFX | None = None

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
