"""All transition scoring constants — the only place for magic numbers.

Pure data: no I/O, no logic, no imports from other app.transition modules.
Components and scorer import from here; settings.py handles runtime-configurable
thresholds (recipe decision tree uses settings.*).
"""

from __future__ import annotations

from app.core.constants import DEFAULT_TRANSITION_WEIGHTS

# ── Component weights (sum = 1.0) ────────────────────────────────────────────
DEFAULT_WEIGHTS: dict[str, float] = DEFAULT_TRANSITION_WEIGHTS

# ── BPM scoring ──────────────────────────────────────────────────────────────
BPM_GAUSS_SIGMA: float = 6.0
BPM_STABILITY_FLOOR: float = 0.7
BPM_CONFIDENCE_PENALTY_FLOOR: float = 0.7

# ── Harmonic scoring ─────────────────────────────────────────────────────────
CAMELOT_BASE_SCORES: dict[int, float] = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
ATONAL_RELAX_FLOOR: float = 0.8
HNR_NORM_LOW_DB: float = -30.0
HNR_NORM_HIGH_DB: float = 0.0
HNR_NORM_FLOOR: float = 0.5
TONNETZ_BLEND: float = 0.30
KEY_CONFIDENCE_BLEND_THRESHOLD: float = 0.5

# ── Energy scoring ───────────────────────────────────────────────────────────
ENERGY_SIGMOID_DIVISOR: float = 3.0
LRA_DIFF_PENALTY_THRESHOLD: float = 5.0
LRA_DIFF_PENALTY: float = 0.10
CREST_DIFF_PENALTY_THRESHOLD: float = 4.0
CREST_DIFF_PENALTY: float = 0.10
ENERGY_SLOPE_BONUS: float = 0.05

# ── Spectral scoring ─────────────────────────────────────────────────────────
SPECTRAL_SUB_WEIGHTS: dict[str, float] = {
    "mfcc": 0.45,
    "centroid": 0.15,
    "energy_bands": 0.15,
    "rolloff": 0.10,
    "slope": 0.10,
    "flux": 0.05,
}
DISSONANCE_PAIR_THRESHOLD: float = 0.4
DISSONANCE_PENALTY: float = 0.15
COMPLEXITY_DIFF_THRESHOLD: float = 10.0
COMPLEXITY_PENALTY: float = 0.10

# ── Groove scoring ───────────────────────────────────────────────────────────
GROOVE_SUB_WEIGHTS: dict[str, float] = {
    "onset_rate": 0.25,
    "kick_prominence": 0.25,
    "beat_loudness": 0.20,
    "pulse_clarity": 0.10,
    "hp_ratio": 0.10,
    "tempogram": 0.10,
}

# ── Timbral scoring ──────────────────────────────────────────────────────────
TIMBRAL_SPECTRAL_CONTRAST_NORM: float = 15.0
TIMBRAL_PITCH_SALIENCE_NORM: float = 0.5
TIMBRAL_DANCEABILITY_NORM: float = 3.0
TIMBRAL_DYNAMIC_COMPLEXITY_NORM: float = 10.0
TIMBRAL_SUB_WEIGHTS: dict[str, float] = {
    "spectral_contrast": 0.35,
    "pitch_salience": 0.35,
    "danceability": 0.15,
    "dynamic_complexity": 0.15,
}

# ── Section-aware modifiers ───────────────────────────────────────────────────
DRUM_ONLY_HARMONIC_FLOOR: float = 0.85
DRUM_ONLY_WEIGHT_OVERRIDE: dict[str, float] = {
    "bpm": 0.22,
    "harmonic": 0.05,
    "energy": 0.18,
    "spectral": 0.20,
    "groove": 0.20,
    "timbral": 0.15,
}

# ── Conflict detection (Mosaikbox 2024) ──────────────────────────────────────
GROOVE_CONFLICT_THRESHOLD: float = 0.95
VOCAL_PITCH_SALIENCE_THRESHOLD: float = 0.4
VOCAL_SPECTRAL_CENTROID_FLOOR_HZ: float = 2500.0
VOCAL_OVERLAP_THRESHOLD_MS: float = 2000.0

# ── Audio engineering constants (Allen & Heath / Pioneer) ────────────────────
BASS_SWAP_RAMP_MS: float = 0.0
MICRO_RAMP_MS: float = 5.0
HPF_FILTER_ORDER: int = 4
KICK_KILL_CUTOFF_HZ: float = 150.0
