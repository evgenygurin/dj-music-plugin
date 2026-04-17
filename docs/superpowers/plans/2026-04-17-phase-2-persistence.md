# Phase 2 — Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port all 13 aggregate-root ORM models into `app/v2/models/`, build 13 thin `BaseRepository[M]` subclasses, 12 Pydantic schema families (View/Filter/Create/Update), extend UoW with lazy repo properties, drop 15 dead DB tables via Alembic, wire reference-data seed, and register 11 user-facing entities on `EntityRegistry`.

**Architecture:** Each aggregate gets one file in `models/`, `repositories/`, `schemas/` (mirroring DB structure). Models copy column definitions + constraints from legacy `app/db/models/` verbatim — no DB schema changes except the dead-table drops. Repositories inherit generic CRUD from `BaseRepository[M]` (Phase 1 Task 14) and add 3-5 domain-specific methods. Pydantic schemas are the single source of truth for tool-surface validation. All changes are additive to `app/v2/`; `app/` remains untouched and runnable.

**Tech Stack:** SQLAlchemy 2.0 (mapped_column style, async), Pydantic v2, pydantic-settings, asyncpg (Supabase), aiosqlite (tests), Alembic, pytest + pytest-asyncio, import-linter.

**Spec reference:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§3, 10, 12, 13.2, 14.1, 14.2, 15.3, 16.

**Preconditions:** Phase 1 complete — `app/v2/shared/`, `app/v2/config/`, `app/v2/registry/{entity,provider}.py`, `app/v2/repositories/{base,unit_of_work}.py`, `tests/v2/conftest.py` all exist and tests pass.

---

## File Structure

New files created by this plan:

### Source code (`app/v2/`)

```text
app/v2/
├── models/
│   ├── __init__.py                # re-exports all ORM classes
│   ├── base.py                    # Base + TimestampMixin
│   ├── key.py                     # Key + KeyEdge (reference)
│   ├── provider_metadata.py       # Provider + YandexMetadata + RawProviderResponse
│   ├── track.py                   # Track + Artist + Genre + Release + TrackArtist + TrackGenre + TrackRelease + TrackExternalId
│   ├── playlist.py                # DjPlaylist + DjPlaylistItem
│   ├── set.py                     # DjSet + DjSetVersion + DjSetItem
│   ├── audio_file.py              # DjLibraryItem + DjBeatgrid
│   ├── track_features.py          # TrackAudioFeaturesComputed + TrackSection + TimeseriesReference + FeatureExtractionRun
│   ├── transition.py              # Transition (persisted scored pair)
│   ├── transition_history.py      # TransitionHistory
│   ├── track_feedback.py          # TrackFeedback
│   ├── track_affinity.py          # TrackAffinity
│   └── scoring_profile.py         # ScoringProfile
├── schemas/
│   ├── common.py                  # Page re-export + EntityListView + EntityAggregateView + EntityRef
│   ├── provider.py                # ProviderResultView + ProviderSearchView
│   ├── track.py                   # TrackView, TrackFilter, TrackCreate, TrackUpdate
│   ├── playlist.py
│   ├── set.py                     # includes SetVersion* schemas
│   ├── audio_file.py
│   ├── track_features.py
│   ├── transition.py
│   ├── transition_history.py
│   ├── track_feedback.py
│   ├── track_affinity.py
│   └── scoring_profile.py
├── repositories/
│   ├── track.py
│   ├── playlist.py
│   ├── set.py
│   ├── audio_file.py
│   ├── track_features.py
│   ├── transition.py
│   ├── transition_history.py
│   ├── track_feedback.py
│   ├── track_affinity.py
│   ├── scoring_profile.py
│   ├── provider_metadata.py
│   └── key.py
└── db/
    ├── __init__.py
    ├── session.py                 # async engine + sessionmaker
    └── seed.py                    # 24 keys (Camelot) + 4 providers
```

### Modified

- `app/v2/repositories/unit_of_work.py` — add 12 lazy `@property` accessors
- `app/v2/registry/entity.py` — add `register_default_entities()` function

### Migrations

- `app/db/migrations/versions/phase2_drop_dead_tables.py` — Alembic migration dropping 15 tables

### Tests

```text
tests/v2/
├── models/
│   ├── __init__.py
│   ├── test_track.py
│   ├── test_playlist.py
│   ├── test_set.py
│   ├── test_audio_file.py
│   ├── test_track_features.py
│   ├── test_transition.py
│   ├── test_transition_history.py
│   ├── test_track_feedback.py
│   ├── test_track_affinity.py
│   ├── test_scoring_profile.py
│   ├── test_provider_metadata.py
│   └── test_key.py
├── repositories/
│   ├── test_track_repo.py
│   ├── test_playlist_repo.py
│   ├── test_set_repo.py
│   ├── test_audio_file_repo.py
│   ├── test_track_features_repo.py
│   ├── test_transition_repo.py
│   ├── test_feedback_affinity_repos.py
│   └── test_misc_repos.py
├── schemas/
│   └── test_pydantic_shapes.py
├── db/
│   └── test_seed.py
├── registry/
│   └── test_register_default_entities.py
└── migrations/
    └── test_drop_dead_tables.py
```

---

## Task 1: `app/v2/models/base.py` + package skeleton

**Files:**
- Create: `app/v2/models/__init__.py`
- Create: `app/v2/models/base.py`
- Test: `tests/v2/models/__init__.py` (empty)

- [ ] **Step 1: Create directories**

```bash
mkdir -p app/v2/models app/v2/db tests/v2/models tests/v2/schemas tests/v2/db tests/v2/migrations
```

- [ ] **Step 2: Write `app/v2/models/base.py`**

```python
"""SQLAlchemy declarative Base + TimestampMixin for v2 models.

All aggregates inherit from ``Base``; rows that need ``created_at`` /
``updated_at`` columns additionally mix in ``TimestampMixin``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.v2.shared.time import sa_now

class Base(DeclarativeBase):
    """Declarative base for every v2 ORM model."""

class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns with DB-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=sa_now(),
        server_default=sa_now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=sa_now(),
        server_default=sa_now(),
        onupdate=sa_now(),
    )
```

- [ ] **Step 3: Write `app/v2/models/__init__.py`**

```python
"""v2 ORM models. One aggregate root per module.

Import side-effect: all model classes are registered on ``Base.metadata``.
"""

from app.v2.models.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
```

- [ ] **Step 4: Write test `tests/v2/models/test_base.py`**

```python
"""Base + TimestampMixin sanity."""

from app.v2.models.base import Base, TimestampMixin

def test_base_is_declarative() -> None:
    # Metadata is accessible and empty before any model imports it.
    assert hasattr(Base, "metadata")

def test_mixin_defines_timestamp_columns() -> None:
    assert "created_at" in TimestampMixin.__annotations__
    assert "updated_at" in TimestampMixin.__annotations__
```

- [ ] **Step 5: Run tests — expected PASS**

```bash
uv run pytest tests/v2/models/test_base.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/models tests/v2/models/__init__.py tests/v2/models/test_base.py \
        tests/v2/schemas tests/v2/db tests/v2/migrations
git commit -m "feat(v2): add models Base + TimestampMixin

Declarative base and timestamp mixin for 13 aggregate-root models.
Uses app.v2.shared.time.sa_now() for Python + DB-side defaults."
```

---

## Task 2: `models/key.py` — Key + KeyEdge (reference data)

**Files:**
- Create: `app/v2/models/key.py`
- Test: `tests/v2/models/test_key.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_key.py
"""Reference model tests: keys + key_edges."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.key import Key, KeyEdge

@pytest.mark.asyncio
async def test_create_key(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Key(key_code=0, pitch_class=0, mode=0, name="C minor", camelot="5A"))
    await session.commit()
    k = await session.get(Key, 0)
    assert k is not None
    assert k.camelot == "5A"
    assert k.mode == 0

@pytest.mark.asyncio
async def test_key_code_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Key(key_code=99, pitch_class=0, mode=0, name="bad", camelot="xx"))
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_key_edge_distance_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(KeyEdge(from_key=0, to_key=1, distance=99, weight=1.0, rule_name="bad"))
    with pytest.raises(IntegrityError):
        await session.commit()
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_key.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/models/key.py`**

```python
"""24 musical keys + compatibility graph (reference data).

``keys.key_code`` spans 0..23 per the Camelot wheel. ``key_edges``
stores weighted compatibility between any two keys (distance 0..6).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin

class Key(Base, TimestampMixin):
    __tablename__ = "keys"
    __table_args__ = (
        CheckConstraint("key_code BETWEEN 0 AND 23", name="ck_key_code_range"),
        CheckConstraint("pitch_class BETWEEN 0 AND 11", name="ck_pitch_class_range"),
        CheckConstraint("mode IN (0, 1)", name="ck_key_mode"),
    )

    key_code: Mapped[int] = mapped_column(primary_key=True)
    pitch_class: Mapped[int] = mapped_column()
    mode: Mapped[int] = mapped_column(doc="0 = minor, 1 = major")
    name: Mapped[str] = mapped_column(String(50))
    camelot: Mapped[str] = mapped_column(String(4), unique=True)

class KeyEdge(Base, TimestampMixin):
    __tablename__ = "key_edges"
    __table_args__ = (
        CheckConstraint("distance BETWEEN 0 AND 6", name="ck_key_edge_distance_range"),
        CheckConstraint("weight BETWEEN 0 AND 1", name="ck_key_edge_weight_range"),
    )

    from_key: Mapped[int] = mapped_column(ForeignKey("keys.key_code"), primary_key=True)
    to_key: Mapped[int] = mapped_column(ForeignKey("keys.key_code"), primary_key=True)
    distance: Mapped[int] = mapped_column()
    weight: Mapped[float] = mapped_column()
    rule_name: Mapped[str] = mapped_column(String(50))
```

- [ ] **Step 4: Update `models/__init__.py`**

```python
"""v2 ORM models."""

from app.v2.models.base import Base, TimestampMixin
from app.v2.models.key import Key, KeyEdge

__all__ = ["Base", "TimestampMixin", "Key", "KeyEdge"]
```

- [ ] **Step 5: Run — expected PASS**

```bash
uv run pytest tests/v2/models/test_key.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/models/key.py app/v2/models/__init__.py tests/v2/models/test_key.py
git commit -m "feat(v2): add Key + KeyEdge reference models

24 keys keyed by key_code 0..23 + compatibility edges with distance 0..6."
```

---

## Task 3: `models/provider_metadata.py`

**Files:**
- Create: `app/v2/models/provider_metadata.py`
- Test: `tests/v2/models/test_provider_metadata.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_provider_metadata.py
"""Provider + YandexMetadata + RawProviderResponse."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)
from app.v2.models.track import Track

@pytest.mark.asyncio
async def test_provider_row(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Provider(code="yandex_music", display_name="Yandex Music"))
    await session.commit()
    provs = (await session.execute(__import__("sqlalchemy").select(Provider))).scalars().all()
    assert len(provs) == 1
    assert provs[0].code == "yandex_music"

@pytest.mark.asyncio
async def test_yandex_metadata_requires_track(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(id=1, title="t"))
    await session.commit()
    session.add(
        YandexMetadata(
            track_id=1, yandex_track_id="12345", album_id=None, duration_ms=180000
        )
    )
    await session.commit()
    ym = await session.get(YandexMetadata, 1)
    assert ym is not None
    assert ym.yandex_track_id == "12345"

@pytest.mark.asyncio
async def test_raw_response_body(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(id=1, title="t"))
    await session.commit()
    session.add(
        RawProviderResponse(
            track_id=1,
            provider_code="yandex_music",
            endpoint="/tracks/12345",
            body='{"id":"12345"}',
        )
    )
    await session.commit()
    rows = (
        (await session.execute(__import__("sqlalchemy").select(RawProviderResponse)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].body.startswith("{")
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_provider_metadata.py -v
```
Expected: `ModuleNotFoundError` (provider_metadata missing, track missing).

- [ ] **Step 3: Write `app/v2/models/provider_metadata.py`**

```python
"""External music platforms: provider registry + per-track metadata + raw responses.

Supports only the providers actually used today (Yandex). Spotify /
Beatport / SoundCloud legacy tables dropped in Phase 2 Alembic migration.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.v2.models.base import Base, TimestampMixin

class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))

class YandexMetadata(Base, TimestampMixin):
    __tablename__ = "yandex_metadata"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    yandex_track_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    album_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    album_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    album_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    album_genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    album_year: Mapped[int | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    release_date: Mapped[date | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    cover_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    explicit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)

class RawProviderResponse(Base, TimestampMixin):
    __tablename__ = "raw_provider_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_code: Mapped[str] = mapped_column(String(50), index=True)
    endpoint: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Add to `models/__init__.py`**

Append imports + `__all__` entries. The final file:

```python
"""v2 ORM models."""

from app.v2.models.base import Base, TimestampMixin
from app.v2.models.key import Key, KeyEdge
from app.v2.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "Key",
    "KeyEdge",
    "Provider",
    "RawProviderResponse",
    "YandexMetadata",
]
```

- [ ] **Step 5: Test still fails — Track model not ported yet**

This task is paired with Task 4 (Track). Skip final Run-Expect-Pass here; verify after Task 4.

- [ ] **Step 6: Commit**

```bash
git add app/v2/models/provider_metadata.py app/v2/models/__init__.py \
        tests/v2/models/test_provider_metadata.py
git commit -m "feat(v2): add provider_metadata models

Provider registry + YandexMetadata + RawProviderResponse. Test runs
green after Task 4 (Track port) because metadata FK references tracks."
```

---

## Task 4: `models/track.py` — Track aggregate (7 classes)

**Files:**
- Create: `app/v2/models/track.py`
- Test: `tests/v2/models/test_track.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_track.py
"""Track aggregate: Track + Artist + Genre + Release + TrackExternalId + joins."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import (
    Artist,
    Genre,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackRelease,
)

@pytest.mark.asyncio
async def test_track_minimal(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="Strobe")
    session.add(t)
    await session.commit()
    assert t.id is not None
    assert t.status == 0

@pytest.mark.asyncio
async def test_track_status_constraint(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(title="x", status=5))
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_track_with_artist_via_join(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="Song")
    a = Artist(name="Deadmau5")
    session.add_all([t, a])
    await session.flush()
    session.add(TrackArtist(track_id=t.id, artist_id=a.id, role="primary"))
    await session.commit()

    rows = (
        await session.execute(
            select(TrackArtist).where(TrackArtist.track_id == t.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].role == "primary"

@pytest.mark.asyncio
async def test_track_external_id_provider(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="Song")
    session.add(t)
    await session.flush()
    session.add(
        TrackExternalId(track_id=t.id, provider_code="yandex_music", external_id="98765")
    )
    await session.commit()
    rows = (
        await session.execute(select(TrackExternalId).where(TrackExternalId.track_id == t.id))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].external_id == "98765"

@pytest.mark.asyncio
async def test_genre_hierarchy(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    parent = Genre(name="Techno")
    session.add(parent)
    await session.flush()
    child = Genre(name="Peak Time Techno", parent_id=parent.id)
    session.add(child)
    await session.commit()
    loaded = await session.get(Genre, child.id)
    assert loaded is not None
    assert loaded.parent_id == parent.id
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_track.py tests/v2/models/test_provider_metadata.py -v
```
Expected: `ModuleNotFoundError` on `app.v2.models.track`.

- [ ] **Step 3: Write `app/v2/models/track.py`**

```python
"""Track aggregate: Track + Artist + Genre + Release + 4 join tables + external IDs.

