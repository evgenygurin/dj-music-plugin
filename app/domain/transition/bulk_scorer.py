"""Vectorised transition scoring — thin adapter.

Delegates to ``scoring/components/*`` for stem bulk scores and to
``scoring/bulk/arrays`` for ``FeatureArrays``. The public API is
preserved unchanged so existing callers are unaffected.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import numpy.typing as npt

from app.config import get_settings
from app.domain.transition.intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.domain.transition.kernels.bpm_distance import bpm_distance_bulk
from app.domain.transition.scoring.bulk.arrays import (
    FeatureArrays,
    extract_feature_arrays,
    key_reliable_mask,
)
from app.domain.transition.scoring.bulk.stem_weight_matrix import (
    energy_bias_modifier_bulk,
    get_bias_vec,
    get_stem_weight_matrix,
)
from app.domain.transition.scoring.components.bass import BassComponent
from app.domain.transition.scoring.components.drums import DrumsComponent
from app.domain.transition.scoring.components.harmonics import HarmonicsComponent
from app.domain.transition.scoring.components.vocals import VocalsComponent
from app.domain.transition.weights import (
    BPM_CONFIDENCE_PENALTY_FLOOR,
    BPM_GAUSS_SIGMA,
    BPM_STABILITY_FLOOR,
    ENERGY_PREFERRED_RISE_LUFS,
    ENERGY_SIGMOID_DIVISOR,
)

FloatArr = npt.NDArray[np.float64]
BoolArr = npt.NDArray[np.bool_]
IntArr = npt.NDArray[np.int64]

_NAN = np.float64("nan")

_STEM_W_MATRIX = get_stem_weight_matrix()
_BIAS_VEC = get_bias_vec()

_drums_comp = DrumsComponent()
_bass_comp = BassComponent()
_harmonics_comp = HarmonicsComponent()
_vocals_comp = VocalsComponent()


def _cosine_similarity_bulk(matrix: FloatArr, ia: IntArr, ib: IntArr) -> FloatArr:
    from app.domain.transition.kernels.cosine import cosine_similarity_bulk

    return cosine_similarity_bulk(matrix, ia, ib)


# ── Hard-reject vectorised ────────────────────────────────────────


def hard_reject_mask_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> BoolArr:
    settings = get_settings().transition

    bpm_a = fa.bpm[ia]
    bpm_b = fa.bpm[ib]
    bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
    bpm_diff = bpm_distance_bulk(bpm_a, bpm_b)
    bpm_violates = bpm_present & (bpm_diff > settings.hard_reject_bpm_diff)

    key_a = fa.key_code[ia]
    key_b = fa.key_code[ib]
    key_present = (key_a >= 0) & (key_b >= 0)
    safe_key_a = np.where(key_present, key_a, 0)
    safe_key_b = np.where(key_present, key_b, 0)
    _camelot = _camelot_distance_table()
    key_dist = _camelot[safe_key_a, safe_key_b]
    reliable = key_reliable_mask(fa, ia) & key_reliable_mask(fa, ib)
    key_violates = key_present & reliable & (key_dist >= settings.hard_reject_camelot_dist)

    lufs_a = fa.integrated_lufs[ia]
    lufs_b = fa.integrated_lufs[ib]
    lufs_present = ~(np.isnan(lufs_a) | np.isnan(lufs_b))
    energy_gap = np.abs(lufs_a - lufs_b)
    lufs_violates = lufs_present & (energy_gap > settings.hard_reject_energy_gap_lufs)

    return bpm_violates | key_violates | lufs_violates


def _camelot_distance_table() -> IntArr:
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


# ── Component scoring (delegated to scoring/components) ───────────


def score_bpm_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
    settings = get_settings().transition

    bpm_a = fa.bpm[ia]
    bpm_b = fa.bpm[ib]
    bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))

    delta = bpm_distance_bulk(bpm_a, bpm_b)
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

    return np.where(bpm_present, score, 0.5)


def score_energy_bulk(fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr:
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


score_drums_bulk = _drums_comp.score_pairs
score_bass_bulk = _bass_comp.score_pairs
score_harmonics_bulk = _harmonics_comp.score_pairs
score_vocals_bulk = _vocals_comp.score_pairs


# ── Bulk overall ──────────────────────────────────────────────────


def neural_best_overall_bulk(
    fa: FeatureArrays,
    ia: IntArr,
    ib: IntArr,
    drums: FloatArr,
    bass: FloatArr,
    harmonics: FloatArr,
    vocals: FloatArr,
) -> FloatArr:
    stems = np.stack([drums, bass, harmonics, vocals], axis=1)
    base = stems @ _STEM_W_MATRIX.T
    lufs_a = fa.integrated_lufs[ia]
    lufs_b = fa.integrated_lufs[ib]
    delta = lufs_b - lufs_a
    delta = np.where(np.isnan(delta), 0.0, delta)
    modifier = energy_bias_modifier_bulk(delta)
    transition_scores = np.clip(base * modifier, 0.0, 1.0)
    return np.asarray(transition_scores.max(axis=1), dtype=np.float64)


# ── Public bulk API ───────────────────────────────────────────────


def score_pairs_bulk(
    fa: FeatureArrays,
    pairs: Sequence[tuple[int, int]],
    intents: Iterable[TransitionIntent],
) -> dict[tuple[int, int, str], float]:
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


__all__ = [
    "FeatureArrays",
    "extract_feature_arrays",
    "hard_reject_mask_bulk",
    "neural_best_overall_bulk",
    "score_bass_bulk",
    "score_bpm_bulk",
    "score_drums_bulk",
    "score_energy_bulk",
    "score_harmonics_bulk",
    "score_pairs_bulk",
    "score_vocals_bulk",
]
