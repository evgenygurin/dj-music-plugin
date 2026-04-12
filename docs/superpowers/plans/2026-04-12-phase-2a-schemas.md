# Phase 2a: schemas/ — Entity-First Schemas

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Create `src/dj_music/schemas/` with base classes (BaseEntity, BaseValueObject, BaseFilter, BaseSort, BasePagination) and all domain entity schemas with validation, DTOs, and filters.

**Architecture:** Entity-First — one package for Entity + Create/Update DTO + Brief/Summary DTO + Filter. Pydantic v2 `from_attributes=True` for ORM mapping.

**Tech Stack:** Pydantic v2, pydantic-settings

**⚠️ ОБЯЗАТЕЛЬНО изучить перед выполнением:**
- Pydantic v2 docs: `from_attributes`, `frozen`, `computed_field`, `field_validator`, `model_validator`, `Discriminator`
- https://gofastmcp.com/servers/resources
- https://gofastmcp.com/servers/prompts

---

### Task 1: Create base classes in schemas/base.py

**Files:**
- Create: `src/dj_music/schemas/__init__.py`
- Create: `src/dj_music/schemas/base.py`

- [ ] **Step 1: Write test for base classes**

```python
# tests/test_schemas/test_base.py
from dj_music.schemas.base import (
    BaseEntity, BaseValueObject, BaseFilter, BaseSort, BasePagination,
)
from dj_music.core.constants import SortDir

def test_base_entity_from_attributes():
    """BaseEntity should support from_attributes for ORM mapping."""
    class FakeORM:
        id = 42
        title = "test"

    class Track(BaseEntity):
        title: str = ""

    track = Track.model_validate(FakeORM())
    assert track.id == 42
    assert track.title == "test"

def test_base_entity_extra_forbid():
    """BaseEntity should reject extra fields."""
    import pytest
    from pydantic import ValidationError

    class Track(BaseEntity):
        title: str = ""

    with pytest.raises(ValidationError):
        Track(id=1, title="x", unknown_field="bad")

def test_base_value_object_frozen():
    """BaseValueObject should be immutable."""
    import pytest
    from pydantic import ValidationError

    class Bpm(BaseValueObject):
        value: float

    bpm = Bpm(value=128.0)
    with pytest.raises(ValidationError):
        bpm.value = 130.0

def test_base_filter_optional():
    """BaseFilter fields should all be optional."""
    class MyFilter(BaseFilter):
        name: str | None = None

    f = MyFilter()
    assert f.name is None

def test_base_pagination_defaults():
    p = BasePagination()
    assert p.limit == 20
    assert p.cursor is None

def test_base_sort_defaults():
    s = BaseSort()
    assert s.sort_dir == SortDir.ASC

def test_composite_filter():
    """Filter inheriting BaseFilter + BaseSort + BasePagination."""
    class TrackFilter(BaseFilter, BaseSort, BasePagination):
        bpm_min: float | None = None

    f = TrackFilter(bpm_min=120.0, limit=50, sort_dir="desc")
    assert f.bpm_min == 120.0
    assert f.limit == 50
    assert f.sort_dir == SortDir.DESC
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_schemas/test_base.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'dj_music.schemas'`

- [ ] **Step 3: Implement base classes**

```python
# src/dj_music/schemas/__init__.py
"""Entity-First schemas: Entity + DTO + Filter + Validator."""

# src/dj_music/schemas/base.py
"""Base classes for all schemas, entities, value objects, filters."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from dj_music.core.constants import SortDir

class BaseEntity(BaseModel):
    """Base for all domain entities. Supports ORM → Pydantic mapping."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int = 0

class BaseValueObject(BaseModel):
    """Immutable value object. Structural equality."""

    model_config = ConfigDict(frozen=True)

class BasePagination(BaseModel):
    """Cursor-based pagination parameters."""

    limit: int = Field(20, ge=1, le=100, description="Items per page")
    cursor: str | None = Field(None, description="Opaque cursor for next page")

class BaseSort(BaseModel):
    """Sort direction. Subclasses add sort_by field with domain-specific enum."""

    sort_dir: SortDir = SortDir.ASC

class BaseFilter(BaseModel):
    """Base filter — all fields optional, extra forbidden."""

    model_config = ConfigDict(extra="forbid")

__all__ = [
    "BaseEntity",
    "BaseValueObject",
    "BaseFilter",
    "BaseSort",
    "BasePagination",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_schemas/test_base.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_music/schemas/ tests/test_schemas/
git commit -m "feat: add schemas/base.py with BaseEntity, BaseFilter, BaseSort, BasePagination

Entity-First base classes. BaseEntity supports from_attributes
for ORM mapping. BaseValueObject is frozen. BaseFilter + BaseSort +
BasePagination composable via multiple inheritance.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Create track schemas

**Files:**
- Create: `src/dj_music/schemas/track.py`

- [ ] **Step 1: Write test**

```python
# tests/test_schemas/test_track.py
from dj_music.schemas.track import Track, TrackBrief, TrackFilter, TrackSortField
from dj_music.core.constants import SortDir

def test_track_entity():
    t = Track(id=1, title="Test", duration_ms=300000)
    assert t.id == 1
    assert t.title == "Test"

def test_track_from_orm():
    class FakeORM:
        id = 1
        title = "Test"
        sort_title = "test"
        duration_ms = 300000
        status = 0

    t = Track.model_validate(FakeORM())
    assert t.id == 1

def test_track_brief():
    b = TrackBrief(id=1, title="Test", bpm=128.0)
    assert b.bpm == 128.0

