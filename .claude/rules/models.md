---
description: SQLAlchemy model patterns for DJ Music Plugin
globs: src/dj_music/models/**/*.py
---

# SQLAlchemy Models

- Use SQLAlchemy 2.0 `mapped_column()` style, not legacy `Column()`
- All models inherit from `Base` (defined in `src/dj_music/models/base.py`)
- `__tablename__` = snake_case plural (e.g., `tracks`, `dj_sets`, `track_audio_features_computed`)
- Always add `created_at` and `updated_at` with server defaults
- Use `CheckConstraint` for domain ranges from `src/dj_music/core/constants.py`:
  - BPM: `CheckConstraint("bpm BETWEEN 20 AND 300")`
  - Confidence: `CheckConstraint("confidence BETWEEN 0 AND 1")`
  - Key codes: `CheckConstraint("key_code BETWEEN 0 AND 23")`
- Use `IntEnum`/`StrEnum` from `src/dj_music/core/constants.py` for status fields
- Foreign keys always have `ondelete` specified (CASCADE or SET NULL)
- Relationships use `Mapped[]` type annotations
- Index frequently queried columns (bpm, key_code, status)

## Gotchas

- Energy band column names: `energy_sub`, `energy_lowmid`, `energy_highmid` (not `energy_band_*`, not `energy_low_mid`)
