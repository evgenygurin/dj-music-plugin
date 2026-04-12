"""Tests for DJ Set models."""

import pytest
from sqlalchemy.exc import IntegrityError

from dj_music.models.playlist import Playlist
from dj_music.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion
from dj_music.models.track import Track
from dj_music.models.transition import Transition


async def _make_track(db, title: str = "Test Track") -> Track:
    t = Track(title=title)
    db.add(t)
    await db.flush()
    return t


async def _make_set_with_version(db) -> tuple[DjSet, SetVersion]:
    s = DjSet(name="My Set")
    db.add(s)
    await db.flush()

    v = SetVersion(set_id=s.id, label="v1")
    db.add(v)
    await db.flush()
    return s, v


async def test_create_dj_set(db):  # type: ignore[no-untyped-def]
    s = DjSet(name="Friday Night")
    db.add(s)
    await db.flush()
    assert s.id is not None
    assert s.name == "Friday Night"
    assert s.description is None
    assert s.target_duration_ms is None


async def test_dj_set_with_all_fields(db):  # type: ignore[no-untyped-def]
    pl = Playlist(name="Source")
    db.add(pl)
    await db.flush()

    s = DjSet(
        name="Full Set",
        description="A test set",
        target_duration_ms=3600000,
        target_bpm_min=128.0,
        target_bpm_max=135.0,
        target_energy_arc="[0.3, 0.5, 0.8, 1.0, 0.6]",
        template_name="classic_60",
        source_playlist_id=pl.id,
        ym_playlist_id="ym_123",
    )
    db.add(s)
    await db.flush()
    assert s.target_bpm_min == 128.0
    assert s.source_playlist_id == pl.id


async def test_set_version_quality_score_valid(db):  # type: ignore[no-untyped-def]
    s = DjSet(name="Scored")
    db.add(s)
    await db.flush()

    v = SetVersion(set_id=s.id, quality_score=0.85)
    db.add(v)
    await db.flush()
    assert v.quality_score == 0.85


async def test_set_version_quality_score_zero(db):  # type: ignore[no-untyped-def]
    s = DjSet(name="Zero Score")
    db.add(s)
    await db.flush()

    v = SetVersion(set_id=s.id, quality_score=0.0)
    db.add(v)
    await db.flush()
    assert v.quality_score == 0.0


async def test_set_version_quality_score_one(db):  # type: ignore[no-untyped-def]
    s = DjSet(name="Perfect Score")
    db.add(s)
    await db.flush()

    v = SetVersion(set_id=s.id, quality_score=1.0)
    db.add(v)
    await db.flush()
    assert v.quality_score == 1.0


async def test_set_version_quality_score_out_of_range(db):  # type: ignore[no-untyped-def]
    s = DjSet(name="Bad Score")
    db.add(s)
    await db.flush()

    v = SetVersion(set_id=s.id, quality_score=1.5)
    db.add(v)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_set_item_pinned_default(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)
    t = await _make_track(db)

    item = SetItem(version_id=v.id, track_id=t.id, sort_index=0)
    db.add(item)
    await db.flush()
    assert item.pinned is False


async def test_set_item_pinned_true(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)
    t = await _make_track(db)

    item = SetItem(version_id=v.id, track_id=t.id, sort_index=0, pinned=True)
    db.add(item)
    await db.flush()
    assert item.pinned is True


async def test_set_item_with_transition(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)
    t1 = await _make_track(db, "From")
    t2 = await _make_track(db, "To")

    tr = Transition(from_track_id=t1.id, to_track_id=t2.id)
    db.add(tr)
    await db.flush()

    item = SetItem(
        version_id=v.id,
        track_id=t2.id,
        sort_index=1,
        transition_id=tr.id,
        mix_in_point_ms=1000,
        mix_out_point_ms=5000,
    )
    db.add(item)
    await db.flush()
    assert item.transition_id == tr.id


async def test_set_constraint(db):  # type: ignore[no-untyped-def]
    s = DjSet(name="Constrained")
    db.add(s)
    await db.flush()

    c = SetConstraint(
        set_id=s.id,
        constraint_type="bpm_range",
        constraint_value='{"min": 128, "max": 135}',
    )
    db.add(c)
    await db.flush()
    assert c.constraint_type == "bpm_range"


async def test_feedback_rating_valid(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)

    fb = SetFeedback(version_id=v.id, rating=4, feedback_type="manual")
    db.add(fb)
    await db.flush()
    assert fb.rating == 4


async def test_feedback_rating_range_min(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)

    fb = SetFeedback(version_id=v.id, rating=1, feedback_type="manual")
    db.add(fb)
    await db.flush()
    assert fb.rating == 1


async def test_feedback_rating_range_max(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)

    fb = SetFeedback(version_id=v.id, rating=5, feedback_type="live_crowd")
    db.add(fb)
    await db.flush()
    assert fb.rating == 5


async def test_feedback_rating_out_of_range(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)

    fb = SetFeedback(version_id=v.id, rating=6, feedback_type="manual")
    db.add(fb)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_feedback_rating_zero_invalid(db):  # type: ignore[no-untyped-def]
    _, v = await _make_set_with_version(db)

    fb = SetFeedback(version_id=v.id, rating=0, feedback_type="ab_test")
    db.add(fb)
    with pytest.raises(IntegrityError):
        await db.flush()
