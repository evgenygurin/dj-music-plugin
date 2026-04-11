"""Tests for PrefetchService — speculative candidate preparation.

Covers:
- Empty pool short-circuit (no DB work)
- Missing seed features short-circuit
- Warm transition cache: inserts missing pairs, skips existing ones
- Hard reject accounting
- Top-K selection bounded by requested k
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.db.models.transition import Transition
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.transition import TransitionRepository
from app.services.prefetch_service import PrefetchService


def _make_features(track_id: int, **kwargs: object) -> TrackAudioFeaturesComputed:
    """Build a TrackAudioFeaturesComputed row with sane defaults.

    Defaults produce a techno-compatible profile so TransitionScorer doesn't
    hard-reject by BPM/key/energy unless a test explicitly overrides them.
    """
    defaults: dict[str, object] = {
        "track_id": track_id,
        "bpm": 128.0,
        "bpm_stability": 0.9,
        "key_code": 14,  # 8A
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 3000.0,
        "spectral_flatness": 0.15,
        "energy_mean": 0.6,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
        "hnr_db": -10.0,
        "chroma_entropy": 1.0,
        "hp_ratio": 1.5,
        "analysis_level": 3,
    }
    defaults.update(kwargs)
    return TrackAudioFeaturesComputed(**defaults)  # type: ignore[arg-type]


async def _seed_tracks_with_features(
    db: AsyncSession,
    count: int,
    start_bpm: float = 128.0,
) -> list[int]:
    """Create N tracks each with compatible features. Returns IDs."""
    ids: list[int] = []
    for i in range(count):
        track = Track(title=f"Track {i + 1}", duration_ms=300_000, status=0)
        db.add(track)
        await db.flush()
        db.add(_make_features(track.id, bpm=start_bpm + i * 0.5))
        await db.flush()
        ids.append(track.id)
    return ids


def _make_service(db: AsyncSession) -> PrefetchService:
    return PrefetchService(
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
        tiered_pipeline=None,  # analysis path is covered separately
    )


@pytest.mark.asyncio
async def test_prefetch_after_empty_pool_noop(db: AsyncSession) -> None:
    """Empty pool returns a zeroed result and touches no rows."""
    ids = await _seed_tracks_with_features(db, count=1)
    svc = _make_service(db)

    result = await svc.prefetch_after(ids[0], [], top_k=5)

    assert result.candidates_considered == 0
    assert result.pairs_scored == 0
    assert result.top_candidate_ids == []


@pytest.mark.asyncio
async def test_prefetch_skips_when_seed_has_no_features(db: AsyncSession) -> None:
    """If the seed lacks features, prefetch short-circuits without error."""
    # Track without features row
    track = Track(title="Orphan", duration_ms=300_000, status=0)
    db.add(track)
    await db.flush()
    pool = await _seed_tracks_with_features(db, count=3)
    svc = _make_service(db)

    result = await svc.prefetch_after(track.id, pool, top_k=5)
    assert result.pairs_scored == 0
    assert result.top_candidate_ids == []


@pytest.mark.asyncio
async def test_prefetch_warms_transition_cache(db: AsyncSession) -> None:
    """Every non-rejected candidate produces a persisted Transition row."""
    ids = await _seed_tracks_with_features(db, count=5)  # all mutually compatible
    seed, *pool = ids
    svc = _make_service(db)

    result = await svc.prefetch_after(seed, pool, top_k=3)

    # Top-K bound: we asked for 3, pool has 4 candidates all accepted, but
    # only top_k rows should be pre-warmed.
    assert result.pairs_scored == 4
    assert result.hard_rejects == 0
    assert len(result.top_candidate_ids) == 3

    # Verify DB has exactly 3 transitions seeded from this seed.
    trepo = TransitionRepository(db)
    cached = await trepo.get_scores_for_seed(seed, pool)
    assert len(cached) == 3


@pytest.mark.asyncio
async def test_prefetch_skips_already_cached_pairs(db: AsyncSession) -> None:
    """Pairs that already have a Transition row should not be re-computed."""
    ids = await _seed_tracks_with_features(db, count=4)
    seed, c1, c2, c3 = ids

    # Pre-populate one existing transition so prefetch should report a hit.
    trepo = TransitionRepository(db)
    await trepo.save_score(
        Transition(
            from_track_id=seed,
            to_track_id=c1,
            overall_quality=0.77,
            bpm_score=1.0,
            harmonic_score=1.0,
            energy_score=0.5,
            spectral_score=0.5,
            groove_score=0.5,
            timbral_score=0.5,
        )
    )

    svc = _make_service(db)
    result = await svc.prefetch_after(seed, [c1, c2, c3], top_k=3)

    # c1 already cached (hit); c2, c3 freshly warmed.
    assert result.pairs_cached_hit >= 1
    # DB now has a row for every top candidate.
    cached = await trepo.get_scores_for_seed(seed, [c1, c2, c3])
    assert set(cached.keys()) == {c1, c2, c3}
    # The existing row was NOT overwritten (still 0.77).
    assert cached[c1].overall_quality == pytest.approx(0.77, abs=1e-6)


@pytest.mark.asyncio
async def test_prefetch_counts_hard_rejects(db: AsyncSession) -> None:
    """Candidates failing hard constraints should bump hard_rejects."""
    seed_ids = await _seed_tracks_with_features(db, count=1)  # BPM 128.0
    seed = seed_ids[0]

    # Candidate too fast (BPM 145 → diff=17 > 10 hard reject threshold).
    fast = Track(title="Too fast", duration_ms=300_000, status=0)
    db.add(fast)
    await db.flush()
    db.add(_make_features(fast.id, bpm=145.0))

    # Candidate compatible.
    ok = Track(title="Compat", duration_ms=300_000, status=0)
    db.add(ok)
    await db.flush()
    db.add(_make_features(ok.id, bpm=129.0))
    await db.flush()

    svc = _make_service(db)
    result = await svc.prefetch_after(seed, [fast.id, ok.id], top_k=5)

    assert result.hard_rejects == 1
    assert result.pairs_scored == 1
    assert result.top_candidate_ids == [ok.id]


@pytest.mark.asyncio
async def test_prefetch_ignores_seed_in_pool(db: AsyncSession) -> None:
    """If the seed accidentally appears in pool_ids it must not self-score."""
    ids = await _seed_tracks_with_features(db, count=3)
    seed = ids[0]
    svc = _make_service(db)

    result = await svc.prefetch_after(seed, ids, top_k=5)

    assert seed not in result.top_candidate_ids
    assert result.pairs_scored == 2  # only the two non-seed tracks
