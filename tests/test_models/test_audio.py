"""Tests for audio analysis models."""

import pytest
from sqlalchemy.exc import IntegrityError

from dj_music.models.audio import (
    Embedding,
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from dj_music.models.track import Track


async def _make_track(db, title="Test Track"):
    """Helper: create and flush a Track."""
    t = Track(title=title)
    db.add(t)
    await db.flush()
    return t


class TestFeatureExtractionRun:
    async def test_create_run(self, db):
        track = await _make_track(db)
        run = FeatureExtractionRun(
            track_id=track.id,
            pipeline_name="full_pipeline",
            pipeline_version="1.0.0",
            status="pending",
        )
        db.add(run)
        await db.flush()
        assert run.id is not None
        assert run.status == "pending"
        assert run.created_at is not None

    async def test_run_status_constraint(self, db):
        track = await _make_track(db)
        run = FeatureExtractionRun(
            track_id=track.id,
            pipeline_name="p",
            pipeline_version="1.0",
            status="invalid_status",
        )
        db.add(run)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_run_valid_statuses(self, db):
        track = await _make_track(db)
        for status in ("pending", "running", "completed", "failed"):
            run = FeatureExtractionRun(
                track_id=track.id,
                pipeline_name="p",
                pipeline_version="1.0",
                status=status,
            )
            db.add(run)
        await db.flush()

    async def test_run_with_parameters_and_error(self, db):
        track = await _make_track(db)
        run = FeatureExtractionRun(
            track_id=track.id,
            pipeline_name="p",
            pipeline_version="1.0",
            parameters='{"sr": 44100}',
            status="failed",
            error_message="Out of memory",
        )
        db.add(run)
        await db.flush()
        assert run.parameters == '{"sr": 44100}'
        assert run.error_message == "Out of memory"


class TestTrackAudioFeaturesComputed:
    async def test_create_features_minimal(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(track_id=track.id)
        db.add(feat)
        await db.flush()
        assert feat.track_id == track.id
        assert feat.bpm is None
        assert feat.created_at is not None

    async def test_create_features_full(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(
            track_id=track.id,
            bpm=138.5,
            bpm_confidence=0.95,
            bpm_stability=0.88,
            variable_tempo=False,
            integrated_lufs=-8.2,
            energy_mean=0.75,
            key_code=14,
            key_confidence=0.92,
            spectral_centroid_hz=3200.0,
            hp_ratio=1.5,
            onset_rate=4.2,
        )
        db.add(feat)
        await db.flush()
        assert feat.bpm == 138.5
        assert feat.energy_mean == 0.75
        assert feat.key_code == 14

    async def test_bpm_range_too_low(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(track_id=track.id, bpm=19.9)
        db.add(feat)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_bpm_range_too_high(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(track_id=track.id, bpm=300.1)
        db.add(feat)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_bpm_confidence_range(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(track_id=track.id, bpm_confidence=1.1)
        db.add(feat)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_energy_mean_range(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(track_id=track.id, energy_mean=1.5)
        db.add(feat)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_key_code_range(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(track_id=track.id, key_code=24)
        db.add(feat)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_key_confidence_range(self, db):
        track = await _make_track(db)
        feat = TrackAudioFeaturesComputed(track_id=track.id, key_confidence=-0.1)
        db.add(feat)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_unique_per_track(self, db):
        track = await _make_track(db)
        f1 = TrackAudioFeaturesComputed(track_id=track.id, bpm=130.0)
        db.add(f1)
        await db.flush()

        # Expunge f1 to avoid SAWarning when adding f2 with same PK
        db.expunge(f1)
        f2 = TrackAudioFeaturesComputed(track_id=track.id, bpm=140.0)
        db.add(f2)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    async def test_pipeline_run_relationship(self, db):
        track = await _make_track(db)
        run = FeatureExtractionRun(
            track_id=track.id,
            pipeline_name="p",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        await db.flush()

        feat = TrackAudioFeaturesComputed(track_id=track.id, pipeline_run_id=run.id, bpm=140.0)
        db.add(feat)
        await db.flush()

        await db.refresh(feat, ["pipeline_run"])
        assert feat.pipeline_run is not None
        assert feat.pipeline_run.pipeline_name == "p"


class TestTrackSection:
    async def test_create_section(self, db):
        track = await _make_track(db)
        section = TrackSection(
            track_id=track.id,
            section_type=0,  # INTRO
            start_ms=0,
            end_ms=30000,
            energy=0.3,
            confidence=0.9,
        )
        db.add(section)
        await db.flush()
        assert section.id is not None
        assert section.section_type == 0

    async def test_section_type_range(self, db):
        track = await _make_track(db)
        section = TrackSection(track_id=track.id, section_type=12, start_ms=0, end_ms=1000)
        db.add(section)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_section_energy_range(self, db):
        track = await _make_track(db)
        section = TrackSection(
            track_id=track.id, section_type=4, start_ms=0, end_ms=1000, energy=1.5
        )
        db.add(section)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_section_confidence_range(self, db):
        track = await _make_track(db)
        section = TrackSection(
            track_id=track.id, section_type=4, start_ms=0, end_ms=1000, confidence=-0.1
        )
        db.add(section)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_section_nullable_energy_confidence(self, db):
        track = await _make_track(db)
        section = TrackSection(track_id=track.id, section_type=7, start_ms=0, end_ms=5000)
        db.add(section)
        await db.flush()
        assert section.energy is None
        assert section.confidence is None


class TestEmbedding:
    async def test_create_embedding(self, db):
        track = await _make_track(db)
        emb = Embedding(
            track_id=track.id,
            embedding_type="mfcc",
            dimensions=13,
            vector_data=b"\x00" * 52,
        )
        db.add(emb)
        await db.flush()
        assert emb.id is not None
        assert emb.embedding_type == "mfcc"
        assert emb.dimensions == 13

    async def test_unique_track_embedding_type(self, db):
        track = await _make_track(db)
        e1 = Embedding(
            track_id=track.id,
            embedding_type="mfcc",
            dimensions=13,
            vector_data=b"\x01" * 52,
        )
        db.add(e1)
        await db.flush()

        e2 = Embedding(
            track_id=track.id,
            embedding_type="mfcc",
            dimensions=13,
            vector_data=b"\x02" * 52,
        )
        db.add(e2)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_different_types_allowed(self, db):
        track = await _make_track(db)
        e1 = Embedding(
            track_id=track.id,
            embedding_type="mfcc",
            dimensions=13,
            vector_data=b"\x01" * 52,
        )
        e2 = Embedding(
            track_id=track.id,
            embedding_type="spectrogram",
            dimensions=128,
            vector_data=b"\x02" * 512,
        )
        db.add_all([e1, e2])
        await db.flush()
        assert e1.id != e2.id


class TestTimeseriesReference:
    async def test_create_timeseries(self, db):
        track = await _make_track(db)
        ts = TimeseriesReference(
            track_id=track.id,
            feature_set_name="energy_frames",
            storage_uri="file:///data/energy/track_1.npy",
            frame_count=1000,
            hop_length=512,
            sample_rate=44100,
            data_type="float32",
            shape="[1000]",
        )
        db.add(ts)
        await db.flush()
        assert ts.id is not None
        assert ts.feature_set_name == "energy_frames"
        assert ts.frame_count == 1000
        assert ts.created_at is not None
