"""Tests for DJ library models."""

import pytest
from sqlalchemy.exc import IntegrityError

from dj_music.models.library import (
    DjBeatgrid,
    DjBeatgridChangePoint,
    DjCuePoint,
    DjLibraryItem,
    DjSavedLoop,
)
from dj_music.models.track import Track


async def _make_track(db, title="Test Track"):
    t = Track(title=title)
    db.add(t)
    await db.flush()
    return t


async def _make_library_item(db, track):
    item = DjLibraryItem(
        track_id=track.id,
        file_path="/music/test.flac",
        file_hash="abc123def456",
        file_size=50_000_000,
        mime_type="audio/flac",
        bitrate=1411,
        sample_rate=44100,
        channels=2,
    )
    db.add(item)
    await db.flush()
    return item


class TestDjLibraryItem:
    async def test_create_item(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        assert item.id is not None
        assert item.track_id == track.id
        assert item.file_path == "/music/test.flac"
        assert item.file_hash == "abc123def456"
        assert item.file_size == 50_000_000
        assert item.created_at is not None

    async def test_optional_fields_nullable(self, db):
        track = await _make_track(db)
        item = DjLibraryItem(
            track_id=track.id,
            file_path="/music/test.mp3",
            file_hash="xyz789",
            file_size=10_000_000,
        )
        db.add(item)
        await db.flush()
        assert item.file_uri is None
        assert item.mime_type is None
        assert item.bitrate is None
        assert item.source_app is None

    async def test_repr(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        r = repr(item)
        assert "/music/test.flac" in r


class TestDjBeatgrid:
    async def test_create_beatgrid(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(
            library_item_id=item.id,
            bpm=138.0,
            first_downbeat_ms=120.5,
            confidence=0.95,
            canonical=True,
        )
        db.add(bg)
        await db.flush()
        assert bg.id is not None
        assert bg.bpm == 138.0
        assert bg.canonical is True
        assert bg.variable_tempo is False

    async def test_bpm_too_low(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(library_item_id=item.id, bpm=19.9)
        db.add(bg)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_bpm_too_high(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(library_item_id=item.id, bpm=300.1)
        db.add(bg)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_bpm_boundary_valid(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg_low = DjBeatgrid(library_item_id=item.id, bpm=20.0)
        bg_high = DjBeatgrid(library_item_id=item.id, bpm=300.0)
        db.add_all([bg_low, bg_high])
        await db.flush()
        assert bg_low.bpm == 20.0
        assert bg_high.bpm == 300.0

    async def test_confidence_range(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(library_item_id=item.id, bpm=130.0, confidence=1.5)
        db.add(bg)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_relationship_to_item(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(library_item_id=item.id, bpm=140.0, canonical=True)
        db.add(bg)
        await db.flush()

        await db.refresh(item, ["beatgrids"])
        assert len(item.beatgrids) == 1
        assert item.beatgrids[0].bpm == 140.0


class TestDjBeatgridChangePoint:
    async def test_create_change_point(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(library_item_id=item.id, bpm=135.0, variable_tempo=True)
        db.add(bg)
        await db.flush()

        cp = DjBeatgridChangePoint(beatgrid_id=bg.id, position_ms=60000.0, bpm=140.0)
        db.add(cp)
        await db.flush()
        assert cp.id is not None
        assert cp.bpm == 140.0

    async def test_change_point_bpm_range(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(library_item_id=item.id, bpm=130.0)
        db.add(bg)
        await db.flush()

        cp = DjBeatgridChangePoint(beatgrid_id=bg.id, position_ms=1000.0, bpm=10.0)
        db.add(cp)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_relationship_to_beatgrid(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        bg = DjBeatgrid(library_item_id=item.id, bpm=135.0, variable_tempo=True)
        db.add(bg)
        await db.flush()

        cp1 = DjBeatgridChangePoint(beatgrid_id=bg.id, position_ms=30000.0, bpm=137.0)
        cp2 = DjBeatgridChangePoint(beatgrid_id=bg.id, position_ms=60000.0, bpm=140.0)
        db.add_all([cp1, cp2])
        await db.flush()

        await db.refresh(bg, ["change_points"])
        assert len(bg.change_points) == 2


class TestDjCuePoint:
    async def test_create_cue(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        cue = DjCuePoint(
            library_item_id=item.id,
            position_ms=15000.0,
            kind=0,
            label="Intro end",
            color="#FF0000",
            quantized=True,
            source_app="rekordbox",
        )
        db.add(cue)
        await db.flush()
        assert cue.id is not None
        assert cue.kind == 0
        assert cue.label == "Intro end"

    async def test_cue_kind_range_valid(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        for kind in range(8):
            cue = DjCuePoint(library_item_id=item.id, position_ms=1000.0 * kind, kind=kind)
            db.add(cue)
        await db.flush()

    async def test_cue_kind_out_of_range(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        cue = DjCuePoint(library_item_id=item.id, position_ms=1000.0, kind=8)
        db.add(cue)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_cue_kind_negative(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        cue = DjCuePoint(library_item_id=item.id, position_ms=1000.0, kind=-1)
        db.add(cue)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_hotcue_index_range(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        cue = DjCuePoint(library_item_id=item.id, position_ms=1000.0, kind=1, hotcue_index=16)
        db.add(cue)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_hotcue_index_valid_boundaries(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        c0 = DjCuePoint(library_item_id=item.id, position_ms=100.0, kind=1, hotcue_index=0)
        c15 = DjCuePoint(library_item_id=item.id, position_ms=200.0, kind=1, hotcue_index=15)
        db.add_all([c0, c15])
        await db.flush()
        assert c0.hotcue_index == 0
        assert c15.hotcue_index == 15

    async def test_relationship_to_item(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        cue = DjCuePoint(library_item_id=item.id, position_ms=5000.0, kind=0)
        db.add(cue)
        await db.flush()

        await db.refresh(item, ["cue_points"])
        assert len(item.cue_points) == 1


class TestDjSavedLoop:
    async def test_create_loop(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        loop = DjSavedLoop(
            library_item_id=item.id,
            in_position_ms=30000.0,
            out_position_ms=38000.0,
            length_ms=8000.0,
            hotcue_index=4,
            label="Drop loop",
            active_on_load=True,
            color="#00FF00",
            source_app="traktor",
        )
        db.add(loop)
        await db.flush()
        assert loop.id is not None
        assert loop.in_position_ms == 30000.0
        assert loop.out_position_ms == 38000.0
        assert loop.active_on_load is True

    async def test_loop_hotcue_index_range(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        loop = DjSavedLoop(
            library_item_id=item.id,
            in_position_ms=0.0,
            out_position_ms=4000.0,
            hotcue_index=16,
        )
        db.add(loop)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_loop_defaults(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        loop = DjSavedLoop(
            library_item_id=item.id,
            in_position_ms=0.0,
            out_position_ms=4000.0,
        )
        db.add(loop)
        await db.flush()
        assert loop.active_on_load is False
        assert loop.label is None
        assert loop.color is None

    async def test_relationship_to_item(self, db):
        track = await _make_track(db)
        item = await _make_library_item(db, track)
        loop = DjSavedLoop(
            library_item_id=item.id,
            in_position_ms=0.0,
            out_position_ms=8000.0,
        )
        db.add(loop)
        await db.flush()

        await db.refresh(item, ["saved_loops"])
        assert len(item.saved_loops) == 1
