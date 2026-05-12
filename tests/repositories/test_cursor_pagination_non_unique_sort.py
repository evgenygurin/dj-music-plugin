"""Regression: cursor pagination on a non-unique sort field must NOT
silently drop rows that share the boundary value.

Before this guard, sorting by ``status`` (all rows status=0) with a
small limit emitted ``next_cursor=encode_cursor(0)``; the follow-up
call then issued ``WHERE status > 0`` and returned an empty page —
data loss with no signal. The fix:

1. No ``next_cursor`` is emitted when the sort key is non-unique.
2. Passing a cursor anyway is refused loudly with guidance ("sort by
   the primary key").
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.base import Base
from app.models.track import Track
from app.repositories.track import TrackRepository
from app.shared.errors import ValidationError


@pytest_asyncio.fixture
async def seeded(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        # All five rows share status=0 — perfect storm for the bug.
        for i in range(1, 6):
            s.add(
                Track(
                    id=i,
                    title=f"T{i}",
                    sort_title=f"t{i}",
                    duration_ms=200_000,
                    status=0,
                )
            )
        await s.flush()
        try:
            yield s
        finally:
            await s.rollback()


@pytest.mark.asyncio
async def test_no_cursor_emitted_on_non_unique_sort(
    seeded: AsyncSession,
) -> None:
    repo = TrackRepository(seeded)
    page = await repo.filter(order=["status_asc"], limit=2)
    assert len(page.items) == 2
    assert page.next_cursor is None, (
        "must not emit a cursor on a non-unique sort field — the follow-up "
        "predicate would silently drop rows sharing the boundary value"
    )


@pytest.mark.asyncio
async def test_cursor_input_rejected_on_non_unique_sort(
    seeded: AsyncSession,
) -> None:
    """If the caller hand-constructs a cursor anyway, the input gate
    raises a clear error pointing at the primary key as the fix."""
    repo = TrackRepository(seeded)
    with pytest.raises(ValidationError, match="non-unique sort field"):
        await repo.filter(order=["status_asc"], limit=2, cursor="MA")  # 0


@pytest.mark.asyncio
async def test_pk_sort_still_paginates(seeded: AsyncSession) -> None:
    """Sanity: the guard must not break sorting by the primary key."""
    repo = TrackRepository(seeded)
    page1 = await repo.filter(order=["id_asc"], limit=2)
    assert [t.id for t in page1.items] == [1, 2]
    assert page1.next_cursor is not None
    page2 = await repo.filter(order=["id_asc"], limit=2, cursor=page1.next_cursor)
    assert [t.id for t in page2.items] == [3, 4]
