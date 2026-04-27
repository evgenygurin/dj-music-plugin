"""Regression: ``best_pairs`` orders non-null scores first.

Audit O-2: ``local://transition_history/best_pairs`` returned entries
with ``overall_score=null`` BEFORE entries with real scores, despite
the resource being labelled "best pairs". Root cause was
``order_by(desc(overall_score))`` — Postgres places NULL first under
DESC unless explicitly told otherwise. Repo must use ``nulls_last()``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, Track, TransitionHistory
from app.repositories.transition_history import TransitionHistoryRepository


@pytest_asyncio.fixture
async def setup(engine: AsyncEngine, session: AsyncSession) -> TransitionHistoryRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    a = Track(title="A")
    b = Track(title="B")
    c = Track(title="C")
    session.add_all([a, b, c])
    await session.flush()
    session.add_all(
        [
            TransitionHistory(from_track_id=a.id, to_track_id=b.id, overall_score=None),
            TransitionHistory(from_track_id=b.id, to_track_id=c.id, overall_score=0.91),
            TransitionHistory(from_track_id=a.id, to_track_id=c.id, overall_score=0.42),
        ]
    )
    await session.flush()
    return TransitionHistoryRepository(session)


@pytest.mark.asyncio
async def test_best_pairs_puts_null_scores_last(
    setup: TransitionHistoryRepository,
) -> None:
    rows = await setup.best_pairs(limit=10)
    scores = [r.overall_score for r in rows]
    # First two must be the real scores in DESC order; null trails.
    assert scores[:2] == [0.91, 0.42]
    assert scores[-1] is None


def test_best_pairs_query_uses_nulls_last() -> None:
    """SQLite places NULLs last under DESC by default — Postgres places
    them first. The audit caught the regression on Supabase. Pin the
    explicit ``NULLS LAST`` clause via the compiled SQL so the bug
    can't regress on prod even when the SQLite-backed test suite is
    unable to reproduce it.
    """
    from sqlalchemy.dialects import postgresql

    from app.models.transition_history import TransitionHistory
    from app.repositories.transition_history import (
        _best_pairs_stmt,  # type: ignore[attr-defined]
    )

    compiled = str(
        _best_pairs_stmt(limit=10).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "NULLS LAST" in compiled.upper(), (
        f"best_pairs query must use NULLS LAST on Postgres; got:\n{compiled}"
    )
    # Sanity: scoring column is still ordered DESC.
    assert "ORDER BY" in compiled.upper()
    assert TransitionHistory.__tablename__ in compiled
