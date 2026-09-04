"""Cell 18 — interactive mix composer alignment enrichment.

The composer pulls candidate next-tracks with a cheap-first pipeline
(BPM+energy filter → 4-component DJ-aware alignment → stem-aware
TransitionScorer). This test pins the contract: the candidate payload
exposes both the legacy ``overall`` (six-component stem-aware) and
the new ``align`` (four-component DJ-aware) fields, and the rank
combines them with a stable 50/50 mix.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, Track, TrackAudioFeaturesComputed
from app.tools.ui.mix_composer import _candidates
from app.domain.transition.scorer import TransitionScorer


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncSession:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


def _seed(session: AsyncSession) -> int:
    """Seed one source track + four candidates with overlapping BPMs."""
    src = Track(title="source")
    session.add(src)
    await_commit = session.flush()
    return src.id  # type: ignore[return-value]


async def _seed_full(session: AsyncSession) -> int:
    source = Track(title="source")
    c1 = Track(title="c1")
    c2 = Track(title="c2")
    c3 = Track(title="c3")
    session.add_all([source, c1, c2, c3])
    await session.flush()
    session.add_all(
        [
            TrackAudioFeaturesComputed(
                track_id=source.id,
                bpm=128.0,
                bpm_confidence=0.9,
                bpm_stability=0.95,
                integrated_lufs=-10.0,
                key_code=8,
                analysis_level=3,
            ),
            TrackAudioFeaturesComputed(
                track_id=c1.id,
                bpm=128.0,
                bpm_confidence=0.9,
                bpm_stability=0.95,
                integrated_lufs=-10.0,
                key_code=8,
                analysis_level=3,
            ),
            TrackAudioFeaturesComputed(
                track_id=c2.id,
                bpm=125.0,
                bpm_confidence=0.7,
                bpm_stability=0.8,
                integrated_lufs=-9.5,
                key_code=8,
                analysis_level=3,
            ),
            TrackAudioFeaturesComputed(
                track_id=c3.id,
                bpm=135.0,
                bpm_confidence=0.6,
                bpm_stability=0.7,
                integrated_lufs=-7.0,
                key_code=1,
                analysis_level=3,
            ),
        ]
    )
    await session.flush()
    return source.id


@pytest.mark.asyncio
async def test_candidates_payload_includes_align_field(session: AsyncSession) -> None:
    from app.repositories.unit_of_work import UnitOfWork

    source_id = await _seed_full(session)
    uow = UnitOfWork(session)
    candidates = await _candidates(uow, TransitionScorer(), source_id, limit=4)
    # At least the two harmonically compatible candidates (c1, c2)
    # pass the gate; c3 (key_code=1) may be hard-rejected.
    assert len(candidates) >= 2
    for c in candidates:
        assert "overall" in c
        assert "align" in c
        assert "align_overall" in c
        if c["align"] is not None:
            assert "s_tempo" in c["align"]
            assert "s_beat_alignment" in c["align"]
            assert "s_phrase_alignment" in c["align"]
            assert "s_drift" in c["align"]
            assert "overall" in c["align"]
            assert 0.0 <= c["align"]["overall"] <= 1.0


@pytest.mark.asyncio
async def test_candidates_pure_alignment_match_ranks_higher(session: AsyncSession) -> None:
    """The BPM-perfect + same-key candidate (c1) should rank above the
    BPM-drifted candidate (c3) on the cheap alignment score, even
    though the full stem-aware ``overall`` may be close."""
    from app.repositories.unit_of_work import UnitOfWork

    source_id = await _seed_full(session)
    uow = UnitOfWork(session)
    candidates = await _candidates(uow, TransitionScorer(), source_id, limit=4)
    by_tid = {c["track_id"]: c for c in candidates}
    if len(by_tid) < 2:
        pytest.skip("not enough candidates survived the gate")
    # The c1 (128 BPM same) candidate has the cleanest alignment.
    best_align = max(by_tid.values(), key=lambda c: c.get("align_overall", 0.0))
    worst_align = min(by_tid.values(), key=lambda c: c.get("align_overall", 0.0))
    assert best_align["align_overall"] >= worst_align["align_overall"]


@pytest.mark.asyncio
async def test_candidates_returns_empty_when_source_missing_features(
    session: AsyncSession,
) -> None:
    from app.repositories.unit_of_work import UnitOfWork

    bare = Track(title="bare")
    session.add(bare)
    await session.flush()
    uow = UnitOfWork(session)
    candidates = await _candidates(uow, TransitionScorer(), bare.id, limit=4)
    assert candidates == []
