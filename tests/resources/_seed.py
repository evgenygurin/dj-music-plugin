"""Canonical seed used across resource tests.

NOTE (Phase 4): this helper is intentionally a reference skeleton for Phase 5.
It calls repository methods (``create(id=...)``, ``add_items``,
``transitions.create`` with all 6 scoring columns) that will ship with
Phase 5's repository completion. Resource tests that depend on seeded
state are marked ``xfail`` in ``conftest.py`` until Phase 5 composes the
full surface.
"""

from __future__ import annotations

from typing import Any


async def seed_canonical_state(uow: Any) -> None:
    """Insert the seed graph used by every resource test.

    3 tracks (ids 1, 2, 3) each with features (bpm 124, 126, 128, key_code 5, 8, 9),
    1 playlist (id 10) referencing them, 1 set (id 100) with one version (id 1000)
    holding the 3 tracks in order, 2 transitions persisted between them.
    """
    # Tracks
    await uow.tracks.create(id=1, title="Alpha", duration_ms=360_000, status=0)
    await uow.tracks.create(id=2, title="Beta", duration_ms=380_000, status=0)
    await uow.tracks.create(id=3, title="Gamma", duration_ms=400_000, status=0)
    # Features (minimal — only fields resources assert on)
    await uow.track_features.create(
        track_id=1,
        bpm=124.0,
        key_code=5,
        integrated_lufs=-10.2,
        energy_mean=0.42,
        kick_prominence=0.30,
        onset_rate=5.1,
        spectral_centroid_hz=1800.0,
        analysis_level=3,
        mood="hypnotic",
    )
    await uow.track_features.create(
        track_id=2,
        bpm=126.0,
        key_code=8,
        integrated_lufs=-9.0,
        energy_mean=0.55,
        kick_prominence=0.42,
        onset_rate=6.0,
        spectral_centroid_hz=2100.0,
        analysis_level=3,
        mood="peak_time",
    )
    await uow.track_features.create(
        track_id=3,
        bpm=128.0,
        key_code=9,
        integrated_lufs=-8.0,
        energy_mean=0.68,
        kick_prominence=0.55,
        onset_rate=7.0,
        spectral_centroid_hz=2500.0,
        analysis_level=3,
        mood="driving",
    )
    # Playlist + items
    pl = await uow.playlists.create(id=10, name="Test PL", source_of_truth="local")
    await uow.playlists.add_items(pl.id, track_ids=[1, 2, 3])
    # Set + version + items
    s = await uow.sets.create(id=100, name="Test Set", template_name="classic_60")
    v = await uow.set_versions.create(id=1000, set_id=s.id, label="v1", quality_score=0.78)
    await uow.set_versions.add_items(v.id, track_ids=[1, 2, 3])
    # Transitions (1→2, 2→3)
    await uow.transitions.create(
        from_track_id=1,
        to_track_id=2,
        bpm_score=0.9,
        harmonic_score=0.5,
        energy_score=0.8,
        spectral_score=0.7,
        groove_score=0.7,
        timbral_score=0.6,
        overall_quality=0.74,
        hard_reject=False,
    )
    await uow.transitions.create(
        from_track_id=2,
        to_track_id=3,
        bpm_score=0.88,
        harmonic_score=0.9,
        energy_score=0.82,
        spectral_score=0.72,
        groove_score=0.75,
        timbral_score=0.65,
        overall_quality=0.81,
        hard_reject=False,
    )
    await uow.session.commit()
