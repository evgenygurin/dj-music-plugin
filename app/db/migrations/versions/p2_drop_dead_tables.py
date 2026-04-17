"""phase2 drop dead tables

Removes 17 tables with 0 rows per blueprint §13.2 (15 dead concepts +
labels + track_labels counted separately):
- spotify_metadata, spotify_album_metadata, spotify_artist_metadata,
  spotify_playlist_metadata, spotify_audio_features
- beatport_metadata
- soundcloud_metadata
- embeddings
- transition_candidates
- dj_saved_loops, dj_cue_points, dj_beatgrid_change_points
- dj_set_constraints, dj_set_feedback
- labels, track_labels
- app_exports

Downgrade recreates minimal columns for rollback.

Revision ID: p2_drop_dead
Revises: b8f2a1c3d4e7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p2_drop_dead"
down_revision = "b8f2a1c3d4e7"
branch_labels = None
depends_on = None

DEAD_TABLES: tuple[str, ...] = (
    "spotify_audio_features",
    "spotify_playlist_metadata",
    "spotify_artist_metadata",
    "spotify_album_metadata",
    "spotify_metadata",
    "beatport_metadata",
    "soundcloud_metadata",
    "embeddings",
    "transition_candidates",
    "dj_saved_loops",
    "dj_cue_points",
    "dj_beatgrid_change_points",
    "dj_set_constraints",
    "dj_set_feedback",
    "track_labels",
    "labels",
    "app_exports",
)


def upgrade() -> None:
    for tbl in DEAD_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')


def downgrade() -> None:
    """Minimal columns only — body not restored."""
    for tbl in DEAD_TABLES:
        op.create_table(
            tbl,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
