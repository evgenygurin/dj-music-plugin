"""Bulk scoring path must match the scalar path bit-for-bit.

The scalar code in ``app.domain.transition.scorer`` /
``neural_mix`` / ``components/`` is the public API and the source of
truth — every score the LLM, REST, and panel layers see comes from
it. The bulk path in ``app.domain.transition.bulk_scorer`` is an
internal numpy clone wired into ``GeneticAlgorithm._eager_populate_cache``
for speed. If the two paths ever drift, optimised set orderings would
silently disagree with the per-pair score the user sees in
``transition_score_pool`` / ``ui_transition_score``.

The randomised pool below covers:
* missing fields (None → nan / -1 sentinel),
* hard-rejects (BPM/Camelot/LUFS gates),
* every ``TransitionIntent`` enum value,
* every TrackFeatures field the scoring functions read.

Tolerance is 1e-9 (sum-of-products floating-point noise; the formulas
are identical, only the iteration order differs).
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from app.domain.transition.bulk_scorer import (
    extract_feature_arrays,
    hard_reject_mask_bulk,
    score_bass_bulk,
    score_bpm_bulk,
    score_drums_bulk,
    score_energy_bulk,
    score_harmonics_bulk,
    score_pairs_bulk,
    score_vocals_bulk,
)
from app.domain.transition.components import score_bpm, score_energy
from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.neural_mix import (
    score_bass_compat,
    score_drums_compat,
    score_harmonic_compat,
    score_vocal_compat,
)
from app.domain.transition.scorer import TransitionScorer
from app.shared.features import TrackFeatures

_PARITY_TOL = 1e-9


def _make_track(rng: random.Random, *, drop_chance: float = 0.1) -> TrackFeatures:
    """Generate one TrackFeatures with realistic ranges; randomly drop fields.

    drop_chance is per-field probability of None — exercises the
    "missing field" branches of every scorer.
    """

    def maybe(value: float | int | bool | list[float] | None) -> object:
        return None if rng.random() < drop_chance else value

    mfcc = [rng.gauss(0.0, 50.0) for _ in range(13)]
    tonnetz = [rng.gauss(0.0, 1.0) for _ in range(6)]
    energy_bands = [rng.uniform(0.0, 0.5) for _ in range(6)]
    beat_loudness = [rng.uniform(0.1, 1.0) for _ in range(6)]

    return TrackFeatures(
        bpm=maybe(rng.uniform(115.0, 145.0)),  # type: ignore[arg-type]
        bpm_stability=maybe(rng.uniform(0.5, 1.0)),  # type: ignore[arg-type]
        bpm_confidence=maybe(rng.uniform(0.5, 1.0)),  # type: ignore[arg-type]
        variable_tempo=maybe(rng.choice([True, False])),  # type: ignore[arg-type]
        key_code=maybe(rng.randint(0, 23)),  # type: ignore[arg-type]
        key_confidence=rng.uniform(0.6, 1.0),
        integrated_lufs=maybe(rng.uniform(-14.0, -4.0)),  # type: ignore[arg-type]
        short_term_lufs_mean=rng.uniform(-14.0, -4.0),
        loudness_range_lu=maybe(rng.uniform(2.0, 8.0)),  # type: ignore[arg-type]
        crest_factor_db=maybe(rng.uniform(5.0, 15.0)),  # type: ignore[arg-type]
        energy_slope=maybe(rng.uniform(-0.3, 0.3)),  # type: ignore[arg-type]
        energy_mean=rng.uniform(0.2, 0.6),
        spectral_centroid_hz=maybe(rng.uniform(1200.0, 4800.0)),  # type: ignore[arg-type]
        spectral_contrast=maybe(rng.uniform(0.2, 0.9)),  # type: ignore[arg-type]
        chroma_entropy=maybe(rng.uniform(0.4, 0.9)),  # type: ignore[arg-type]
        pitch_salience_mean=maybe(rng.uniform(0.1, 0.6)),  # type: ignore[arg-type]
        onset_rate=maybe(rng.uniform(2.0, 9.0)),  # type: ignore[arg-type]
        kick_prominence=maybe(rng.uniform(0.2, 0.9)),  # type: ignore[arg-type]
        hnr_db=maybe(rng.uniform(-25.0, -3.0)),  # type: ignore[arg-type]
        dissonance_mean=maybe(rng.uniform(0.2, 0.6)),  # type: ignore[arg-type]
        mfcc_vector=maybe(mfcc),  # type: ignore[arg-type]
        tonnetz_vector=maybe(tonnetz),  # type: ignore[arg-type]
        energy_bands=maybe(energy_bands),  # type: ignore[arg-type]
        beat_loudness_band_ratio=maybe(beat_loudness),  # type: ignore[arg-type]
    )


def _pool(seed: int = 7, n: int = 30) -> list[TrackFeatures]:
    rng = random.Random(seed)
    return [_make_track(rng) for _ in range(n)]


def _all_pairs(n: int) -> tuple[list[tuple[int, int]], np.ndarray, np.ndarray]:
    pairs = [(a, b) for a in range(n) for b in range(n) if a != b]
    ia = np.array([p[0] for p in pairs], dtype=np.int64)
    ib = np.array([p[1] for p in pairs], dtype=np.int64)
    return pairs, ia, ib


def _scalar_call(
    fn,  # type: ignore[no-untyped-def]
    tracks: list[TrackFeatures],
    pairs: list[tuple[int, int]],
) -> np.ndarray:
    return np.array([fn(tracks[a], tracks[b]) for a, b in pairs], dtype=np.float64)


@pytest.fixture(scope="module")
def pool() -> list[TrackFeatures]:
    return _pool()


@pytest.fixture(scope="module")
def fa(pool):  # type: ignore[no-untyped-def]
    return extract_feature_arrays(pool)


@pytest.fixture(scope="module")
def pair_arrays(pool):  # type: ignore[no-untyped-def]
    return _all_pairs(len(pool))


def test_score_bpm_parity(pool, fa, pair_arrays) -> None:  # type: ignore[no-untyped-def]
    pairs, ia, ib = pair_arrays
    bulk = score_bpm_bulk(fa, ia, ib)
    scalar = _scalar_call(score_bpm, pool, pairs)
    np.testing.assert_allclose(bulk, scalar, atol=_PARITY_TOL)


def test_score_energy_parity(pool, fa, pair_arrays) -> None:  # type: ignore[no-untyped-def]
    pairs, ia, ib = pair_arrays
    bulk = score_energy_bulk(fa, ia, ib)
    scalar = _scalar_call(score_energy, pool, pairs)
    np.testing.assert_allclose(bulk, scalar, atol=_PARITY_TOL)


def test_score_drums_parity(pool, fa, pair_arrays) -> None:  # type: ignore[no-untyped-def]
    pairs, ia, ib = pair_arrays
    bulk = score_drums_bulk(fa, ia, ib)
    scalar = _scalar_call(score_drums_compat, pool, pairs)
    np.testing.assert_allclose(bulk, scalar, atol=_PARITY_TOL)


def test_score_bass_parity(pool, fa, pair_arrays) -> None:  # type: ignore[no-untyped-def]
    pairs, ia, ib = pair_arrays
    bulk = score_bass_bulk(fa, ia, ib)
    scalar = _scalar_call(score_bass_compat, pool, pairs)
    np.testing.assert_allclose(bulk, scalar, atol=_PARITY_TOL)


def test_score_harmonics_parity(pool, fa, pair_arrays) -> None:  # type: ignore[no-untyped-def]
    pairs, ia, ib = pair_arrays
    bulk = score_harmonics_bulk(fa, ia, ib)
    scalar = _scalar_call(score_harmonic_compat, pool, pairs)
    np.testing.assert_allclose(bulk, scalar, atol=_PARITY_TOL)


def test_score_vocals_parity(pool, fa, pair_arrays) -> None:  # type: ignore[no-untyped-def]
    pairs, ia, ib = pair_arrays
    bulk = score_vocals_bulk(fa, ia, ib)
    scalar = _scalar_call(score_vocal_compat, pool, pairs)
    np.testing.assert_allclose(bulk, scalar, atol=_PARITY_TOL)


def test_hard_reject_mask_parity(pool, fa, pair_arrays) -> None:  # type: ignore[no-untyped-def]
    pairs, ia, ib = pair_arrays
    bulk = hard_reject_mask_bulk(fa, ia, ib)
    scalar = np.array(
        [check_hard_constraints(pool[a], pool[b]) is not None for a, b in pairs],
        dtype=np.bool_,
    )
    np.testing.assert_array_equal(bulk, scalar)


@pytest.mark.parametrize("intent", list(TransitionIntent))
def test_score_pairs_overall_parity(
    pool,  # type: ignore[no-untyped-def]
    fa,
    pair_arrays,
    intent: TransitionIntent,
) -> None:
    """End-to-end: bulk per-intent overall == scalar score(a, b, intent=I).overall.

    For hard-rejected pairs both paths land on 0.0 (scalar via
    ``check_hard_constraints`` short-circuit, bulk via the
    ``hard_reject_mask`` ``np.where`` clamp).
    """
    pairs, _ia, _ib = pair_arrays
    scorer = TransitionScorer()

    bulk_dict = score_pairs_bulk(fa, pairs, [intent])
    bulk = np.array([bulk_dict[(a, b, intent.value)] for a, b in pairs], dtype=np.float64)

    scalar = np.array(
        [
            (lambda s: 0.0 if s.hard_reject else s.overall)(
                scorer.score(pool[a], pool[b], intent=intent)
            )
            for a, b in pairs
        ],
        dtype=np.float64,
    )
    np.testing.assert_allclose(bulk, scalar, atol=_PARITY_TOL)


# ---------------------------------------------------------------------------
# Phase-0 baseline guard (v1.5.0 refactor): bulk path does NOT yet apply the
# section_context overlay. Scalar path DOES (since PR #219). Until Phase 3
# wires bulk into the same overlay chain via CompositeScorer, this test
# documents the asymmetry: bulk overall == scalar overall WITHOUT context,
# regardless of what context the caller passes. Phase 3 will strengthen
# this to "bulk overall == scalar overall WITH ctx".
# ---------------------------------------------------------------------------

from app.domain.transition.section_context import SectionContext
from app.shared.constants import SectionType

_SECTION_CONTEXTS = [
    None,
    SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO),  # drum_only
    SectionContext(from_section=SectionType.DROP, to_section=SectionType.DROP),  # drop_to_drop
    SectionContext(
        from_section=SectionType.BREAKDOWN, to_section=SectionType.INTRO
    ),  # breakdown_out
    SectionContext(from_section=SectionType.BUILD, to_section=SectionType.DROP),  # buildup_in
]


def _ctx_id(ctx: SectionContext | None) -> str:
    return "none" if ctx is None else ctx.section_pair_class.value


@pytest.mark.parametrize("intent", list(TransitionIntent))
@pytest.mark.parametrize("ctx", _SECTION_CONTEXTS, ids=_ctx_id)
def test_score_pairs_overall_baseline_under_section_context(
    pool,  # type: ignore[no-untyped-def]
    fa,
    pair_arrays,
    intent: TransitionIntent,
    ctx: SectionContext | None,
) -> None:
    """Document v1.4.0 asymmetry: bulk has no overlay; must match no-ctx scalar.

    After Phase 3 (bulk wired to CompositeScorer), this test becomes
    "bulk matches scalar WITH ctx" — kept as-is to surface the change
    as a deliberate snapshot regen.
    """
    pairs, _ia, _ib = pair_arrays
    scorer = TransitionScorer()

    bulk_dict = score_pairs_bulk(fa, pairs, [intent])
    bulk = np.array([bulk_dict[(a, b, intent.value)] for a, b in pairs], dtype=np.float64)

    scalar_no_ctx = np.array(
        [
            (lambda s: 0.0 if s.hard_reject else s.overall)(
                scorer.score(pool[a], pool[b], intent=intent)
            )
            for a, b in pairs
        ],
        dtype=np.float64,
    )
    # ctx is held for documentation purposes; bulk currently ignores it.
    _ = ctx
    np.testing.assert_allclose(bulk, scalar_no_ctx, atol=_PARITY_TOL)
