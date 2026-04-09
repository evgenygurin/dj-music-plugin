"""Unit tests for EntityResolver helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastmcp.exceptions import ToolError

from app.controllers.tools._shared.resolvers import (
    ensure_reference,
    resolve_entity,
    resolve_track_id,
)


@dataclass
class _Entity:
    id: int
    name: str


def test_ensure_reference_rejects_empty() -> None:
    with pytest.raises(ToolError, match="Provide track id or query"):
        ensure_reference(None, None, entity_name="track")


def test_ensure_reference_accepts_id() -> None:
    ensure_reference(1, None)  # no raise


def test_ensure_reference_accepts_query() -> None:
    ensure_reference(None, "amelie lens")  # no raise


def test_ensure_reference_rejects_empty_string() -> None:
    with pytest.raises(ToolError):
        ensure_reference(None, "", entity_name="track")


async def test_resolve_entity_by_id() -> None:
    async def get_by_id(i: int) -> _Entity | None:
        return _Entity(id=i, name="hit")

    async def search(_: str) -> _Entity | None:
        raise AssertionError("should not hit search path")

    e = await resolve_entity(
        entity_id=42,
        query=None,
        entity_name="track",
        get_by_id=get_by_id,
        search_by_query=search,
    )
    assert e.id == 42


async def test_resolve_entity_by_query() -> None:
    async def get_by_id(_: int) -> _Entity | None:
        raise AssertionError("should not hit id path")

    async def search(q: str) -> _Entity | None:
        return _Entity(id=7, name=q)

    e = await resolve_entity(
        entity_id=None,
        query="minimal",
        entity_name="track",
        get_by_id=get_by_id,
        search_by_query=search,
    )
    assert e.id == 7 and e.name == "minimal"


async def test_resolve_entity_not_found_by_id() -> None:
    async def get_by_id(_: int) -> _Entity | None:
        return None

    async def search(_: str) -> _Entity | None:
        return None

    with pytest.raises(ToolError, match="track not found: 99"):
        await resolve_entity(
            entity_id=99,
            query=None,
            entity_name="track",
            get_by_id=get_by_id,
            search_by_query=search,
        )


async def test_resolve_entity_not_found_by_query() -> None:
    async def get_by_id(_: int) -> _Entity | None:
        return None

    async def search(_: str) -> _Entity | None:
        return None

    with pytest.raises(ToolError, match="playlist not found: ghosts"):
        await resolve_entity(
            entity_id=None,
            query="ghosts",
            entity_name="playlist",
            get_by_id=get_by_id,
            search_by_query=search,
        )


async def test_resolve_track_id_passthrough() -> None:
    async def search(_q: str, _l: int) -> list[object]:
        raise AssertionError("should not search when id given")

    assert await resolve_track_id(entity_id=5, query=None, search=search) == 5


async def test_resolve_track_id_by_query() -> None:
    @dataclass
    class _Hit:
        id: int

    async def search(q: str, limit: int) -> list[_Hit]:
        assert q == "tresor" and limit == 1
        return [_Hit(id=11)]

    assert await resolve_track_id(entity_id=None, query="tresor", search=search) == 11


async def test_resolve_track_id_not_found() -> None:
    async def search(_q: str, _l: int) -> list[object]:
        return []

    with pytest.raises(ToolError, match="track not found: ghosts"):
        await resolve_track_id(entity_id=None, query="ghosts", search=search)
