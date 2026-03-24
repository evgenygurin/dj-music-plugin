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
