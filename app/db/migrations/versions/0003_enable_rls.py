"""enable RLS + authenticated policies on all public tables

Revision ID: 0003
Revises: f3702c8a41cd
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "f3702c8a41cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES: list[str] = [
    "app_exports",
    "artists",
    "beatport_metadata",
    "cross_similarity",
    "dj_beatgrid_change_points",
    "dj_beatgrids",
    "dj_cue_points",
    "dj_library_items",
    "dj_playlist_items",
    "dj_playlists",
    "dj_saved_loops",
    "dj_set_constraints",
    "dj_set_feedback",
    "dj_set_items",
    "dj_set_versions",
    "dj_sets",
    "embeddings",
    "feature_extraction_runs",
    "genres",
    "key_edges",
    "keys",
    "labels",
    "providers",
    "raw_provider_responses",
    "releases",
    "scoring_profiles",
    "soundcloud_metadata",
    "spotify_album_metadata",
    "spotify_artist_metadata",
    "spotify_audio_features",
    "spotify_metadata",
    "spotify_playlist_metadata",
    "stem_features",
    "timeseries_references",
    "track_affinity",
    "track_artists",
    "track_audio_features_computed",
    "track_embeddings",
    "track_external_ids",
    "track_feedback",
    "track_genres",
    "track_labels",
    "track_releases",
    "track_sections",
    "tracks",
    "transition_candidates",
    "transition_history",
    "transitions",
    "yandex_metadata",
]


def upgrade() -> None:
    for tbl in TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY authenticated_full_access_{tbl} ON {tbl} "
            "FOR ALL TO authenticated USING (true) WITH CHECK (true);"
        )
    op.execute("REVOKE EXECUTE ON FUNCTION rls_auto_enable() FROM anon;")


def downgrade() -> None:
    for tbl in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS authenticated_full_access_{tbl} ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
    op.execute("GRANT EXECUTE ON FUNCTION rls_auto_enable() TO anon;")
