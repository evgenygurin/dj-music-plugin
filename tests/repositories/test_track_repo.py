"""TrackRepository domain methods."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, TrackExternalId
from app.repositories.track import TrackRepository


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return TrackRepository(session)


@pytest.mark.asyncio
async def test_inherited_crud(repo: TrackRepository) -> None:
    t = await repo.create(title="hello")
    assert t.id is not None
    fetched = await repo.get(t.id)
    assert fetched is not None
    assert fetched.title == "hello"


@pytest.mark.asyncio
async def test_get_provider_id(repo: TrackRepository, session: AsyncSession) -> None:
    t = await repo.create(title="x")
    session.add(TrackExternalId(track_id=t.id, provider_code="yandex_music", external_id="12345"))
    await session.flush()
    pid = await repo.get_provider_id(t.id, "yandex_music")
    assert pid == "12345"


@pytest.mark.asyncio
async def test_get_provider_id_missing(repo: TrackRepository) -> None:
    t = await repo.create(title="x")
    assert await repo.get_provider_id(t.id, "yandex_music") is None


@pytest.mark.asyncio
async def test_batch_get_by_provider_ids(repo: TrackRepository, session: AsyncSession) -> None:
    t1 = await repo.create(title="a")
    t2 = await repo.create(title="b")
    session.add_all(
        [
            TrackExternalId(track_id=t1.id, provider_code="yandex_music", external_id="A1"),
            TrackExternalId(track_id=t2.id, provider_code="yandex_music", external_id="B2"),
        ]
    )
    await session.flush()
    found = await repo.batch_get_by_provider_ids("yandex_music", ["A1", "B2", "missing"])
    assert set(found.keys()) == {"A1", "B2"}
    assert found["A1"].id == t1.id


@pytest.mark.asyncio
async def test_get_unanalyzed_stub(repo: TrackRepository) -> None:
    ids = await repo.get_unanalyzed(level=3, limit=10)
    assert ids == []  # no features rows yet
