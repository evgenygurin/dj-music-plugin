"""Audit iter 59 (T-57): ``best_pairs`` returned leftover self-pair
rows (``from_track_id == to_track_id``) that pre-T-52 inserts had
left in production. Schema validators (v1.2.51-52) prevent new ones,
but historical data still polluted the "best pairs" view.

Live confirmation:

    /transition_history/best_pairs?limit=3
    -> [{147,148,score=0.75}, {146,146,score=null}, {146,146,score=null}]
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^ pre-T-52 detritus

Now ``_best_pairs_stmt`` adds ``WHERE from_track_id != to_track_id``
so all consumers (best_pairs resource + history endpoint, which
falls back to best_pairs) skip degenerate rows.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.models.track import Track
from app.models.transition_history import TransitionHistory
from app.repositories.transition_history import TransitionHistoryRepository


async def _seed_tracks(session: AsyncSession, *ids: int) -> None:
    """Insert minimal ``Track`` rows so FK constraints can resolve.

    Required after SQLite ``PRAGMA foreign_keys=ON`` (commit landing
    this fixture): previously the tests relied on SQLite's silent
    drop of FK enforcement, which let them insert ``TransitionHistory``
    rows with track ids no ``Track`` row existed for. PG would have
    rejected the same rows in prod.
    """
    for tid in set(ids):
        session.add(
            Track(id=tid, title=f"T{tid}", sort_title=f"t{tid}", duration_ms=200_000, status=0)
        )
    await session.flush()


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TransitionHistoryRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return TransitionHistoryRepository(session)


@pytest.mark.asyncio
async def test_best_pairs_filters_self_pairs(
    repo: TransitionHistoryRepository, session: AsyncSession
) -> None:
    """A row with ``from == to`` is silently filtered from the result."""
    await _seed_tracks(session, 146, 147, 148, 149, 150, 151)
    session.add_all(
        [
            TransitionHistory(from_track_id=147, to_track_id=148, overall_score=0.75),
            TransitionHistory(from_track_id=146, to_track_id=146, overall_score=None),
            TransitionHistory(from_track_id=149, to_track_id=149, overall_score=0.9),
            TransitionHistory(from_track_id=150, to_track_id=151, overall_score=0.8),
        ]
    )
    await session.flush()

    rows = await repo.best_pairs(limit=10)
    pairs = [(r.from_track_id, r.to_track_id) for r in rows]
    assert (146, 146) not in pairs
    assert (149, 149) not in pairs
    # The two distinct pairs survive.
    assert (147, 148) in pairs
    assert (150, 151) in pairs


@pytest.mark.asyncio
async def test_best_pairs_only_self_pairs_returns_empty(
    repo: TransitionHistoryRepository, session: AsyncSession
) -> None:
    """If the only existing rows are self-pairs, the result is empty."""
    await _seed_tracks(session, 146, 147)
    session.add_all(
        [
            TransitionHistory(from_track_id=146, to_track_id=146, overall_score=0.9),
            TransitionHistory(from_track_id=147, to_track_id=147, overall_score=0.8),
        ]
    )
    await session.flush()

    rows = await repo.best_pairs(limit=10)
    assert rows == []