Port of legacy ``app/db/models/track.py`` + external-IDs slice of
``app/db/models/ingestion.py``. ``track_labels`` / ``labels`` dropped per
blueprint §13.2.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.v2.models.base import Base, TimestampMixin

class Track(Base, TimestampMixin):
    __tablename__ = "tracks"
    __table_args__ = (CheckConstraint("status IN (0, 1)", name="ck_track_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    sort_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[int] = mapped_column(default=0, server_default="0", index=True)

    track_artists: Mapped[list["TrackArtist"]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    track_genres: Mapped[list["TrackGenre"]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    track_releases: Mapped[list["TrackRelease"]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )
    external_ids: Mapped[list["TrackExternalId"]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )

class Artist(Base, TimestampMixin):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True)
    sort_name: Mapped[str | None] = mapped_column(String(300), nullable=True)

class Genre(Base, TimestampMixin):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("genres.id", ondelete="SET NULL"), nullable=True, index=True
    )

class Release(Base, TimestampMixin):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    release_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    release_date: Mapped[date | None] = mapped_column(nullable=True)

class TrackArtist(Base):
    __tablename__ = "track_artists"
    __table_args__ = (
        UniqueConstraint("track_id", "artist_id", "role", name="uq_track_artist_role"),
    )

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), primary_key=True)

    track: Mapped[Track] = relationship(back_populates="track_artists")

class TrackGenre(Base):
    __tablename__ = "track_genres"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )

    track: Mapped[Track] = relationship(back_populates="track_genres")

class TrackRelease(Base):
    __tablename__ = "track_releases"

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    release_id: Mapped[int] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    track_number: Mapped[int | None] = mapped_column(nullable=True)

    track: Mapped[Track] = relationship(back_populates="track_releases")

class TrackExternalId(Base, TimestampMixin):
    __tablename__ = "track_external_ids"
    __table_args__ = (
        UniqueConstraint(
            "provider_code", "external_id", name="uq_provider_external_id"
        ),
        UniqueConstraint("track_id", "provider_code", name="uq_track_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    provider_code: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(200), index=True)

    track: Mapped[Track] = relationship(back_populates="external_ids")
```

- [ ] **Step 4: Update `models/__init__.py`**

```python
"""v2 ORM models."""

from app.v2.models.base import Base, TimestampMixin
from app.v2.models.key import Key, KeyEdge
from app.v2.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)
from app.v2.models.track import (
    Artist,
    Genre,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackRelease,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "Key",
    "KeyEdge",
    "Provider",
    "RawProviderResponse",
    "YandexMetadata",
    "Track",
    "Artist",
    "Genre",
    "Release",
    "TrackArtist",
    "TrackGenre",
    "TrackRelease",
    "TrackExternalId",
]
```

- [ ] **Step 5: Run track + provider_metadata tests together — expected PASS**

```bash
uv run pytest tests/v2/models/test_track.py tests/v2/models/test_provider_metadata.py -v
```
Expected: 8 passed (5 track + 3 provider_metadata).

- [ ] **Step 6: Commit**

```bash
git add app/v2/models/track.py app/v2/models/__init__.py tests/v2/models/test_track.py
git commit -m "feat(v2): add Track aggregate (7 classes)

Track + Artist + Genre + Release + TrackArtist + TrackGenre +
TrackRelease + TrackExternalId. Merges current track.py + external_ids
slice of ingestion.py. Drops labels / track_labels per blueprint."
```

---

## Task 5: `models/playlist.py`

**Files:**
- Create: `app/v2/models/playlist.py`
- Test: `tests/v2/models/test_playlist.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_playlist.py
"""DjPlaylist + DjPlaylistItem."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.playlist import DjPlaylist, DjPlaylistItem
from app.v2.models.track import Track

@pytest.mark.asyncio
async def test_create_playlist(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    pl = DjPlaylist(name="Peak Hour", source_of_truth="local")
    session.add(pl)
    await session.commit()
    assert pl.id is not None
    assert pl.source_of_truth == "local"

@pytest.mark.asyncio
async def test_playlist_item_sort_index(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    pl = DjPlaylist(name="P")
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([pl, t1, t2])
    await session.flush()
    session.add_all(
        [
            DjPlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=0),
            DjPlaylistItem(playlist_id=pl.id, track_id=t2.id, sort_index=1),
        ]
    )
    await session.commit()
    items = (
        await session.execute(
            select(DjPlaylistItem)
            .where(DjPlaylistItem.playlist_id == pl.id)
            .order_by(DjPlaylistItem.sort_index)
        )
    ).scalars().all()
    assert [i.track_id for i in items] == [t1.id, t2.id]
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_playlist.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/models/playlist.py`**

```python
"""Playlist aggregate: DjPlaylist + DjPlaylistItem.

Port of legacy ``app/db/models/playlist.py``.
"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.v2.models.base import Base, TimestampMixin
from app.v2.shared.time import utc_now

class DjPlaylist(Base, TimestampMixin):
    __tablename__ = "dj_playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_app: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_of_truth: Mapped[str] = mapped_column(
        String(100), default="local", server_default="local"
    )
    platform_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent: Mapped["DjPlaylist | None"] = relationship(
        back_populates="children", remote_side="DjPlaylist.id"
    )
    children: Mapped[list["DjPlaylist"]] = relationship(back_populates="parent")
    items: Mapped[list["DjPlaylistItem"]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan"
    )

