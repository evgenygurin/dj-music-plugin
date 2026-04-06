"""add indexes on foreign key columns

20 indexes on frequently queried FK columns that were missing index=True.
Improves JOIN and WHERE performance on all FK lookups.

Revision ID: c4f8a9b2d1e3
Revises: bdc73180c4b9
Create Date: 2026-04-06 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f8a9b2d1e3"
down_revision: str | None = "bdc73180c4b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index_name, table_name, column_name)
_INDEXES: list[tuple[str, str, str]] = [
    ("ix_feature_extraction_runs_track_id", "feature_extraction_runs", "track_id"),
    (
        "ix_track_audio_features_computed_pipeline_run_id",
        "track_audio_features_computed",
        "pipeline_run_id",
    ),
    ("ix_embeddings_track_id", "embeddings", "track_id"),
    ("ix_timeseries_references_track_id", "timeseries_references", "track_id"),
    ("ix_dj_library_items_track_id", "dj_library_items", "track_id"),
    ("ix_dj_beatgrids_library_item_id", "dj_beatgrids", "library_item_id"),
    ("ix_dj_beatgrid_change_points_beatgrid_id", "dj_beatgrid_change_points", "beatgrid_id"),
    ("ix_dj_cue_points_library_item_id", "dj_cue_points", "library_item_id"),
    ("ix_dj_saved_loops_library_item_id", "dj_saved_loops", "library_item_id"),
    ("ix_dj_playlists_parent_id", "dj_playlists", "parent_id"),
    ("ix_dj_playlist_items_playlist_id", "dj_playlist_items", "playlist_id"),
    ("ix_dj_playlist_items_track_id", "dj_playlist_items", "track_id"),
    ("ix_dj_sets_source_playlist_id", "dj_sets", "source_playlist_id"),
    ("ix_dj_set_versions_set_id", "dj_set_versions", "set_id"),
    ("ix_dj_set_items_version_id", "dj_set_items", "version_id"),
    ("ix_dj_set_items_track_id", "dj_set_items", "track_id"),
    ("ix_dj_set_constraints_set_id", "dj_set_constraints", "set_id"),
    ("ix_dj_set_feedback_version_id", "dj_set_feedback", "version_id"),
    ("ix_raw_provider_responses_track_id", "raw_provider_responses", "track_id"),
    ("ix_raw_provider_responses_provider_id", "raw_provider_responses", "provider_id"),
]


def upgrade() -> None:
    for ix_name, table, column in _INDEXES:
        op.create_index(ix_name, table, [column])


def downgrade() -> None:
    for ix_name, table, _column in reversed(_INDEXES):
        op.drop_index(ix_name, table_name=table)
