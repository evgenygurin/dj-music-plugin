"""BaseRepository tests on a toy model."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.repositories.base import BaseRepository
from app.shared.errors import NotFoundError, ValidationError


class _Base(DeclarativeBase):
    pass


class _Widget(_Base):
    __tablename__ = "_widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    weight: Mapped[float] = mapped_column(default=0.0)
    active: Mapped[bool] = mapped_column(default=True)


class WidgetRepository(BaseRepository[_Widget]):
    model = _Widget


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> WidgetRepository:
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    return WidgetRepository(session)


@pytest_asyncio.fixture
async def repo_seeded(repo: WidgetRepository) -> WidgetRepository:
    for i, (name, weight) in enumerate(
        [("alpha", 1.0), ("beta", 2.5), ("gamma", 3.0), ("delta", 0.5)], start=1
    ):
        await repo.create(id=i, name=name, weight=weight)
    return repo


@pytest.mark.asyncio
async def test_create_and_get(repo: WidgetRepository) -> None:
    w = await repo.create(name="hello", weight=1.0)
    assert w.id is not None
    fetched = await repo.get(w.id)
    assert fetched is not None
    assert fetched.name == "hello"


@pytest.mark.asyncio
async def test_get_missing_returns_none(repo: WidgetRepository) -> None:
    assert await repo.get(99999) is None


@pytest.mark.asyncio
async def test_exists(repo_seeded: WidgetRepository) -> None:
    assert await repo_seeded.exists(1) is True
    assert await repo_seeded.exists(999) is False


@pytest.mark.asyncio
async def test_update(repo_seeded: WidgetRepository) -> None:
    updated = await repo_seeded.update(1, name="renamed")
    assert updated.name == "renamed"
    fetched = await repo_seeded.get(1)
    assert fetched is not None
    assert fetched.name == "renamed"


@pytest.mark.asyncio
async def test_update_missing_raises(repo: WidgetRepository) -> None:
    with pytest.raises(NotFoundError):
        await repo.update(9999, name="x")


@pytest.mark.asyncio
async def test_delete(repo_seeded: WidgetRepository) -> None:
    await repo_seeded.delete(1)
    assert await repo_seeded.get(1) is None


@pytest.mark.asyncio
async def test_delete_missing_raises(repo: WidgetRepository) -> None:
    with pytest.raises(NotFoundError):
        await repo.delete(9999)


@pytest.mark.asyncio
async def test_count_all(repo_seeded: WidgetRepository) -> None:
    assert await repo_seeded.count() == 4


@pytest.mark.asyncio
async def test_count_filtered(repo_seeded: WidgetRepository) -> None:
    assert await repo_seeded.count(where={"weight__gte": 2.0}) == 2


@pytest.mark.asyncio
async def test_filter_basic(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={"active": True}, order=["id"], limit=10)
    assert len(page.items) == 4


@pytest.mark.asyncio
async def test_filter_paginates(repo_seeded: WidgetRepository) -> None:
    page1 = await repo_seeded.filter(where={}, order=["id"], limit=2)
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    page2 = await repo_seeded.filter(where={}, order=["id"], limit=2, cursor=page1.next_cursor)
    assert len(page2.items) == 2
    ids1 = {w.id for w in page1.items}
    ids2 = {w.id for w in page2.items}
    assert not (ids1 & ids2)


@pytest.mark.asyncio
async def test_filter_with_gte(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={"weight__gte": 2.0}, order=["id"], limit=10)
    names = sorted(w.name for w in page.items)
    assert names == ["beta", "gamma"]


@pytest.mark.asyncio
async def test_filter_icontains(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={"name__icontains": "a"}, order=["id"], limit=10)
    assert {w.name for w in page.items} == {"alpha", "beta", "gamma", "delta"}


@pytest.mark.asyncio
async def test_filter_in(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={"name__in": ["alpha", "gamma"]}, order=["id"], limit=10)
    assert {w.name for w in page.items} == {"alpha", "gamma"}


@pytest.mark.asyncio
async def test_filter_order_desc(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={}, order=["id_desc"], limit=10)
    assert [w.id for w in page.items] == [4, 3, 2, 1]


@pytest.mark.asyncio
async def test_filter_rejects_unknown_field(repo: WidgetRepository) -> None:
    with pytest.raises(ValidationError):
        await repo.filter(where={"nonexistent": 1}, order=["id"], limit=10)


@pytest.mark.asyncio
async def test_filter_with_total(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={}, order=["id"], limit=2, with_total=True)
    assert page.total == 4
