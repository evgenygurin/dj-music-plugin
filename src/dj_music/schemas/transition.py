"""Transition domain schemas."""

from __future__ import annotations

from dj_music.schemas.base import BaseEntity


class Transition(BaseEntity):
    """Scored quality of playing two tracks in sequence."""

    from_track_id: int = 0
    to_track_id: int = 0
    overall_quality: float | None = None
    bpm_score: float | None = None
    harmonic_score: float | None = None
    energy_score: float | None = None
    spectral_score: float | None = None
    groove_score: float | None = None
    timbral_score: float | None = None
    # TODO: add from/to section, overlap_ms during Phase 4


class TransitionCandidate(BaseEntity):
    """A potential transition before full scoring."""

    from_track_id: int = 0
    to_track_id: int = 0
    bpm_distance: float | None = None
    key_distance: int | None = None
    energy_delta: float | None = None
    fully_scored: bool = False
