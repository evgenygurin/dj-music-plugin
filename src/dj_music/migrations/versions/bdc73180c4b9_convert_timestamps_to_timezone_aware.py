"""convert_timestamps_to_timezone_aware

PostgreSQL requires TIMESTAMP WITH TIME ZONE for timezone-aware datetimes.
SQLite ignores this change (no distinction between timestamp types).
All 70 timestamp columns across 35 tables are converted.

Revision ID: bdc73180c4b9
Revises: b5e7f234a891
Create Date: 2026-04-06 16:43:38.912677

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bdc73180c4b9"
down_revision: str | None = "b5e7f234a891"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All tables with TimestampMixin (created_at, updated_at)
_TIMESTAMPED_TABLES = [
    "app_exports",
    "artists",
    "beatport_metadata",
    "dj_beatgrids",
    "dj_cue_points",
    "dj_library_items",
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
    "labels",
    "providers",
    "raw_provider_responses",
    "releases",
    "soundcloud_metadata",
    "spotify_album_metadata",
    "spotify_artist_metadata",
    "spotify_audio_features",
    "spotify_metadata",
    "spotify_playlist_metadata",
    "timeseries_references",
    "track_audio_features_computed",
    "track_external_ids",
    "track_sections",
    "tracks",
    "transition_candidates",
    "transitions",
    "yandex_metadata",
]

# Extra datetime columns beyond created_at/updated_at
_EXTRA_COLUMNS = [
    ("dj_playlist_items", "added_at"),
    ("raw_provider_responses", "fetched_at"),
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"

    if not is_postgresql:
        return  # SQLite has no timestamp type distinction

    timestamptz = sa.DateTime(timezone=True)

    for table in _TIMESTAMPED_TABLES:
        op.alter_column(table, "created_at", type_=timestamptz, existing_type=sa.DateTime())
        op.alter_column(table, "updated_at", type_=timestamptz, existing_type=sa.DateTime())

    for table, column in _EXTRA_COLUMNS:
        op.alter_column(table, column, type_=timestamptz, existing_type=sa.DateTime())


def downgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"

    if not is_postgresql:
        return

    timestamp_naive = sa.DateTime()

    for table in _TIMESTAMPED_TABLES:
        op.alter_column(
            table, "created_at", type_=timestamp_naive, existing_type=sa.DateTime(timezone=True)
        )
        op.alter_column(
            table, "updated_at", type_=timestamp_naive, existing_type=sa.DateTime(timezone=True)
        )

    for table, column in _EXTRA_COLUMNS:
        op.alter_column(
            table, column, type_=timestamp_naive, existing_type=sa.DateTime(timezone=True)
        )
