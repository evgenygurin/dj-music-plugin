---
description: Repository layer patterns
globs: app/repositories/**/*.py
---

# Repositories

- Extend `BaseRepository` from `app/repositories/base.py`
- Receive `AsyncSession` via `__init__(self, session: AsyncSession)`
- **Never commit** — only `session.flush()`. Commit happens in DI wrapper `get_db_session()`
- Use `session.execute(select(...))` for queries, not `session.query()`
- Cursor-based pagination via `_paginate()` from base class
- Return model instances, not dicts
- Methods are async: `async def get_by_id(self, id: int) -> Track | None`
- Use `selectinload()` for eager loading relationships when needed
- Filter methods accept Optional params: `bpm_min: float | None = None`

## Gotchas

- `AsyncSession.delete()` IS async in SQLAlchemy 2.0 — `await` is correct
- `TrackRepository.filter_tracks_advanced` `sort_by` поддерживает direction-суффикс: `bpm`/`bpm_desc`/`bpm_asc`, `id_desc`, `energy_desc`, `title_asc`. Без суффикса — ascending. Cursor pagination корректно работает только при сортировке по `id` (TODO в коде).
- `filter_tracks_advanced` делает **INNER JOIN** на `track_audio_features_computed` если `has_features` ∈ {None, True} → треки без features НЕ возвращаются. В тестах сначала seed `TrackAudioFeaturesComputed(track_id=..., bpm=..., analysis_level=3)` для каждого трека, иначе результат пуст.
