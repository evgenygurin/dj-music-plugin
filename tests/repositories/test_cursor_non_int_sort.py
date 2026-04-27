"""Audit iter 35 (T-33): cursor pagination crashed on non-integer
sort fields.

After v1.2.31 widened ``sortable_fields`` to include ``created_at``
(datetime), ``mood_confidence`` (nullable float), etc.,
``BaseRepository.filter`` started crashing with
``int() argument must be a string, ..., not 'datetime.datetime'``
when paginating - the cursor encoder hardcoded ``int(getattr(...))``.

Now:

* When sort is by an integer column (id, track_id, …), pagination
  works as before.
* When sort is by a non-integer column, ``next_cursor`` stays
  ``None`` (signalling end-of-stream cleanly) and passing a cursor
  on such a sort raises a typed ValidationError instead of
  crashing the dispatcher.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.repositories.track import TrackRepository
from app.shared.errors import ValidationError


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repo = TrackRepository(session)
    for i in range(5):
        await repo.create(title=f"t{i}")
    return repo


@pytest.mark.asyncio
async def test_sort_by_datetime_does_not_crash_encoder(repo: TrackRepository) -> None:
    """``created_at`` is a datetime column. Without the iter-35 guard
    the encoder used to crash with ``int(datetime)``."""
    page = await repo.filter(order=["created_at_desc"], limit=2)
    # Page returns rows; cursor is None because field is non-integer.
    assert len(page.items) == 2
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_cursor_with_non_integer_sort_raises_typed_error(
    repo: TrackRepository,
) -> None:
    page = await repo.filter(order=["id"], limit=2)
    assert page.next_cursor is not None
    cursor = page.next_cursor
    with pytest.raises(ValidationError, match=r"(?i)integer sort field"):
        await repo.filter(order=["created_at_desc"], cursor=cursor, limit=2)


@pytest.mark.asyncio
async def test_sort_by_int_field_still_paginates(repo: TrackRepository) -> None:
    """Sanity: id-based pagination still works."""
    page1 = await repo.filter(order=["id"], limit=2)
    assert page1.next_cursor is not None
    page2 = await repo.filter(order=["id"], cursor=page1.next_cursor, limit=2)
    page1_ids = {t.id for t in page1.items}
    page2_ids = {t.id for t in page2.items}
    assert not (page1_ids & page2_ids), "pages overlapped"
