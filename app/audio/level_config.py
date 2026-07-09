"""Analysis level configuration — which analyzers run at which level."""

from __future__ import annotations

from enum import IntEnum


class AnalysisLevel(IntEnum):
    NONE = 0
    TRIAGE = 2  # L1+L2 combined: bpm, loudness, energy, spectral, key, mfcc
    SCORING = 3  # L3: + beat analyzer (onset, kick, hp_ratio, pulse)
    TRANSITION = 4  # L4: + structure (sections), permanent file
    ADVANCED = 5  # L5: + P3 DSP (danceability, dissonance, tonnetz, etc.)
    DEEP = 6  # L6: + per-stem features (demucs + stem_analyzer), beatgrid, sbic, embeddings


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
    AnalysisLevel.DEEP: [
        "chords",
        "hpcp_extended",
        "inharmonicity",
        "meter",
        "audio_qa",
    ],
}


def get_analyzers_for_level(target: AnalysisLevel) -> list[str]:
    """Return all analyzer names needed up to and including target level."""
    names: list[str] = []
    for level in sorted(_LEVEL_ANALYZERS):
        if level <= target:
            names.extend(_LEVEL_ANALYZERS[level])
    return names
