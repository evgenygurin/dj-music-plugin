"""Numeric constants for transition scoring (post Neural Mix refactor).

Pure data — no I/O, no logic. Imported by the BPM and energy component
scorers, the hard-constraint check, and the legacy bass/harmonic compat
helpers in ``neural_mix.py``.

The pre-refactor sub-weights for spectral / groove / timbral / harmonic
component scorers have been deleted along with those modules — the
Neural Mix scorer in ``app/domain/transition/neural_mix.py`` is the
single source of truth for stem-aware scoring.
"""

from __future__ import annotations

# ── Component weights (sum = 1.0) ────────────────────────
# Six top-level components: bpm + energy + four Neural Mix stem compats
# (drums, bass, harmonics, vocals).
#
# The slight uplift on ``drums`` reflects techno DJ practice — kick /
# onset alignment is the load-bearing scoring axis even more than key
# matching at peak time.
DEFAULT_WEIGHTS: dict[str, float] = {
    "bpm": 0.20,
    "energy": 0.15,
    "drums": 0.20,
    "bass": 0.15,
    "harmonics": 0.15,
    "vocals": 0.15,
}

# ── BPM scoring ──────────────────────────────────────────
# sigma=10 matches Pioneer DJ / Mixed In Key professional thresholds:
# dBPM=3-5 -> 0.96-0.88 (within CDJ +/-6% pitch range), dBPM=8 -> 0.73,
# dBPM=10 -> 0.61 (hard-reject boundary). Aligned with Kim et al. ISMIR
# 2020 analysis of 20 765 real-world DJ transitions.
BPM_GAUSS_SIGMA: float = 10.0
BPM_STABILITY_FLOOR: float = 0.7  # max 30% penalty for unstable tempo
BPM_CONFIDENCE_PENALTY_FLOOR: float = 0.7  # symmetric with stability

# ── Harmonic scoring (legacy table for stem compat helpers) ──────
# Used by ``neural_mix.score_bass_compat`` / ``score_harmonic_compat``.
CAMELOT_BASE_SCORES: dict[int, float] = {0: 1.0, 1: 0.95, 2: 0.85, 3: 0.6, 4: 0.3}
ATONAL_RELAX_FLOOR: float = 0.8  # both atonal → at least 0.8
HNR_NORM_LOW_DB: float = -30.0
HNR_NORM_HIGH_DB: float = 0.0
HNR_NORM_FLOOR: float = 0.5
TONNETZ_BLEND: float = 0.30
KEY_CONFIDENCE_BLEND_THRESHOLD: float = 0.5

# ── Energy scoring ───────────────────────────────────────
# Gauss around a preferred rise (~0.5 LUFS, under the 2 LUFS perceptual
# threshold). Peak=1.0 at equal-ish loudness; symmetric decay for drops
# and big jumps.
ENERGY_SIGMOID_DIVISOR: float = 3.0
ENERGY_PREFERRED_RISE_LUFS: float = 0.5
LRA_DIFF_PENALTY_THRESHOLD: float = 5.0
LRA_DIFF_PENALTY: float = 0.10
CREST_DIFF_PENALTY_THRESHOLD: float = 4.0
CREST_DIFF_PENALTY: float = 0.10
ENERGY_SLOPE_BONUS: float = 0.05

# ── Section-pair weight overlay (Phase 1 v2 refactor) ───────────────
#
# Multiplicative modifiers applied on top of intent-derived base weights
# before renormalisation. Phase 1 scope: only DRUM_ONLY is active; the
# other four classes get identity overlays (x1.0) and will be filled in
# Phase 3 once phrase + structure components exist.
#
# Rationale (DRUM_ONLY): both mix-out and mix-in windows are percussion-only
# (INTRO / OUTRO / SUSTAIN / AMBIENT). Harmonic clash is minimal —
# down-weight harmonics + vocals; rely on drums/bass tightness instead.
# Source: docs/transitions-refactor.md § 5.3, § A.2.

_IDENTITY_OVERLAY: dict[str, float] = {
    "bpm": 1.0,
    "energy": 1.0,
    "drums": 1.0,
    "bass": 1.0,
    "harmonics": 1.0,
    "vocals": 1.0,
}

SECTION_PAIR_OVERLAY: dict[str, dict[str, float]] = {
    "drum_only": {
        "bpm": 1.10,
        "energy": 0.95,
        "drums": 1.30,
        "bass": 0.70,
        "harmonics": 0.40,
        "vocals": 0.30,
    },
    "drop_to_drop": dict(_IDENTITY_OVERLAY),
    "breakdown_out": dict(_IDENTITY_OVERLAY),
    "buildup_in": dict(_IDENTITY_OVERLAY),
    "generic": dict(_IDENTITY_OVERLAY),
}
