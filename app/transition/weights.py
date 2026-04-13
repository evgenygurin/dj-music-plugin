"""All transition scoring magic numbers in one place.

Pure data — no I/O, no logic. Imported by component scorers, the
hard-constraint check, and ``recommend_style``.

Values mirror the previous inline constants from ``scorer.py`` so that
extracting them is a no-op for behaviour. The actual rebalancing of
``DEFAULT_WEIGHTS`` (research §4.4) lands in commit 6.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import DEFAULT_TRANSITION_WEIGHTS

# ── Component weights (sum = 1.0) ────────────────────────
# Single source of truth lives in ``app/core/constants.py`` so the core
# layer doesn't depend on the domain layer. This module re-exports it
# as ``DEFAULT_WEIGHTS`` for ergonomic imports inside the transition
# package.
DEFAULT_WEIGHTS: dict[str, float] = DEFAULT_TRANSITION_WEIGHTS

# ── BPM scoring ──────────────────────────────────────────
BPM_GAUSS_SIGMA: float = 3.0  # ~2.5% on 124 BPM
BPM_STABILITY_FLOOR: float = 0.7  # max 30% penalty for unstable tempo
BPM_CONFIDENCE_PENALTY_FLOOR: float = 0.7  # symmetric with stability

# ── Harmonic scoring ─────────────────────────────────────
CAMELOT_BASE_SCORES: dict[int, float] = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
ATONAL_RELAX_FLOOR: float = 0.8  # both atonal → at least 0.8
HNR_NORM_LOW_DB: float = -30.0  # HNR < -30 → factor 0.5
HNR_NORM_HIGH_DB: float = 0.0  # HNR ≥ 0 → factor 1.0
HNR_NORM_FLOOR: float = 0.5
TONNETZ_BLEND: float = 0.30  # weight of tonnetz cosine vs Camelot base
KEY_CONFIDENCE_BLEND_THRESHOLD: float = 0.5

# ── Energy scoring ───────────────────────────────────────
ENERGY_SIGMOID_DIVISOR: float = 3.0  # rebalanced in commit 6
LRA_DIFF_PENALTY_THRESHOLD: float = 5.0
LRA_DIFF_PENALTY: float = 0.10
CREST_DIFF_PENALTY_THRESHOLD: float = 4.0
CREST_DIFF_PENALTY: float = 0.10
ENERGY_SLOPE_BONUS: float = 0.05

# ── Spectral scoring ─────────────────────────────────────
SPECTRAL_SUB_WEIGHTS: dict[str, float] = {
    "mfcc": 0.45,  # was 0.30 — #1 predictor of real DJ transitions (Kim 2020)
    "centroid": 0.15,  # was 0.20
    "energy_bands": 0.15,  # was 0.20
    "rolloff": 0.10,  # was 0.15
    "slope": 0.10,  # was 0.10
    "flux": 0.05,  # was 0.05
}
DISSONANCE_PAIR_THRESHOLD: float = 0.4
DISSONANCE_PENALTY: float = 0.15
COMPLEXITY_DIFF_THRESHOLD: float = 10.0
COMPLEXITY_PENALTY: float = 0.10

# ── Groove scoring ───────────────────────────────────────
GROOVE_SUB_WEIGHTS: dict[str, float] = {
    "onset_rate": 0.25,
    "kick_prominence": 0.25,
    "beat_loudness": 0.20,
    "pulse_clarity": 0.10,
    "hp_ratio": 0.10,
    "tempogram": 0.10,
}

# ── Timbral scoring ──────────────────────────────────────
TIMBRAL_SPECTRAL_CONTRAST_NORM: float = 15.0  # dB
TIMBRAL_PITCH_SALIENCE_NORM: float = 0.5
TIMBRAL_DANCEABILITY_NORM: float = 3.0
TIMBRAL_DYNAMIC_COMPLEXITY_NORM: float = 10.0
TIMBRAL_SUB_WEIGHTS: dict[str, float] = {
    "spectral_contrast": 0.35,
    "pitch_salience": 0.35,
    "danceability": 0.15,
    "dynamic_complexity": 0.15,
}


# ── Style recommendation thresholds ──────────────────────
@dataclass(frozen=True)
class StyleRules:
    """Decision-tree thresholds for ``recommend_style``.

    Defaults reflect the historical behaviour from ``scorer.py``.
    Held in a dataclass so future per-template overrides can swap them
    without touching component code.
    """

    spectral_collision_cutoff: float = 0.45
    energy_gap_cutoff: float = 0.40
    harmonic_drift_cutoff: float = 0.55
    perfect_bpm_cutoff: float = 0.95
    perfect_harmonic_cutoff: float = 0.85
    perfect_groove_cutoff: float = 0.75
    confident_overall_cutoff: float = 0.75


DEFAULT_STYLE_RULES = StyleRules()

# ── Section-aware modifiers (commit 5) ───────────────────
# When both the mix-out and mix-in windows fall on percussion-only
# sections (intro/outro/sustain/ambient), key compatibility loses
# perceptual relevance — Pioneer DJ blog, Vande Veire & De Bie 2018.
# `score_harmonic` applies the floor; `TransitionScorer.score` swaps to
# the override weight set for the weighted sum.
DRUM_ONLY_HARMONIC_FLOOR: float = 0.85

# Sums to 1.0. Harmonic collapsed, groove boosted relative to the
# default — the structural rationale is in
# docs/research/2026-04-08-techno-transitions-research.md §4.1.
DRUM_ONLY_WEIGHT_OVERRIDE: dict[str, float] = {
    "bpm": 0.22,
    "harmonic": 0.05,
    "energy": 0.18,
    "spectral": 0.20,
    "groove": 0.20,
    "timbral": 0.15,
}

# ── Conflict detection thresholds (Mosaikbox 2024) ──────
# Drum pattern conflict: when groove similarity < this, incoming drums
# should be muted during the transition overlap. Mosaikbox uses 0.95.
GROOVE_CONFLICT_THRESHOLD: float = 0.95

# Vocal conflict: when both tracks have pitch_salience above this
# threshold AND their vocal segments overlap > VOCAL_OVERLAP_MS,
# outgoing vocals should be muted. Mosaikbox: > 2 seconds overlap.
VOCAL_PITCH_SALIENCE_THRESHOLD: float = 0.4
VOCAL_SPECTRAL_CENTROID_FLOOR_HZ: float = 2500.0  # vocals above this
VOCAL_OVERLAP_THRESHOLD_MS: float = 2000.0

# ── Audio engineering constants (Allen & Heath / Pioneer) ─
# Bass swap is a hard cut (0ms), not a fade. Two kicks must NEVER
# play simultaneously — phase cancellation destroys sub-bass.
BASS_SWAP_RAMP_MS: float = 0.0  # hard cut on downbeat

# Click prevention micro-ramp applied on CUT transitions and
# instant bass kills. 5ms = ~220 samples at 44.1kHz.
MICRO_RAMP_MS: float = 5.0

# HPF filter order: 24 dB/oct (LR4) matches Allen & Heath Xone:92
# and Pioneer DJM-900NXS2 in ISO mode. Previous: 12 dB/oct (order 2).
HPF_FILTER_ORDER: int = 4  # butterworth order → 24 dB/oct

# Kick kill cutoff: 150 Hz LR4 removes kick fundamental (40-80Hz)
# and body (80-150Hz) while preserving upper harmonics. Previous: 200Hz.
KICK_KILL_CUTOFF_HZ: float = 150.0