class DjPlaylistItem(Base):
    __tablename__ = "dj_playlist_items"
    __table_args__ = (
        UniqueConstraint(
            "playlist_id", "sort_index", name="uq_playlist_sort_index"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    sort_index: Mapped[int] = mapped_column(index=True)
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    playlist: Mapped[DjPlaylist] = relationship(back_populates="items")
```

- [ ] **Step 4: Re-export + run — expected PASS**

Append to `app/v2/models/__init__.py`:
```python
from app.v2.models.playlist import DjPlaylist, DjPlaylistItem
```
Add `"DjPlaylist"`, `"DjPlaylistItem"` to `__all__`.

```bash
uv run pytest tests/v2/models/test_playlist.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/models/playlist.py app/v2/models/__init__.py tests/v2/models/test_playlist.py
git commit -m "feat(v2): add DjPlaylist + DjPlaylistItem"
```

---

## Task 6: `models/set.py` — DJ Set aggregate

**Files:**
- Create: `app/v2/models/set.py`
- Test: `tests/v2/models/test_set.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_set.py
"""DjSet + DjSetVersion + DjSetItem."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.playlist import DjPlaylist
from app.v2.models.set import DjSet, DjSetItem, DjSetVersion
from app.v2.models.track import Track

@pytest.mark.asyncio
async def test_create_set_and_version(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    pl = DjPlaylist(name="seed")
    session.add(pl)
    await session.flush()
    s = DjSet(
        name="Summer 2026",
        target_duration_ms=3_600_000,
        target_bpm_min=124,
        target_bpm_max=132,
        source_playlist_id=pl.id,
    )
    session.add(s)
    await session.flush()
    v = DjSetVersion(set_id=s.id, version_label="v1", quality_score=0.82)
    session.add(v)
    await session.commit()
    assert v.id is not None
    assert v.quality_score == 0.82

@pytest.mark.asyncio
async def test_set_item_pin_flag(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    pl = DjPlaylist(name="p")
    t = Track(title="x")
    session.add_all([pl, t])
    await session.flush()
    s = DjSet(name="s", source_playlist_id=pl.id)
    session.add(s)
    await session.flush()
    v = DjSetVersion(set_id=s.id, version_label="v1")
    session.add(v)
    await session.flush()
    item = DjSetItem(
        set_version_id=v.id,
        track_id=t.id,
        sort_index=0,
        pinned=True,
    )
    session.add(item)
    await session.commit()
    loaded = await session.get(DjSetItem, item.id)
    assert loaded is not None
    assert loaded.pinned is True
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_set.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/models/set.py`**

```python
"""DJ Set aggregate: DjSet + DjSetVersion + DjSetItem.

Port of legacy ``app/db/models/set.py``. Drops SetConstraint + SetFeedback
per blueprint §13.2 (0 rows, feature unimplemented).
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.v2.models.base import Base, TimestampMixin

class DjSet(Base, TimestampMixin):
    __tablename__ = "dj_sets"
    __table_args__ = (
        CheckConstraint(
            "target_bpm_min IS NULL OR target_bpm_min BETWEEN 20 AND 300",
            name="ck_set_bpm_min_range",
        ),
        CheckConstraint(
            "target_bpm_max IS NULL OR target_bpm_max BETWEEN 20 AND 300",
            name="ck_set_bpm_max_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    target_bpm_min: Mapped[int | None] = mapped_column(nullable=True)
    target_bpm_max: Mapped[int | None] = mapped_column(nullable=True)
    target_energy_arc: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_playlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_playlists.id", ondelete="SET NULL"), nullable=True, index=True
    )
    linked_ym_playlist_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    versions: Mapped[list["DjSetVersion"]] = relationship(
        back_populates="dj_set", cascade="all, delete-orphan"
    )

class DjSetVersion(Base, TimestampMixin):
    __tablename__ = "dj_set_versions"
    __table_args__ = (
        CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 1",
            name="ck_version_quality_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(
        ForeignKey("dj_sets.id", ondelete="CASCADE"), index=True
    )
    version_label: Mapped[str] = mapped_column(String(100))
    generator_run_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(nullable=True)

    dj_set: Mapped[DjSet] = relationship(back_populates="versions")
    items: Mapped[list["DjSetItem"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

class DjSetItem(Base):
    __tablename__ = "dj_set_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    set_version_id: Mapped[int] = mapped_column(
        ForeignKey("dj_set_versions.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    sort_index: Mapped[int] = mapped_column(index=True)
    transition_id: Mapped[int | None] = mapped_column(
        ForeignKey("transitions.id", ondelete="SET NULL"), nullable=True
    )
    out_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    in_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    mix_in_point_ms: Mapped[int | None] = mapped_column(nullable=True)
    mix_out_point_ms: Mapped[int | None] = mapped_column(nullable=True)
    planned_eq: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    version: Mapped[DjSetVersion] = relationship(back_populates="items")
```

- [ ] **Step 4: Re-export**

Append `from app.v2.models.set import DjSet, DjSetItem, DjSetVersion` and update `__all__`.

- [ ] **Step 5: Test still fails — `transitions`, `track_sections` not ported yet**

These FKs target tables created later. Test will pass after Tasks 8 (`track_features`, creates `track_sections`) + 9 (`transition`). Defer verification.

- [ ] **Step 6: Commit**

```bash
git add app/v2/models/set.py app/v2/models/__init__.py tests/v2/models/test_set.py
git commit -m "feat(v2): add DjSet + DjSetVersion + DjSetItem

Drop dj_set_constraints + dj_set_feedback per blueprint §13.2."
```

---

## Task 7: `models/audio_file.py`

**Files:**
- Create: `app/v2/models/audio_file.py`
- Test: `tests/v2/models/test_audio_file.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_audio_file.py
"""DjLibraryItem + DjBeatgrid."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.audio_file import DjBeatgrid, DjLibraryItem
from app.v2.models.base import Base
from app.v2.models.track import Track

@pytest.mark.asyncio
async def test_create_library_item(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    li = DjLibraryItem(
        track_id=t.id,
        file_path="/vault/track.mp3",
        file_size=4_000_000,
        mime_type="audio/mpeg",
        bitrate_kbps=320,
        sample_rate=44100,
        channels=2,
    )
    session.add(li)
    await session.commit()
    assert li.id is not None

@pytest.mark.asyncio
async def test_beatgrid_bpm_range(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    li = DjLibraryItem(track_id=t.id, file_path="/x.mp3", file_size=1, mime_type="audio/mpeg")
    session.add(li)
    await session.flush()
    bg = DjBeatgrid(
        library_item_id=li.id,
        bpm=128.0,
        first_downbeat_ms=320.0,
        confidence=0.9,
        canonical=True,
    )
    session.add(bg)
    await session.commit()
    assert bg.id is not None
    assert bg.canonical is True
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_audio_file.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/models/audio_file.py`**

```python
"""Audio file + beatgrid models.

Port of legacy ``app/db/models/library.py``. Drops DjCuePoint,
DjSavedLoop, DjBeatgridChangePoint per blueprint §13.2.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.v2.models.base import Base, TimestampMixin

class DjLibraryItem(Base, TimestampMixin):
    __tablename__ = "dj_library_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(1000))
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    file_size: Mapped[int] = mapped_column()
    mime_type: Mapped[str] = mapped_column(String(50))
    bitrate_kbps: Mapped[int | None] = mapped_column(nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(nullable=True)
    channels: Mapped[int | None] = mapped_column(nullable=True)
    source_app: Mapped[str | None] = mapped_column(String(100), nullable=True)

    beatgrids: Mapped[list["DjBeatgrid"]] = relationship(
        back_populates="library_item", cascade="all, delete-orphan"
    )

class DjBeatgrid(Base, TimestampMixin):
    __tablename__ = "dj_beatgrids"
    __table_args__ = (
        CheckConstraint("bpm BETWEEN 20 AND 300", name="ck_beatgrid_bpm_range"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_beatgrid_conf_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("dj_library_items.id", ondelete="CASCADE"), index=True
    )
    bpm: Mapped[float] = mapped_column()
    first_downbeat_ms: Mapped[float] = mapped_column()
    grid_offset_ms: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    canonical: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    source_app: Mapped[str | None] = mapped_column(String(100), nullable=True)

    library_item: Mapped[DjLibraryItem] = relationship(back_populates="beatgrids")
```

- [ ] **Step 4: Re-export**

Append imports + `__all__` entries.

- [ ] **Step 5: Run — expected PASS**

```bash
uv run pytest tests/v2/models/test_audio_file.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/models/audio_file.py app/v2/models/__init__.py tests/v2/models/test_audio_file.py
git commit -m "feat(v2): add DjLibraryItem + DjBeatgrid"
```

---

## Task 8: `models/track_features.py` (66 columns + sections + timeseries + runs)

**Files:**
- Create: `app/v2/models/track_features.py`
- Test: `tests/v2/models/test_track_features.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_track_features.py
"""Track features aggregate: TrackAudioFeaturesComputed + TrackSection +
TimeseriesReference + FeatureExtractionRun."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import Track
from app.v2.models.track_features import (
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)

@pytest.mark.asyncio
async def test_features_minimal(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    f = TrackAudioFeaturesComputed(track_id=t.id, bpm=128.0, key_code=5)
    session.add(f)
    await session.commit()
    loaded = await session.get(TrackAudioFeaturesComputed, t.id)
    assert loaded is not None
    assert loaded.bpm == 128.0

@pytest.mark.asyncio
async def test_features_bpm_range_constraint(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    f = TrackAudioFeaturesComputed(track_id=t.id, bpm=500.0)
    session.add(f)
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_analysis_level_constraint(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    f = TrackAudioFeaturesComputed(track_id=t.id, analysis_level=99)
    session.add(f)
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_section_type_range(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    sec = TrackSection(
        track_id=t.id, section_type=99, start_ms=0, end_ms=1000, energy=0.5
    )
    session.add(sec)
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_feature_run_status_constraint(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    run = FeatureExtractionRun(
        track_id=t.id, pipeline_name="v2", pipeline_version="1", status="bogus"
    )
    session.add(run)
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_timeseries_reference(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    ts = TimeseriesReference(
        track_id=t.id,
        feature_set="energy",
        storage_uri="cache/timeseries/1/energy.npz",
        frame_count=1200,
        hop_length=512,
        sample_rate=22050,
        dtype="float32",
        shape="[1200]",
    )
    session.add(ts)
    await session.commit()
    loaded = await session.get(TimeseriesReference, ts.id)
    assert loaded is not None
    assert loaded.frame_count == 1200
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_track_features.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/models/track_features.py`**

```python
"""Track audio features + sections + timeseries + extraction runs.

Port of legacy ``app/db/models/audio.py``. 66-column flat schema
preserved verbatim. Indexes on bpm / integrated_lufs / key_code / mood
for fast candidate filtering.
"""

from __future__ import annotations

from typing import Any, ClassVar

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.v2.models.base import Base, TimestampMixin

class FeatureExtractionRun(Base, TimestampMixin):
    __tablename__ = "feature_extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_fer_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    pipeline_name: Mapped[str] = mapped_column(String(100))
    pipeline_version: Mapped[str] = mapped_column(String(50))
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    computed_features: Mapped["TrackAudioFeaturesComputed | None"] = relationship(
        back_populates="pipeline_run"
    )

class TrackAudioFeaturesComputed(Base, TimestampMixin):
    __tablename__ = "track_audio_features_computed"
    __table_args__ = (
        CheckConstraint("bpm IS NULL OR bpm BETWEEN 20 AND 300", name="ck_features_bpm"),
        CheckConstraint(
            "key_code IS NULL OR key_code BETWEEN 0 AND 23", name="ck_features_key_code"
        ),
        CheckConstraint(
            "analysis_level BETWEEN 0 AND 5", name="ck_features_analysis_level"
        ),
    )

    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("feature_extraction_runs.id"), nullable=True, index=True
    )
    analysis_level: Mapped[int] = mapped_column(default=0, server_default="0")

    # Tempo (4)
    bpm: Mapped[float | None] = mapped_column(nullable=True, index=True)
    bpm_confidence: Mapped[float | None] = mapped_column(nullable=True)
    bpm_stability: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool | None] = mapped_column(nullable=True)

    # Loudness (7)
    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True, index=True)
    short_term_lufs_mean: Mapped[float | None] = mapped_column(nullable=True)
    momentary_max: Mapped[float | None] = mapped_column(nullable=True)
    rms_dbfs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak_db: Mapped[float | None] = mapped_column(nullable=True)
    crest_factor_db: Mapped[float | None] = mapped_column(nullable=True)
    loudness_range_lu: Mapped[float | None] = mapped_column(nullable=True)

    # Energy (16)
    energy_mean: Mapped[float | None] = mapped_column(nullable=True)
    energy_max: Mapped[float | None] = mapped_column(nullable=True)
    energy_std: Mapped[float | None] = mapped_column(nullable=True)
    energy_slope: Mapped[float | None] = mapped_column(nullable=True)
    energy_sub: Mapped[float | None] = mapped_column(nullable=True)
    energy_low: Mapped[float | None] = mapped_column(nullable=True)
    energy_lowmid: Mapped[float | None] = mapped_column(nullable=True)
    energy_mid: Mapped[float | None] = mapped_column(nullable=True)
    energy_highmid: Mapped[float | None] = mapped_column(nullable=True)
    energy_high: Mapped[float | None] = mapped_column(nullable=True)
    energy_sub_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_low_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_lowmid_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_mid_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_highmid_ratio: Mapped[float | None] = mapped_column(nullable=True)
    energy_high_ratio: Mapped[float | None] = mapped_column(nullable=True)

    # Spectral (8)
    spectral_centroid_hz: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_85: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_95: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flatness: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_mean: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_std: Mapped[float | None] = mapped_column(nullable=True)
    spectral_slope: Mapped[float | None] = mapped_column(nullable=True)
    spectral_contrast: Mapped[float | None] = mapped_column(nullable=True)

    # Key (5)
    key_code: Mapped[int | None] = mapped_column(nullable=True, index=True)
    key_confidence: Mapped[float | None] = mapped_column(nullable=True)
    atonality: Mapped[bool | None] = mapped_column(nullable=True)
    hnr_db: Mapped[float | None] = mapped_column(nullable=True)
    chroma_entropy: Mapped[float | None] = mapped_column(nullable=True)

    # Rhythm (5)
    mfcc_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hp_ratio: Mapped[float | None] = mapped_column(nullable=True)
    onset_rate: Mapped[float | None] = mapped_column(nullable=True)
    pulse_clarity: Mapped[float | None] = mapped_column(nullable=True)
    kick_prominence: Mapped[float | None] = mapped_column(nullable=True)

    # P1 (6)
    danceability: Mapped[float | None] = mapped_column(nullable=True)
    dynamic_complexity: Mapped[float | None] = mapped_column(nullable=True)
    dissonance_mean: Mapped[float | None] = mapped_column(nullable=True)
    tonnetz_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tempogram_ratio_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    beat_loudness_band_ratio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # P2 (7)
    spectral_complexity_mean: Mapped[float | None] = mapped_column(nullable=True)
    pitch_salience_mean: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_first_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    phrase_boundaries_ms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    dominant_phrase_bars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    first_downbeat_ms: Mapped[float | None] = mapped_column(nullable=True)

    # Classification
    mood: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    mood_confidence: Mapped[float | None] = mapped_column(nullable=True)

    pipeline_run: Mapped[FeatureExtractionRun | None] = relationship(
        back_populates="computed_features"
    )

    @classmethod
    def filter_features(cls, features: dict[str, Any]) -> dict[str, Any]:
        """Filter pipeline dict to only columns that exist on this model."""
        known = {c.name for c in cls.__table__.columns}
        return {k: v for k, v in features.items() if k in known}

class TrackSection(Base, TimestampMixin):
    __tablename__ = "track_sections"
    __table_args__ = (
        CheckConstraint(
            "section_type BETWEEN 0 AND 11", name="ck_section_type_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    section_type: Mapped[int] = mapped_column()
    start_ms: Mapped[int] = mapped_column()
    end_ms: Mapped[int] = mapped_column()
    energy: Mapped[float] = mapped_column()
    confidence: Mapped[float | None] = mapped_column(nullable=True)

class TimeseriesReference(Base, TimestampMixin):
    __tablename__ = "timeseries_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    feature_set: Mapped[str] = mapped_column(String(50))
    storage_uri: Mapped[str] = mapped_column(String(500))
    frame_count: Mapped[int] = mapped_column()
    hop_length: Mapped[int] = mapped_column()
    sample_rate: Mapped[int] = mapped_column()
    dtype: Mapped[str] = mapped_column(String(20))
    shape: Mapped[str] = mapped_column(String(100))
```

- [ ] **Step 4: Re-export + run — expected PASS**

Append imports + `__all__`.

```bash
uv run pytest tests/v2/models/test_track_features.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/models/track_features.py app/v2/models/__init__.py \
        tests/v2/models/test_track_features.py
git commit -m "feat(v2): add TrackAudioFeaturesComputed + sections + timeseries + runs

66-column flat schema preserved verbatim from legacy audio.py."
```

---

## Task 9: `models/transition.py` + `transition_history.py`

**Files:**
- Create: `app/v2/models/transition.py`
- Create: `app/v2/models/transition_history.py`
- Test: `tests/v2/models/test_transition.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_transition.py
"""Transition (persisted scored pair) + TransitionHistory (run log)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import Track
from app.v2.models.transition import Transition
from app.v2.models.transition_history import TransitionHistory

@pytest.mark.asyncio
async def test_transition_score_bounds(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    tr = Transition(
        from_track_id=t1.id, to_track_id=t2.id, overall_score=2.0
    )
    session.add(tr)
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_transition_happy_path(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    tr = Transition(
        from_track_id=t1.id,
        to_track_id=t2.id,
        bpm_distance=0.5,
        energy_step=1.0,
        groove_similarity=0.8,
        key_distance_weighted=0.1,
        overall_quality=0.75,
        overall_score=0.75,
    )
    session.add(tr)
    await session.commit()
    assert tr.id is not None

@pytest.mark.asyncio
async def test_transition_history_log(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    h = TransitionHistory(
        from_track_id=t1.id,
        to_track_id=t2.id,
        overall_score=0.78,
        style="bass_swap_short",
        reaction=None,
    )
    session.add(h)
    await session.commit()
    assert h.id is not None
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_transition.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/models/transition.py`**

```python
"""Transition — persisted scored pair. Drop TransitionCandidate per §13.2."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin

class Transition(Base, TimestampMixin):
    __tablename__ = "transitions"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 1",
            name="ck_transition_score_range",
        ),
        CheckConstraint(
            "overall_quality IS NULL OR overall_quality BETWEEN 0 AND 1",
            name="ck_transition_quality_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    to_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    from_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    to_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("track_sections.id", ondelete="SET NULL"), nullable=True
    )
    overlap_ms: Mapped[int | None] = mapped_column(nullable=True)

    bpm_distance: Mapped[float | None] = mapped_column(nullable=True)
    energy_step: Mapped[float | None] = mapped_column(nullable=True)
    centroid_gap_hz: Mapped[float | None] = mapped_column(nullable=True)
    low_conflict: Mapped[float | None] = mapped_column(nullable=True)
    overlap_score: Mapped[float | None] = mapped_column(nullable=True)
    groove_similarity: Mapped[float | None] = mapped_column(nullable=True)
    key_distance_weighted: Mapped[float | None] = mapped_column(nullable=True)
    overall_quality: Mapped[float | None] = mapped_column(nullable=True)
    overall_score: Mapped[float | None] = mapped_column(nullable=True, index=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

- [ ] **Step 4: Write `app/v2/models/transition_history.py`**

```python
"""TransitionHistory — append-only log of real DJ transitions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin

class TransitionHistory(Base, TimestampMixin):
    __tablename__ = "transition_history"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 0 AND 1",
            name="ck_history_score_range",
        ),
        CheckConstraint(
            "reaction IS NULL OR reaction IN ('positive', 'neutral', 'negative')",
            name="ck_history_reaction_enum",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    to_track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    set_id: Mapped[int | None] = mapped_column(
        ForeignKey("dj_sets.id", ondelete="SET NULL"), nullable=True
    )
    overall_score: Mapped[float | None] = mapped_column(nullable=True, index=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reaction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
```

- [ ] **Step 5: Re-export + run — expected PASS**

```bash
uv run pytest tests/v2/models/test_transition.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/models/transition.py app/v2/models/transition_history.py \
        app/v2/models/__init__.py tests/v2/models/test_transition.py
git commit -m "feat(v2): add Transition + TransitionHistory"
```

---

## Task 10: `models/track_feedback.py` + `track_affinity.py`

**Files:**
- Create: `app/v2/models/track_feedback.py`
- Create: `app/v2/models/track_affinity.py`
- Test: `tests/v2/models/test_track_feedback.py`, `test_track_affinity.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/models/test_track_feedback.py
"""TrackFeedback (like/ban/rate + notes)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import Track
from app.v2.models.track_feedback import TrackFeedback

@pytest.mark.asyncio
async def test_feedback_minimal(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, kind="like")
    session.add(fb)
    await session.commit()
    assert fb.id is not None

@pytest.mark.asyncio
async def test_feedback_kind_constraint(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, kind="bogus")
    session.add(fb)
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_feedback_rating_range(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    fb = TrackFeedback(track_id=t.id, kind="rate", rating=99)
    session.add(fb)
    with pytest.raises(IntegrityError):
        await session.commit()
```

```python
# tests/v2/models/test_track_affinity.py
"""TrackAffinity (aggregated pair stats from history)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import Track
from app.v2.models.track_affinity import TrackAffinity

@pytest.mark.asyncio
async def test_affinity_pair(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    a = TrackAffinity(
        track_a_id=t1.id,
        track_b_id=t2.id,
        play_count=3,
        positive_count=2,
        negative_count=0,
        avg_score=0.82,
    )
    session.add(a)
    await session.commit()
    assert a.id is not None
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_track_feedback.py tests/v2/models/test_track_affinity.py -v
```
Expected: `ModuleNotFoundError` on both.

- [ ] **Step 3: Write `app/v2/models/track_feedback.py`**

```python
"""Per-track feedback: like / ban / rate."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin

class TrackFeedback(Base, TimestampMixin):
    __tablename__ = "track_feedback"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('like', 'ban', 'rate')", name="ck_feedback_kind"
        ),
        CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5",
            name="ck_feedback_rating_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))
    rating: Mapped[int | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Write `app/v2/models/track_affinity.py`**

```python
"""TrackAffinity — aggregated A-B pair stats, computed from history."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin

class TrackAffinity(Base, TimestampMixin):
    __tablename__ = "track_affinity"
    __table_args__ = (
        UniqueConstraint("track_a_id", "track_b_id", name="uq_affinity_pair"),
        CheckConstraint(
            "avg_score IS NULL OR avg_score BETWEEN 0 AND 1",
            name="ck_affinity_score_range",
        ),
        CheckConstraint("play_count >= 0", name="ck_affinity_play_count_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_a_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    track_b_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    play_count: Mapped[int] = mapped_column(default=0, server_default="0")
    positive_count: Mapped[int] = mapped_column(default=0, server_default="0")
    negative_count: Mapped[int] = mapped_column(default=0, server_default="0")
    avg_score: Mapped[float | None] = mapped_column(nullable=True)
```

- [ ] **Step 5: Re-export + run — expected PASS**

```bash
uv run pytest tests/v2/models/test_track_feedback.py tests/v2/models/test_track_affinity.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/models/track_feedback.py app/v2/models/track_affinity.py \
        app/v2/models/__init__.py tests/v2/models/test_track_feedback.py \
        tests/v2/models/test_track_affinity.py
git commit -m "feat(v2): add TrackFeedback + TrackAffinity models"
```

---

## Task 11: `models/scoring_profile.py`

**Files:**
- Create: `app/v2/models/scoring_profile.py`
- Test: `tests/v2/models/test_scoring_profile.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/models/test_scoring_profile.py
"""ScoringProfile (custom transition-scorer weight sets)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.scoring_profile import ScoringProfile

@pytest.mark.asyncio
async def test_profile_weights_sum(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    p = ScoringProfile(
        name="melodic_priority",
        bpm_weight=0.15,
        harmonic_weight=0.25,
        energy_weight=0.15,
        spectral_weight=0.20,
        groove_weight=0.15,
        timbral_weight=0.10,
        description="more harmony weight for melodic sets",
    )
    session.add(p)
    await session.commit()
    assert p.id is not None

@pytest.mark.asyncio
async def test_profile_weight_range(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    p = ScoringProfile(
        name="bad",
        bpm_weight=2.0,
        harmonic_weight=0.1,
        energy_weight=0.1,
        spectral_weight=0.1,
        groove_weight=0.1,
        timbral_weight=0.1,
    )
    session.add(p)
    with pytest.raises(IntegrityError):
        await session.commit()
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/models/test_scoring_profile.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/models/scoring_profile.py`**

```python
"""Custom scoring weight profile."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.v2.models.base import Base, TimestampMixin

class ScoringProfile(Base, TimestampMixin):
    __tablename__ = "scoring_profiles"
    __table_args__ = (
        CheckConstraint("bpm_weight BETWEEN 0 AND 1", name="ck_profile_bpm"),
        CheckConstraint("harmonic_weight BETWEEN 0 AND 1", name="ck_profile_harm"),
        CheckConstraint("energy_weight BETWEEN 0 AND 1", name="ck_profile_energy"),
        CheckConstraint("spectral_weight BETWEEN 0 AND 1", name="ck_profile_spectral"),
        CheckConstraint("groove_weight BETWEEN 0 AND 1", name="ck_profile_groove"),
        CheckConstraint("timbral_weight BETWEEN 0 AND 1", name="ck_profile_timbral"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    bpm_weight: Mapped[float] = mapped_column()
    harmonic_weight: Mapped[float] = mapped_column()
    energy_weight: Mapped[float] = mapped_column()
    spectral_weight: Mapped[float] = mapped_column()
    groove_weight: Mapped[float] = mapped_column()
    timbral_weight: Mapped[float] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Re-export + run — expected PASS**

```bash
uv run pytest tests/v2/models/test_scoring_profile.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/models/scoring_profile.py app/v2/models/__init__.py \
        tests/v2/models/test_scoring_profile.py
git commit -m "feat(v2): add ScoringProfile model"
```

---

## Task 12: Full-metadata integration test + `__init__.py` final

**Files:**
- Test: `tests/v2/models/test_metadata_sanity.py`
- Modify: `app/v2/models/__init__.py` (final form)

- [ ] **Step 1: Finalize `app/v2/models/__init__.py`**

```python
"""v2 ORM models. One aggregate root per module."""

from app.v2.models.audio_file import DjBeatgrid, DjLibraryItem
from app.v2.models.base import Base, TimestampMixin
from app.v2.models.key import Key, KeyEdge
from app.v2.models.playlist import DjPlaylist, DjPlaylistItem
from app.v2.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)
from app.v2.models.scoring_profile import ScoringProfile
from app.v2.models.set import DjSet, DjSetItem, DjSetVersion
from app.v2.models.track import (
    Artist,
    Genre,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackRelease,
)
from app.v2.models.track_affinity import TrackAffinity
from app.v2.models.track_feedback import TrackFeedback
from app.v2.models.track_features import (
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from app.v2.models.transition import Transition
from app.v2.models.transition_history import TransitionHistory

__all__ = [
    "Base",
    "TimestampMixin",
    "Artist",
    "DjBeatgrid",
    "DjLibraryItem",
    "DjPlaylist",
    "DjPlaylistItem",
    "DjSet",
    "DjSetItem",
    "DjSetVersion",
    "FeatureExtractionRun",
    "Genre",
    "Key",
    "KeyEdge",
    "Provider",
    "RawProviderResponse",
    "Release",
    "ScoringProfile",
    "TimeseriesReference",
    "Track",
    "TrackAffinity",
    "TrackArtist",
    "TrackAudioFeaturesComputed",
    "TrackExternalId",
    "TrackFeedback",
    "TrackGenre",
    "TrackRelease",
    "TrackSection",
    "Transition",
    "TransitionHistory",
    "YandexMetadata",
]
```

- [ ] **Step 2: Write sanity test — all 31 tables create cleanly on one engine**

```python
# tests/v2/models/test_metadata_sanity.py
"""Full metadata sanity: create every table on a single engine."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.v2.models import Base

@pytest.mark.asyncio
async def test_create_all_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "keys",
        "key_edges",
        "providers",
        "yandex_metadata",
        "raw_provider_responses",
        "tracks",
        "artists",
        "genres",
        "releases",
        "track_artists",
        "track_genres",
        "track_releases",
        "track_external_ids",
        "dj_playlists",
        "dj_playlist_items",
        "dj_sets",
        "dj_set_versions",
        "dj_set_items",
        "dj_library_items",
        "dj_beatgrids",
        "feature_extraction_runs",
        "track_audio_features_computed",
        "track_sections",
        "timeseries_references",
        "transitions",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profiles",
    }
    assert expected.issubset(table_names), f"Missing: {expected - table_names}"

def test_no_dropped_tables_present() -> None:
    table_names = set(Base.metadata.tables.keys())
    dropped = {
        "spotify_metadata",
        "spotify_album_metadata",
        "spotify_artist_metadata",
        "spotify_playlist_metadata",
        "spotify_audio_features",
        "beatport_metadata",
        "soundcloud_metadata",
        "embeddings",
        "transition_candidates",
        "dj_saved_loops",
        "dj_cue_points",
        "dj_beatgrid_change_points",
        "dj_set_constraints",
        "dj_set_feedback",
        "labels",
        "track_labels",
        "app_exports",
    }
    overlap = dropped & table_names
    assert not overlap, f"Dropped tables still in metadata: {overlap}"
```

- [ ] **Step 3: Run — expected PASS**

```bash
uv run pytest tests/v2/models/test_metadata_sanity.py -v
```
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/models/__init__.py tests/v2/models/test_metadata_sanity.py
git commit -m "feat(v2): finalize models package + metadata sanity test

31 tables create cleanly on a single engine. 17 legacy tables (incl.
5 spotify_*, 3 dj_* unused, labels/track_labels, app_exports) are
confirmed absent from metadata."
```

---

## Task 13: `schemas/common.py` + `schemas/provider.py`

**Files:**
- Create: `app/v2/schemas/__init__.py`
- Create: `app/v2/schemas/common.py`
- Create: `app/v2/schemas/provider.py`
- Test: `tests/v2/schemas/test_common.py`

- [ ] **Step 1: Create skeleton + failing test**

```bash
mkdir -p app/v2/schemas tests/v2/schemas
printf '""""""' > app/v2/schemas/__init__.py
```

```python
# tests/v2/schemas/test_common.py
"""EntityListView + EntityAggregateView + EntityRef."""

from app.v2.schemas.common import EntityAggregateView, EntityListView, EntityRef

def test_entity_ref() -> None:
    r = EntityRef(entity="track", id=42)
    assert r.entity == "track"
    assert r.id == 42

def test_entity_list_view() -> None:
    v = EntityListView(
        items=[{"id": 1}, {"id": 2}],
        next_cursor="abc",
        total=2,
        preset="id",
        fields=["id"],
    )
    assert v.has_more is True
    assert len(v.items) == 2

def test_entity_list_view_no_more() -> None:
    v = EntityListView(items=[{"id": 1}], next_cursor=None, total=None, fields=["id"])
    assert v.has_more is False

def test_entity_aggregate_view_scalar() -> None:
    v = EntityAggregateView(operation="count", value=42)
    assert v.value == 42

def test_entity_aggregate_view_groups() -> None:
    v = EntityAggregateView(
        operation="group_by", groups={"peak_time": 120, "acid": 42}
    )
    assert v.groups == {"peak_time": 120, "acid": 42}
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/schemas/test_common.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/schemas/common.py`**

```python
"""Shared Pydantic DTOs used across tools + resources."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

class EntityRef(BaseModel):
    """Opaque reference to a registered entity."""

    model_config = ConfigDict(frozen=True)

    entity: str
    id: int

class EntityListView(BaseModel):
    """Generic paginated list response for ``entity_list``."""

    items: list[dict[str, Any]]
    next_cursor: str | None = None
    total: int | None = None
    preset: str | None = None
    fields: list[str] = Field(default_factory=list)

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None

class EntityAggregateView(BaseModel):
    """Generic aggregate response."""

    operation: Literal[
        "count", "distinct", "histogram", "min_max", "sum", "avg", "group_by"
    ]
    value: float | int | None = None
    distinct_values: list[Any] | None = None
    min: float | int | None = None
    max: float | int | None = None
    histogram: list[dict[str, Any]] | None = None
    groups: dict[str, int] | None = None
```

- [ ] **Step 4: Write `app/v2/schemas/provider.py`**

```python
"""Provider tool DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

class ProviderResultView(BaseModel):
    provider: str
    entity: str
    id: str | None = None
    data: dict[str, Any]

class ProviderSearchItem(BaseModel):
    id: str
    title: str | None = None
    artists: list[str] = []
    extra: dict[str, Any] = {}

class ProviderSearchView(BaseModel):
    provider: str
    query: str
    type: Literal["tracks", "albums", "artists", "playlists", "all"]
    results: list[ProviderSearchItem]
    total: int | None = None
```

- [ ] **Step 5: Run — expected PASS**

```bash
uv run pytest tests/v2/schemas/test_common.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/schemas tests/v2/schemas/test_common.py
git commit -m "feat(v2): add common + provider Pydantic schemas

EntityRef / EntityListView / EntityAggregateView drive entity_* tool
responses. ProviderResultView / ProviderSearchView drive provider_* tools."
```

---

## Task 14: `schemas/track.py` — 4 DTOs

**Files:**
- Create: `app/v2/schemas/track.py`
- Test: `tests/v2/schemas/test_track_schema.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/schemas/test_track_schema.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.schemas.track import TrackCreate, TrackFilter, TrackUpdate, TrackView

def test_track_view_minimal() -> None:
    v = TrackView(id=1, title="x")
    assert v.id == 1

def test_track_filter_django_lookups() -> None:
    f = TrackFilter(
        bpm__gte=120,
        bpm__lt=155,
        mood__in=["peak_time", "acid"],
        title__icontains="mix",
    )
    dumped = f.model_dump(exclude_unset=True)
    assert dumped["bpm__gte"] == 120
    assert dumped["mood__in"] == ["peak_time", "acid"]

def test_track_create_requires_title() -> None:
    with pytest.raises(ValidationError):
        TrackCreate()  # type: ignore[call-arg]

def test_track_update_all_optional() -> None:
    u = TrackUpdate()
    assert u.model_dump(exclude_unset=True) == {}
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/schemas/test_track_schema.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/schemas/track.py`**

```python
"""Track entity DTOs: View / Filter / Create / Update."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class TrackView(BaseModel):
    """Read projection — what clients see. Accepts ORM attr access."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    sort_title: str | None = None
    duration_ms: int | None = None
    status: int = 0
    primary_artist_name: str | None = None

class TrackFilter(BaseModel):
    """Django-lookup filter schema. Every field is optional."""

    model_config = ConfigDict(extra="forbid")

    id__in: list[int] | None = None
    id__eq: int | None = None
    title__icontains: str | None = None
    status__eq: int | None = None
    status__in: list[int] | None = None

    bpm__gte: float | None = None
    bpm__lte: float | None = None
    bpm__lt: float | None = None
    bpm__gt: float | None = None
    bpm__range: list[float] | None = None

    key_code__eq: int | None = None
    key_code__in: list[int] | None = None

    integrated_lufs__gte: float | None = None
    integrated_lufs__lte: float | None = None

    mood__eq: str | None = None
    mood__in: list[str] | None = None

    has_features__eq: bool | None = None

class TrackCreate(BaseModel):
    """Create payload (no custom handler → default INSERT; with handler → import from provider)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=500)
    sort_title: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: int = Field(default=0, ge=0, le=1)
    # Handler-driven import path:
    source: str | None = Field(default=None, description='e.g. "yandex_music"')
    provider_ids: list[str] | None = None

class TrackUpdate(BaseModel):
    """Partial update — only supplied fields are applied."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    sort_title: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: int | None = Field(default=None, ge=0, le=1)
```

- [ ] **Step 4: Run — expected PASS**

```bash
uv run pytest tests/v2/schemas/test_track_schema.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/schemas/track.py tests/v2/schemas/test_track_schema.py
git commit -m "feat(v2): add Track schemas (View/Filter/Create/Update)"
```

---

## Task 15: Schemas batch — playlist, set, audio_file, track_features, transition, transition_history, feedback, affinity, scoring_profile

**Files:**
- Create: 9 files in `app/v2/schemas/`
- Test: `tests/v2/schemas/test_pydantic_shapes.py`

Pattern repeats Task 14 for the remaining entities. Each module defines exactly four classes (`XxxView`, `XxxFilter`, `XxxCreate`, `XxxUpdate`) with `model_config = ConfigDict(extra="forbid")` on Filter/Create/Update and `from_attributes=True` on View.

- [ ] **Step 1: Write batch test**

```python
# tests/v2/schemas/test_pydantic_shapes.py
"""Smoke test that every entity's 4 DTOs exist and validate."""

from __future__ import annotations

import pytest

ENTITIES = [
    "track",
    "playlist",
    "set",
    "audio_file",
    "track_features",
    "transition",
    "transition_history",
    "track_feedback",
    "track_affinity",
    "scoring_profile",
]

@pytest.mark.parametrize("entity", ENTITIES)
def test_four_dtos_importable(entity: str) -> None:
    mod = __import__(f"app.v2.schemas.{entity}", fromlist=["*"])
    camel = "".join(p.capitalize() for p in entity.split("_"))
    # Accept either "Set" or the entity's own capitalized name.
    for suffix in ("View", "Filter", "Create", "Update"):
        assert hasattr(mod, f"{camel}{suffix}"), f"{entity} missing {camel}{suffix}"
```

- [ ] **Step 2: Write `app/v2/schemas/playlist.py`**

```python
"""Playlist DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class PlaylistView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    parent_id: int | None = None
    source_of_truth: str = "local"
    item_count: int | None = None

class PlaylistFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__in: list[int] | None = None
    name__icontains: str | None = None
    source_of_truth__eq: str | None = None
    parent_id__eq: int | None = None
    parent_id__isnull: bool | None = None

class PlaylistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=500)
    parent_id: int | None = None
    source_of_truth: str = "local"

class PlaylistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=500)
    parent_id: int | None = None
    source_of_truth: str | None = None
```

- [ ] **Step 3: Write `app/v2/schemas/set.py`**

```python
"""DJ set DTOs — covers DjSet + DjSetVersion via nested create helpers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

class SetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    target_duration_ms: int | None = None
    target_bpm_min: int | None = None
    target_bpm_max: int | None = None
    template_name: str | None = None
    source_playlist_id: int | None = None
    version_count: int | None = None

class SetFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__in: list[int] | None = None
    name__icontains: str | None = None
    template_name__eq: str | None = None
    source_playlist_id__eq: int | None = None

class SetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    target_duration_ms: int | None = Field(default=None, ge=60_000, le=12 * 3600_000)
    target_bpm_min: int | None = Field(default=None, ge=60, le=250)
    target_bpm_max: int | None = Field(default=None, ge=60, le=250)
    template_name: str | None = None
    source_playlist_id: int | None = None
    # Handler-driven build hint:
    algorithm: Literal["greedy", "ga"] | None = None

class SetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    target_duration_ms: int | None = None
    template_name: str | None = None

class SetVersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    set_id: int
    version_label: str
    quality_score: float | None = None
    generator_run_meta: dict[str, Any] | None = None

class SetVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: int
    version_label: str
    track_order: list[int]
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    generator_run_meta: dict[str, Any] | None = None
```

- [ ] **Step 4: Write `app/v2/schemas/audio_file.py`**

```python
"""Audio file DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class AudioFileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    file_path: str
    file_size: int
    bitrate_kbps: int | None = None
    sample_rate: int | None = None
    channels: int | None = None

class AudioFileFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__in: list[int] | None = None
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    file_path__icontains: str | None = None

class AudioFileCreate(BaseModel):
    """Single or batch download-and-register.

    Either ``track_id`` (one) or ``track_ids`` (batch) must be set.
    ``source`` picks the provider (e.g. ``"yandex_music"``).
    """

    model_config = ConfigDict(extra="forbid")
    track_id: int | None = None
    track_ids: list[int] | None = None
    source: str = Field(..., min_length=1)

class AudioFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str | None = None
    file_size: int | None = Field(default=None, ge=0)
```

- [ ] **Step 5: Write `app/v2/schemas/track_features.py`**

```python
"""Audio feature DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class TrackFeaturesView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    track_id: int
    analysis_level: int = 0
    bpm: float | None = None
    key_code: int | None = None
    integrated_lufs: float | None = None
    energy_mean: float | None = None
    spectral_centroid_hz: float | None = None
    hp_ratio: float | None = None
    kick_prominence: float | None = None
    mood: str | None = None
    mood_confidence: float | None = None

class TrackFeaturesFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id__in: list[int] | None = None
    analysis_level__gte: int | None = None
    analysis_level__lt: int | None = None
    bpm__gte: float | None = None
    bpm__lte: float | None = None
    mood__in: list[str] | None = None

class TrackFeaturesCreate(BaseModel):
    """Creation triggers the audio pipeline via custom handler."""

    model_config = ConfigDict(extra="forbid")
    track_id: int | None = None
    track_ids: list[int] | None = None
    level: int = Field(default=3, ge=1, le=5)

class TrackFeaturesUpdate(BaseModel):
    """Reanalyze with a higher level."""

    model_config = ConfigDict(extra="forbid")
    level: int = Field(..., ge=1, le=5)
```

- [ ] **Step 6: Write `app/v2/schemas/transition.py`**

```python
"""Transition DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class TransitionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    overall_score: float | None = None
    style: str | None = None

class TransitionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id__eq: int | None = None
    to_track_id__eq: int | None = None
    from_track_id__in: list[int] | None = None
    to_track_id__in: list[int] | None = None
    overall_score__gte: float | None = None

class TransitionCreate(BaseModel):
    """Create triggers compute-score-then-persist via custom handler."""

    model_config = ConfigDict(extra="forbid")
    from_track_id: int
    to_track_id: int
    persist: bool = True
    scoring_profile: str | None = None

class TransitionUpdate(BaseModel):
    """Overwrite style on an existing row (no rescoring)."""

    model_config = ConfigDict(extra="forbid")
    style: str | None = Field(default=None, min_length=1, max_length=50)
```

- [ ] **Step 7: Write `app/v2/schemas/transition_history.py`**

```python
"""TransitionHistory DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

class TransitionHistoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    set_id: int | None = None
    overall_score: float | None = None
    style: str | None = None
    reaction: Literal["positive", "neutral", "negative"] | None = None
    notes: str | None = None

class TransitionHistoryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id__eq: int | None = None
    to_track_id__eq: int | None = None
    reaction__eq: Literal["positive", "neutral", "negative"] | None = None
    overall_score__gte: float | None = None

class TransitionHistoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id: int
    to_track_id: int
    set_id: int | None = None
    overall_score: float | None = Field(default=None, ge=0.0, le=1.0)
    style: str | None = None
    reaction: Literal["positive", "neutral", "negative"] | None = None
    notes: str | None = None

class TransitionHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaction: Literal["positive", "neutral", "negative"] | None = None
    notes: str | None = None
```

- [ ] **Step 8: Write `app/v2/schemas/track_feedback.py`**

```python
"""TrackFeedback DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

class TrackFeedbackView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_id: int
    kind: Literal["like", "ban", "rate"]
    rating: int | None = None
    notes: str | None = None

class TrackFeedbackFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    kind__eq: Literal["like", "ban", "rate"] | None = None

class TrackFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    kind: Literal["like", "ban", "rate"]
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None

class TrackFeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
```

- [ ] **Step 9: Write `app/v2/schemas/track_affinity.py`**

```python
"""TrackAffinity DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class TrackAffinityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    track_a_id: int
    track_b_id: int
    play_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    avg_score: float | None = None

class TrackAffinityFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_a_id__eq: int | None = None
    track_b_id__eq: int | None = None
    avg_score__gte: float | None = None

class TrackAffinityCreate(BaseModel):
    """Explicit creation rare — usually derived via ``refresh`` handler."""

    model_config = ConfigDict(extra="forbid")
    track_a_id: int
    track_b_id: int
    avg_score: float | None = Field(default=None, ge=0.0, le=1.0)

class TrackAffinityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avg_score: float | None = Field(default=None, ge=0.0, le=1.0)
    play_count: int | None = Field(default=None, ge=0)
```

- [ ] **Step 10: Write `app/v2/schemas/scoring_profile.py`**

```python
"""ScoringProfile DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class ScoringProfileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    bpm_weight: float
    harmonic_weight: float
    energy_weight: float
    spectral_weight: float
    groove_weight: float
    timbral_weight: float
    description: str | None = None

class ScoringProfileFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name__eq: str | None = None
    name__icontains: str | None = None

class ScoringProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    bpm_weight: float = Field(..., ge=0.0, le=1.0)
    harmonic_weight: float = Field(..., ge=0.0, le=1.0)
    energy_weight: float = Field(..., ge=0.0, le=1.0)
    spectral_weight: float = Field(..., ge=0.0, le=1.0)
    groove_weight: float = Field(..., ge=0.0, le=1.0)
    timbral_weight: float = Field(..., ge=0.0, le=1.0)
    description: str | None = None

class ScoringProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bpm_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    harmonic_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    energy_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    spectral_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    groove_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    timbral_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    description: str | None = None
```

- [ ] **Step 11: Run — expected PASS**

```bash
uv run pytest tests/v2/schemas/test_pydantic_shapes.py -v
```
Expected: 10 parameterized passes.

- [ ] **Step 12: Commit**

```bash
git add app/v2/schemas tests/v2/schemas/test_pydantic_shapes.py
git commit -m "feat(v2): add 9 entity schema families

playlist, set (+ set_version), audio_file, track_features, transition,
transition_history, track_feedback, track_affinity, scoring_profile —
4 DTOs each (View / Filter / Create / Update). Total 40 Pydantic classes."
```

---

## Task 16: `repositories/track.py`

**Files:**
- Create: `app/v2/repositories/track.py`
- Test: `tests/v2/repositories/test_track_repo.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/repositories/test_track_repo.py
"""TrackRepository domain methods."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models import Base, Track, TrackExternalId
from app.v2.repositories.track import TrackRepository

@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return TrackRepository(session)

@pytest.mark.asyncio
async def test_inherited_crud(repo: TrackRepository) -> None:
    t = await repo.create(title="hello")
    assert t.id is not None
    fetched = await repo.get(t.id)
    assert fetched is not None
    assert fetched.title == "hello"

@pytest.mark.asyncio
async def test_get_provider_id(repo: TrackRepository, session: AsyncSession) -> None:
    t = await repo.create(title="x")
    session.add(
        TrackExternalId(track_id=t.id, provider_code="yandex_music", external_id="12345")
    )
    await session.flush()
    pid = await repo.get_provider_id(t.id, "yandex_music")
    assert pid == "12345"

@pytest.mark.asyncio
async def test_get_provider_id_missing(repo: TrackRepository) -> None:
    t = await repo.create(title="x")
    assert await repo.get_provider_id(t.id, "yandex_music") is None

@pytest.mark.asyncio
async def test_batch_get_by_provider_ids(
    repo: TrackRepository, session: AsyncSession
) -> None:
    t1 = await repo.create(title="a")
    t2 = await repo.create(title="b")
    session.add_all(
        [
            TrackExternalId(track_id=t1.id, provider_code="yandex_music", external_id="A1"),
            TrackExternalId(track_id=t2.id, provider_code="yandex_music", external_id="B2"),
        ]
    )
    await session.flush()
    found = await repo.batch_get_by_provider_ids("yandex_music", ["A1", "B2", "missing"])
    assert set(found.keys()) == {"A1", "B2"}
    assert found["A1"].id == t1.id

@pytest.mark.asyncio
async def test_get_unanalyzed_stub(repo: TrackRepository) -> None:
    ids = await repo.get_unanalyzed(level=3, limit=10)
    assert ids == []  # no features rows yet
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/repositories/test_track_repo.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/repositories/track.py`**

```python
"""Track repository — inherits BaseRepository CRUD + 4 domain methods."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.track import Track, TrackExternalId
from app.v2.models.track_features import TrackAudioFeaturesComputed
from app.v2.repositories.base import BaseRepository

class TrackRepository(BaseRepository[Track]):
    model = Track

    async def get_provider_id(self, track_id: int, provider_code: str) -> str | None:
        """Return ``external_id`` for ``track_id`` on ``provider_code`` or None."""
        stmt = select(TrackExternalId.external_id).where(
            TrackExternalId.track_id == track_id,
            TrackExternalId.provider_code == provider_code,
        )
        return await self.session.scalar(stmt)

    async def batch_get_by_provider_ids(
        self, provider_code: str, external_ids: list[str]
    ) -> dict[str, Track]:
        """Resolve many ``external_id`` values → Track instances in one query."""
        if not external_ids:
            return {}
        stmt = (
            select(TrackExternalId.external_id, Track)
            .join(Track, Track.id == TrackExternalId.track_id)
            .where(
                TrackExternalId.provider_code == provider_code,
                TrackExternalId.external_id.in_(external_ids),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return {ext_id: track for ext_id, track in rows}

    async def get_unanalyzed(self, level: int, limit: int = 100) -> list[int]:
        """Return track IDs whose analysis_level < ``level`` (or no features row)."""
        stmt = (
            select(Track.id)
            .outerjoin(TrackAudioFeaturesComputed, TrackAudioFeaturesComputed.track_id == Track.id)
            .where(
                (TrackAudioFeaturesComputed.track_id.is_(None))
                | (TrackAudioFeaturesComputed.analysis_level < level)
            )
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def ensure_external_id(
        self, track_id: int, provider_code: str, external_id: str
    ) -> TrackExternalId:
        """Upsert one (track_id, provider_code, external_id) mapping."""
        existing = await self.session.scalar(
            select(TrackExternalId).where(
                TrackExternalId.track_id == track_id,
                TrackExternalId.provider_code == provider_code,
            )
        )
        if existing is not None:
            if existing.external_id != external_id:
                existing.external_id = external_id
                await self.session.flush()
            return existing
        row = TrackExternalId(
            track_id=track_id, provider_code=provider_code, external_id=external_id
        )
        self.session.add(row)
        await self.session.flush()
        return row
```

- [ ] **Step 4: Run — expected PASS**

```bash
uv run pytest tests/v2/repositories/test_track_repo.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/repositories/track.py tests/v2/repositories/test_track_repo.py
git commit -m "feat(v2): add TrackRepository

CRUD inherited + get_provider_id / batch_get_by_provider_ids /
get_unanalyzed / ensure_external_id."
```

---

## Task 17: `repositories/track_features.py`

**Files:**
- Create: `app/v2/repositories/track_features.py`
- Test: `tests/v2/repositories/test_track_features_repo.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/repositories/test_track_features_repo.py
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models import Base, Track, TrackAudioFeaturesComputed
from app.v2.repositories.track_features import TrackFeaturesRepository

@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackFeaturesRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return TrackFeaturesRepository(session)

@pytest.mark.asyncio
async def test_get_scoring_features_batch(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    t1, t2, t3 = Track(title="a"), Track(title="b"), Track(title="c")
    session.add_all([t1, t2, t3])
    await session.flush()
    session.add_all(
        [
            TrackAudioFeaturesComputed(track_id=t1.id, bpm=128.0, analysis_level=3),
            TrackAudioFeaturesComputed(track_id=t2.id, bpm=130.0, analysis_level=3),
        ]
    )
    await session.flush()
    result = await repo.get_scoring_features_batch([t1.id, t2.id, t3.id])
    assert set(result.keys()) == {t1.id, t2.id}
    assert result[t1.id].bpm == 128.0

@pytest.mark.asyncio
async def test_set_mood(repo: TrackFeaturesRepository, session: AsyncSession) -> None:
    t = Track(title="a")
    session.add(t)
    await session.flush()
    session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=128.0))
    await session.flush()
    await repo.set_mood(t.id, mood="peak_time", confidence=0.82)
    row = await session.get(TrackAudioFeaturesComputed, t.id)
    assert row is not None
    assert row.mood == "peak_time"
    assert row.mood_confidence == 0.82
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/repositories/test_track_features_repo.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/repositories/track_features.py`**

```python
"""Track features repository — batch load for scoring + targeted mood writes."""

from __future__ import annotations

from sqlalchemy import select, update

from app.v2.models.track_features import TrackAudioFeaturesComputed
from app.v2.repositories.base import BaseRepository
from app.v2.shared.errors import NotFoundError

class TrackFeaturesRepository(BaseRepository[TrackAudioFeaturesComputed]):
    model = TrackAudioFeaturesComputed

    async def get_scoring_features_batch(
        self, track_ids: list[int]
    ) -> dict[int, TrackAudioFeaturesComputed]:
        """One SQL for N tracks; missing rows are silently omitted."""
        if not track_ids:
            return {}
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {r.track_id: r for r in rows}

    async def set_mood(self, track_id: int, *, mood: str, confidence: float) -> None:
        """Update mood + confidence on an existing features row."""
        stmt = (
            update(TrackAudioFeaturesComputed)
            .where(TrackAudioFeaturesComputed.track_id == track_id)
            .values(mood=mood, mood_confidence=confidence)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundError("track_features", track_id)
        await self.session.flush()

    async def get_analysis_level(self, track_id: int) -> int:
        """Return current analysis_level (0 if no row)."""
        stmt = select(TrackAudioFeaturesComputed.analysis_level).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        row = await self.session.scalar(stmt)
        return int(row) if row is not None else 0
```

- [ ] **Step 4: Run — expected PASS**

```bash
uv run pytest tests/v2/repositories/test_track_features_repo.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/repositories/track_features.py \
        tests/v2/repositories/test_track_features_repo.py
git commit -m "feat(v2): add TrackFeaturesRepository

Batch scoring load + set_mood + get_analysis_level domain methods."
```

---

## Task 18: Remaining repositories (playlist, set, audio_file, transition, transition_history, track_feedback, track_affinity, scoring_profile, provider_metadata, key)

**Files:**
- Create 10 files in `app/v2/repositories/`
- Test: `tests/v2/repositories/test_misc_repos.py`

Each repository is a thin subclass: `class XxxRepository(BaseRepository[Xxx]): model = Xxx` + 1-3 domain methods. Keep each under 60 LOC.

- [ ] **Step 1: Write `app/v2/repositories/playlist.py`**

```python
"""Playlist repository."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.v2.models.playlist import DjPlaylist, DjPlaylistItem
from app.v2.repositories.base import BaseRepository

class PlaylistRepository(BaseRepository[DjPlaylist]):
    model = DjPlaylist

    async def get_track_ids(self, playlist_id: int) -> list[int]:
        stmt = (
            select(DjPlaylistItem.track_id)
            .where(DjPlaylistItem.playlist_id == playlist_id)
            .order_by(DjPlaylistItem.sort_index)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def append_tracks(self, playlist_id: int, track_ids: list[int]) -> int:
        """Append tracks; returns new item count. Idempotent on duplicates."""
        start = await self.session.scalar(
            select(func.coalesce(func.max(DjPlaylistItem.sort_index), -1)).where(
                DjPlaylistItem.playlist_id == playlist_id
            )
        ) or -1
        items = [
            DjPlaylistItem(
                playlist_id=playlist_id, track_id=tid, sort_index=start + 1 + i
            )
            for i, tid in enumerate(track_ids)
        ]
        self.session.add_all(items)
        await self.session.flush()
        return len(items)

    async def remove_track(self, playlist_id: int, track_id: int) -> int:
        stmt = delete(DjPlaylistItem).where(
            DjPlaylistItem.playlist_id == playlist_id,
            DjPlaylistItem.track_id == track_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0
```

- [ ] **Step 2: Write `app/v2/repositories/set.py`**

```python
"""Set repository + set-version helpers."""

from __future__ import annotations

from sqlalchemy import func, select

from app.v2.models.set import DjSet, DjSetItem, DjSetVersion
from app.v2.repositories.base import BaseRepository

class SetRepository(BaseRepository[DjSet]):
    model = DjSet

    async def version_count(self, set_id: int) -> int:
        stmt = select(func.count()).select_from(DjSetVersion).where(
            DjSetVersion.set_id == set_id
        )
        return int(await self.session.scalar(stmt) or 0)

    async def latest_version(self, set_id: int) -> DjSetVersion | None:
        stmt = (
            select(DjSetVersion)
            .where(DjSetVersion.set_id == set_id)
            .order_by(DjSetVersion.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

class SetVersionRepository(BaseRepository[DjSetVersion]):
    model = DjSetVersion

    async def get_items(self, version_id: int) -> list[DjSetItem]:
        stmt = (
            select(DjSetItem)
            .where(DjSetItem.set_version_id == version_id)
            .order_by(DjSetItem.sort_index)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def create_items(
        self, version_id: int, track_order: list[int]
    ) -> int:
        items = [
            DjSetItem(set_version_id=version_id, track_id=tid, sort_index=i)
            for i, tid in enumerate(track_order)
        ]
        self.session.add_all(items)
        await self.session.flush()
        return len(items)
```

- [ ] **Step 3: Write `app/v2/repositories/audio_file.py`**

```python
"""Audio file repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.audio_file import DjBeatgrid, DjLibraryItem
from app.v2.repositories.base import BaseRepository

class AudioFileRepository(BaseRepository[DjLibraryItem]):
    model = DjLibraryItem

    async def get_for_track(self, track_id: int) -> DjLibraryItem | None:
        stmt = select(DjLibraryItem).where(DjLibraryItem.track_id == track_id).limit(1)
        return await self.session.scalar(stmt)

    async def register_beatgrid(
        self,
        library_item_id: int,
        *,
        bpm: float,
        first_downbeat_ms: float,
        canonical: bool = True,
    ) -> DjBeatgrid:
        bg = DjBeatgrid(
            library_item_id=library_item_id,
            bpm=bpm,
            first_downbeat_ms=first_downbeat_ms,
            canonical=canonical,
        )
        self.session.add(bg)
        await self.session.flush()
        return bg
```

- [ ] **Step 4: Write `app/v2/repositories/transition.py`**

```python
"""Transition repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.transition import Transition
from app.v2.repositories.base import BaseRepository

class TransitionRepository(BaseRepository[Transition]):
    model = Transition

    async def get_pair(
        self, from_track_id: int, to_track_id: int
    ) -> Transition | None:
        stmt = (
            select(Transition)
            .where(
                Transition.from_track_id == from_track_id,
                Transition.to_track_id == to_track_id,
            )
            .order_by(Transition.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)
```

- [ ] **Step 5: Write `app/v2/repositories/transition_history.py`**

```python
"""TransitionHistory repository."""

from __future__ import annotations

from sqlalchemy import desc, func, select

from app.v2.models.transition_history import TransitionHistory
from app.v2.repositories.base import BaseRepository

class TransitionHistoryRepository(BaseRepository[TransitionHistory]):
    model = TransitionHistory

    async def best_pairs(self, limit: int = 20) -> list[TransitionHistory]:
        stmt = (
            select(TransitionHistory)
            .order_by(desc(TransitionHistory.overall_score))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def reaction_counts(self) -> dict[str, int]:
        stmt = (
            select(TransitionHistory.reaction, func.count())
            .group_by(TransitionHistory.reaction)
        )
        return {r or "none": n for r, n in (await self.session.execute(stmt)).all()}
```

- [ ] **Step 6: Write `app/v2/repositories/track_feedback.py`**

```python
"""TrackFeedback repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.track_feedback import TrackFeedback
from app.v2.repositories.base import BaseRepository

class TrackFeedbackRepository(BaseRepository[TrackFeedback]):
    model = TrackFeedback

    async def list_by_kind(self, kind: str, limit: int = 100) -> list[TrackFeedback]:
        stmt = select(TrackFeedback).where(TrackFeedback.kind == kind).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def latest_for_track(self, track_id: int) -> TrackFeedback | None:
        stmt = (
            select(TrackFeedback)
            .where(TrackFeedback.track_id == track_id)
            .order_by(TrackFeedback.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)
```

- [ ] **Step 7: Write `app/v2/repositories/track_affinity.py`**

```python
"""TrackAffinity repository."""

from __future__ import annotations

from sqlalchemy import desc, select

from app.v2.models.track_affinity import TrackAffinity
from app.v2.repositories.base import BaseRepository

class TrackAffinityRepository(BaseRepository[TrackAffinity]):
    model = TrackAffinity

    async def get_pair(
        self, track_a_id: int, track_b_id: int
    ) -> TrackAffinity | None:
        stmt = select(TrackAffinity).where(
            TrackAffinity.track_a_id == track_a_id,
            TrackAffinity.track_b_id == track_b_id,
        )
        return await self.session.scalar(stmt)

    async def recommend(
        self, track_id: int, limit: int = 10
    ) -> list[TrackAffinity]:
        stmt = (
            select(TrackAffinity)
            .where(
                (TrackAffinity.track_a_id == track_id)
                | (TrackAffinity.track_b_id == track_id)
            )
            .order_by(desc(TrackAffinity.avg_score))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())
```

- [ ] **Step 8: Write `app/v2/repositories/scoring_profile.py`, `provider_metadata.py`, `key.py`**

```python
# app/v2/repositories/scoring_profile.py
"""ScoringProfile repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.scoring_profile import ScoringProfile
from app.v2.repositories.base import BaseRepository

class ScoringProfileRepository(BaseRepository[ScoringProfile]):
    model = ScoringProfile

    async def get_by_name(self, name: str) -> ScoringProfile | None:
        stmt = select(ScoringProfile).where(ScoringProfile.name == name).limit(1)
        return await self.session.scalar(stmt)
```

```python
# app/v2/repositories/provider_metadata.py
"""Provider + YandexMetadata + RawProviderResponse repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.provider_metadata import (
    Provider,
    RawProviderResponse,
    YandexMetadata,
)
from app.v2.repositories.base import BaseRepository

class ProviderMetadataRepository(BaseRepository[Provider]):
    model = Provider

    async def get_by_code(self, code: str) -> Provider | None:
        return await self.session.scalar(
            select(Provider).where(Provider.code == code).limit(1)
        )

class YandexMetadataRepository(BaseRepository[YandexMetadata]):
    model = YandexMetadata

    async def get_for_track(self, track_id: int) -> YandexMetadata | None:
        return await self.session.get(YandexMetadata, track_id)

class RawProviderResponseRepository(BaseRepository[RawProviderResponse]):
    model = RawProviderResponse
```

```python
# app/v2/repositories/key.py
"""Key reference repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.key import Key, KeyEdge
from app.v2.repositories.base import BaseRepository

class KeyRepository(BaseRepository[Key]):
    model = Key

    async def get_by_camelot(self, camelot: str) -> Key | None:
        return await self.session.scalar(
            select(Key).where(Key.camelot == camelot).limit(1)
        )

class KeyEdgeRepository(BaseRepository[KeyEdge]):
    model = KeyEdge

    async def edges_from(self, from_key: int) -> list[KeyEdge]:
        stmt = select(KeyEdge).where(KeyEdge.from_key == from_key).order_by(KeyEdge.distance)
        return list((await self.session.execute(stmt)).scalars())
```

- [ ] **Step 9: Write batch test `tests/v2/repositories/test_misc_repos.py`**

```python
"""Smoke-test every non-track repository: CRUD on its primary model."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models import Base, Track
from app.v2.repositories.audio_file import AudioFileRepository
from app.v2.repositories.key import KeyEdgeRepository, KeyRepository
from app.v2.repositories.playlist import PlaylistRepository
from app.v2.repositories.provider_metadata import (
    ProviderMetadataRepository,
    YandexMetadataRepository,
)
from app.v2.repositories.scoring_profile import ScoringProfileRepository
from app.v2.repositories.set import SetRepository, SetVersionRepository
from app.v2.repositories.track_affinity import TrackAffinityRepository
from app.v2.repositories.track_feedback import TrackFeedbackRepository
from app.v2.repositories.transition import TransitionRepository
from app.v2.repositories.transition_history import TransitionHistoryRepository

@pytest_asyncio.fixture
async def setup(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@pytest.mark.asyncio
async def test_playlist_append_and_get_ids(
    setup: None, session: AsyncSession
) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = PlaylistRepository(session)
    pl = await repo.create(name="P")
    added = await repo.append_tracks(pl.id, [t.id])
    assert added == 1
    ids = await repo.get_track_ids(pl.id)
    assert ids == [t.id]

@pytest.mark.asyncio
async def test_set_version_roundtrip(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    set_repo = SetRepository(session)
    sv_repo = SetVersionRepository(session)
    s = await set_repo.create(name="set")
    v = await sv_repo.create(set_id=s.id, version_label="v1", quality_score=0.7)
    n = await sv_repo.create_items(v.id, [t1.id, t2.id])
    assert n == 2
    items = await sv_repo.get_items(v.id)
    assert [i.track_id for i in items] == [t1.id, t2.id]

@pytest.mark.asyncio
async def test_audio_file_and_beatgrid(setup: None, session: AsyncSession) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = AudioFileRepository(session)
    f = await repo.create(
        track_id=t.id, file_path="/a.mp3", file_size=1, mime_type="audio/mpeg"
    )
    bg = await repo.register_beatgrid(
        f.id, bpm=128.0, first_downbeat_ms=320.0, canonical=True
    )
    assert bg.id is not None

@pytest.mark.asyncio
async def test_transition_pair(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    repo = TransitionRepository(session)
    await repo.create(
        from_track_id=t1.id, to_track_id=t2.id, overall_score=0.8
    )
    tr = await repo.get_pair(t1.id, t2.id)
    assert tr is not None
    assert tr.overall_score == 0.8

@pytest.mark.asyncio
async def test_history_best_pairs(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    repo = TransitionHistoryRepository(session)
    await repo.create(
        from_track_id=t1.id, to_track_id=t2.id, overall_score=0.9
    )
    rows = await repo.best_pairs(limit=5)
    assert len(rows) == 1

@pytest.mark.asyncio
async def test_feedback_list(setup: None, session: AsyncSession) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = TrackFeedbackRepository(session)
    await repo.create(track_id=t.id, kind="like")
    rows = await repo.list_by_kind("like")
    assert len(rows) == 1

@pytest.mark.asyncio
async def test_affinity_recommend(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    repo = TrackAffinityRepository(session)
    await repo.create(track_a_id=t1.id, track_b_id=t2.id, avg_score=0.75)
    recs = await repo.recommend(t1.id, limit=5)
    assert len(recs) == 1

@pytest.mark.asyncio
async def test_scoring_profile_by_name(setup: None, session: AsyncSession) -> None:
    repo = ScoringProfileRepository(session)
    await repo.create(
        name="x",
        bpm_weight=0.2,
        harmonic_weight=0.15,
        energy_weight=0.15,
        spectral_weight=0.2,
        groove_weight=0.15,
        timbral_weight=0.15,
    )
    found = await repo.get_by_name("x")
    assert found is not None

@pytest.mark.asyncio
async def test_provider_metadata_lookup(
    setup: None, session: AsyncSession
) -> None:
    repo = ProviderMetadataRepository(session)
    await repo.create(code="yandex_music", display_name="Yandex Music")
    p = await repo.get_by_code("yandex_music")
    assert p is not None

@pytest.mark.asyncio
async def test_yandex_metadata_lookup(
    setup: None, session: AsyncSession
) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = YandexMetadataRepository(session)
    await repo.create(track_id=t.id, yandex_track_id="12345")
    row = await repo.get_for_track(t.id)
    assert row is not None

@pytest.mark.asyncio
async def test_key_by_camelot(setup: None, session: AsyncSession) -> None:
    repo = KeyRepository(session)
    await repo.create(
        key_code=0, pitch_class=0, mode=0, name="C minor", camelot="5A"
    )
    k = await repo.get_by_camelot("5A")
    assert k is not None

    edges = KeyEdgeRepository(session)
    assert await edges.edges_from(0) == []
```

- [ ] **Step 10: Run — expected PASS**

```bash
uv run pytest tests/v2/repositories/test_misc_repos.py -v
```
Expected: 11 passed.

- [ ] **Step 11: Commit**

```bash
git add app/v2/repositories tests/v2/repositories/test_misc_repos.py
git commit -m "feat(v2): add 10 remaining repositories

playlist / set / set_version / audio_file / transition /
transition_history / track_feedback / track_affinity / scoring_profile /
provider_metadata (3 repos) / key (2 repos). Each inherits BaseRepository
CRUD and adds 1-3 domain methods."
```

---

## Task 19: Extend `UnitOfWork` with lazy repo properties

**Files:**
- Modify: `app/v2/repositories/unit_of_work.py`
- Test: `tests/v2/repositories/test_uow_repos.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/repositories/test_uow_repos.py
"""UoW exposes all 14 repos as lazy properties."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.v2.models import Base, Track
from app.v2.repositories.track import TrackRepository
from app.v2.repositories.unit_of_work import UnitOfWork

@pytest_asyncio.fixture
async def factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)

@pytest.mark.asyncio
async def test_uow_tracks_attr_is_repo(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as s:
        async with UnitOfWork(s) as uow:
            assert isinstance(uow.tracks, TrackRepository)
            t = await uow.tracks.create(title="hi")
            assert t.id is not None

@pytest.mark.asyncio
async def test_uow_all_repos_present(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as s:
        async with UnitOfWork(s) as uow:
            for attr in (
                "tracks",
                "playlists",
                "sets",
                "set_versions",
                "audio_files",
                "track_features",
                "transitions",
                "transition_history",
                "track_feedback",
                "track_affinity",
                "scoring_profiles",
                "provider_metadata",
                "yandex_metadata",
                "keys",
            ):
                assert hasattr(uow, attr), f"UoW missing {attr}"

@pytest.mark.asyncio
async def test_uow_repo_cached(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as s:
        async with UnitOfWork(s) as uow:
            assert uow.tracks is uow.tracks  # same instance
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/repositories/test_uow_repos.py -v
```
Expected: `AttributeError: UnitOfWork has no attribute 'tracks'`.

- [ ] **Step 3: Extend `app/v2/repositories/unit_of_work.py`**

```python
"""Unit of Work — transaction boundary = tool call.

Phase 2: adds lazy ``@property`` accessors for every registered entity.
Each property caches the repository instance so calls like
``uow.tracks`` return the same object within one UoW lifetime.
"""

from __future__ import annotations

from functools import cached_property
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.v2.repositories.audio_file import AudioFileRepository
from app.v2.repositories.key import KeyEdgeRepository, KeyRepository
from app.v2.repositories.playlist import PlaylistRepository
from app.v2.repositories.provider_metadata import (
    ProviderMetadataRepository,
    RawProviderResponseRepository,
    YandexMetadataRepository,
)
from app.v2.repositories.scoring_profile import ScoringProfileRepository
from app.v2.repositories.set import SetRepository, SetVersionRepository
from app.v2.repositories.track import TrackRepository
from app.v2.repositories.track_affinity import TrackAffinityRepository
from app.v2.repositories.track_feedback import TrackFeedbackRepository
from app.v2.repositories.track_features import TrackFeaturesRepository
from app.v2.repositories.transition import TransitionRepository
from app.v2.repositories.transition_history import TransitionHistoryRepository

class UnitOfWork:
    """Commit on success, rollback on exception."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is None:
            await self.session.commit()
        else:
            await self.session.rollback()

    # ── lazy repository properties ────────────────────

    @cached_property
    def tracks(self) -> TrackRepository:
        return TrackRepository(self.session)

    @cached_property
    def playlists(self) -> PlaylistRepository:
        return PlaylistRepository(self.session)

    @cached_property
    def sets(self) -> SetRepository:
        return SetRepository(self.session)

    @cached_property
    def set_versions(self) -> SetVersionRepository:
        return SetVersionRepository(self.session)

    @cached_property
    def audio_files(self) -> AudioFileRepository:
        return AudioFileRepository(self.session)

    @cached_property
    def track_features(self) -> TrackFeaturesRepository:
        return TrackFeaturesRepository(self.session)

    @cached_property
    def transitions(self) -> TransitionRepository:
        return TransitionRepository(self.session)

    @cached_property
    def transition_history(self) -> TransitionHistoryRepository:
        return TransitionHistoryRepository(self.session)

    @cached_property
    def track_feedback(self) -> TrackFeedbackRepository:
        return TrackFeedbackRepository(self.session)

    @cached_property
    def track_affinity(self) -> TrackAffinityRepository:
        return TrackAffinityRepository(self.session)

    @cached_property
    def scoring_profiles(self) -> ScoringProfileRepository:
        return ScoringProfileRepository(self.session)

    @cached_property
    def provider_metadata(self) -> ProviderMetadataRepository:
        return ProviderMetadataRepository(self.session)

    @cached_property
    def yandex_metadata(self) -> YandexMetadataRepository:
        return YandexMetadataRepository(self.session)

    @cached_property
    def raw_provider_responses(self) -> RawProviderResponseRepository:
        return RawProviderResponseRepository(self.session)

    @cached_property
    def keys(self) -> KeyRepository:
        return KeyRepository(self.session)

    @cached_property
    def key_edges(self) -> KeyEdgeRepository:
        return KeyEdgeRepository(self.session)
```

- [ ] **Step 4: Run — expected PASS**

```bash
uv run pytest tests/v2/repositories/test_uow_repos.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/repositories/unit_of_work.py tests/v2/repositories/test_uow_repos.py
git commit -m "feat(v2): expand UnitOfWork with 16 lazy repo properties

uow.tracks / .playlists / .sets / .set_versions / .audio_files /
.track_features / .transitions / .transition_history /
.track_feedback / .track_affinity / .scoring_profiles /
.provider_metadata / .yandex_metadata / .raw_provider_responses /
.keys / .key_edges. Cached via @cached_property."
```

---

## Task 20: `app/v2/db/session.py` + `db/seed.py`

**Files:**
- Create: `app/v2/db/__init__.py`
- Create: `app/v2/db/session.py`
- Create: `app/v2/db/seed.py`
- Test: `tests/v2/db/test_seed.py`

- [ ] **Step 1: Write `app/v2/db/__init__.py`** (empty docstring)

```python
"""Database infrastructure: engine, session factory, reference-data seed."""
```

- [ ] **Step 2: Write `app/v2/db/session.py`**

```python
"""Async engine + session factory.

The engine is constructed lazily via ``get_engine()`` so tests can
substitute their own URL without touching process-level state.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.v2.config import get_settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None

def get_engine() -> AsyncEngine:
    """Return the process-wide engine, constructing it on first call."""
    global _engine
    if _engine is None:
        s = get_settings().database
        _engine = create_async_engine(
            s.database_url,
            echo=s.db_echo,
            pool_pre_ping=s.db_pool_pre_ping,
            pool_size=s.db_pool_size if "postgresql" in s.database_url else 5,
            connect_args={"statement_cache_size": s.db_statement_cache_size}
            if "postgresql" in s.database_url
            else {},
        )
    return _engine

def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session maker."""
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _factory

async def dispose() -> None:
    """Dispose the engine. Call in lifespan teardown."""
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _factory = None
```

- [ ] **Step 3: Write `app/v2/db/seed.py`**

```python
"""Reference-data seed: 24 Camelot keys + 4 provider rows.

Idempotent — safe to call on every startup.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.v2.models.key import Key, KeyEdge
from app.v2.models.provider_metadata import Provider

# (key_code, pitch_class, mode, name, camelot)
# Minor keys → mode=0 (A series), major → mode=1 (B series).
_KEYS: tuple[tuple[int, int, int, str, str], ...] = (
    (0, 9, 0, "A minor", "8A"),
    (1, 4, 0, "E minor", "9A"),
    (2, 11, 0, "B minor", "10A"),
    (3, 6, 0, "F# minor", "11A"),
    (4, 1, 0, "C# minor", "12A"),
    (5, 8, 0, "G# minor", "1A"),
    (6, 3, 0, "D# minor", "2A"),
    (7, 10, 0, "A# minor", "3A"),
    (8, 5, 0, "F minor", "4A"),
    (9, 0, 0, "C minor", "5A"),
    (10, 7, 0, "G minor", "6A"),
    (11, 2, 0, "D minor", "7A"),
    (12, 0, 1, "C major", "8B"),
    (13, 7, 1, "G major", "9B"),
    (14, 2, 1, "D major", "10B"),
    (15, 9, 1, "A major", "11B"),
    (16, 4, 1, "E major", "12B"),
    (17, 11, 1, "B major", "1B"),
    (18, 6, 1, "F# major", "2B"),
    (19, 1, 1, "C# major", "3B"),
    (20, 8, 1, "G# major", "4B"),
    (21, 3, 1, "D# major", "5B"),
    (22, 10, 1, "A# major", "6B"),
    (23, 5, 1, "F major", "7B"),
)

_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("yandex_music", "Yandex Music"),
    ("spotify", "Spotify"),
    ("beatport", "Beatport"),
    ("soundcloud", "SoundCloud"),
)

async def seed_reference(session: AsyncSession) -> None:
    """Ensure all 24 keys + 4 provider rows exist (idempotent)."""
    existing_keys = {
        k for (k,) in (await session.execute(select(Key.key_code))).all()
    }
    for key_code, pitch_class, mode, name, camelot in _KEYS:
        if key_code not in existing_keys:
            session.add(
                Key(
                    key_code=key_code,
                    pitch_class=pitch_class,
                    mode=mode,
                    name=name,
                    camelot=camelot,
                )
            )

    existing_provs = {
        c for (c,) in (await session.execute(select(Provider.code))).all()
    }
    for code, display in _PROVIDERS:
        if code not in existing_provs:
            session.add(Provider(code=code, display_name=display))

    await session.flush()
```

- [ ] **Step 4: Write seed test**

```python
# tests/v2/db/test_seed.py
"""Seed is idempotent and populates all 24 keys + 4 providers."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.db.seed import seed_reference
from app.v2.models import Base, Key, Provider

@pytest.mark.asyncio
async def test_seed_populates_keys_and_providers(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_reference(session)
    await session.commit()

    key_count = await session.scalar(select(func.count()).select_from(Key))
    prov_count = await session.scalar(select(func.count()).select_from(Provider))
    assert key_count == 24
    assert prov_count == 4

@pytest.mark.asyncio
async def test_seed_is_idempotent(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_reference(session)
    await session.commit()
    await seed_reference(session)  # second call
    await session.commit()

    key_count = await session.scalar(select(func.count()).select_from(Key))
    prov_count = await session.scalar(select(func.count()).select_from(Provider))
    assert key_count == 24
    assert prov_count == 4
```

- [ ] **Step 5: Run — expected PASS**

```bash
uv run pytest tests/v2/db/test_seed.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add app/v2/db tests/v2/db/test_seed.py
git commit -m "feat(v2): add db session factory + reference seed

get_engine / get_session_factory / dispose. seed_reference loads
24 Camelot keys + 4 providers, idempotent on reruns."
```

---

## Task 21: Alembic migration — drop 15 dead tables

**Files:**
- Create: `app/db/migrations/versions/phase2_drop_dead_tables.py`
- Test: `tests/v2/migrations/test_drop_dead_tables.py`

- [ ] **Step 1: Find current Alembic head**

```bash
uv run alembic current
```
Record the output (e.g. `abc123 (head)`).

- [ ] **Step 2: Create migration file skeleton**

```bash
uv run alembic revision -m "phase2_drop_dead_tables"
```
Alembic prints the path, e.g. `app/db/migrations/versions/20260417_phase2_drop_dead_tables.py`.

- [ ] **Step 3: Replace generated file contents**

```python
"""phase2 drop dead tables

Removes 15 tables with 0 rows per blueprint §13.2:
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
Revises: <fill in from `alembic current` above>
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p2_drop_dead"
down_revision = "<replace_with_current_head>"
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
    # Drop FK-child tables first where needed.
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
```

Replace `<replace_with_current_head>` with the revision ID captured in Step 1.

- [ ] **Step 4: Write migration sanity test**

```python
# tests/v2/migrations/test_drop_dead_tables.py
"""Sanity: migration module imports + lists 15+2 tables (15 + labels compound)."""

from __future__ import annotations

import importlib
import pathlib

def test_migration_imports() -> None:
    path = next(
        pathlib.Path("app/db/migrations/versions").glob("*phase2_drop_dead_tables*.py")
    )
    module_name = f"app.db.migrations.versions.{path.stem}"
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
    assert hasattr(mod, "DEAD_TABLES")
    assert len(mod.DEAD_TABLES) == 17  # 15 unique + labels + track_labels pair counted
    assert "spotify_metadata" in mod.DEAD_TABLES
    assert "app_exports" in mod.DEAD_TABLES
```

Note: the migration drops the 15 user-facing dead tables plus `labels` + `track_labels` (counted as 2 separate tables in blueprint §13.2 but one logical concept). The test counts 17 because it enumerates tables, not concepts.

- [ ] **Step 5: Run — expected PASS**

```bash
uv run pytest tests/v2/migrations/test_drop_dead_tables.py -v
```
Expected: 1 passed.

- [ ] **Step 6: DO NOT run `alembic upgrade head` yet**

The migration is staged but not applied. Production apply happens in Phase 7 Task 18 (cutover). For now we only verify the file is syntactically valid.

```bash
uv run alembic check 2>&1 || true
```
(Non-fatal — check just validates SQL syntax.)

- [ ] **Step 7: Commit**

```bash
git add app/db/migrations/versions/ tests/v2/migrations/test_drop_dead_tables.py
git commit -m "feat(v2): add alembic migration dropping 15 dead tables

Forward: DROP spotify_* (×5), beatport, soundcloud, embeddings,
transition_candidates, dj_saved_loops, dj_cue_points,
dj_beatgrid_change_points, dj_set_constraints, dj_set_feedback,
labels, track_labels, app_exports.
Downgrade: recreate empty stubs (id + created_at). Not applied
to production until Phase 7 Task 18."
```

---

## Task 22: `register_default_entities()` in `registry/entity.py`

**Files:**
- Modify: `app/v2/registry/entity.py` (add function, don't change class)
- Create: `app/v2/registry/defaults.py` (holds the 11 configs)
- Test: `tests/v2/registry/test_register_default_entities.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/registry/test_register_default_entities.py
"""Registering default entities populates the registry with 11 configs."""

from __future__ import annotations

import pytest

from app.v2.registry.defaults import register_default_entities
from app.v2.registry.entity import EntityRegistry

@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    EntityRegistry.clear()

def test_register_all() -> None:
    register_default_entities()
    names = EntityRegistry.names()
    expected = {
        "track",
        "playlist",
        "set",
        "set_version",
        "audio_file",
        "track_features",
        "transition",
        "transition_history",
        "track_feedback",
        "track_affinity",
        "scoring_profile",
    }
    assert set(names) == expected

def test_track_config_shape() -> None:
    register_default_entities()
    cfg = EntityRegistry.get("track")
    assert cfg.name == "track"
    assert cfg.repo_attr == "tracks"
    assert "list" in cfg.allowed_ops
    assert "id" in cfg.field_presets
    assert cfg.default_preset == "id"
    assert cfg.create_handler is None  # Phase 3 wires handlers

def test_idempotent_register_raises_on_duplicate() -> None:
    register_default_entities()
    # Second call should fail — we rely on Phase 1 EntityRegistry behaviour.
    with pytest.raises(ValueError):
        register_default_entities()
```

- [ ] **Step 2: Run — expected FAIL**

```bash
uv run pytest tests/v2/registry/test_register_default_entities.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/registry/defaults.py`**

```python
"""Register the 11 user-facing entities with their schemas + presets.

Handlers default to ``None``; Phase 3 assigns custom handlers for
``track`` (import), ``track_features`` (analyze/reanalyze),
``audio_file`` (download), ``transition`` (persist score),
``set_version`` (build snapshot).
"""

from __future__ import annotations

from app.v2.models.audio_file import DjLibraryItem
from app.v2.models.playlist import DjPlaylist
from app.v2.models.scoring_profile import ScoringProfile
from app.v2.models.set import DjSet, DjSetVersion
from app.v2.models.track import Track
from app.v2.models.track_affinity import TrackAffinity
from app.v2.models.track_feedback import TrackFeedback
from app.v2.models.track_features import TrackAudioFeaturesComputed
from app.v2.models.transition import Transition
from app.v2.models.transition_history import TransitionHistory
from app.v2.registry.entity import EntityConfig, EntityRegistry
from app.v2.schemas.audio_file import (
    AudioFileCreate,
    AudioFileFilter,
    AudioFileUpdate,
    AudioFileView,
)
from app.v2.schemas.playlist import (
    PlaylistCreate,
    PlaylistFilter,
    PlaylistUpdate,
    PlaylistView,
)
from app.v2.schemas.scoring_profile import (
    ScoringProfileCreate,
    ScoringProfileFilter,
    ScoringProfileUpdate,
    ScoringProfileView,
)
from app.v2.schemas.set import (
    SetCreate,
    SetFilter,
    SetUpdate,
    SetView,
    SetVersionCreate,
    SetVersionView,
)
from app.v2.schemas.track import TrackCreate, TrackFilter, TrackUpdate, TrackView
from app.v2.schemas.track_affinity import (
    TrackAffinityCreate,
    TrackAffinityFilter,
    TrackAffinityUpdate,
    TrackAffinityView,
)
from app.v2.schemas.track_feedback import (
    TrackFeedbackCreate,
    TrackFeedbackFilter,
    TrackFeedbackUpdate,
    TrackFeedbackView,
)
from app.v2.schemas.track_features import (
    TrackFeaturesCreate,
    TrackFeaturesFilter,
    TrackFeaturesUpdate,
    TrackFeaturesView,
)
from app.v2.schemas.transition import (
    TransitionCreate,
    TransitionFilter,
    TransitionUpdate,
    TransitionView,
)
from app.v2.schemas.transition_history import (
    TransitionHistoryCreate,
    TransitionHistoryFilter,
    TransitionHistoryUpdate,
    TransitionHistoryView,
)

def register_default_entities() -> None:
    EntityRegistry.register(
        EntityConfig(
            name="track",
            model=Track,
            repo_attr="tracks",
            view_schema=TrackView,
            filter_schema=TrackFilter,
            create_schema=TrackCreate,
            update_schema=TrackUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "title"],
                "summary": ["id", "title", "duration_ms", "status"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("title", "sort_title"),
            filterable_fields={
                "id": ("eq", "in"),
                "title": ("icontains",),
                "status": ("eq", "in"),
            },
            sortable_fields=("id", "title", "duration_ms"),
            relations={"artists": "artists", "features": "track_audio_features_computed"},
            tags=frozenset({"namespace:library"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="playlist",
            model=DjPlaylist,
            repo_attr="playlists",
            view_schema=PlaylistView,
            filter_schema=PlaylistFilter,
            create_schema=PlaylistCreate,
            update_schema=PlaylistUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "name"],
                "summary": ["id", "name", "source_of_truth"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("name",),
            filterable_fields={"id": ("eq", "in"), "name": ("icontains",)},
            sortable_fields=("id", "name"),
            relations={"items": "dj_playlist_items"},
            tags=frozenset({"namespace:library"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="set",
            model=DjSet,
            repo_attr="sets",
            view_schema=SetView,
            filter_schema=SetFilter,
            create_schema=SetCreate,
            update_schema=SetUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "ref": ["id", "name"],
                "summary": ["id", "name", "template_name", "target_duration_ms"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("name",),
            filterable_fields={
                "id": ("eq", "in"),
                "name": ("icontains",),
                "template_name": ("eq",),
            },
            sortable_fields=("id", "name"),
            relations={"versions": "dj_set_versions"},
            tags=frozenset({"namespace:sets"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="set_version",
            model=DjSetVersion,
            repo_attr="set_versions",
            view_schema=SetVersionView,
            filter_schema=SetFilter,  # reused — filters by set_id etc.
            create_schema=SetVersionCreate,
            update_schema=SetUpdate,
            allowed_ops=frozenset({"list", "get", "create", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "set_id", "version_label", "quality_score"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("version_label",),
            filterable_fields={"set_id": ("eq", "in")},
            sortable_fields=("id", "quality_score"),
            relations={"items": "dj_set_items"},
            tags=frozenset({"namespace:sets"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="audio_file",
            model=DjLibraryItem,
            repo_attr="audio_files",
            view_schema=AudioFileView,
            filter_schema=AudioFileFilter,
            create_schema=AudioFileCreate,
            update_schema=AudioFileUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "file_path", "file_size"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("file_path",),
            filterable_fields={
                "id": ("eq", "in"),
                "track_id": ("eq", "in"),
            },
            sortable_fields=("id", "file_size"),
            relations={"beatgrids": "dj_beatgrids"},
            tags=frozenset({"namespace:library"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_features",
            model=TrackAudioFeaturesComputed,
            repo_attr="track_features",
            view_schema=TrackFeaturesView,
            filter_schema=TrackFeaturesFilter,
            create_schema=TrackFeaturesCreate,
            update_schema=TrackFeaturesUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update"}),
            field_presets={
                "id": ["track_id"],
                "scoring": [
                    "track_id",
                    "bpm",
                    "key_code",
                    "integrated_lufs",
                    "energy_mean",
                    "spectral_centroid_hz",
                    "hp_ratio",
                    "kick_prominence",
                    "mood",
                ],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "track_id": ("eq", "in"),
                "bpm": ("gte", "lte", "range"),
                "mood": ("eq", "in"),
            },
            sortable_fields=("track_id", "bpm"),
            relations={},
            tags=frozenset({"namespace:analysis"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="transition",
            model=Transition,
            repo_attr="transitions",
            view_schema=TransitionView,
            filter_schema=TransitionFilter,
            create_schema=TransitionCreate,
            update_schema=TransitionUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "from_track_id",
                    "to_track_id",
                    "overall_score",
                    "style",
                ],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "overall_score": ("gte", "lte"),
            },
            sortable_fields=("id", "overall_score"),
            relations={},
            tags=frozenset({"namespace:transitions"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="transition_history",
            model=TransitionHistory,
            repo_attr="transition_history",
            view_schema=TransitionHistoryView,
            filter_schema=TransitionHistoryFilter,
            create_schema=TransitionHistoryCreate,
            update_schema=TransitionHistoryUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "from_track_id",
                    "to_track_id",
                    "overall_score",
                    "reaction",
                ],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "from_track_id": ("eq", "in"),
                "to_track_id": ("eq", "in"),
                "reaction": ("eq",),
            },
            sortable_fields=("id", "overall_score"),
            relations={},
            tags=frozenset({"namespace:transitions"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_feedback",
            model=TrackFeedback,
            repo_attr="track_feedback",
            view_schema=TrackFeedbackView,
            filter_schema=TrackFeedbackFilter,
            create_schema=TrackFeedbackCreate,
            update_schema=TrackFeedbackUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "track_id", "kind", "rating"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "track_id": ("eq", "in"),
                "kind": ("eq",),
            },
            sortable_fields=("id",),
            relations={},
            tags=frozenset({"namespace:feedback"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="track_affinity",
            model=TrackAffinity,
            repo_attr="track_affinity",
            view_schema=TrackAffinityView,
            filter_schema=TrackAffinityFilter,
            create_schema=TrackAffinityCreate,
            update_schema=TrackAffinityUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update"}),
            field_presets={
                "id": ["id"],
                "summary": [
                    "id",
                    "track_a_id",
                    "track_b_id",
                    "avg_score",
                    "play_count",
                ],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=(),
            filterable_fields={
                "track_a_id": ("eq",),
                "track_b_id": ("eq",),
                "avg_score": ("gte",),
            },
            sortable_fields=("id", "avg_score"),
            relations={},
            tags=frozenset({"namespace:feedback"}),
        )
    )

    EntityRegistry.register(
        EntityConfig(
            name="scoring_profile",
            model=ScoringProfile,
            repo_attr="scoring_profiles",
            view_schema=ScoringProfileView,
            filter_schema=ScoringProfileFilter,
            create_schema=ScoringProfileCreate,
            update_schema=ScoringProfileUpdate,
            allowed_ops=frozenset({"list", "get", "create", "update", "delete"}),
            field_presets={
                "id": ["id"],
                "summary": ["id", "name"],
                "full": "*",
            },
            default_preset="id",
            searchable_fields=("name",),
            filterable_fields={"name": ("eq", "icontains")},
            sortable_fields=("id", "name"),
            relations={},
            tags=frozenset({"namespace:scoring"}),
        )
    )
```

- [ ] **Step 4: Run — expected PASS**

```bash
uv run pytest tests/v2/registry/test_register_default_entities.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/registry/defaults.py \
        tests/v2/registry/test_register_default_entities.py
git commit -m "feat(v2): register 11 default entities

track / playlist / set / set_version / audio_file / track_features /
transition / transition_history / track_feedback / track_affinity /
scoring_profile. All handler fields None; Phase 3 wires handlers."
```

---

## Task 23: Full Phase 2 verification

**Files:** none (verification only)

- [ ] **Step 1: Run every v2 test**

```bash
uv run pytest tests/v2/ -v
```
Expected: all tests pass (Phase 1 + Phase 2 suites combined).

- [ ] **Step 2: mypy strict on all of `app/v2/`**

```bash
uv run mypy app/v2/
```
Expected: no errors.

- [ ] **Step 3: Lint**

```bash
uv run ruff check app/v2/ tests/v2/
uv run ruff format --check app/v2/ tests/v2/
```
Expected: clean.

- [ ] **Step 4: Import-linter contracts**

```bash
uv run lint-imports
```
Expected: 11 contracts PASS (6 legacy + 5 Phase 1).

- [ ] **Step 5: Full `make check` including legacy tests**

```bash
make check
```
Expected: everything green. This confirms **nothing in `app/` has regressed**.

- [ ] **Step 6: Verify BFS/L5 scripts do not reference v2**

```bash
uv run python -c "
import pathlib
for p in pathlib.Path('scripts').rglob('*.py'):
    src = p.read_text()
    assert 'app.v2' not in src, f'{p} imports app.v2 — Phase 2 forbids this'
print('scripts/ clean')"
```
Expected: `scripts/ clean`.

- [ ] **Step 7: Phase 2 tag**

```bash
git tag -a phase-2-persistence -m "Phase 2 complete: 13 models, 16 repos, 12 schemas, UoW wired, migration staged, 11 entities registered"
git log --oneline dev..HEAD | head -30
```

---

## Self-Review — Spec Coverage

| Blueprint §15.3 deliverable | Task(s) |
|---|---|
| 13 models in `app/v2/models/` | Tasks 1-11 (models) + Task 12 (__init__) |
| 13 repositories extending `BaseRepository[M]` | Tasks 16-18 |
| 12 Pydantic schema families (View/Filter/Create/Update) | Tasks 13-15 |
| UoW extended with lazy `@property` accessors | Task 19 |
| Alembic migration dropping 15 dead tables | Task 21 |
| `app/v2/db/session.py` + `seed.py` (24 keys + 4 providers) | Task 20 |
| `register_default_entities()` covering 11 user-facing entities | Task 22 |
| Exit: Phase 1 + Phase 2 tests green, staging DB migrated | Task 23 (migration applies in Phase 7) |

**Explicitly deferred:**
- Migration applied to production — Phase 7 Task 18
- Handler wiring on entities — Phase 3 Task 28
- REST / server composition — Phase 5
- Panel integration — out of scope (blueprint D2)
