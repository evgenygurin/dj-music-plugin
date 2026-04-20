---
description: Repository layer patterns (v1 layout)
globs: app/repositories/**/*.py
---

# Repositories

- Extend `BaseRepository[M]` from `app/repositories/base.py` (generic
  over the SQLAlchemy model type).
- Receive `AsyncSession` via `__init__(self, session: AsyncSession)`
  — or rely on `UnitOfWork` to inject it.
- **Never commit** — only `session.flush()` if needed. Commit happens
  in `UnitOfWork.__aexit__` via the DI wrapper `get_uow()`.
- Use `session.execute(select(...))` (SQLAlchemy 2.0), not legacy
  `session.query()`.
- Generic CRUD (`list`, `get`, `create`, `update`, `delete`) lives
  in the base. Override only when an entity needs specialized joins
  or query shapes.
- **Django-style filter DSL.** `BaseRepository.list(filters={...})`
  accepts lookups like `bpm__gte`, `mood__in`, `title__icontains`,
  `key_code__isnull`. Parser lives in `app/shared/filters.py`.
- **Pagination.** Cursor-based via `BaseRepository._paginate()`. The
  encoded cursor is opaque to callers.
- **Relations.** Use `selectinload()` when the caller passes
  `include_relations=[...]` — never eager-load by default.
- Return model instances, not dicts. Pydantic mapping happens in the
  tool/handler layer.
- Entity-specific repositories (e.g. `TrackFeaturesRepository`) live
  in `app/repositories/<entity>.py` and add entity-specific batch
  helpers (`get_scoring_features_batch`, …).

## UnitOfWork

`app/repositories/unit_of_work.py` aggregates all repositories under
one session:

```python
async with get_uow() as uow:
    track = await uow.tracks.get(track_id)
    feats = await uow.track_features.get_scoring_features_batch(ids)
    uow.track_feedback.create(...)
    # commit/rollback is handled by __aexit__
```

UoW property names are **plural** (mirrors the DB table names):
`tracks`, `playlists`, `sets`, `set_versions`, `audio_files`,
`track_features`, `transitions`, `transition_history`, `track_feedback`,
`track_affinity`, `scoring_profiles`, `provider_metadata`,
`yandex_metadata`, `raw_provider_responses`, `keys`, `key_edges`.

All tools receive `uow` via `Depends(get_uow)`. Handlers receive
`uow` as an argument — never create their own session.

## Gotchas

- `AsyncSession.delete()` IS async in SQLAlchemy 2.0 — `await` is
  correct.
- Filter DSL: `has_features=True` becomes an INNER JOIN on
  `track_audio_features_computed`; `has_features=False` becomes a
  NOT-EXISTS subquery. Default (`None`) does nothing. Seed
  `TrackAudioFeaturesComputed` for every `Track` in repository tests
  or the INNER JOIN filters everything out.
- Sort suffix: `bpm__desc`, `bpm__asc`, etc. Cursor pagination works
  correctly only when the sort key is unique (prefer `id` as final
  tiebreaker).
