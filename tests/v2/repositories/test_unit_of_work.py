"""UnitOfWork tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.v2.repositories.unit_of_work import UnitOfWork


class _Base(DeclarativeBase):
    pass


class _Widget(_Base):
    __tablename__ = "_widgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


@pytest_asyncio.fixture
async def prepared_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_uow_commits_on_success(
    prepared_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with prepared_factory() as session, UnitOfWork(session) as uow:
        uow.session.add(_Widget(id=1, name="first"))
    async with prepared_factory() as session:
        found = await session.get(_Widget, 1)
        assert found is not None
        assert found.name == "first"


@pytest.mark.asyncio
async def test_uow_rolls_back_on_exception(
    prepared_factory: async_sessionmaker[AsyncSession],
) -> None:
    class _Boom(Exception): ...

    with pytest.raises(_Boom):
        async with prepared_factory() as session:
            async with UnitOfWork(session) as uow:
                uow.session.add(_Widget(id=2, name="will-rollback"))
                raise _Boom

    async with prepared_factory() as session:
        assert await session.get(_Widget, 2) is None


@pytest.mark.asyncio
async def test_uow_exposes_session(
    prepared_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with prepared_factory() as session:
        uow = UnitOfWork(session)
        assert uow.session is session
