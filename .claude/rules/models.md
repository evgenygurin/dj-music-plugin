---
description: SQLAlchemy model patterns for DJ Music Plugin (v1 layout)
globs: app/models/**/*.py
---

# SQLAlchemy Models

- All models live in `app/models/` — **one file per aggregate root**.
- Use SQLAlchemy 2.0 `mapped_column()` style, not legacy `Column()`.
- All models inherit from `Base` (defined in `app/models/base.py`).
- `__tablename__` = snake_case plural (e.g., `tracks`, `dj_sets`,
  `track_audio_features_computed`).
- Always add `created_at` and `updated_at` with server defaults (helper
  mixin in `app/models/base.py`).
- Use `CheckConstraint` for domain ranges from
  `app/shared/constants.py`:
  - BPM: `CheckConstraint("bpm BETWEEN 20 AND 300")`
  - Confidence: `CheckConstraint("confidence BETWEEN 0 AND 1")`
  - Key codes: `CheckConstraint("key_code BETWEEN 0 AND 23")`
- Use `IntEnum`/`StrEnum` from `app/shared/constants.py` for status
  fields.
- Foreign keys always have `ondelete` specified (CASCADE or SET NULL).
- Relationships use `Mapped[]` type annotations.
- Index frequently queried columns (bpm, key_code, status, mood).
- Aggregate roots tracked in `EntityRegistry` — every new model must
  be registered or it's invisible to `entity_*` tools.

## Gotchas

- Energy band column names: `energy_sub`, `energy_lowmid`,
  `energy_highmid` (not `energy_band_*`, not `energy_low_mid`).
- Drop-pending tables (blueprint §13.2): spotify_\*, beatport_metadata,
  soundcloud_metadata, embeddings, transition_candidates,
  dj_saved_loops, dj_cue_points, dj_beatgrid_change_points,
  dj_set_constraints, dj_set_feedback, labels, track_labels,
  app_exports — the Alembic migration `p2_drop_dead_tables` is
  **not present in the repo** (no files under
  `app/db/migrations/versions/`) and has not been applied to
  Supabase. v1 code has no ORM models for them — do not reintroduce.
- Every new aggregate root must be registered in
  `app/registry/defaults.py:register_default_entities()` or it stays
  invisible to `entity_*` tools.
- Current live aggregate roots: **11 registered entities** (visible via
  `schema://entities`):
  `track`, `track_features`, `audio_file`, `playlist`, `set`,
  `set_version`, `transition`, `transition_history`, `track_feedback`,
  `track_affinity`, `scoring_profile`.
- Plus 2 reference-only models that have ORM + repos but are NOT in
  `EntityRegistry`: `key` (Camelot wheel — exposed via
  `reference://camelot`) and `provider_metadata` (raw provider response
  cache — surfaced through `provider_*` tools).
