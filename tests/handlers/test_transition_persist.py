"""TransitionPersistHandler tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastmcp.server.context import Context
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.handlers.transition_persist import transition_persist_handler
from app.models.base import Base
from app.models.track import Track
from app.repositories.transition import TransitionRepository
from app.shared.errors import NotFoundError


@pytest.fixture
def ctx() -> MagicMock:
    return MagicMock(spec=Context)


@pytest.fixture
def uow() -> MagicMock:
    u = MagicMock()
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock()}
    )
    # Restrict to the actual repository surface so the test catches calls to
    # methods that don't exist on the real ``TransitionRepository``.
    u.transitions = MagicMock(spec=["upsert", "get_pair", "create", "update"])
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=10))
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock()
    score.overall = 0.82
    score.bpm = 0.9
    score.harmonics = 0.8
    score.energy = 0.75
    score.bass = 0.85
    score.drums = 0.78
    score.vocals = 0.82
    score.hard_reject = False
    score.reject_reason = None
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_scores_and_persists_pair(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)

    assert result["from_track_id"] == 1
    assert result["to_track_id"] == 2
    assert result["overall"] == pytest.approx(0.82)
    uow.transitions.upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_features_raises(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.track_features.get_scoring_features_batch.return_value = {1: MagicMock()}
    data = {"from_track_id": 1, "to_track_id": 2}
    with pytest.raises(NotFoundError):
        await transition_persist_handler(ctx, uow, data, scorer)


@pytest.mark.asyncio
async def test_hard_reject_is_persisted_with_zero_overall(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    rejected = MagicMock()
    rejected.overall = 0.0
    rejected.hard_reject = True
    rejected.reject_reason = "bpm_diff>10"
    rejected.bpm = rejected.harmonic = rejected.energy = 0.0
    rejected.spectral = rejected.groove = rejected.timbral = 0.0
    scorer.score.return_value = rejected

    data = {"from_track_id": 1, "to_track_id": 2}
    result = await transition_persist_handler(ctx, uow, data, scorer)
    assert result["hard_reject"] is True
    assert result["overall"] == 0.0
    uow.transitions.upsert.assert_awaited_once()


# ── Real-DB regression for BUG: TransitionRepository.upsert must exist. ──


@pytest_asyncio.fixture
async def real_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def real_session(real_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(real_engine, expire_on_commit=False)
    async with factory() as s:
        # Seed two real tracks so transition FKs validate.
        s.add(Track(id=1, title="A", sort_title="a", duration_ms=180_000))
        s.add(Track(id=2, title="B", sort_title="b", duration_ms=180_000))
        await s.flush()
        try:
            yield s
        finally:
            await s.rollback()


@pytest.mark.asyncio
async def test_transition_repository_upsert_creates_then_updates(
    real_session: AsyncSession,
) -> None:
    """Regression: ``TransitionRepository.upsert`` must exist and behave as
    upsert — first call creates, second call with the same (from, to) pair
    updates in place rather than raising AttributeError.
    """
    repo = TransitionRepository(real_session)

    row1 = await repo.upsert(
        from_track_id=1,
        to_track_id=2,
        bpm_score=0.9,
        harmonics_score=0.8,
        energy_score=0.7,
        bass_score=0.85,
        drums_score=0.75,
        vocals_score=0.8,
        overall_quality=0.8,
        hard_reject=False,
        reject_reason=None,
    )
    assert row1.id is not None

    row2 = await repo.upsert(
        from_track_id=1,
        to_track_id=2,
        bpm_score=0.5,
        harmonics_score=0.5,
        energy_score=0.5,
        bass_score=0.5,
        drums_score=0.5,
        vocals_score=0.5,
        overall_quality=0.5,
        hard_reject=False,
        reject_reason=None,
    )
    # Same row should be reused (upsert, not insert).
    assert row2.id == row1.id
    assert row2.overall_quality == pytest.approx(0.5)