def test_track_filter_validation():
    import pytest
    from pydantic import ValidationError

    # Valid
    f = TrackFilter(bpm_min=120, bpm_max=140, sort_by="bpm", sort_dir="desc", limit=50)
    assert f.bpm_min == 120
    assert f.sort_by == TrackSortField.BPM

    # Invalid: bpm out of range
    with pytest.raises(ValidationError):
        TrackFilter(bpm_min=10)  # ge=20

def test_track_filter_range_validator():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TrackFilter(bpm_min=140, bpm_max=120)  # min > max
```

- [ ] **Step 2: Run test — fails**

```bash
uv run pytest tests/test_schemas/test_track.py -v
```

- [ ] **Step 3: Implement**

```python
# src/dj_music/schemas/track.py
"""Track schemas: Entity + DTOs + Filter."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from dj_music.schemas.base import BaseEntity, BaseFilter, BasePagination, BaseSort

class TrackSortField(StrEnum):
    ID = "id"
    BPM = "bpm"
    TITLE = "title"
    ENERGY = "energy"
    CREATED_AT = "created_at"

class Track(BaseEntity):
    """Full track entity."""

    title: str = ""
    sort_title: str = ""
    duration_ms: int = 0
    status: int = 0

class TrackBrief(BaseEntity):
    """Minimal track info for list views."""

    title: str = ""
    bpm: float | None = None
    key_code: int | None = None
    mood: str | None = None

class TrackFilter(BaseFilter, BaseSort, BasePagination):
    """Track filtering + sorting + pagination."""

    bpm_min: float | None = Field(None, ge=20, le=300)
    bpm_max: float | None = Field(None, ge=20, le=300)
    key_code: int | None = Field(None, ge=0, le=23)
    energy_min: float | None = Field(None, ge=0, le=1)
    energy_max: float | None = Field(None, ge=0, le=1)
    mood: str | None = None
    has_features: bool | None = None
    exclude_set_id: int | None = None
    sort_by: TrackSortField = TrackSortField.ID

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.bpm_min is not None and self.bpm_max is not None:
            if self.bpm_min > self.bpm_max:
                raise ValueError("bpm_min must be <= bpm_max")
        if self.energy_min is not None and self.energy_max is not None:
            if self.energy_min > self.energy_max:
                raise ValueError("energy_min must be <= energy_max")
        return self
```

- [ ] **Step 4: Run test — passes**

```bash
uv run pytest tests/test_schemas/test_track.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/dj_music/schemas/track.py tests/test_schemas/test_track.py
git commit -m "feat: add track schemas — Track, TrackBrief, TrackFilter

TrackFilter composable: BaseFilter + BaseSort + BasePagination.
Range validation via model_validator. TrackSortField enum.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Create remaining domain schemas

**Files:**
- Create: `src/dj_music/schemas/audio.py` — TrackFeatures, AudioFeatures
- Create: `src/dj_music/schemas/playlist.py` — Playlist, PlaylistItem, PlaylistFilter
- Create: `src/dj_music/schemas/set.py` — DjSet, SetVersion, SetItem, SetFilter
- Create: `src/dj_music/schemas/transition.py` — Transition, TransitionCandidate
- Create: `src/dj_music/schemas/library.py` — LibraryItem, Beatgrid, CuePoint
- Create: `src/dj_music/schemas/platform.py` — YandexMetadata
- Create: `src/dj_music/schemas/common.py` — CursorPage

- [ ] **Step 1: Create each file following the Track pattern**

Each file follows the same structure:
1. Entity class (BaseEntity, from_attributes=True)
2. Brief/Summary DTO (subset of fields)
3. Filter class (BaseFilter + BaseSort + BasePagination) where applicable
4. model_validator for range checks

**audio.py** — copy TrackFeatures from `app/entities/audio/features.py`, convert from dataclass to Pydantic BaseEntity.

**common.py:**
```python
# src/dj_music/schemas/common.py
from __future__ import annotations
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class CursorPage(BaseModel, Generic[T]):
    """Cursor-paginated response."""
    items: list[T]
    next_cursor: str | None = None
    total: int | None = None
```

- [ ] **Step 2: Write basic tests for each**

One test per schema file verifying entity creation and from_attributes.

- [ ] **Step 3: Add re-export shims for existing schemas**

```python
# app/schemas/__init__.py — update to re-export from new location
from dj_music.schemas.common import CursorPage  # noqa: F401
# keep existing exports for backward compat
```

For `app/entities/audio/features.py`:
```python
# app/entities/audio/features.py — re-export shim
from dj_music.schemas.audio import TrackFeatures  # noqa: F401
```

- [ ] **Step 4: Run full tests, commit**

```bash
uv run pytest -x -q && git add -A && git commit -m "feat: add all domain schemas — audio, playlist, set, transition, library, platform

Entity-First: each file contains Entity + Brief + Filter.
TrackFeatures migrated from dataclass to Pydantic BaseEntity.
Re-export shims for backward compatibility.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Final Phase 2a verification

- [ ] **Step 1: Verify schemas structure**

```bash
find src/dj_music/schemas -name "*.py" | sort
```

Expected:
```text
src/dj_music/schemas/__init__.py
src/dj_music/schemas/audio.py
src/dj_music/schemas/base.py
src/dj_music/schemas/common.py
src/dj_music/schemas/library.py
src/dj_music/schemas/platform.py
src/dj_music/schemas/playlist.py
src/dj_music/schemas/set.py
src/dj_music/schemas/track.py
src/dj_music/schemas/transition.py
```

- [ ] **Step 2: Run make check**

```bash
make check
```
Expected: all pass
