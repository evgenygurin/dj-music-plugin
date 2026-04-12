# Phase 3: repositories/ — Data Access + Ports

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Create `src/dj_music/repositories/` with BaseRepository[TModel, TSchema], Protocol ports, UoW, session factory. Repositories return Pydantic schemas, not ORM models.

**Architecture:** BaseRepository generic auto-converts ORM ↔ Schema via `model_validate()`/`model_dump()`. Protocol ports define interfaces that services depend on.

**Tech Stack:** SQLAlchemy 2.0 async, Pydantic v2

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- https://gofastmcp.com/servers/dependency-injection
- https://gofastmcp.com/servers/lifespan
- SQLAlchemy 2.0: selectinload, load_only, WriteOnlyMapped, expire_on_commit

---

### Task 1: Create BaseRepository[TModel, TSchema]

**Files:**
- Create: `src/dj_music/repositories/__init__.py`
- Create: `src/dj_music/repositories/base.py`

- [ ] **Step 1: Write test**

```python
# tests/test_repositories/test_base_generic.py
import pytest
from pydantic import ConfigDict
from dj_music.schemas.base import BaseEntity
from dj_music.repositories.base import BaseRepository

class FakeModel:
    """Simulates SQLAlchemy model."""
    id = 1
    name = "test"

class FakeSchema(BaseEntity):
    model_config = ConfigDict(from_attributes=True)
    name: str = ""

def test_base_repo_to_schema():
    """model_validate converts ORM → Schema."""
    schema = FakeSchema.model_validate(FakeModel())
    assert schema.id == 1
    assert schema.name == "test"

def test_base_repo_to_dict():
    """model_dump converts Schema → dict for ORM creation."""
    schema = FakeSchema(id=0, name="new")
    data = schema.model_dump(exclude_unset=True)
    assert data == {"name": "new"}
```

- [ ] **Step 2: Run test — fails**

- [ ] **Step 3: Implement BaseRepository**

```python
# src/dj_music/repositories/base.py
"""Generic async repository with auto ORM ↔ Schema conversion."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.core.utils.pagination import CursorPage, decode_cursor, encode_cursor

TModel = TypeVar("TModel")
TSchema = TypeVar("TSchema")

class BaseRepository(Generic[TModel, TSchema]):
    """Base repository: CRUD + cursor pagination + ORM ↔ Schema mapping.

    - TModel: SQLAlchemy ORM model class
    - TSchema: Pydantic schema class (from_attributes=True)
    - All reads return TSchema (via model_validate)
    - All writes accept TSchema (via model_dump)
    - flush() only — never commit()
    """

    def __init__(
        self,
        session: AsyncSession,
        model_class: type[TModel],
        schema_class: type[TSchema],
    ) -> None:
        self.session = session
        self.model_class = model_class
        self.schema_class = schema_class

    def _to_schema(self, obj: TModel) -> TSchema:
        return self.schema_class.model_validate(obj)

    def _to_schemas(self, objs: list[TModel]) -> list[TSchema]:
        return [self._to_schema(o) for o in objs]

    async def get_by_id(self, id: int) -> TSchema | None:
        stmt = select(self.model_class).where(
            self.model_class.id == id  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        return self._to_schema(obj) if obj else None

    async def list_all(
        self, limit: int = 20, cursor: str | None = None
    ) -> CursorPage[TSchema]:
        return await self._paginate(
            select(self.model_class), limit=limit, cursor=cursor
        )

    async def create(self, schema: TSchema) -> TSchema:
        data = schema.model_dump(exclude_unset=True, exclude={"id"})
        obj = self.model_class(**data)
        self.session.add(obj)
        await self.session.flush()
        return self._to_schema(obj)

    async def update(self, id: int, schema: TSchema) -> TSchema | None:
        stmt = select(self.model_class).where(
            self.model_class.id == id  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        for key, value in schema.model_dump(exclude_unset=True, exclude={"id"}).items():
            setattr(obj, key, value)
        await self.session.flush()
        return self._to_schema(obj)

    async def delete(self, id: int) -> bool:
        stmt = select(self.model_class).where(
            self.model_class.id == id  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def _paginate(
        self,
        stmt: Any,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[TSchema]:
        # Reuse existing pagination logic from core/utils/pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        if cursor:
            offset = decode_cursor(cursor)
            stmt = stmt.offset(offset)
        else:
            offset = 0

        stmt = stmt.limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = self._to_schemas(rows[:limit])
        next_cursor = encode_cursor(offset + limit) if has_more else None

        return CursorPage(items=items, next_cursor=next_cursor, total=total)
```

