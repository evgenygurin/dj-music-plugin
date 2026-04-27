"""Audit iter 53 (T-51): ``entity_update(playlist, id, {parent_id: ...})``
accepted self-cycles and N-cycles, corrupting the playlist tree.

Live confirmation:

    entity_create(playlist, {"name":"X"})              -> {"id":32, ...}
    entity_update(playlist, 32, {"parent_id": 32})     -> 200 OK   ← self-cycle
    entity_create(playlist, {"name":"Y","parent_id":32}) -> {"id":33, ...}
    entity_update(playlist, 32, {"parent_id": 33})     -> 200 OK   ← 2-cycle: 32→33→32

Now the dispatcher walks the proposed parent's ancestor chain
and rejects any update where the playlist being updated already
appears in the chain. Self-cycle is the trivial case
(``parent_id == id``).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry
from app.repositories.playlist import PlaylistRepository
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import ValidationError
from app.tools.entity.update import entity_update


@pytest.fixture(autouse=True)
def _registered() -> None:
    EntityRegistry.clear()
    register_default_entities()
    yield
    EntityRegistry.clear()


@pytest_asyncio.fixture
async def uow(engine: AsyncEngine, session: AsyncSession) -> UnitOfWork:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return UnitOfWork(session)


@pytest.mark.asyncio
async def test_self_parent_rejected(uow: UnitOfWork) -> None:
    """``parent_id == id`` raises ValidationError with self-cycle message."""
    p = await uow.playlists.create(name="solo")
    with pytest.raises(ValidationError, match=r"self-cycle"):
        await entity_update(
            entity="playlist",
            id=p.id,
            data={"parent_id": p.id},
            uow=uow,
            registry=None,
            pipeline=None,
            scorer=None,
        )


@pytest.mark.asyncio
async def test_two_cycle_rejected(uow: UnitOfWork) -> None:
    """A → B → A: setting B's parent to A's child triggers cycle detection."""
    a = await uow.playlists.create(name="A")
    b = await uow.playlists.create(name="B", parent_id=a.id)
    # Try to make ``a.parent_id = b.id`` → would create A → B → A.
    with pytest.raises(ValidationError, match=r"would create a cycle"):
        await entity_update(
            entity="playlist",
            id=a.id,
            data={"parent_id": b.id},
            uow=uow,
            registry=None,
            pipeline=None,
            scorer=None,
        )


@pytest.mark.asyncio
async def test_three_cycle_rejected(uow: UnitOfWork) -> None:
    """Deeper chain: A → B → C, then try to set A.parent = C."""
    a = await uow.playlists.create(name="A")
    b = await uow.playlists.create(name="B", parent_id=a.id)
    c = await uow.playlists.create(name="C", parent_id=b.id)
    with pytest.raises(ValidationError, match=r"would create a cycle"):
        await entity_update(
            entity="playlist",
            id=a.id,
            data={"parent_id": c.id},
            uow=uow,
            registry=None,
            pipeline=None,
            scorer=None,
        )


@pytest.mark.asyncio
async def test_valid_reparent_accepted(uow: UnitOfWork) -> None:
    """Sibling reparent (no cycle) → success."""
    a = await uow.playlists.create(name="A")
    b = await uow.playlists.create(name="B")
    c = await uow.playlists.create(name="C")
    # Move C under A — no cycle.
    result = await entity_update(
        entity="playlist",
        id=c.id,
        data={"parent_id": a.id},
        uow=uow,
        registry=None,
        pipeline=None,
        scorer=None,
    )
    assert result.data["parent_id"] == a.id
    # Sanity: B unaffected.
    fresh_b = await uow.playlists.get(b.id)
    assert fresh_b is not None and fresh_b.parent_id is None


@pytest.mark.asyncio
async def test_clear_parent_accepted(uow: UnitOfWork) -> None:
    """``parent_id: None`` (un-parent) always passes — no cycle possible."""
    a = await uow.playlists.create(name="A")
    b = await uow.playlists.create(name="B", parent_id=a.id)
    result = await entity_update(
        entity="playlist",
        id=b.id,
        data={"parent_id": None},
        uow=uow,
        registry=None,
        pipeline=None,
        scorer=None,
    )
    assert result.data["parent_id"] is None


@pytest.mark.asyncio
async def test_ancestor_ids_returns_chain(engine: AsyncEngine, session: AsyncSession) -> None:
    """``PlaylistRepository.ancestor_ids`` walks the chain root-first."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repo = PlaylistRepository(session)
    a = await repo.create(name="A")
    b = await repo.create(name="B", parent_id=a.id)
    c = await repo.create(name="C", parent_id=b.id)

    chain = await repo.ancestor_ids(c.id)
    assert chain == [a.id, b.id, c.id]


@pytest.mark.asyncio
async def test_ancestor_ids_terminates_on_pre_existing_cycle(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """Even if the DB somehow already has a self-loop (data drift),
    the walk terminates at MAX_DEPTH instead of spinning forever."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repo = PlaylistRepository(session)
    a = await repo.create(name="A")
    # Inject a self-loop directly via the row's parent_id (bypassing
    # the dispatcher guard).
    a.parent_id = a.id
    await session.flush()

    chain = await repo.ancestor_ids(a.id)
    # Loop detected on second visit → walk stops with single-element chain.
    assert chain == [a.id]
