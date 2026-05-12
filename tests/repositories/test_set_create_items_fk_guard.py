"""Regression: ``SetVersionRepository.create_items`` must reject ghost track ids.

Previously ``create_items(version_id=N, track_order=[1, 2, 99999])``
just bulk-inserted three ``DjSetItem`` rows. SQLite (default FK
enforcement off) silently kept the orphan; PostgreSQL would raise an
opaque ``ForeignKeyViolationError`` long after the validation gate
would have produced a clean message. The repo now validates with a
single batch ``SELECT IN (...)`` and raises a typed
``ValidationError`` naming the bad ids.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.base import Base
from app.models.set import DjSet, DjSetItem, DjSetVersion
from app.models.track import Track
from app.repositories.set import SetVersionRepository
from app.shared.errors import ValidationError


@pytest_asyncio.fixture
async def seeded_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session with all DB tables created (the shared ``session`` fixture
    skips ``create_all`` to let each test pick its own Base)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        try:
            yield s
        finally:
            await s.rollback()


@pytest.mark.asyncio
async def test_create_items_rejects_ghost_track_id(seeded_session: AsyncSession) -> None:
    seeded_session.add(Track(id=1, title="Real", sort_title="real", duration_ms=200_000, status=0))
    seeded_session.add(DjSet(id=1, name="S"))
    seeded_session.add(DjSetVersion(id=1, set_id=1, label="v1"))
    await seeded_session.flush()

    repo = SetVersionRepository(seeded_session)
    with pytest.raises(ValidationError, match=r"unknown track id\(s\) \[99999\]"):
        await repo.create_items(version_id=1, track_order=[1, 99999])

    # Confirm the partial insert (track_id=1) was NOT applied — the guard
    # fires before ``add_all``, so the transaction state stays clean.
    rows = (await seeded_session.execute(select(DjSetItem))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_create_items_happy_path_with_valid_ids(
    seeded_session: AsyncSession,
) -> None:
    for tid in (1, 2, 3):
        seeded_session.add(
            Track(id=tid, title=f"T{tid}", sort_title=f"t{tid}", duration_ms=200_000, status=0)
        )
    seeded_session.add(DjSet(id=1, name="S"))
    seeded_session.add(DjSetVersion(id=1, set_id=1, label="v1"))
    await seeded_session.flush()

    repo = SetVersionRepository(seeded_session)
    count = await repo.create_items(version_id=1, track_order=[1, 2, 3])
    assert count == 3


@pytest.mark.asyncio
async def test_create_items_empty_input_is_noop(seeded_session: AsyncSession) -> None:
    """Empty ``track_order`` skips the validation query and the bulk
    insert — caller responsibility to handle this case upstream."""
    repo = SetVersionRepository(seeded_session)
    count = await repo.create_items(version_id=1, track_order=[])
    assert count == 0
