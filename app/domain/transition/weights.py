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
    "bpm": 0.22,
    "energy": 0.18,
    "drums": 0.22,
    "bass": 0.15,
    "harmonics": 0.10,
    "vocals": 0.13,
}

# ── BPM scoring ──────────────────────────────────────────
# sigma=10 matches Pioneer DJ / Mixed In Key professional thresholds:
# dBPM=3-5 -> 0.96-0.88 (within CDJ +/-6% pitch range), dBPM=8 -> 0.73,
# dBPM=10 -> 0.61 (hard-reject boundary). Aligned with Kim et al. ISMIR
# 2020 analysis of 20 765 real-world DJ transitions.
BPM_GAUSS_SIGMA: float = 10.0
BPM_STABILITY_FLOOR: float = 0.7  # max 30% penalty for unstable tempo
BPM_CONFIDENCE_PENALTY_FLOOR: float = 0.7  # symmetric with stability

# ── Harmonic scoring ─────────────────────────────────────────────
# LIVE single-source Camelot base tables, indexed by Camelot distance
# (0..4; ≥5 → 0.0). Imported by both the scalar scorer
# (``neural_mix.score_{harmonic,bass}_compat``) and the vectorised
# ``bulk_scorer`` so the two paths can never drift. The bass table is
# tighter (bass-fundamental clash is less forgiving than pads/leads).
CAMELOT_HARMONIC_BASE: dict[int, float] = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
CAMELOT_BASS_BASE: dict[int, float] = {0: 1.0, 1: 0.85, 2: 0.55, 3: 0.25, 4: 0.05}

# REFERENCE-ONLY (NOT used by the scorer): kept because
# ``tests/domain/transition/test_weights.py`` pins it as a reference spec.
CAMELOT_BASE_SCORES: dict[int, float] = {0: 1.0, 1: 0.95, 2: 0.85, 3: 0.6, 4: 0.3}

# ── Energy scoring ───────────────────────────────────────
# Gauss around a preferred rise (~0.5 LUFS, under the 2 LUFS perceptual
# threshold). Peak=1.0 at equal-ish loudness; symmetric decay for drops
# and big jumps.
ENERGY_SIGMOID_DIVISOR: float = 3.0
ENERGY_PREFERRED_RISE_LUFS: float = 0.5
LRA_DIFF_PENALTY: float = 0.10
ENERGY_SLOPE_BONUS: float = 0.05

# ── Section-pair weight overlay ──────────────────────────────────────
#
# Multiplicative modifiers on top of intent-derived base weights before
# renormalisation. All five section-pair classes are now filled:
#
# * DRUM_ONLY: percussion-only windows — down-weight harmonics/vocals;
#   up-weight drums.
# * DROP_TO_DROP: two high-energy sections — up-weight energy flow
#   (body-shake continuity) at the expense of BPM precision.
# * BREAKDOWN_OUT: mix-out is a breakdown (drums drop out) — down-weight
#   drums, up-weight harmonics (pad/lead fluency into the next track).
# * BUILDUP_IN: mix-in is a buildup — up-weight energy swells
#   (tense rise), slightly down-weight raw BPM lock.
# * GENERIC: identity pass-through.

SECTION_PAIR_OVERLAY: dict[str, dict[str, float]] = {
    "drum_only": {
        "bpm": 1.10,
        "energy": 0.95,
        "drums": 1.30,
        "bass": 0.70,
        "harmonics": 0.40,
        "vocals": 0.30,
    },
    "drop_to_drop": {
        "bpm": 0.80,
        "energy": 1.25,
        "drums": 1.0,
        "bass": 1.0,
        "harmonics": 1.0,
        "vocals": 1.0,
    },
    "breakdown_out": {
        "bpm": 1.0,
        "energy": 1.0,
        "drums": 0.70,
        "bass": 1.0,
        "harmonics": 1.20,
        "vocals": 1.0,
    },
    "buildup_in": {
        "bpm": 0.85,
        "energy": 1.30,
        "drums": 1.0,
        "bass": 1.0,
        "harmonics": 1.0,
        "vocals": 1.0,
    },
    "generic": {
        "bpm": 1.0,
        "energy": 1.0,
        "drums": 1.0,
        "bass": 1.0,
        "harmonics": 1.0,
        "vocals": 1.0,
    },
}
