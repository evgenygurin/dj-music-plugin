"""Tests for BaseRepository — CRUD + cursor pagination."""

import pytest

from app.db.models.track import Track
from app.db.repositories.base import BaseRepository


@pytest.fixture
def track_repo(db):
    return BaseRepository(db, Track)


async def test_create_and_get(track_repo):
    track = Track(title="Test", duration_ms=180000)
    created = await track_repo.create(track)
    assert created.id is not None
    fetched = await track_repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.title == "Test"


async def test_get_nonexistent(track_repo):
    result = await track_repo.get_by_id(999)
    assert result is None


async def test_list_paginated(track_repo):
    for i in range(5):
        await track_repo.create(Track(title=f"Track {i}"))

    page = await track_repo.list_all(limit=3)
    assert len(page.items) == 3
    assert page.next_cursor is not None
    assert page.total == 5

    page2 = await track_repo.list_all(limit=3, cursor=page.next_cursor)
    assert len(page2.items) == 2
    assert page2.next_cursor is None

    # No overlap
    ids1 = {t.id for t in page.items}
    ids2 = {t.id for t in page2.items}
    assert ids1.isdisjoint(ids2)


async def test_list_empty(track_repo):
    page = await track_repo.list_all()
    assert page.items == []
    assert page.total == 0
    assert page.next_cursor is None


async def test_delete(track_repo):
    t = await track_repo.create(Track(title="Del"))
    assert await track_repo.delete(t.id) is True
    assert await track_repo.get_by_id(t.id) is None


async def test_delete_nonexistent(track_repo):
    assert await track_repo.delete(999) is False


async def test_update(track_repo):
    t = await track_repo.create(Track(title="Old"))
    t.title = "New"
    updated = await track_repo.update(t)
    assert updated.title == "New"
    fetched = await track_repo.get_by_id(t.id)
    assert fetched.title == "New"
