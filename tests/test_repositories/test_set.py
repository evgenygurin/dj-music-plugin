"""Tests for SetRepository."""

import pytest

from app.db.models.set import DjSet, SetItem, SetVersion
from app.db.models.track import Track
from app.db.repositories.set import SetRepository


@pytest.fixture
def set_repo(db):
    return SetRepository(db)


async def test_get_version_items(set_repo, db):
    """get_version_items returns ordered items for a set version."""
    dj_set = DjSet(name="Test Set")
    t1 = Track(title="Track A")
    t2 = Track(title="Track B")
    t3 = Track(title="Track C")
    db.add_all([dj_set, t1, t2, t3])
    await db.flush()

    version = SetVersion(set_id=dj_set.id, label="v1")
    db.add(version)
    await db.flush()

    # Add items in non-sequential order to verify sorting
    db.add(SetItem(version_id=version.id, track_id=t3.id, sort_index=0))
    db.add(SetItem(version_id=version.id, track_id=t1.id, sort_index=1))
    db.add(SetItem(version_id=version.id, track_id=t2.id, sort_index=2))
    await db.flush()

    items = await set_repo.get_version_items(version.id)
    assert len(items) == 3
    assert items[0].track_id == t3.id
    assert items[1].track_id == t1.id
    assert items[2].track_id == t2.id
    # Verify sort order
    assert [item.sort_index for item in items] == [0, 1, 2]


async def test_get_version_items_empty(set_repo, db):
    """get_version_items returns empty list for version with no items."""
    dj_set = DjSet(name="Empty Set")
    db.add(dj_set)
    await db.flush()

    version = SetVersion(set_id=dj_set.id, label="empty")
    db.add(version)
    await db.flush()

    items = await set_repo.get_version_items(version.id)
    assert items == []
