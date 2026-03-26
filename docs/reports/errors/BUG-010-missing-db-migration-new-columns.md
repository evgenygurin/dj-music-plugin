# BUG-010: Missing DB migration for new model columns

**Status:** OPEN (2026-03-27)

## Symptom

`build_set` and any query touching `track_audio_features_computed` fails:
```text
sqlite3.OperationalError: no such column: track_audio_features_computed.mfcc_vector
```

## Root Cause

Previous review added `mfcc_vector` column to the SQLAlchemy model (`app/models/audio.py`) but no Alembic migration was created. Similarly `energy_mid_ratio` was added to the model in the review phase but never migrated.

The actual DB schema lacks these columns.

## Affected Columns

- `mfcc_vector` (String, nullable) — added in review for REQUIREMENTS compliance
- `energy_mid_ratio` (Float, nullable) — added for 7-band completeness

## Fix

Run:
```bash
uv run alembic revision --autogenerate -m "add mfcc_vector and energy_mid_ratio"
uv run alembic upgrade head
```

## Impact

- `build_set`, `score_transitions`, `filter_tracks` with features — all broken
- Any tool that queries TrackAudioFeaturesComputed fails
