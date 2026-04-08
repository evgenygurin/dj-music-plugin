"""Tests for CurationService — classify_mood persists mood to DB (B1)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import TrackAudioFeaturesComputed
from app.models.playlist import Playlist, PlaylistItem
from app.models.track import Track
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.curation.facade import CurationService


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
    # BUG-11: tracks with features but already-classified mood are reported
    # in their own bucket, not lumped under "skipped_no_features".
    assert result["skipped_no_features"] == 0
    assert result["skipped_already_classified"] == 1


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


# ── Regression: classify_mood is N+1-free ───────────────


@pytest.mark.asyncio
async def test_classify_mood_uses_batch_query_for_features(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: classify_mood must call get_features_batch, not loop get_features."""
    svc = _make_curation_service(db)

    # Create 5 tracks with features
    track_ids: list[int] = []
    for i in range(5):
        track = Track(title=f"Track {i}", duration_ms=360000)
        db.add(track)
        await db.flush()
        track_ids.append(track.id)

        features = _make_techno_features(track.id)
        db.add(features)
    await db.flush()

    # Spy on the inner mood service's feature_repo
    feat_repo = svc._mood._features  # type: ignore[attr-defined]
    batch_calls = 0
    single_calls = 0
    original_batch = feat_repo.get_features_batch
    original_single = feat_repo.get_features

    async def spy_batch(ids):  # type: ignore[no-untyped-def]
        nonlocal batch_calls
        batch_calls += 1
        return await original_batch(ids)

    async def spy_single(track_id):  # type: ignore[no-untyped-def]
        nonlocal single_calls
        single_calls += 1
        return await original_single(track_id)

    monkeypatch.setattr(feat_repo, "get_features_batch", spy_batch)
    monkeypatch.setattr(feat_repo, "get_features", spy_single)

    result = await svc.classify_mood(track_ids=track_ids)

    assert result["classified"] == 5
    assert batch_calls == 1, (
        f"Expected 1 batch call, got {batch_calls} — should batch-load features"
    )
    assert single_calls == 0, (
        f"Expected 0 single get_features calls, got {single_calls} (N+1 regression)"
    )


# ── audit_playlist ───────────────


@pytest.mark.asyncio
async def test_audit_playlist_returns_stats(db: AsyncSession) -> None:
    """audit_playlist returns track stats and runs audit rules without N+1."""
    svc = _make_curation_service(db)

    # Build a playlist with 3 tracks
    track_ids: list[int] = []
    for i in range(3):
        track = Track(title=f"Audit Track {i}", duration_ms=360000)
        db.add(track)
        await db.flush()
        track_ids.append(track.id)

        features = _make_techno_features(track.id)
        db.add(features)
    await db.flush()

    playlist = Playlist(name="Audit Test")
    db.add(playlist)
    await db.flush()

    for idx, tid in enumerate(track_ids):
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=tid, sort_index=idx))
    await db.flush()

    result = await svc.audit_playlist(playlist_id=playlist.id)

    assert result["playlist_id"] == playlist.id
    assert result["stats"]["total_tracks"] == 3
    assert result["stats"]["with_features"] == 3
    assert result["stats"]["without_features"] == 0


@pytest.mark.asyncio
async def test_audit_playlist_uses_batch_queries(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: audit_playlist must call batch loaders, not loop singles."""
    svc = _make_curation_service(db)

    # 4 tracks with features
    track_ids: list[int] = []
    for i in range(4):
        track = Track(title=f"Batch Track {i}", duration_ms=360000)
        db.add(track)
        await db.flush()
        track_ids.append(track.id)

        features = _make_techno_features(track.id)
        db.add(features)
    await db.flush()

    playlist = Playlist(name="Batch Test")
    db.add(playlist)
    await db.flush()

    for idx, tid in enumerate(track_ids):
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=tid, sort_index=idx))
    await db.flush()

    audit_svc = svc._audit  # type: ignore[attr-defined]
    track_repo = audit_svc._tracks  # type: ignore[attr-defined]
    feat_repo = audit_svc._features  # type: ignore[attr-defined]

    track_batch_calls = 0
    track_single_calls = 0
    feat_batch_calls = 0
    feat_single_calls = 0

    original_track_batch = track_repo.get_by_ids
    original_track_single = track_repo.get_by_id
    original_feat_batch = feat_repo.get_features_batch
    original_feat_single = feat_repo.get_features

    async def spy_track_batch(ids):  # type: ignore[no-untyped-def]
        nonlocal track_batch_calls
        track_batch_calls += 1
        return await original_track_batch(ids)

    async def spy_track_single(track_id):  # type: ignore[no-untyped-def]
        nonlocal track_single_calls
        track_single_calls += 1
        return await original_track_single(track_id)

    async def spy_feat_batch(ids):  # type: ignore[no-untyped-def]
        nonlocal feat_batch_calls
        feat_batch_calls += 1
        return await original_feat_batch(ids)

    async def spy_feat_single(track_id):  # type: ignore[no-untyped-def]
        nonlocal feat_single_calls
        feat_single_calls += 1
        return await original_feat_single(track_id)

    monkeypatch.setattr(track_repo, "get_by_ids", spy_track_batch)
    monkeypatch.setattr(track_repo, "get_by_id", spy_track_single)
    monkeypatch.setattr(feat_repo, "get_features_batch", spy_feat_batch)
    monkeypatch.setattr(feat_repo, "get_features", spy_feat_single)

    await svc.audit_playlist(playlist_id=playlist.id)

    assert track_batch_calls == 1, f"Expected 1 batch get_by_ids call, got {track_batch_calls}"
    assert track_single_calls == 0, (
        f"Expected 0 get_by_id calls, got {track_single_calls} (N+1 regression)"
    )
    assert feat_batch_calls == 1, f"Expected 1 batch features call, got {feat_batch_calls}"
    assert feat_single_calls == 0, (
        f"Expected 0 single get_features calls, got {feat_single_calls} (N+1 regression)"
    )