- [ ] **Step 4: Run test — passes**

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add BaseRepository[TModel, TSchema] with auto ORM mapping

Generic CRUD: get_by_id, list_all, create, update, delete.
ORM → Schema via model_validate, Schema → ORM via model_dump.
Cursor pagination. flush() only, never commit.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Create Protocol ports

**Files:**
- Create: `src/dj_music/repositories/ports.py`

- [ ] **Step 1: Define repository Protocol interfaces**

```python
# src/dj_music/repositories/ports.py
"""Repository port interfaces (Protocol). Services depend on these."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dj_music.core.utils.pagination import CursorPage
from dj_music.schemas.track import Track, TrackBrief, TrackFilter

@runtime_checkable
class TrackRepositoryPort(Protocol):
    async def get_by_id(self, id: int) -> Track | None: ...
    async def list_all(self, limit: int = 20, cursor: str | None = None) -> CursorPage[Track]: ...
    async def create(self, schema: Track) -> Track: ...
    async def filter(self, params: TrackFilter) -> CursorPage[TrackBrief]: ...

# Add more ports as needed: PlaylistRepositoryPort, SetRepositoryPort, etc.
# Each port defines only the methods that services actually use (ISP).
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat: add repository Protocol ports for dependency inversion

Services depend on Protocol, not concrete repos. ISP compliant.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Move concrete repositories + session + seed + UoW

**Files:**
- Copy: `app/db/repositories/` → `src/dj_music/repositories/`
- Copy: `app/db/session.py` → `src/dj_music/repositories/session.py`
- Copy: `app/db/seed.py` → `src/dj_music/repositories/seed.py`
- Copy: `app/db/repositories/unit_of_work.py` → `src/dj_music/repositories/unit_of_work.py`

- [ ] **Step 1: Copy all repository files**

```bash
# Copy concrete repos (preserving track/ subdirectory)
cp -r app/db/repositories/* src/dj_music/repositories/
cp app/db/session.py src/dj_music/repositories/session.py
cp app/db/seed.py src/dj_music/repositories/seed.py
```

- [ ] **Step 2: Update imports in all copied files**

Replace `from app.db.repositories.` → `from dj_music.repositories.`
Replace `from app.db.models.` → `from dj_music.models.` (will exist after Phase 6)
Replace `from app.db.session` → `from dj_music.repositories.session`
Replace `from app.core.` → `from dj_music.core.`
Replace `from app.entities.` → `from dj_music.schemas.`

**Note:** `from dj_music.models.` won't resolve until Phase 6. For now, keep `from app.db.models.` in concrete repos — they'll be updated in Phase 6.

- [ ] **Step 3: Shims in app/db/repositories/ and app/db/session.py**

- [ ] **Step 4: Run repo tests**

```bash
uv run pytest tests/test_repositories/ -x -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move repositories + session + seed to dj_music.repositories

Concrete repos still import app.db.models (updated in Phase 6).
Re-export shims in app/db/ for backward compat.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Final Phase 3 verification

- [ ] **Step 1: Verify structure**

```bash
ls src/dj_music/repositories/
```

Expected: base.py, ports.py, unit_of_work.py, session.py, seed.py, track/, playlist.py, set.py, feature.py, etc.

- [ ] **Step 2: Full check**

```bash
make check
```
