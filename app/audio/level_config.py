"""Analysis level configuration — which analyzers run at which level."""

from __future__ import annotations

from enum import IntEnum

from app.config import settings


class AnalysisLevel(IntEnum):
    NONE = 0
    TRIAGE = 2  # L1+L2 combined: bpm, loudness, energy, spectral, key, mfcc
    SCORING = 3  # L3: + beat analyzer (onset, kick, hp_ratio, pulse)
    TRANSITION = 4  # L4: + structure (sections), permanent file
    ADVANCED = 5  # L5: + P3 DSP (danceability, dissonance, tonnetz, etc.)


_LEVEL_ANALYZERS: dict[int, list[str]] = {
    AnalysisLevel.TRIAGE: ["loudness", "energy", "spectral", "bpm", "key", "mfcc"],
    AnalysisLevel.SCORING: ["beat"],
    AnalysisLevel.TRANSITION: ["structure"],
    AnalysisLevel.ADVANCED: [
        "danceability",
        "dissonance",
        "dynamic_complexity",
        "spectral_complexity",
        "pitch_salience",
        "tonnetz",
        "tempogram",
        "beats_loudness",
        "bpm_histogram",
        "phrase",
    ],
}


def get_analyzers_for_level(target: AnalysisLevel) -> list[str]:
    """Return all analyzer names needed up to and including target level."""
    names: list[str] = []
    for level in sorted(_LEVEL_ANALYZERS):
        if level <= target:
            names.extend(_LEVEL_ANALYZERS[level])
    return names


def get_clip_duration(level: AnalysisLevel) -> float | None:
    """Return audio clip duration in seconds for analysis level.

    Returns None for TRANSITION and above — full track needed for
    structure segmentation and section detection.
    """
    if level <= AnalysisLevel.TRIAGE:
        return settings.audio_triage_clip_duration
    if level <= AnalysisLevel.SCORING:
        return settings.audio_beat_analysis_duration
    return None  # TRANSITION+ — full track, no clip
