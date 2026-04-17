"""Full metadata sanity: create every table on a single engine."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base


@pytest.mark.asyncio
async def test_create_all_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "keys",
        "key_edges",
        "providers",
        "yandex_metadata",
        "raw_provider_responses",
        "tracks",
        "artists",
        "genres",
        "releases",
        "track_artists",
        "track_genres",
        "track_releases",
        "track_external_ids",
        "dj_playlists",
        "dj_playlist_items",
        "dj_sets",
        "dj_set_versions",
        "dj_set_items",
        "dj_library_items",
        "dj_beatgrids",
        "feature_extraction_runs",
        "track_audio_features_computed",
        "track_sections",
        "timeseries_references",
        "transitions",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profiles",
    }
    assert expected.issubset(table_names), f"Missing: {expected - table_names}"


def test_no_dropped_tables_present() -> None:
    table_names = set(Base.metadata.tables.keys())
    dropped = {
        "spotify_metadata",
        "spotify_album_metadata",
        "spotify_artist_metadata",
        "spotify_playlist_metadata",
        "spotify_audio_features",
        "beatport_metadata",
        "soundcloud_metadata",
        "embeddings",
        "transition_candidates",
        "dj_saved_loops",
        "dj_cue_points",
        "dj_beatgrid_change_points",
        "dj_set_constraints",
        "dj_set_feedback",
        "labels",
        "track_labels",
        "app_exports",
    }
    overlap = dropped & table_names
    assert not overlap, f"Dropped tables still in metadata: {overlap}"
