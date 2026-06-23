"""Vectorised transition scoring for the GA's eager-populate stage.

The scalar code path in ``scorer.py`` / ``neural_mix.py`` / ``components/``
is the public API and the source of truth — it is how MCP consumers
read a single (a, b) pair. ``BulkTransitionScorer``
shares the **same** algorithm but runs it batched over (idx_a, idx_b)
arrays via numpy. The scalar path stays the parity oracle: every
function here has a corresponding parity test in
``tests/domain/transition/test_bulk_scorer_parity.py`` that drives a
randomised pool through both paths and asserts ``np.allclose``.

Wired into ``GeneticAlgorithm._eager_populate_cache`` for pools
larger than ``_BULK_SCORER_THRESHOLD``; below that the scalar path
plus intent-share is already fast enough that the per-call
``np.array``/``np.einsum`` allocation overhead would lose net.

NOT a separate scoring engine — same weights, same gauss params,
same Camelot lookup, same bias modifier. If the scalar path changes,
this module changes lockstep, and the parity tests catch the drift.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.config import get_settings
from app.domain.transition.intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.domain.transition.neural_mix import (
    TRANSITION_ENERGY_BIAS,
    TRANSITION_STEM_WEIGHTS,
    NeuralMixStem,
    NeuralMixTransition,
)
from app.domain.transition.weights import (
    BPM_CONFIDENCE_PENALTY_FLOOR,
    BPM_GAUSS_SIGMA,
    BPM_STABILITY_FLOOR,
    CAMELOT_BASS_BASE,
    CAMELOT_HARMONIC_BASE,
    ENERGY_PREFERRED_RISE_LUFS,
    ENERGY_SIGMOID_DIVISOR,
)
from app.shared.features import TrackFeatures

FloatArr = npt.NDArray[np.float64]
BoolArr = npt.NDArray[np.bool_]
IntArr = npt.NDArray[np.int64]

_NAN = np.float64("nan")

# Dimensions for vector features. mfcc=13 (fixed by extractor), tonnetz=6
# (Tonnetz space cardinality), energy_bands=6 (sub/low/lowmid/mid/highmid/high).
# beat_loudness is variable-length in the wild but in practice analyzers
# emit either 5 or 6 — we pad to 6 with zeros and ignore the trailing slot
# via ``_beat_loudness_len``.
_MFCC_DIM = 13
_TONNETZ_DIM = 6
_ENERGY_BAND_DIM = 6
_BEAT_LOUDNESS_DIM = 6


# ── Feature extraction ────────────────────────────────────────────


@dataclass(frozen=True)
class FeatureArrays:
    """Numpy-backed view of a list of TrackFeatures.

    Missing scalar values are ``nan`` (float arrays) or ``-1`` (int).
    Missing vectors get a zero row plus a corresponding ``_present``
    bool mask so consumers can fall back to the neutral 0.5 the scalar
    path uses when one side lacks the field.
    """

    n: int

    # Scalars — nan-marked
    bpm: FloatArr
    bpm_stability: FloatArr
    bpm_confidence: FloatArr
    key_confidence: FloatArr
    integrated_lufs: FloatArr
    loudness_range_lu: FloatArr
    crest_factor_db: FloatArr
    energy_slope: FloatArr
    spectral_centroid_hz: FloatArr
    spectral_contrast: FloatArr
    chroma_entropy: FloatArr
    pitch_salience_mean: FloatArr
    onset_rate: FloatArr
    kick_prominence: FloatArr
    hnr_db: FloatArr
    dissonance_mean: FloatArr

    # Booleans / int — sentinel-marked
    variable_tempo: BoolArr  # False if missing
    atonality: BoolArr  # False if missing
    key_code: IntArr  # -1 if missing

    # Vectors with presence masks
    mfcc: FloatArr  # (n, 13)
    mfcc_present: BoolArr
    tonnetz: FloatArr  # (n, 6)
    tonnetz_present: BoolArr
    energy_bands: FloatArr  # (n, 6)
    energy_bands_present: BoolArr
    beat_loudness: FloatArr  # (n, 6), padded
    beat_loudness_present: BoolArr


def _scalar_arr(values: Sequence[float | None]) -> FloatArr:
    """Pack ``Sequence[float | None]`` into a float64 array with nan for None."""
    return np.array([_NAN if v is None else float(v) for v in values], dtype=np.float64)


def _bool_arr(values: Sequence[bool | None]) -> BoolArr:
    """Pack ``Sequence[bool | None]`` into a bool array (None → False)."""
    return np.array([bool(v) if v is not None else False for v in values], dtype=np.bool_)


def _int_arr(values: Sequence[int | None], missing: int = -1) -> IntArr:
    return np.array([missing if v is None else int(v) for v in values], dtype=np.int64)


def _vector_matrix(values: Sequence[Sequence[float] | None], dim: int) -> tuple[FloatArr, BoolArr]:
    """Pack a list of vectors into a (n, dim) matrix + presence mask.

    Vectors longer than ``dim`` are truncated; shorter ones zero-padded.
    Missing vectors become a zero row with ``present[i] = False``.
    """
    n = len(values)
    mat = np.zeros((n, dim), dtype=np.float64)
    present = np.zeros(n, dtype=np.bool_)
    for i, vec in enumerate(values):
        if vec is None or len(vec) == 0:
            continue
        present[i] = True
        cap = min(dim, len(vec))
        mat[i, :cap] = np.asarray(vec[:cap], dtype=np.float64)
    return mat, present


def extract_feature_arrays(tracks: Sequence[TrackFeatures]) -> FeatureArrays:
    """Materialise a ``FeatureArrays`` view in a single pass over ``tracks``."""
    mfcc, mfcc_present = _vector_matrix([t.mfcc_vector for t in tracks], _MFCC_DIM)
    tonnetz, tonnetz_present = _vector_matrix([t.tonnetz_vector for t in tracks], _TONNETZ_DIM)
    energy_bands, energy_bands_present = _vector_matrix(
        [t.energy_bands for t in tracks], _ENERGY_BAND_DIM
    )
    beat_loudness, beat_loudness_present = _vector_matrix(
        [t.beat_loudness_band_ratio for t in tracks], _BEAT_LOUDNESS_DIM
    )

    return FeatureArrays(
        n=len(tracks),
        bpm=_scalar_arr([t.bpm for t in tracks]),
        bpm_stability=_scalar_arr([t.bpm_stability for t in tracks]),
        bpm_confidence=_scalar_arr([t.bpm_confidence for t in tracks]),
        key_confidence=_scalar_arr([t.key_confidence for t in tracks]),
        integrated_lufs=_scalar_arr([t.integrated_lufs for t in tracks]),
        loudness_range_lu=_scalar_arr([t.loudness_range_lu for t in tracks]),
        crest_factor_db=_scalar_arr([t.crest_factor_db for t in tracks]),
        energy_slope=_scalar_arr([t.energy_slope for t in tracks]),
        spectral_centroid_hz=_scalar_arr([t.spectral_centroid_hz for t in tracks]),
        spectral_contrast=_scalar_arr([t.spectral_contrast for t in tracks]),
        chroma_entropy=_scalar_arr([t.chroma_entropy for t in tracks]),
        pitch_salience_mean=_scalar_arr([t.pitch_salience_mean for t in tracks]),
        onset_rate=_scalar_arr([t.onset_rate for t in tracks]),
        kick_prominence=_scalar_arr([t.kick_prominence for t in tracks]),
        hnr_db=_scalar_arr([t.hnr_db for t in tracks]),
        dissonance_mean=_scalar_arr([t.dissonance_mean for t in tracks]),
        variable_tempo=_bool_arr([t.variable_tempo for t in tracks]),
        atonality=_bool_arr([t.atonality for t in tracks]),
        key_code=_int_arr([t.key_code for t in tracks], missing=-1),
        mfcc=mfcc,
        mfcc_present=mfcc_present,
        tonnetz=tonnetz,
        tonnetz_present=tonnetz_present,
        energy_bands=energy_bands,
        energy_bands_present=energy_bands_present,
        beat_loudness=beat_loudness,
        beat_loudness_present=beat_loudness_present,
    )


# ── Camelot distance lookup ───────────────────────────────────────


def _camelot_distance_table() -> IntArr:
    """Build the 24x24 Camelot distance matrix once.

    Mirrors ``app.domain.camelot.wheel.camelot_distance``. Range 0..7.
    Missing-key sentinel handling lives in the consumers (they mask -1).
    """
    table = np.zeros((24, 24), dtype=np.int64)
    for a in range(24):
        pos_a = (a // 2) + 1
        mode_a = a % 2
        for b in range(24):
            pos_b = (b // 2) + 1
            mode_b = b % 2
            raw_diff = abs(pos_a - pos_b)
            wheel_dist = min(raw_diff, 12 - raw_diff)
            mode_penalty = 0 if mode_a == mode_b else 1
            table[a, b] = wheel_dist + mode_penalty
    return table


_CAMELOT_DISTANCE: IntArr = _camelot_distance_table()


def _base_lookup(table: dict[int, float]) -> FloatArr:
    """8-element distance→score lookup from a Camelot base dict (≥5 → 0.0)."""
    return np.array([table.get(d, 0.0) for d in range(8)], dtype=np.float64)


# Single source of truth shared with the scalar scorer (weights.py).
_BASS_BASE_LOOKUP: FloatArr = _base_lookup(CAMELOT_BASS_BASE)
_HARMONIC_BASE_LOOKUP: FloatArr = _base_lookup(CAMELOT_HARMONIC_BASE)


def _key_reliable_mask(fa: FeatureArrays, idx: IntArr) -> BoolArr:
    """Vectorised mirror of ``hard_constraints.key_reliable`` for ``idx``.

    A track's key is reliable when it is not atonal AND key_confidence >= floor.
    Atonal/None → not-atonal; NaN/None confidence → treated as confident.
    """
    floor = get_settings().transition.hard_reject_key_confidence_floor
    conf = fa.key_confidence[idx]
    return ~fa.atonality[idx] & (np.isnan(conf) | (conf >= floor))


# ── Pair-array helpers ────────────────────────────────────────────


def _bpm_distance_bulk(bpm_a: FloatArr, bpm_b: FloatArr) -> FloatArr:
    """Min-of-(direct, double, half), nan-propagating to mirror scalar."""
    direct = np.abs(bpm_a - bpm_b)
    double = np.abs(bpm_a - bpm_b * 2.0)
    half = np.abs(bpm_a - bpm_b / 2.0)
    return np.minimum(direct, np.minimum(double, half))


def _cosine_similarity_bulk(matrix: FloatArr, ia: IntArr, ib: IntArr) -> FloatArr:
    """Cosine similarity mapped to ``[0, 1]`` for paired rows.

    Mirrors ``math_helpers.cosine_similarity`` exactly:
    ``max(0, min(1, (dot/(|a||b|) + 1) / 2))``. Returns ``0.0`` whenever
    either norm is zero (the scalar code's degenerate-vector handling).
    """
    a = matrix[ia]
    b = matrix[ib]
    dot = np.sum(a * b, axis=1)
    norm_a = np.sqrt(np.sum(a * a, axis=1))
    norm_b = np.sqrt(np.sum(b * b, axis=1))
    denom = norm_a * norm_b
    safe_denom = np.where(denom == 0, 1.0, denom)
    cos = np.where(denom == 0, -1.0, dot / safe_denom)  # cos=-1 → mapped→0
    mapped = np.clip((cos + 1.0) / 2.0, 0.0, 1.0)
    return mapped


# ── Hard-reject vectorised ────────────────────────────────────────


def hard_reject_mask_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> BoolArr:
    """Vector of bool: True → pair fails any hard constraint.

    Matches ``check_hard_constraints`` exactly, including the
    "missing field → no rejection" behaviour. Pairs flagged here
    don't go into the score cache (the GA reject_mask path catches
    them upstream via the same scalar gate).
    """
    settings = get_settings().transition

    bpm_a = fa.bpm[ia]
    bpm_b = fa.bpm[ib]
    bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
    bpm_diff = _bpm_distance_bulk(bpm_a, bpm_b)
    bpm_violates = bpm_present & (bpm_diff > settings.hard_reject_bpm_diff)

    key_a = fa.key_code[ia]
    key_b = fa.key_code[ib]
    key_present = (key_a >= 0) & (key_b >= 0)
    safe_key_a = np.where(key_present, key_a, 0)
    safe_key_b = np.where(key_present, key_b, 0)
    key_dist = _CAMELOT_DISTANCE[safe_key_a, safe_key_b]
    # Only reject when BOTH sides are tonal + confident (key clash is real).
    reliable = _key_reliable_mask(fa, ia) & _key_reliable_mask(fa, ib)
    key_violates = key_present & reliable & (key_dist >= settings.hard_reject_camelot_dist)

    lufs_a = fa.integrated_lufs[ia]
    lufs_b = fa.integrated_lufs[ib]
    lufs_present = ~(np.isnan(lufs_a) | np.isnan(lufs_b))
    energy_gap = np.abs(lufs_a - lufs_b)
    lufs_violates = lufs_present & (energy_gap > settings.hard_reject_energy_gap_lufs)

    return bpm_violates | key_violates | lufs_violates


# ── Component scoring (each is a 1-to-1 numpy clone of scalar) ────


def score_bpm_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
    """Vectorised ``components.bpm.score_bpm``."""
    settings = get_settings().transition

    bpm_a = fa.bpm[ia]
    bpm_b = fa.bpm[ib]
    bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))

    delta = _bpm_distance_bulk(bpm_a, bpm_b)
    score = np.exp(-(delta**2) / (2 * BPM_GAUSS_SIGMA**2))

    stab_a = fa.bpm_stability[ia]
    stab_b = fa.bpm_stability[ib]
    stab_present = ~(np.isnan(stab_a) | np.isnan(stab_b))
    stability = np.minimum(stab_a, stab_b)
    stab_factor = np.where(stab_present, np.maximum(BPM_STABILITY_FLOOR, stability), 1.0)
    score = score * stab_factor

    conf_a = fa.bpm_confidence[ia]
    conf_b = fa.bpm_confidence[ib]
    conf_present = ~(np.isnan(conf_a) | np.isnan(conf_b))
    min_conf = np.minimum(conf_a, conf_b)
    floor_conf = settings.scoring_bpm_confidence_floor
    needs_penalty = conf_present & (min_conf < floor_conf)
    conf_factor = np.where(
        needs_penalty,
        np.maximum(BPM_CONFIDENCE_PENALTY_FLOOR, min_conf / floor_conf),
        1.0,
    )
    score = score * conf_factor

    var_a = fa.variable_tempo[ia]
    var_b = fa.variable_tempo[ib]
    var_penalty = (var_a | var_b).astype(np.float64) * settings.scoring_variable_tempo_penalty
    score = np.maximum(0.0, score - var_penalty)

    # Scalar returns 0.5 (neutral) when bpm itself is missing.
    return np.where(bpm_present, score, 0.5)


def score_energy_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
    """Vectorised ``components.energy.score_energy``."""
    settings = get_settings().transition

    lufs_a = fa.integrated_lufs[ia]
    lufs_b = fa.integrated_lufs[ib]
    lufs_present = ~(np.isnan(lufs_a) | np.isnan(lufs_b))

    delta = lufs_b - lufs_a
    score = np.exp(
        -((delta - ENERGY_PREFERRED_RISE_LUFS) ** 2) / (2.0 * ENERGY_SIGMOID_DIVISOR**2)
    )

    lra_a = fa.loudness_range_lu[ia]
    lra_b = fa.loudness_range_lu[ib]
    lra_present = ~(np.isnan(lra_a) | np.isnan(lra_b))
    lra_diff = np.abs(lra_a - lra_b)
    lra_pen = (lra_present & (lra_diff > settings.scoring_lra_diff_penalty_threshold)).astype(
        np.float64
    ) * settings.scoring_lra_diff_penalty
    score = np.maximum(0.0, score - lra_pen)

    crest_a = fa.crest_factor_db[ia]
    crest_b = fa.crest_factor_db[ib]
    crest_present = ~(np.isnan(crest_a) | np.isnan(crest_b))
    crest_diff = np.abs(crest_a - crest_b)
    crest_pen = (
        crest_present & (crest_diff > settings.scoring_crest_diff_penalty_threshold)
    ).astype(np.float64) * settings.scoring_crest_diff_penalty
    score = np.maximum(0.0, score - crest_pen)

    slope_a = fa.energy_slope[ia]
    slope_b = fa.energy_slope[ib]
    slope_present = ~(np.isnan(slope_a) | np.isnan(slope_b))
    slope_match = slope_present & ((slope_a > 0) == (slope_b > 0))
    score = np.where(
        slope_match,
        np.minimum(1.0, score + settings.scoring_energy_slope_bonus),
        score,
    )

    return np.where(lufs_present, score, 0.5)


# Scalar code uses _weighted_average over a list of [(value, weight), ...].
# Empty list → 0.5; otherwise sum(value*w)/sum(w). With our vectorised
# components every value is **always present** (we substitute 0.5 for the
# missing branch upstream and adjust the weight where the scalar would
# have skipped the term entirely). Below: pre-computed weight totals.


def score_drums_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
    """Vectorised ``neural_mix.score_drums_compat``."""
    bpm_a = fa.bpm[ia]
    bpm_b = fa.bpm[ib]
    bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
    delta = _bpm_distance_bulk(bpm_a, bpm_b)
    bpm_score = np.exp(-(delta**2) / (2 * 3.0**2))  # sigma=3 (drums-specific)
    stab_a = fa.bpm_stability[ia]
    stab_b = fa.bpm_stability[ib]
    stab_present = ~(np.isnan(stab_a) | np.isnan(stab_b))
    stab_factor = np.where(stab_present, np.maximum(0.7, np.minimum(stab_a, stab_b)), 1.0)
    bpm_score = bpm_score * stab_factor
    bpm_term = np.where(bpm_present, bpm_score, 0.5)
    weight_bpm = np.full_like(bpm_term, 0.50)

    kick_a = fa.kick_prominence[ia]
    kick_b = fa.kick_prominence[ib]
    kick_present = ~(np.isnan(kick_a) | np.isnan(kick_b))
    kick_term = np.where(kick_present, np.maximum(0.0, 1.0 - np.abs(kick_a - kick_b)), 0.0)
    weight_kick = np.where(kick_present, 0.25, 0.0)

    onset_a = fa.onset_rate[ia]
    onset_b = fa.onset_rate[ib]
    onset_present = ~(np.isnan(onset_a) | np.isnan(onset_b))
    max_rate = np.maximum(np.maximum(onset_a, onset_b), 1.0)
    onset_term = np.where(
        onset_present,
        np.maximum(0.0, 1.0 - np.abs(onset_a - onset_b) / max_rate),
        0.0,
    )
    weight_onset = np.where(onset_present, 0.15, 0.0)

    bl_present = fa.beat_loudness_present[ia] & fa.beat_loudness_present[ib]
    bl_cos = _cosine_similarity_bulk(fa.beat_loudness, ia, ib)
    bl_term = np.where(bl_present, bl_cos, 0.0)
    weight_bl = np.where(bl_present, 0.10, 0.0)

    numerator = (
        bpm_term * weight_bpm
        + kick_term * weight_kick
        + onset_term * weight_onset
        + bl_term * weight_bl
    )
    denominator = weight_bpm + weight_kick + weight_onset + weight_bl
    return np.where(denominator > 0, numerator / denominator, 0.5)


def score_bass_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
    """Vectorised ``neural_mix.score_bass_compat``."""
    # Camelot block — CAMELOT_BASS_BASE (single source of truth, weights.py)
    key_a = fa.key_code[ia]
    key_b = fa.key_code[ib]
    key_present = (key_a >= 0) & (key_b >= 0)
    safe_a = np.where(key_present, key_a, 0)
    safe_b = np.where(key_present, key_b, 0)
    key_dist = _CAMELOT_DISTANCE[safe_a, safe_b]
    cam_score = _BASS_BASE_LOOKUP[np.clip(key_dist, 0, 7)]
    # Neutral key (0.5) when missing OR not reliably tonal (atonal/low-conf).
    reliable = _key_reliable_mask(fa, ia) & _key_reliable_mask(fa, ib)
    cam_term = np.where(key_present & reliable, cam_score, 0.5)
    weight_cam = np.full_like(cam_term, 0.65)

    # Bass-band — energy_bands[0] + energy_bands[1] (sub + low)
    eb_present = fa.energy_bands_present[ia] & fa.energy_bands_present[ib]
    bass_a = fa.energy_bands[ia, 0] + fa.energy_bands[ia, 1]
    bass_b = fa.energy_bands[ib, 0] + fa.energy_bands[ib, 1]
    max_bass = np.maximum(np.maximum(bass_a, bass_b), 1e-6)
    bass_band_term = np.where(
        eb_present,
        np.maximum(0.0, 1.0 - np.abs(bass_a - bass_b) / max_bass),
        0.0,
    )
    weight_bb = np.where(eb_present, 0.20, 0.0)

    bpm_a = fa.bpm[ia]
    bpm_b = fa.bpm[ib]
    bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
    delta = _bpm_distance_bulk(bpm_a, bpm_b)
    bpm_score = np.exp(-(delta**2) / 18.0)
    bpm_term = np.where(bpm_present, bpm_score, 0.0)
    weight_bpm = np.where(bpm_present, 0.15, 0.0)

    numerator = cam_term * weight_cam + bass_band_term * weight_bb + bpm_term * weight_bpm
    denominator = weight_cam + weight_bb + weight_bpm
    return np.where(denominator > 0, numerator / denominator, 0.5)


def score_harmonics_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
    """Vectorised ``neural_mix.score_harmonic_compat``."""
    # Camelot — CAMELOT_HARMONIC_BASE (single source of truth, weights.py)
    key_a = fa.key_code[ia]
    key_b = fa.key_code[ib]
    key_present = (key_a >= 0) & (key_b >= 0)
    safe_a = np.where(key_present, key_a, 0)
    safe_b = np.where(key_present, key_b, 0)
    key_dist = _CAMELOT_DISTANCE[safe_a, safe_b]
    base_cam = _HARMONIC_BASE_LOOKUP[np.clip(key_dist, 0, 7)]
    hnr_a = fa.hnr_db[ia]
    hnr_b = fa.hnr_db[ib]
    hnr_present = ~(np.isnan(hnr_a) | np.isnan(hnr_b))
    avg_hnr = (hnr_a + hnr_b) / 2.0
    hnr_factor = np.where(
        hnr_present, np.maximum(0.5, np.minimum(1.0, (avg_hnr + 30.0) / 30.0)), 1.0
    )
    # Neutral key (0.5) when missing OR not reliably tonal (atonal/low-conf).
    reliable = _key_reliable_mask(fa, ia) & _key_reliable_mask(fa, ib)
    cam_term = np.where(key_present & reliable, base_cam * hnr_factor, 0.5)
    weight_cam = np.full_like(cam_term, 0.40)

    tonnetz_present = fa.tonnetz_present[ia] & fa.tonnetz_present[ib]
    tonnetz_cos = _cosine_similarity_bulk(fa.tonnetz, ia, ib)
    tonnetz_term = np.where(tonnetz_present, tonnetz_cos, 0.0)
    weight_tonnetz = np.where(tonnetz_present, 0.20, 0.0)

    mfcc_present = fa.mfcc_present[ia] & fa.mfcc_present[ib]
    mfcc_cos = _cosine_similarity_bulk(fa.mfcc, ia, ib)
    mfcc_term = np.where(mfcc_present, mfcc_cos, 0.0)
    weight_mfcc = np.where(mfcc_present, 0.20, 0.0)

    sc_a = fa.spectral_contrast[ia]
    sc_b = fa.spectral_contrast[ib]
    sc_present = ~(np.isnan(sc_a) | np.isnan(sc_b))
    sc_diff = np.abs(sc_a - sc_b)
    sc_term = np.where(sc_present, np.maximum(0.0, 1.0 - sc_diff / 15.0), 0.0)
    weight_sc = np.where(sc_present, 0.10, 0.0)

    numerator = (
        cam_term * weight_cam
        + tonnetz_term * weight_tonnetz
        + mfcc_term * weight_mfcc
        + sc_term * weight_sc
    )
    denominator = weight_cam + weight_tonnetz + weight_mfcc + weight_sc
    base = np.where(denominator > 0, numerator / denominator, 0.5)

    diss_a = fa.dissonance_mean[ia]
    diss_b = fa.dissonance_mean[ib]
    diss_present = ~(np.isnan(diss_a) | np.isnan(diss_b))
    both_dissonant = diss_present & (diss_a > 0.4) & (diss_b > 0.4)
    penalty = both_dissonant.astype(np.float64) * 0.15
    return np.maximum(0.0, base - penalty)


def score_vocals_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
    """Vectorised ``neural_mix.score_vocal_compat``."""
    cent_a = fa.spectral_centroid_hz[ia]
    cent_b = fa.spectral_centroid_hz[ib]
    cent_present = ~(np.isnan(cent_a) | np.isnan(cent_b))
    max_c = np.maximum(np.maximum(cent_a, cent_b), 1.0)
    cent_term = np.where(
        cent_present,
        np.maximum(0.0, 1.0 - np.abs(cent_a - cent_b) / max_c),
        0.5,
    )
    weight_cent = np.full_like(cent_term, 0.40)

    chroma_a = fa.chroma_entropy[ia]
    chroma_b = fa.chroma_entropy[ib]
    chroma_present = ~(np.isnan(chroma_a) | np.isnan(chroma_b))
    chroma_term = np.where(chroma_present, np.maximum(0.0, 1.0 - np.abs(chroma_a - chroma_b)), 0.0)
    weight_chroma = np.where(chroma_present, 0.30, 0.0)

    pitch_a = fa.pitch_salience_mean[ia]
    pitch_b = fa.pitch_salience_mean[ib]
    pitch_present = ~(np.isnan(pitch_a) | np.isnan(pitch_b))
    pitch_term = np.where(
        pitch_present, np.maximum(0.0, 1.0 - np.abs(pitch_a - pitch_b) / 0.5), 0.0
    )
    weight_pitch = np.where(pitch_present, 0.30, 0.0)

    numerator = cent_term * weight_cent + chroma_term * weight_chroma + pitch_term * weight_pitch
    denominator = weight_cent + weight_chroma + weight_pitch
    return np.where(denominator > 0, numerator / denominator, 0.5)


# ── Bulk overall ──────────────────────────────────────────────────


def _stem_weight_matrix() -> tuple[FloatArr, FloatArr, list[NeuralMixTransition]]:
    """Pack TRANSITION_STEM_WEIGHTS into a (T, 4) matrix + (T,) bias array."""
    transitions = list(NeuralMixTransition)
    stems_order: list[NeuralMixStem] = [
        NeuralMixStem.DRUMS,
        NeuralMixStem.BASS,
        NeuralMixStem.HARMONICS,
        NeuralMixStem.VOCALS,
    ]
    stem_w = np.zeros((len(transitions), 4), dtype=np.float64)
    bias = np.zeros(len(transitions), dtype=np.float64)
    for i, t in enumerate(transitions):
        for j, s in enumerate(stems_order):
            stem_w[i, j] = TRANSITION_STEM_WEIGHTS[t][s]
        bias[i] = TRANSITION_ENERGY_BIAS[t]
    return stem_w, bias, transitions


_STEM_W_MATRIX, _BIAS_VEC, _TRANSITION_ORDER = _stem_weight_matrix()


def _energy_bias_modifier_bulk(
    energy_delta: FloatArr,
) -> FloatArr:
    """Per-pair x per-transition multiplier matrix.

    Output shape: ``(P, T)`` where ``P = len(energy_delta)`` and ``T = 7``.
    Mirrors ``neural_mix._energy_bias_modifier`` which returns
    ``1 + 0.15*max(0, alignment) - 0.30*max(0, -alignment)`` per (delta, bias).
    """
    delta = np.where(np.isnan(energy_delta), 0.0, energy_delta)
    normalised = np.clip(delta / 4.0, -1.0, 1.0)  # (P,)
    bias = _BIAS_VEC  # (T,)
    alignment = normalised[:, None] * bias[None, :]  # (P, T)
    pos = np.maximum(0.0, alignment)
    neg = np.maximum(0.0, -alignment)
    bias_zero = bias == 0.0
    modifier = 1.0 + 0.15 * pos - 0.30 * neg
    return np.where(bias_zero[None, :], 1.0, modifier)


def neural_best_overall_bulk(
    fa: FeatureArrays,
    ia: IntArr,
    ib: IntArr,
    drums: FloatArr,
    bass: FloatArr,
    harmonics: FloatArr,
    vocals: FloatArr,
) -> FloatArr:
    """Per-pair best-of-7 transition score (the ``overall`` field).

    NOT used by the per-intent ``overall`` (intent-share path uses raw
    stems). Currently here for parity testing — may be promoted to the
    main path later if the picker ever wants the bulk best-pick.
    """
    stems = np.stack([drums, bass, harmonics, vocals], axis=1)  # (P, 4)
    base = stems @ _STEM_W_MATRIX.T  # (P, T)
    lufs_a = fa.integrated_lufs[ia]
    lufs_b = fa.integrated_lufs[ib]
    delta = lufs_b - lufs_a
    delta = np.where(np.isnan(delta), 0.0, delta)
    modifier = _energy_bias_modifier_bulk(delta)
    transition_scores = np.clip(base * modifier, 0.0, 1.0)
    return np.asarray(transition_scores.max(axis=1), dtype=np.float64)


# ── Public bulk API ───────────────────────────────────────────────


def score_pairs_bulk(
    fa: FeatureArrays,
    pairs: Sequence[tuple[int, int]],
    intents: Iterable[TransitionIntent],
) -> dict[tuple[int, int, str], float]:
    """Compute the GA's score-cache entries for ``pairs`` x ``intents``.

    Returns the same shape ``GeneticAlgorithm._eager_populate_cache``
    populates: ``{(idx_a, idx_b, intent_value): overall_or_zero}``.
    Hard-rejected pairs land at ``0.0`` for every intent (matches the
    scalar path's ``hard_reject → overall=0`` semantics).
    """
    intents_list = list(intents)
    if not pairs or not intents_list:
        return {}

    ia = np.fromiter((p[0] for p in pairs), dtype=np.int64, count=len(pairs))
    ib = np.fromiter((p[1] for p in pairs), dtype=np.int64, count=len(pairs))

    bpm = score_bpm_bulk(fa, ia, ib)
    energy = score_energy_bulk(fa, ia, ib)
    drums = score_drums_bulk(fa, ia, ib)
    bass = score_bass_bulk(fa, ia, ib)
    harmonics = score_harmonics_bulk(fa, ia, ib)
    vocals = score_vocals_bulk(fa, ia, ib)

    rejected = hard_reject_mask_bulk(fa, ia, ib)

    out: dict[tuple[int, int, str], float] = {}
    for intent in intents_list:
        weights = INTENT_WEIGHT_MODIFIERS[intent]
        overall = (
            weights.get("bpm", 0.0) * bpm
            + weights.get("energy", 0.0) * energy
            + weights.get("drums", 0.0) * drums
            + weights.get("bass", 0.0) * bass
            + weights.get("harmonics", 0.0) * harmonics
            + weights.get("vocals", 0.0) * vocals
        )
        overall = np.where(rejected, 0.0, overall)
        for k, p in enumerate(pairs):
            out[(p[0], p[1], intent.value)] = float(overall[k])
    return out
