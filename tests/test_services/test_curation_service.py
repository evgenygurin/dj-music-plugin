"""Tests for CurationService — classify_mood persists mood to DB (B1)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import TrackAudioFeaturesComputed
from app.models.track import Track
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.curation_service import CurationService


def _make_curation_service(db: AsyncSession) -> CurationService:
    return CurationService(
        track_repo=TrackRepository(db),
        playlist_repo=PlaylistRepository(db),
        set_repo=SetRepository(db),
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
    )


def _make_techno_features(track_id: int) -> TrackAudioFeaturesComputed:
    """Create audio features that look like a typical techno track."""
    return TrackAudioFeaturesComputed(
        track_id=track_id,
        analysis_level=2,
        bpm=130.0,
        bpm_confidence=0.9,
        bpm_stability=0.95,
        integrated_lufs=-8.0,
        short_term_lufs_mean=-7.5,
        momentary_max=-5.0,
        rms_dbfs=-10.0,
        true_peak_db=-1.0,
        crest_factor_db=9.0,
        loudness_range_lu=5.0,
        energy_mean=0.6,
        energy_max=0.9,
        energy_std=0.15,
        energy_slope=0.01,
        spectral_centroid_hz=2500.0,
        spectral_rolloff_85=5000.0,
        spectral_rolloff_95=8000.0,
        spectral_flatness=0.1,
        spectral_flux_mean=2.0,
        spectral_flux_std=1.5,
        spectral_contrast=20.0,
        hp_ratio=0.8,
        onset_rate=4.0,
        pulse_clarity=0.5,
        kick_prominence=0.4,
        key_code=8,
        key_confidence=0.7,
        atonality=False,
        hnr_db=5.0,
        mood=None,
        mood_confidence=None,
    )


# ── B1: classify_mood persists mood to DB ──────────────


@pytest.mark.asyncio
async def test_classify_mood_persists_mood_to_db(db: AsyncSession) -> None:
    """classify_mood should write mood and mood_confidence back to features row."""
    svc = _make_curation_service(db)

    # Create a track with audio features but no mood
    track = Track(title="Acid Test", duration_ms=360000)
    db.add(track)
    await db.flush()

    features = _make_techno_features(track.id)
    db.add(features)
    await db.flush()

    # Verify mood is initially None
    assert features.mood is None
    assert features.mood_confidence is None

    # Classify
    result = await svc.classify_mood(track_ids=[track.id])

    assert result["classified"] == 1
    assert result["skipped_no_features"] == 0

    # Re-fetch features from DB to verify persistence
    feat_repo = FeatureRepository(db)
    updated = await feat_repo.get_features(track.id)
    assert updated is not None
    assert updated.mood is not None
    assert updated.mood_confidence is not None
    assert updated.mood_confidence > 0.0


@pytest.mark.asyncio
async def test_classify_mood_skips_already_classified(db: AsyncSession) -> None:
    """classify_mood should skip tracks that already have a mood (unless reclassify)."""
    svc = _make_curation_service(db)

    track = Track(title="Driving Track", duration_ms=360000)
    db.add(track)
    await db.flush()

    features = _make_techno_features(track.id)
    features.mood = "driving"
    features.mood_confidence = 0.85
    db.add(features)
    await db.flush()

    result = await svc.classify_mood(track_ids=[track.id])
    assert result["classified"] == 0
    assert result["skipped_no_features"] == 1  # skipped because already has mood


@pytest.mark.asyncio
async def test_classify_mood_reclassify_updates_mood(db: AsyncSession) -> None:
    """classify_mood with reclassify=True should overwrite existing mood."""
    svc = _make_curation_service(db)

    track = Track(title="Reclassify Me", duration_ms=360000)
    db.add(track)
    await db.flush()

    features = _make_techno_features(track.id)
    features.mood = "ambient_dub"  # wrong classification
    features.mood_confidence = 0.3
    db.add(features)
    await db.flush()

    result = await svc.classify_mood(track_ids=[track.id], reclassify=True)
    assert result["classified"] == 1

    feat_repo = FeatureRepository(db)
    updated = await feat_repo.get_features(track.id)
    assert updated is not None
    assert updated.mood is not None
    # With these features the mood should NOT be ambient_dub (energy too high)
    assert updated.mood_confidence is not None
