# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `app/v2/` skeleton with shared primitives, split config, registries, BaseRepository, and Unit of Work — zero behavior change to `app/`, unblocks Phase 2 (models + repos migration).

**Architecture:** Parallel refactor per blueprint §15.2 — new code lives under `app/v2/` while `app/` runs unmodified. `app/v2/` MAY import FROM `app/` during transition; `app/` MUST NOT import from `app/v2/`. All tests for new code live under `tests/v2/` and run in the same CI.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, Pydantic v2, pydantic-settings v2, pytest + pytest-asyncio, aiosqlite (tests), asyncpg (prod), import-linter.

**Spec reference:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§3, 10, 15.2, 16.

---

## File Structure

Files created by this plan (exact paths, each self-contained):

### Source code (`app/v2/`)

```bash
app/v2/
├── __init__.py                    # namespace marker, v2 version
├── shared/
│   ├── __init__.py
│   ├── errors.py                  # DJMusicError, NotFoundError, ValidationError, ConflictError, NotAllowedError
│   ├── ids.py                     # type aliases TrackId, PlaylistId, SetId, ...
│   ├── time.py                    # utc_now, utc_timestamp_iso, sa_now
│   ├── pagination.py              # Page[M] dataclass + cursor encode/decode
│   └── filters.py                 # Django-style lookup parser (bpm__gte, mood__in, ...)
├── config/
│   ├── __init__.py                # Settings facade with lru_cache
│   ├── database.py                # DatabaseSettings
│   ├── yandex.py                  # YandexSettings
│   ├── audio.py                   # AudioSettings
│   ├── transition.py              # TransitionSettings
│   ├── optimization.py            # OptimizationSettings
│   ├── discovery.py               # DiscoverySettings
│   ├── delivery.py                # DeliverySettings
│   └── mcp.py                     # MCPSettings
├── registry/
│   ├── __init__.py
│   ├── entity.py                  # EntityConfig, EntityRegistry
│   └── provider.py                # Provider Protocol, ProviderRegistry
└── repositories/
    ├── __init__.py
    ├── base.py                    # BaseRepository[M]
    └── unit_of_work.py            # UnitOfWork (skeleton; repos added in Phase 2)
```

### Tests (`tests/v2/`)

```bash
tests/v2/
├── __init__.py
├── conftest.py                    # fixtures: in-memory SQLite engine + session
├── shared/
│   ├── __init__.py
│   ├── test_errors.py
│   ├── test_pagination.py
│   └── test_filters.py
├── config/
│   ├── __init__.py
│   └── test_settings_facade.py
├── registry/
│   ├── __init__.py
│   ├── test_entity_registry.py
│   └── test_provider_registry.py
└── repositories/
    ├── __init__.py
    ├── test_base_repository.py
    └── test_unit_of_work.py
```

### Config updates

- `.importlinter` — 2 new Phase 1 contracts (v2 shared leaf, v2 repositories isolated)
- `pyproject.toml` — verify `[tool.setuptools.packages.find] include` or equivalent picks up `app.v2.*` (likely already covered by `app*`)

---

## Task 1: Create `app/v2/` package skeleton

**Files:**
- Create: `app/v2/__init__.py`
- Create: `app/v2/shared/__init__.py`
- Create: `app/v2/config/__init__.py` (empty for now — fleshed out in Task 11)
- Create: `app/v2/registry/__init__.py`
- Create: `app/v2/repositories/__init__.py`
- Create: `tests/v2/__init__.py`

- [ ] **Step 1: Create directory structure and empty `__init__.py` files**

```bash
mkdir -p app/v2/shared app/v2/config app/v2/registry app/v2/repositories
mkdir -p tests/v2/shared tests/v2/config tests/v2/registry tests/v2/repositories
```

- [ ] **Step 2: Write top-level marker file `app/v2/__init__.py`**

```python
"""Target architecture (parallel refactor).

Phase 1-7 implementation per
docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md

`app/v2/` MAY import from `app/` during transition.
`app/` MUST NOT import from `app/v2/`.
"""

__version__ = "0.0.0-v2"
```

- [ ] **Step 3: Create empty `__init__.py` in every subpackage**

```python
# app/v2/shared/__init__.py, app/v2/config/__init__.py,
# app/v2/registry/__init__.py, app/v2/repositories/__init__.py,
# tests/v2/__init__.py, tests/v2/shared/__init__.py,
# tests/v2/config/__init__.py, tests/v2/registry/__init__.py,
# tests/v2/repositories/__init__.py

"""[module docstring; can be one line]"""
```

Use: `""""""` (triple-empty) in every `__init__.py` except `app/v2/__init__.py` (which has content above).

- [ ] **Step 4: Verify package is importable**

Run:
```bash
uv run python -c "import app.v2; print(app.v2.__version__)"
```
Expected: `0.0.0-v2`

- [ ] **Step 5: Commit**

```bash
git add app/v2 tests/v2
git commit -m "feat(v2): create app/v2 package skeleton

Parallel-refactor shell per blueprint phase 1.
Empty packages for shared, config, registry, repositories."
```

---

## Task 2: `app/v2/shared/errors.py` — error hierarchy

**Files:**
- Create: `app/v2/shared/errors.py`
- Test: `tests/v2/shared/test_errors.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/shared/test_errors.py
"""Error hierarchy tests."""

import pytest

from app.v2.shared.errors import (
    ConflictError,
    DJMusicError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)

def test_base_error_is_exception() -> None:
    assert issubclass(DJMusicError, Exception)

def test_not_found_formats_message() -> None:
    err = NotFoundError("track", 42)
    assert err.entity_type == "track"
    assert err.identifier == 42
    assert "track" in str(err)
    assert "42" in str(err)

def test_not_found_subclasses_base() -> None:
    assert issubclass(NotFoundError, DJMusicError)

def test_validation_error_keeps_details() -> None:
    err = ValidationError("bpm must be in [20, 300]", details={"field": "bpm", "value": 500})
    assert err.details == {"field": "bpm", "value": 500}
    assert "bpm must be in [20, 300]" in str(err)

def test_conflict_error_message() -> None:
    err = ConflictError("track with yandex_id=12345 already exists")
    assert "12345" in str(err)
    assert isinstance(err, DJMusicError)

def test_not_allowed_error_holds_context() -> None:
    err = NotAllowedError(entity="track", operation="delete")
    assert err.entity == "track"
    assert err.operation == "delete"
    assert "track" in str(err)
    assert "delete" in str(err)
```

- [ ] **Step 2: Run tests — expected FAIL (module missing)**

```bash
uv run pytest tests/v2/shared/test_errors.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.v2.shared.errors'`

- [ ] **Step 3: Write `app/v2/shared/errors.py`**

```python
"""Typed error hierarchy for DJ Music Plugin v2.

These map to MCP errors at the tool boundary:
- NotFoundError    -> ToolError "entity not found" (404-like)
- ValidationError  -> ToolError with details (400-like)
- ConflictError    -> ToolError "duplicate / version mismatch" (409-like)
- NotAllowedError  -> ToolError "operation not permitted on entity" (403-like)

Infrastructure errors (DB, HTTP) are masked in production — never surfaced raw.
"""

from __future__ import annotations

from typing import Any

class DJMusicError(Exception):
    """Base for all domain errors."""

class NotFoundError(DJMusicError):
    """Entity not found by identifier."""

    def __init__(self, entity_type: str, identifier: Any) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier!r}")

class ValidationError(DJMusicError):
    """Input validation failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.details = details or {}
        super().__init__(message)

class ConflictError(DJMusicError):
    """Conflict: duplicate key, optimistic-lock mismatch, invalid state transition."""

class NotAllowedError(DJMusicError):
    """Operation not allowed on this entity (missing from EntityConfig.allowed_ops)."""

    def __init__(self, *, entity: str, operation: str) -> None:
        self.entity = entity
        self.operation = operation
        super().__init__(f"operation {operation!r} not allowed on entity {entity!r}")
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/shared/test_errors.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/shared/errors.py tests/v2/shared/test_errors.py
git commit -m "feat(v2): add shared error hierarchy

5 error types: base DJMusicError + NotFoundError / ValidationError /
ConflictError / NotAllowedError. All map to MCP tool errors."
```

---

## Task 3: `app/v2/shared/ids.py` — type aliases for entity IDs

**Files:**
- Create: `app/v2/shared/ids.py`
- Test: inline (type alias verification)

- [ ] **Step 1: Write `app/v2/shared/ids.py`**

```python
"""Type aliases for entity identifiers.

These are NewType wrappers — they behave as ``int`` at runtime but are
distinct types for static type checking. Using ``TrackId`` vs plain ``int``
prevents accidentally passing a ``PlaylistId`` where a ``TrackId`` was expected.
"""

from __future__ import annotations

from typing import NewType

TrackId = NewType("TrackId", int)
PlaylistId = NewType("PlaylistId", int)
SetId = NewType("SetId", int)
SetVersionId = NewType("SetVersionId", int)
SetItemId = NewType("SetItemId", int)
AudioFileId = NewType("AudioFileId", int)
TransitionId = NewType("TransitionId", int)
TransitionHistoryId = NewType("TransitionHistoryId", int)
TrackFeedbackId = NewType("TrackFeedbackId", int)
TrackAffinityId = NewType("TrackAffinityId", int)
ScoringProfileId = NewType("ScoringProfileId", int)
ArtistId = NewType("ArtistId", int)
GenreId = NewType("GenreId", int)
ReleaseId = NewType("ReleaseId", int)
KeyCode = NewType("KeyCode", int)  # 0-23 per Camelot

# Provider-side identifiers are strings (yandex ID, spotify ID, ...)
ProviderTrackId = NewType("ProviderTrackId", str)
ProviderAlbumId = NewType("ProviderAlbumId", str)
ProviderArtistId = NewType("ProviderArtistId", str)
ProviderPlaylistId = NewType("ProviderPlaylistId", str)
```

- [ ] **Step 2: Verify import + runtime behavior**

Run:
```bash
uv run python -c "from app.v2.shared.ids import TrackId, ProviderTrackId; print(TrackId(42), type(TrackId(42)).__name__); print(ProviderTrackId('12345'))"
```
Expected: `42 int` on line 1, `12345` on line 2.

- [ ] **Step 3: Run mypy strict**

```bash
uv run mypy app/v2/shared/ids.py
```
Expected: `Success: no issues found in 1 source file`.

- [ ] **Step 4: Commit**

```bash
git add app/v2/shared/ids.py
git commit -m "feat(v2): add ID type aliases for entities

NewType wrappers for TrackId, PlaylistId, SetId, ... so the type checker
catches id-type confusion. Runtime behavior unchanged."
```

---

## Task 4: `app/v2/shared/time.py` — centralized time utilities

**Files:**
- Create: `app/v2/shared/time.py`

- [ ] **Step 1: Write `app/v2/shared/time.py`** (port from `app/core/utils/time.py` with identical API)

```python
"""Centralized time utilities (v2).

Single source of truth for all datetime operations. All timestamps are UTC.
Use these instead of direct datetime calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func

def utc_now() -> datetime:
    """Current UTC datetime. Use for Python-side timestamps."""
    return datetime.now(UTC)

def utc_timestamp_iso() -> str:
    """Current UTC datetime as ISO-8601 string. Use for JSON metadata."""
    return utc_now().isoformat()

def sa_now():  # type: ignore[no-untyped-def]
    """SQLAlchemy NOW() expression for column defaults.

    Use as ``mapped_column(default=sa_now(), server_default=sa_now())`` —
    generates ``NOW()`` on the database side.
    """
    return func.now()
```

- [ ] **Step 2: Smoke-test**

Run:
```bash
uv run python -c "from app.v2.shared.time import utc_now, utc_timestamp_iso; print(utc_now()); print(utc_timestamp_iso())"
```
Expected: two lines of current UTC time.

- [ ] **Step 3: Commit**

```bash
git add app/v2/shared/time.py
git commit -m "feat(v2): port time utilities to shared module

utc_now, utc_timestamp_iso, sa_now — identical API to app/core/utils/time.py
for future drop-in swap at Phase 7 cutover."
```

---

## Task 5: `app/v2/shared/pagination.py` — cursor pagination

**Files:**
- Create: `app/v2/shared/pagination.py`
- Test: `tests/v2/shared/test_pagination.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/shared/test_pagination.py
"""Cursor pagination tests."""

from dataclasses import dataclass

import pytest

from app.v2.shared.pagination import Page, decode_cursor, encode_cursor

@dataclass
class _FakeItem:
    id: int
    name: str

def test_encode_decode_round_trip() -> None:
    cursor = encode_cursor(42)
    assert isinstance(cursor, str)
    assert decode_cursor(cursor) == 42

def test_cursor_is_url_safe() -> None:
    cursor = encode_cursor(12345)
    assert "+" not in cursor and "/" not in cursor and "=" not in cursor

def test_decode_invalid_cursor_raises() -> None:
    with pytest.raises(ValueError):
        decode_cursor("not-a-cursor")

def test_page_construction() -> None:
    items = [_FakeItem(1, "a"), _FakeItem(2, "b")]
    page = Page(items=items, next_cursor="abc", total=None)
    assert page.items == items
    assert page.next_cursor == "abc"
    assert page.total is None

def test_page_has_more_when_cursor_present() -> None:
    page = Page(items=[_FakeItem(1, "a")], next_cursor="abc")
    assert page.has_more is True

def test_page_no_more_when_cursor_none() -> None:
    page = Page(items=[_FakeItem(1, "a")], next_cursor=None)
    assert page.has_more is False

def test_page_generic_typing() -> None:
    # Smoke check: Page[str] constructs
    page: Page[str] = Page(items=["x", "y"], next_cursor=None, total=2)
    assert page.items == ["x", "y"]
```

- [ ] **Step 2: Run tests — expected FAIL (module missing)**

```bash
uv run pytest tests/v2/shared/test_pagination.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/shared/pagination.py`**

```python
"""Cursor-based pagination primitives.

Cursors encode an integer row ID as a URL-safe base64 string. This keeps
cursors opaque to clients (no raw row IDs leak) and URL-embeddable.

Repository ``filter()`` / ``list()`` methods return ``Page[M]``; callers
propagate ``page.next_cursor`` to fetch subsequent pages.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from typing import Generic, TypeVar

M = TypeVar("M")

def encode_cursor(row_id: int) -> str:
    """Encode a row ID as a URL-safe opaque cursor."""
    raw = str(row_id).encode("ascii")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

def decode_cursor(cursor: str) -> int:
    """Decode a cursor back to its row ID.

    Raises ``ValueError`` on malformed input.
    """
    try:
        # base64 needs padding; add enough to be safe.
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
        return int(raw)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid cursor: {cursor!r}") from exc

@dataclass(slots=True)
class Page(Generic[M]):
    """A page of results with an optional cursor for the next page.

    ``total`` is optional (counting is expensive; only set when requested).
    ``next_cursor`` is ``None`` when no more pages remain.
    """

    items: list[M]
    next_cursor: str | None = None
    total: int | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/shared/test_pagination.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/shared/pagination.py tests/v2/shared/test_pagination.py
git commit -m "feat(v2): add cursor pagination primitives

Page[M] dataclass + encode_cursor/decode_cursor with URL-safe base64.
Used by BaseRepository in Task 13."
```

---

## Task 6: `app/v2/shared/filters.py` — Django-style lookup parser

**Files:**
- Create: `app/v2/shared/filters.py`
- Test: `tests/v2/shared/test_filters.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/shared/test_filters.py
"""Django-style lookup parser tests."""

import pytest
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.v2.shared.errors import ValidationError
from app.v2.shared.filters import parse_filter, split_lookup

class _Base(DeclarativeBase):
    pass

class _DummyModel(_Base):
    __tablename__ = "_dummy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bpm: Mapped[float] = mapped_column(primary_key=False)
    title: Mapped[str] = mapped_column(String(200))
    mood: Mapped[str | None] = mapped_column(String(30), nullable=True)
    variable: Mapped[bool] = mapped_column(Boolean, default=False)

def test_split_lookup_plain_field() -> None:
    assert split_lookup("bpm") == ("bpm", "eq")

def test_split_lookup_with_operator() -> None:
    assert split_lookup("bpm__gte") == ("bpm", "gte")

def test_split_lookup_multi_underscore_field() -> None:
    assert split_lookup("track_id__in") == ("track_id", "in")

def test_parse_filter_equality() -> None:
    clauses = parse_filter(_DummyModel, {"id": 42})
    assert len(clauses) == 1
    # The clause is a SQLAlchemy BinaryExpression; stringifying it gives SQL-ish text.
    assert "id" in str(clauses[0])

def test_parse_filter_gte_lt() -> None:
    clauses = parse_filter(_DummyModel, {"bpm__gte": 120, "bpm__lt": 155})
    assert len(clauses) == 2

def test_parse_filter_in_list() -> None:
    clauses = parse_filter(_DummyModel, {"mood__in": ["peak_time", "acid"]})
    assert len(clauses) == 1

def test_parse_filter_icontains_wildcards() -> None:
    clauses = parse_filter(_DummyModel, {"title__icontains": "mix"})
    assert len(clauses) == 1

def test_parse_filter_isnull_true() -> None:
    clauses = parse_filter(_DummyModel, {"mood__isnull": True})
    assert len(clauses) == 1

def test_parse_filter_range() -> None:
    clauses = parse_filter(_DummyModel, {"bpm__range": [120.0, 155.0]})
    assert len(clauses) == 1

def test_parse_filter_unknown_field_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_filter(_DummyModel, {"nonexistent_field": 1})
    assert "nonexistent_field" in str(exc_info.value)

def test_parse_filter_unknown_operator_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_filter(_DummyModel, {"bpm__bogus": 1})
    assert "bogus" in str(exc_info.value)

def test_parse_filter_allowed_fields_whitelist() -> None:
    # Only "bpm" allowed; "title" must be rejected.
    with pytest.raises(ValidationError):
        parse_filter(_DummyModel, {"title": "Mixdown"}, allowed_fields={"bpm"})

def test_parse_filter_empty_dict_returns_empty() -> None:
    assert parse_filter(_DummyModel, {}) == []
```

- [ ] **Step 2: Run tests — expected FAIL (module missing)**

```bash
uv run pytest tests/v2/shared/test_filters.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/shared/filters.py`**

```python
"""Django-style lookup parser for generic filtering.

Parses dict filters like ``{"bpm__gte": 120, "mood__in": ["peak_time"]}``
into SQLAlchemy clause objects. Used by ``BaseRepository.filter()``.

Supported operators:
    eq         exact match (default when no suffix)
    ne         not equal
    lt / lte   less than / less-or-equal
    gt / gte   greater than / greater-or-equal
    in         value IN list
    not_in     value NOT IN list
    icontains  case-insensitive substring
    contains   case-sensitive substring
    startswith case-sensitive prefix
    endswith   case-sensitive suffix
    isnull     IS NULL if True, IS NOT NULL if False
    range      BETWEEN [lo, hi] — value must be a 2-tuple/list
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any

from sqlalchemy import Column
from sqlalchemy.sql.elements import ColumnElement

from app.v2.shared.errors import ValidationError

# ── Operator table ────────────────────────────────────

def _eq(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col == val

def _ne(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col != val

def _lt(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col < val

def _lte(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col <= val

def _gt(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col > val

def _gte(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col >= val

def _in(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not isinstance(val, (list, tuple, set)):
        raise ValidationError(f"'in' operator requires list/tuple, got {type(val).__name__}")
    return col.in_(list(val))

def _not_in(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not isinstance(val, (list, tuple, set)):
        raise ValidationError(f"'not_in' operator requires list/tuple, got {type(val).__name__}")
    return ~col.in_(list(val))

def _icontains(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.ilike(f"%{val}%")

def _contains(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.like(f"%{val}%")

def _startswith(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.like(f"{val}%")

def _endswith(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.like(f"%{val}")

def _isnull(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not isinstance(val, bool):
        raise ValidationError(f"'isnull' operator requires bool, got {type(val).__name__}")
    return col.is_(None) if val else col.is_not(None)

def _range(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not (isinstance(val, (list, tuple)) and len(val) == 2):
        raise ValidationError(f"'range' operator requires [lo, hi], got {val!r}")
    return col.between(val[0], val[1])

LOOKUP_OPERATORS: dict[str, Callable[[Column[Any], Any], ColumnElement[bool]]] = {
    "eq": _eq,
    "ne": _ne,
    "lt": _lt,
    "lte": _lte,
    "gt": _gt,
    "gte": _gte,
    "in": _in,
    "not_in": _not_in,
    "icontains": _icontains,
    "contains": _contains,
    "startswith": _startswith,
    "endswith": _endswith,
    "isnull": _isnull,
    "range": _range,
}

def split_lookup(key: str) -> tuple[str, str]:
    """Split ``"bpm__gte"`` into ``("bpm", "gte")``. Plain ``"bpm"`` → ``("bpm", "eq")``.

    Uses ``rsplit`` so field names with underscores (``track_id__in``) work correctly.
    """
    if "__" not in key:
        return key, "eq"
    field, op = key.rsplit("__", 1)
    if op not in LOOKUP_OPERATORS:
        # Underscore in field name, no real operator — treat whole thing as field.
        return key, "eq"
    return field, op

def parse_filter(
    model: type[Any],
    where: Mapping[str, Any],
    *,
    allowed_fields: Collection[str] | None = None,
) -> list[ColumnElement[bool]]:
    """Parse a ``where`` dict into a list of SQLAlchemy clauses.

    Args:
        model: SQLAlchemy declarative class.
        where: ``{field[__op]: value}`` mapping.
        allowed_fields: optional whitelist — fields not in the set raise
            ``ValidationError``. ``None`` means all model columns are allowed.

    Raises:
        ValidationError: on unknown field, unknown operator, or disallowed field.
    """
    clauses: list[ColumnElement[bool]] = []
    for raw_key, value in where.items():
        field, op = split_lookup(raw_key)
        if allowed_fields is not None and field not in allowed_fields:
            raise ValidationError(
                f"field {field!r} not allowed (allowed: {sorted(allowed_fields)})",
                details={"field": field, "allowed": list(allowed_fields)},
            )
        column = getattr(model, field, None)
        if column is None:
            raise ValidationError(
                f"unknown field {field!r} on model {model.__name__}",
                details={"field": field, "model": model.__name__},
            )
        if op not in LOOKUP_OPERATORS:
            raise ValidationError(
                f"unknown operator {op!r} (supported: {sorted(LOOKUP_OPERATORS)})",
                details={"operator": op, "supported": sorted(LOOKUP_OPERATORS)},
            )
        clauses.append(LOOKUP_OPERATORS[op](column, value))
    return clauses
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/shared/test_filters.py -v
```
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/shared/filters.py tests/v2/shared/test_filters.py
git commit -m "feat(v2): add Django-style filter parser

14 operators (eq/ne/lt/lte/gt/gte/in/not_in/icontains/contains/
startswith/endswith/isnull/range). Used by BaseRepository.filter()
in Task 13. Field whitelist via allowed_fields parameter."
```

---

## Task 7: `app/v2/config/database.py` + `mcp.py`

**Files:**
- Create: `app/v2/config/database.py`
- Create: `app/v2/config/mcp.py`

- [ ] **Step 1: Write `app/v2/config/database.py`**

```python
"""Database connection settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseSettings):
    """Database connection (Supabase PostgreSQL in prod, SQLite in tests)."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="Async DB connection URL. Supports postgresql+asyncpg or sqlite+aiosqlite.",
    )
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_pool_pre_ping: bool = Field(default=True)
    db_echo: bool = Field(default=False, description="Log all SQL statements.")
    db_statement_cache_size: int = Field(
        default=0,
        description="asyncpg statement cache size. 0 disables cache (pgbouncer workaround).",
    )
```

- [ ] **Step 2: Write `app/v2/config/mcp.py`**

```python
"""MCP server runtime settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class MCPSettings(BaseSettings):
    """MCP-specific knobs: pagination, caching, retries, timeouts, rate limits."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_MCP_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    pagination_size: int = Field(default=100, ge=10, le=1000)
    response_cache_ttl_s: int = Field(default=60, ge=0, le=3600)
    response_size_limit_bytes: int = Field(default=50_000, ge=1000)
    retry_max_attempts: int = Field(default=2, ge=0, le=5)
    retry_base_delay_s: float = Field(default=0.5, ge=0.0, le=10.0)
    sampling_budget_per_session: int = Field(default=10, ge=0, le=100)
    progress_throttle_hz: float = Field(default=1.0, ge=0.1, le=10.0)
    tool_timeout_default_s: float = Field(default=30.0, ge=1.0, le=600.0)
    tool_timeout_heavy_s: float = Field(default=120.0, ge=1.0, le=600.0)
    tool_timeout_batch_s: float = Field(default=600.0, ge=1.0, le=3600.0)
    code_mode_enabled: bool = Field(default=False, description="Experimental (FastMCP 3.1+).")
    log_payloads: bool = Field(default=False, description="Full request/response payloads in logs.")
```

- [ ] **Step 3: Smoke-test import + env override**

Run:
```bash
DJ_DB_ECHO=true uv run python -c "from app.v2.config.database import DatabaseSettings; s=DatabaseSettings(); print(s.database_url, s.db_echo)"
```
Expected: `sqlite+aiosqlite:///:memory: True`.

- [ ] **Step 4: Commit**

```bash
git add app/v2/config/database.py app/v2/config/mcp.py
git commit -m "feat(v2): add database + MCP settings

DatabaseSettings (DJ_ prefix) + MCPSettings (DJ_MCP_ prefix)."
```

---

## Task 8: `app/v2/config/yandex.py` + `audio.py`

**Files:**
- Create: `app/v2/config/yandex.py`
- Create: `app/v2/config/audio.py`

- [ ] **Step 1: Write `app/v2/config/yandex.py`**

```python
"""Yandex Music provider settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class YandexSettings(BaseSettings):
    """Yandex Music OAuth + API tuning."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_YM_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    token: str = Field(default="", description="OAuth token; if empty, provider is unavailable.")
    user_id: int = Field(default=0, ge=0)
    base_url: str = Field(default="https://api.music.yandex.net")
    rate_limit_delay_s: float = Field(default=1.5, ge=0.0, le=30.0)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    library_path: str = Field(default="", description="Local path for downloaded audio files.")
```

- [ ] **Step 2: Write `app/v2/config/audio.py`**

```python
"""Audio analysis pipeline settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AudioSettings(BaseSettings):
    """Audio loader + analyzer configuration (librosa / essentia)."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_AUDIO_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    sample_rate: int = Field(default=22050, ge=8000, le=48000)
    mfcc_coefficients: int = Field(default=13, ge=1, le=40)
    hop_length: int = Field(default=512, ge=128, le=4096)
    n_fft: int = Field(default=2048, ge=256, le=8192)
    process_pool_workers: int = Field(default=2, ge=0, le=16)
    process_worker_cache_size: int = Field(default=4, ge=1, le=32)
    clip_duration_s: float = Field(default=60.0, ge=10.0, le=300.0)
    clip_window_count: int = Field(default=3, ge=1, le=10)
    clip_window_fade_ms: float = Field(default=20.0, ge=0.0, le=200.0)
```

- [ ] **Step 3: Smoke-test**

Run:
```bash
uv run python -c "from app.v2.config.yandex import YandexSettings; from app.v2.config.audio import AudioSettings; print(YandexSettings().base_url, AudioSettings().sample_rate)"
```
Expected: `https://api.music.yandex.net 22050`.

- [ ] **Step 4: Commit**

```bash
git add app/v2/config/yandex.py app/v2/config/audio.py
git commit -m "feat(v2): add yandex + audio settings

YandexSettings (DJ_YM_ prefix) + AudioSettings (DJ_AUDIO_ prefix)."
```

---

## Task 9: `app/v2/config/{transition,optimization,discovery,delivery}.py`

**Files:**
- Create: `app/v2/config/transition.py`
- Create: `app/v2/config/optimization.py`
- Create: `app/v2/config/discovery.py`
- Create: `app/v2/config/delivery.py`

- [ ] **Step 1: Write `app/v2/config/transition.py`**

```python
"""Transition scoring settings (weights, thresholds, cache)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class TransitionSettings(BaseSettings):
    """6-component scoring weights + hard constraints + cache."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_TRANSITION_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    weight_bpm: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_harmonic: float = Field(default=0.12, ge=0.0, le=1.0)
    weight_energy: float = Field(default=0.18, ge=0.0, le=1.0)
    weight_spectral: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_groove: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_timbral: float = Field(default=0.15, ge=0.0, le=1.0)

    hard_reject_bpm_diff: float = Field(default=10.0, ge=0.0, le=100.0)
    hard_reject_camelot_dist: int = Field(default=5, ge=0, le=12)
    hard_reject_energy_gap_lufs: float = Field(default=6.0, ge=0.0, le=30.0)

    cache_ttl_s: int = Field(default=3600, ge=0)
    cache_max_size: int = Field(default=10_000, ge=100)

    scoring_bpm_confidence_floor: float = Field(default=0.3, ge=0.0, le=1.0)
    variable_tempo_penalty: float = Field(default=0.05, ge=0.0, le=0.5)
```

- [ ] **Step 2: Write `app/v2/config/optimization.py`**

```python
"""Set optimization algorithm settings (GA + greedy)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class OptimizationSettings(BaseSettings):
    """Genetic algorithm knobs."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_GA_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    population_size: int = Field(default=50, ge=10, le=500)
    max_generations: int = Field(default=100, ge=10, le=1000)
    mutation_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    elitism_rate: float = Field(default=0.1, ge=0.0, le=0.5)
    tournament_size: int = Field(default=5, ge=2, le=20)
    convergence_threshold: int = Field(default=20, ge=5, le=200)
    two_opt_iterations: int = Field(default=50, ge=0, le=500)
```

- [ ] **Step 3: Write `app/v2/config/discovery.py`**

```python
"""Discovery / expansion settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class DiscoverySettings(BaseSettings):
    """Similar-track discovery + playlist expansion."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_DISCOVERY_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    similar_default_limit: int = Field(default=20, ge=1, le=200)
    expand_default_target: int = Field(default=500, ge=10, le=20_000)
    expand_max_bfs_depth: int = Field(default=5, ge=1, le=20)
    default_min_duration_ms: int = Field(default=120_000, ge=0)
    default_max_duration_ms: int = Field(default=900_000, ge=0)
    feedback_boost_factor: float = Field(default=1.5, ge=0.0, le=10.0)
    feedback_penalty_factor: float = Field(default=0.1, ge=0.0, le=1.0)
    prefetch_top_n: int = Field(default=3, ge=0, le=20)
    prefetch_max_l3: int = Field(default=2, ge=0, le=20)
```

- [ ] **Step 4: Write `app/v2/config/delivery.py`**

```python
"""Set delivery + export settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class DeliverySettings(BaseSettings):
    """Deliverable output paths + format toggles."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_DELIVERY_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    output_dir: str = Field(default="generated-sets", description="Root dir for exports.")
    copy_audio_files: bool = Field(default=True)
    emit_m3u8: bool = Field(default=True)
    emit_rekordbox_xml: bool = Field(default=False)
    emit_json_guide: bool = Field(default=True)
    emit_cheatsheet: bool = Field(default=True)
    icloud_min_download_ratio: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Skip copying files whose local size is < ratio * metadata size (icloud stub).",
    )
```

- [ ] **Step 5: Smoke-test**

Run:
```bash
uv run python -c "
from app.v2.config.transition import TransitionSettings
from app.v2.config.optimization import OptimizationSettings
from app.v2.config.discovery import DiscoverySettings
from app.v2.config.delivery import DeliverySettings
print('w_bpm=', TransitionSettings().weight_bpm)
print('pop=', OptimizationSettings().population_size)
print('exp_target=', DiscoverySettings().expand_default_target)
print('out=', DeliverySettings().output_dir)
"
```
Expected: `w_bpm= 0.2`, `pop= 50`, `exp_target= 500`, `out= generated-sets`.

- [ ] **Step 6: Commit**

```bash
git add app/v2/config/transition.py app/v2/config/optimization.py \
         app/v2/config/discovery.py app/v2/config/delivery.py
git commit -m "feat(v2): add transition/optimization/discovery/delivery settings

4 per-domain Settings classes with distinct env prefixes."
```

---

## Task 10: `app/v2/config/__init__.py` — Settings facade

**Files:**
- Create: `app/v2/config/__init__.py`
- Test: `tests/v2/config/test_settings_facade.py`

- [ ] **Step 1: Write failing test**

```python
# tests/v2/config/test_settings_facade.py
"""Settings facade tests."""

import pytest

from app.v2.config import Settings, get_settings

def test_facade_exposes_all_domains() -> None:
    s = get_settings()
    assert hasattr(s, "database")
    assert hasattr(s, "yandex")
    assert hasattr(s, "audio")
    assert hasattr(s, "transition")
    assert hasattr(s, "optimization")
    assert hasattr(s, "discovery")
    assert hasattr(s, "delivery")
    assert hasattr(s, "mcp")

def test_facade_is_cached() -> None:
    assert get_settings() is get_settings()

def test_settings_construction_without_env() -> None:
    s = Settings()
    assert s.database.database_url.startswith("sqlite")
    assert s.transition.weight_bpm == 0.20

def test_reset_cache_rebuilds_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    first = get_settings()
    assert first.audio.sample_rate == 22050
    # Change env + clear cache.
    monkeypatch.setenv("DJ_AUDIO_SAMPLE_RATE", "44100")
    from app.v2.config import reset_settings_cache

    reset_settings_cache()
    second = get_settings()
    assert second.audio.sample_rate == 44100
    assert second is not first
```

- [ ] **Step 2: Run test — expected FAIL**

```bash
uv run pytest tests/v2/config/test_settings_facade.py -v
```
Expected: `ImportError` on `Settings` or `get_settings`.

- [ ] **Step 3: Write `app/v2/config/__init__.py`**

```python
"""Settings facade — aggregates per-domain Settings classes.

Usage:
    from app.v2.config import get_settings

    settings = get_settings()
    print(settings.transition.weight_bpm)

All per-domain classes read from environment independently (each has its own
``env_prefix``). Facade is cached via ``lru_cache`` — call
``reset_settings_cache()`` in tests if env changes between calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.v2.config.audio import AudioSettings
from app.v2.config.database import DatabaseSettings
from app.v2.config.delivery import DeliverySettings
from app.v2.config.discovery import DiscoverySettings
from app.v2.config.mcp import MCPSettings
from app.v2.config.optimization import OptimizationSettings
from app.v2.config.transition import TransitionSettings
from app.v2.config.yandex import YandexSettings

__all__ = [
    "Settings",
    "get_settings",
    "reset_settings_cache",
    "AudioSettings",
    "DatabaseSettings",
    "DeliverySettings",
    "DiscoverySettings",
    "MCPSettings",
    "OptimizationSettings",
    "TransitionSettings",
    "YandexSettings",
]

@dataclass(frozen=True, slots=True)
class Settings:
    """Aggregate of per-domain Settings. Construct with ``get_settings()``."""

    database: DatabaseSettings
    yandex: YandexSettings
    audio: AudioSettings
    transition: TransitionSettings
    optimization: OptimizationSettings
    discovery: DiscoverySettings
    delivery: DeliverySettings
    mcp: MCPSettings

    def __init__(self) -> None:  # type: ignore[misc]
        object.__setattr__(self, "database", DatabaseSettings())
        object.__setattr__(self, "yandex", YandexSettings())
        object.__setattr__(self, "audio", AudioSettings())
        object.__setattr__(self, "transition", TransitionSettings())
        object.__setattr__(self, "optimization", OptimizationSettings())
        object.__setattr__(self, "discovery", DiscoverySettings())
        object.__setattr__(self, "delivery", DeliverySettings())
        object.__setattr__(self, "mcp", MCPSettings())

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached process-wide Settings instance."""
    return Settings()

def reset_settings_cache() -> None:
    """Clear the cached Settings. Use in tests after env mutation."""
    get_settings.cache_clear()
```

- [ ] **Step 4: Run test — expected PASS**

```bash
uv run pytest tests/v2/config/test_settings_facade.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/config/__init__.py tests/v2/config/test_settings_facade.py
git commit -m "feat(v2): add Settings facade with lru_cache

Settings dataclass aggregates 8 per-domain Settings objects.
get_settings() is cached; reset_settings_cache() for tests."
```

---

## Task 11: `app/v2/registry/entity.py` — EntityRegistry

**Files:**
- Create: `app/v2/registry/entity.py`
- Test: `tests/v2/registry/test_entity_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/registry/test_entity_registry.py
"""EntityRegistry tests."""

from collections.abc import Mapping

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.v2.registry.entity import EntityConfig, EntityRegistry
from app.v2.shared.errors import NotFoundError

class _Base(DeclarativeBase):
    pass

class _WidgetModel(_Base):
    __tablename__ = "_widgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

class WidgetView(BaseModel):
    id: int
    name: str

class WidgetFilter(BaseModel):
    id: int | None = None

class WidgetCreate(BaseModel):
    name: str

class WidgetUpdate(BaseModel):
    name: str | None = None

@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Reset the registry between tests."""
    EntityRegistry._registry.clear()  # type: ignore[attr-defined]

def _make_config(**overrides: object) -> EntityConfig:
    base: Mapping[str, object] = {
        "name": "widget",
        "model": _WidgetModel,
        "repo_attr": "widgets",
        "view_schema": WidgetView,
        "filter_schema": WidgetFilter,
        "create_schema": WidgetCreate,
        "update_schema": WidgetUpdate,
        "allowed_ops": frozenset({"list", "get", "create"}),
        "field_presets": {"id": ["id"], "full": "*"},
        "default_preset": "id",
        "searchable_fields": ("name",),
        "filterable_fields": {"id": ("eq", "in")},
        "sortable_fields": ("id", "name"),
        "relations": {},
        "tags": frozenset({"namespace:test"}),
    }
    return EntityConfig(**{**base, **overrides})  # type: ignore[arg-type]

def test_register_and_get() -> None:
    cfg = _make_config()
    EntityRegistry.register(cfg)
    assert EntityRegistry.get("widget") is cfg

def test_get_unknown_raises_not_found() -> None:
    with pytest.raises(NotFoundError) as exc_info:
        EntityRegistry.get("bogus")
    assert "bogus" in str(exc_info.value)

def test_names_returns_sorted_list() -> None:
    EntityRegistry.register(_make_config(name="zebra"))
    EntityRegistry.register(_make_config(name="alpha"))
    assert EntityRegistry.names() == ["alpha", "zebra"]

def test_register_duplicate_raises() -> None:
    EntityRegistry.register(_make_config())
    with pytest.raises(ValueError) as exc_info:
        EntityRegistry.register(_make_config())
    assert "widget" in str(exc_info.value)

def test_config_is_frozen() -> None:
    cfg = _make_config()
    with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError subclass
        cfg.name = "other"  # type: ignore[misc]

def test_allowed_ops_validation() -> None:
    cfg = _make_config()
    assert "list" in cfg.allowed_ops
    assert "delete" not in cfg.allowed_ops

def test_has_handler_flags() -> None:
    cfg_default = _make_config()
    assert cfg_default.create_handler is None

    async def fake_handler(ctx, uow, data):  # type: ignore[no-untyped-def]
        return {}

    cfg_custom = _make_config(create_handler=fake_handler)
    assert cfg_custom.create_handler is fake_handler
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/registry/test_entity_registry.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/registry/entity.py`**

```python
"""EntityRegistry — declarative configuration for generic CRUD tools.

Per blueprint §5. An EntityConfig maps an entity name (e.g. "track") to:
- ORM model + repository attribute on UnitOfWork
- Pydantic schemas (View, Filter, Create, Update)
- Allowed operations + visibility tags
- Field presets for projection, searchable/filterable/sortable fields
- Relations that can be ``include_relations`` ed
- Optional custom handlers for create/update/delete (side-effects)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel

from app.v2.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase

# Handler signature: (ctx, uow, data) -> view-dict(s)
HandlerCallable = Callable[
    [Any, Any, dict[str, Any]],
    Awaitable[dict[str, Any] | list[dict[str, Any]]],
]

Operation = Literal["list", "get", "create", "update", "delete", "aggregate"]
_FieldPreset = Sequence[str] | Literal["*"]

@dataclass(frozen=True, slots=True)
class EntityConfig:
    """Declarative entity configuration. All fields required except handlers."""

    name: str
    model: type["DeclarativeBase"]
    repo_attr: str
    view_schema: type[BaseModel]
    filter_schema: type[BaseModel]
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    allowed_ops: frozenset[Operation]
    field_presets: Mapping[str, _FieldPreset]
    default_preset: str
    searchable_fields: Sequence[str]
    filterable_fields: Mapping[str, Sequence[str]]
    sortable_fields: Sequence[str]
    relations: Mapping[str, str]
    tags: frozenset[str]

    # Handlers for side-effect CRUD. None → default repo behaviour.
    create_handler: HandlerCallable | None = None
    update_handler: HandlerCallable | None = None
    delete_handler: HandlerCallable | None = None

class EntityRegistry:
    """Process-wide registry of EntityConfig objects, keyed by entity name.

    Registration happens once at server startup (see
    ``app/v2/server/lifespan.py`` in Phase 5). Lookup is O(1).
    """

    _registry: ClassVar[dict[str, EntityConfig]] = {}

    @classmethod
    def register(cls, config: EntityConfig) -> None:
        """Register an EntityConfig. Raises ``ValueError`` on duplicate name."""
        if config.name in cls._registry:
            raise ValueError(f"entity {config.name!r} already registered")
        cls._registry[config.name] = config

    @classmethod
    def get(cls, name: str) -> EntityConfig:
        """Return the config for ``name``. Raises ``NotFoundError`` if unknown."""
        cfg = cls._registry.get(name)
        if cfg is None:
            raise NotFoundError("entity", name)
        return cfg

    @classmethod
    def names(cls) -> list[str]:
        """Return all registered entity names, sorted alphabetically."""
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """Remove all registrations. Intended for tests only."""
        cls._registry.clear()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/registry/test_entity_registry.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/registry/entity.py tests/v2/registry/test_entity_registry.py
git commit -m "feat(v2): add EntityRegistry + EntityConfig dataclass

Frozen EntityConfig per aggregate root. EntityRegistry.register/get/names/clear.
Handlers for side-effect create/update/delete default to None."
```

---

## Task 12: `app/v2/registry/provider.py` — ProviderRegistry

**Files:**
- Create: `app/v2/registry/provider.py`
- Test: `tests/v2/registry/test_provider_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/registry/test_provider_registry.py
"""ProviderRegistry + Provider protocol tests."""

import pytest

from app.v2.registry.provider import Provider, ProviderRegistry
from app.v2.shared.errors import NotFoundError

class _FakeProvider:
    """Minimal Provider implementation for tests."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    async def read(self, entity: str, id: str | None, params: dict) -> dict:  # type: ignore[type-arg]
        return {"provider": self.name, "entity": entity, "id": id}

    async def write(self, entity: str, operation: str, params: dict) -> dict:  # type: ignore[type-arg]
        return {"provider": self.name, "op": operation}

    async def search(self, query: str, type: str, limit: int) -> dict:  # type: ignore[type-arg]
        return {"query": query, "type": type, "limit": limit}

    async def download_audio(self, track_id: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def close(self) -> None:
        self.closed = True

def test_protocol_runtime_check() -> None:
    """Any class matching the shape is a Provider."""
    p = _FakeProvider("yandex")
    assert isinstance(p, Provider)

def test_register_and_get() -> None:
    reg = ProviderRegistry()
    p = _FakeProvider("yandex")
    reg.register(p)
    assert reg.get("yandex") is p

def test_get_unknown_raises() -> None:
    reg = ProviderRegistry()
    with pytest.raises(NotFoundError):
        reg.get("spotify")

def test_default_follows_first_registered_when_flagged() -> None:
    reg = ProviderRegistry()
    p1 = _FakeProvider("yandex")
    p2 = _FakeProvider("spotify")
    reg.register(p1, default=True)
    reg.register(p2)
    assert reg.default() is p1

def test_default_raises_when_none_set() -> None:
    reg = ProviderRegistry()
    with pytest.raises(NotFoundError) as exc_info:
        reg.default()
    assert "default" in str(exc_info.value).lower()

def test_names_sorted() -> None:
    reg = ProviderRegistry()
    reg.register(_FakeProvider("zeta"))
    reg.register(_FakeProvider("alpha"))
    assert reg.names() == ["alpha", "zeta"]

def test_register_duplicate_raises() -> None:
    reg = ProviderRegistry()
    reg.register(_FakeProvider("yandex"))
    with pytest.raises(ValueError):
        reg.register(_FakeProvider("yandex"))

def test_contains_membership() -> None:
    reg = ProviderRegistry()
    reg.register(_FakeProvider("yandex"))
    assert "yandex" in reg
    assert "spotify" not in reg

@pytest.mark.asyncio
async def test_close_all_closes_each() -> None:
    reg = ProviderRegistry()
    p1 = _FakeProvider("yandex")
    p2 = _FakeProvider("spotify")
    reg.register(p1)
    reg.register(p2)
    await reg.close_all()
    assert p1.closed is True
    assert p2.closed is True
    assert reg.names() == []
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/registry/test_provider_registry.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/registry/provider.py`**

```python
"""Provider Protocol + ProviderRegistry.

Per blueprint §6. A Provider represents an external music platform (Yandex
Music, Spotify, Beatport, SoundCloud). All have the same surface via the
``Provider`` protocol; the generic ``provider_read`` / ``provider_write`` /
``provider_search`` tools dispatch via ``ProviderRegistry``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.v2.shared.errors import NotFoundError

@runtime_checkable
class Provider(Protocol):
    """Universal interface for an external music platform."""

    name: str

    async def read(self, entity: str, id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        """Read an entity by id or list with params. Entity-specific semantics per adapter."""

    async def write(
        self, entity: str, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Write operation (playlist add/remove, like/unlike, create/rename/delete)."""

    async def search(self, query: str, type: str, limit: int) -> dict[str, Any]:
        """Search catalog. ``type`` is one of 'tracks' / 'albums' / 'artists' / 'playlists'."""

    async def download_audio(self, track_id: str) -> Path:
        """Download audio, return local file path."""

    async def close(self) -> None:
        """Release network resources."""

class ProviderRegistry:
    """Container for registered Provider adapters, with optional default."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._default: str | None = None

    def register(self, provider: Provider, *, default: bool = False) -> None:
        """Register a Provider. Raises ``ValueError`` on duplicate name."""
        if provider.name in self._providers:
            raise ValueError(f"provider {provider.name!r} already registered")
        self._providers[provider.name] = provider
        if default or self._default is None:
            self._default = provider.name

    def get(self, name: str) -> Provider:
        """Return adapter by name. Raises ``NotFoundError`` if unknown."""
        p = self._providers.get(name)
        if p is None:
            raise NotFoundError("provider", name)
        return p

    def default(self) -> Provider:
        """Return the default provider. Raises ``NotFoundError`` if none set."""
        if self._default is None:
            raise NotFoundError("provider", "default")
        return self._providers[self._default]

    def names(self) -> list[str]:
        """Return registered provider names, sorted."""
        return sorted(self._providers.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._providers

    async def close_all(self) -> None:
        """Close every provider and empty the registry."""
        for p in list(self._providers.values()):
            await p.close()
        self._providers.clear()
        self._default = None
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/registry/test_provider_registry.py -v
```
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/registry/provider.py tests/v2/registry/test_provider_registry.py
git commit -m "feat(v2): add Provider protocol + ProviderRegistry

runtime_checkable Protocol defines read/write/search/download_audio/close.
ProviderRegistry with default + close_all."
```

---

## Task 13: `tests/v2/conftest.py` — shared test fixtures

**Files:**
- Create: `tests/v2/conftest.py`

- [ ] **Step 1: Write `tests/v2/conftest.py`**

```python
"""Shared fixtures for v2 tests.

Provides:
- ``engine``: session-scoped aiosqlite in-memory engine
- ``session``: function-scoped AsyncSession with rollback

Both are wired for SQLAlchemy 2.0 async. In tests that use the ORM, the
module should define its own declarative Base + models (or import them).
The fixture creates all tables belonging to whatever Base it is given via
the ``register_base`` helper.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Fresh in-memory SQLite engine per test."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    try:
        yield eng
    finally:
        await eng.dispose()

@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)

@pytest_asyncio.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        try:
            yield s
        finally:
            await s.rollback()

@pytest.fixture
def create_tables() -> Callable[[type[DeclarativeBase], AsyncEngine], AsyncIterator[None]]:
    """Helper returning an async context manager for creating tables per-Base."""

    async def _create(base: type[DeclarativeBase], eng: AsyncEngine) -> None:
        async with eng.begin() as conn:
            await conn.run_sync(base.metadata.create_all)

    return _create  # type: ignore[return-value]
```

- [ ] **Step 2: Smoke-test fixture loads**

Run:
```bash
uv run pytest tests/v2/ -v --collect-only | head -30
```
Expected: no errors; collection shows existing tests.

- [ ] **Step 3: Commit**

```bash
git add tests/v2/conftest.py
git commit -m "test(v2): add shared engine + session fixtures for v2 tests"
```

---

## Task 14: `app/v2/repositories/base.py` — BaseRepository[M]

**Files:**
- Create: `app/v2/repositories/base.py`
- Test: `tests/v2/repositories/test_base_repository.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/repositories/test_base_repository.py
"""BaseRepository tests on a toy model."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.v2.repositories.base import BaseRepository
from app.v2.shared.errors import NotFoundError, ValidationError

class _Base(DeclarativeBase):
    pass

class _Widget(_Base):
    __tablename__ = "_widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    weight: Mapped[float] = mapped_column(default=0.0)
    active: Mapped[bool] = mapped_column(default=True)

class WidgetRepository(BaseRepository[_Widget]):
    model = _Widget

@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> WidgetRepository:
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    return WidgetRepository(session)

@pytest_asyncio.fixture
async def repo_seeded(repo: WidgetRepository) -> WidgetRepository:
    for i, (name, weight) in enumerate(
        [("alpha", 1.0), ("beta", 2.5), ("gamma", 3.0), ("delta", 0.5)], start=1
    ):
        await repo.create(id=i, name=name, weight=weight)
    return repo

@pytest.mark.asyncio
async def test_create_and_get(repo: WidgetRepository) -> None:
    w = await repo.create(name="hello", weight=1.0)
    assert w.id is not None
    fetched = await repo.get(w.id)
    assert fetched is not None
    assert fetched.name == "hello"

@pytest.mark.asyncio
async def test_get_missing_returns_none(repo: WidgetRepository) -> None:
    assert await repo.get(99999) is None

@pytest.mark.asyncio
async def test_exists(repo_seeded: WidgetRepository) -> None:
    assert await repo_seeded.exists(1) is True
    assert await repo_seeded.exists(999) is False

@pytest.mark.asyncio
async def test_update(repo_seeded: WidgetRepository) -> None:
    updated = await repo_seeded.update(1, name="renamed")
    assert updated.name == "renamed"
    fetched = await repo_seeded.get(1)
    assert fetched is not None
    assert fetched.name == "renamed"

@pytest.mark.asyncio
async def test_update_missing_raises(repo: WidgetRepository) -> None:
    with pytest.raises(NotFoundError):
        await repo.update(9999, name="x")

@pytest.mark.asyncio
async def test_delete(repo_seeded: WidgetRepository) -> None:
    await repo_seeded.delete(1)
    assert await repo_seeded.get(1) is None

@pytest.mark.asyncio
async def test_delete_missing_raises(repo: WidgetRepository) -> None:
    with pytest.raises(NotFoundError):
        await repo.delete(9999)

@pytest.mark.asyncio
async def test_count_all(repo_seeded: WidgetRepository) -> None:
    assert await repo_seeded.count() == 4

@pytest.mark.asyncio
async def test_count_filtered(repo_seeded: WidgetRepository) -> None:
    assert await repo_seeded.count(where={"weight__gte": 2.0}) == 2

@pytest.mark.asyncio
async def test_filter_basic(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={"active": True}, order=["id"], limit=10)
    assert len(page.items) == 4

@pytest.mark.asyncio
async def test_filter_paginates(repo_seeded: WidgetRepository) -> None:
    page1 = await repo_seeded.filter(where={}, order=["id"], limit=2)
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    page2 = await repo_seeded.filter(where={}, order=["id"], limit=2, cursor=page1.next_cursor)
    assert len(page2.items) == 2
    # No overlap.
    ids1 = {w.id for w in page1.items}
    ids2 = {w.id for w in page2.items}
    assert not (ids1 & ids2)

@pytest.mark.asyncio
async def test_filter_with_gte(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={"weight__gte": 2.0}, order=["id"], limit=10)
    names = sorted(w.name for w in page.items)
    assert names == ["beta", "gamma"]

@pytest.mark.asyncio
async def test_filter_icontains(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={"name__icontains": "a"}, order=["id"], limit=10)
    assert {w.name for w in page.items} == {"alpha", "beta", "gamma", "delta"}

@pytest.mark.asyncio
async def test_filter_in(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(
        where={"name__in": ["alpha", "gamma"]}, order=["id"], limit=10
    )
    assert {w.name for w in page.items} == {"alpha", "gamma"}

@pytest.mark.asyncio
async def test_filter_order_desc(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={}, order=["id_desc"], limit=10)
    assert [w.id for w in page.items] == [4, 3, 2, 1]

@pytest.mark.asyncio
async def test_filter_rejects_unknown_field(repo: WidgetRepository) -> None:
    with pytest.raises(ValidationError):
        await repo.filter(where={"nonexistent": 1}, order=["id"], limit=10)

@pytest.mark.asyncio
async def test_filter_with_total(repo_seeded: WidgetRepository) -> None:
    page = await repo_seeded.filter(where={}, order=["id"], limit=2, with_total=True)
    assert page.total == 4
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/repositories/test_base_repository.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/repositories/base.py`**

```python
"""Generic async BaseRepository[M].

Per blueprint §10. Provides 9 methods covering the common CRUD + filter
surface. Entity-specific repositories subclass and add domain methods.

Repositories **flush but never commit** — transaction boundary is the tool
call, managed by DbSessionMiddleware in Phase 5.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Generic, TypeVar

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.v2.shared.errors import NotFoundError, ValidationError
from app.v2.shared.filters import parse_filter
from app.v2.shared.pagination import Page, decode_cursor, encode_cursor

M = TypeVar("M", bound=DeclarativeBase)

class BaseRepository(Generic[M]):
    """Thin async CRUD + filter. Subclass + set ``model``."""

    model: ClassVar[type[DeclarativeBase]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── single-row ────────────────────────────────────

    async def get(self, id: int) -> M | None:
        return await self.session.get(self.model, id)

    async def exists(self, id: int) -> bool:
        return (await self.get(id)) is not None

    async def create(self, **data: Any) -> M:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj  # type: ignore[return-value]

    async def update(self, id: int, **data: Any) -> M:
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(self.model.__name__, id)
        for key, value in data.items():
            if not hasattr(obj, key):
                raise ValidationError(f"unknown field {key!r} on {self.model.__name__}")
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(self.model.__name__, id)
        await self.session.delete(obj)
        await self.session.flush()

    # ── collection ────────────────────────────────────

    async def count(self, *, where: dict[str, Any] | None = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        for clause in parse_filter(self.model, where or {}):
            stmt = stmt.where(clause)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def filter(
        self,
        *,
        where: dict[str, Any] | None = None,
        order: Sequence[str] | None = None,
        limit: int = 50,
        cursor: str | None = None,
        with_total: bool = False,
    ) -> Page[M]:
        """Filter + sort + paginate.

        - ``where``: Django-style lookups, see ``app.v2.shared.filters``.
        - ``order``: list of ``field`` or ``field_asc`` / ``field_desc``.
        - ``limit``: page size. Fetches limit+1 to detect hasMore.
        - ``cursor``: opaque cursor from prior page's ``next_cursor``.
        - ``with_total``: if True, runs a separate ``count()`` (extra query).
        """
        stmt = select(self.model)

        # WHERE
        for clause in parse_filter(self.model, where or {}):
            stmt = stmt.where(clause)

        # Keyset pagination: the outermost sort col is used for cursor.
        order_clauses = list(order or ["id"])
        # If cursor present, apply keyset predicate on the first sort field.
        if cursor is not None:
            cursor_id = decode_cursor(cursor)
            # We assume the first sort field is a PK-ish integer column.
            first_field = order_clauses[0].removesuffix("_desc").removesuffix("_asc")
            column = getattr(self.model, first_field, None)
            if column is None:
                raise ValidationError(f"unknown order field {first_field!r}")
            if order_clauses[0].endswith("_desc"):
                stmt = stmt.where(column < cursor_id)
            else:
                stmt = stmt.where(column > cursor_id)

        # ORDER BY
        for spec in order_clauses:
            if spec.endswith("_desc"):
                field = spec.removesuffix("_desc")
                direction = "desc"
            elif spec.endswith("_asc"):
                field = spec.removesuffix("_asc")
                direction = "asc"
            else:
                field = spec
                direction = "asc"
            column = getattr(self.model, field, None)
            if column is None:
                raise ValidationError(f"unknown order field {field!r}")
            stmt = stmt.order_by(column.desc() if direction == "desc" else column.asc())

        stmt = stmt.limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor: str | None = None
        if has_more and items:
            first_field = order_clauses[0].removesuffix("_desc").removesuffix("_asc")
            last_row = items[-1]
            next_cursor = encode_cursor(int(getattr(last_row, first_field)))

        total: int | None = None
        if with_total:
            total = await self.count(where=where)

        return Page(items=items, next_cursor=next_cursor, total=total)  # type: ignore[arg-type]
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/repositories/test_base_repository.py -v
```
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/repositories/base.py tests/v2/repositories/test_base_repository.py
git commit -m "feat(v2): add generic BaseRepository[M]

9 methods: get/exists/create/update/delete/count/filter.
Django-style where + keyset pagination + asc/desc order.
with_total toggle for count-on-demand."
```

---

## Task 15: `app/v2/repositories/unit_of_work.py` — UoW skeleton

**Files:**
- Create: `app/v2/repositories/unit_of_work.py`
- Test: `tests/v2/repositories/test_unit_of_work.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/repositories/test_unit_of_work.py
"""UnitOfWork tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.v2.repositories.unit_of_work import UnitOfWork

class _Base(DeclarativeBase):
    pass

class _Widget(_Base):
    __tablename__ = "_widgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

@pytest_asyncio.fixture
async def prepared_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)

@pytest.mark.asyncio
async def test_uow_commits_on_success(
    prepared_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with prepared_factory() as session:
        async with UnitOfWork(session) as uow:
            uow.session.add(_Widget(id=1, name="first"))
    # Reopen and confirm persistence.
    async with prepared_factory() as session:
        found = await session.get(_Widget, 1)
        assert found is not None
        assert found.name == "first"

@pytest.mark.asyncio
async def test_uow_rolls_back_on_exception(
    prepared_factory: async_sessionmaker[AsyncSession],
) -> None:
    class _Boom(Exception): ...

    with pytest.raises(_Boom):
        async with prepared_factory() as session:
            async with UnitOfWork(session) as uow:
                uow.session.add(_Widget(id=2, name="will-rollback"))
                raise _Boom

    async with prepared_factory() as session:
        assert await session.get(_Widget, 2) is None

@pytest.mark.asyncio
async def test_uow_exposes_session(
    prepared_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with prepared_factory() as session:
        uow = UnitOfWork(session)
        assert uow.session is session
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/repositories/test_unit_of_work.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/repositories/unit_of_work.py`**

```python
"""Unit of Work — transaction boundary = tool call.

Per blueprint §10. Phase 1 ships the skeleton with no registered repositories.
Phase 2 adds lazy ``@property`` accessors for each entity's repository as
models land.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

class UnitOfWork:
    """One UoW per tool call. Commit on success, rollback on exception.

    Usage in tools (Phase 3+):
        async def my_tool(uow: UnitOfWork = Depends(get_uow)) -> ...:
            async with uow:
                track = await uow.tracks.get(42)
                ...

    In Phase 1 there are no ``uow.<entity>`` properties yet — Phase 2 adds
    them as each repository lands.
    """

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
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/repositories/test_unit_of_work.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/repositories/unit_of_work.py tests/v2/repositories/test_unit_of_work.py
git commit -m "feat(v2): add UnitOfWork skeleton

Async context manager: commit on clean exit, rollback on exception.
Phase 2 will add lazy repo properties (uow.tracks, uow.playlists, ...)."
```

---

## Task 16: Add import-linter contracts for v2 layer

**Files:**
- Modify: `.importlinter` (append Phase 1 contracts)

- [ ] **Step 1: Read current `.importlinter`**

```bash
cat .importlinter
```
Expected: 6 existing contracts (services-no-mcp, transition-pure, optimization-pure, utils-leaf, api-no-db, engines-no-transport).

- [ ] **Step 2: Append Phase 1 contracts**

Add to the end of `.importlinter`:

```ini

# ──────────────────────────────────────────────────────────────────────
# Phase 1: v2 structural contracts
# ──────────────────────────────────────────────────────────────────────

# app.v2.shared must be leaf — no imports from other app.v2 subpackages.
[importlinter:contract:v2-shared-leaf]
name = app.v2.shared must not import from other v2 subpackages
type = forbidden
source_modules =
    app.v2.shared
forbidden_modules =
    app.v2.config
    app.v2.registry
    app.v2.repositories
    fastmcp
    httpx

# app.v2.config must not depend on domain code.
[importlinter:contract:v2-config-indep]
name = app.v2.config must only depend on pydantic-settings + stdlib
type = forbidden
source_modules =
    app.v2.config
forbidden_modules =
    app.v2.registry
    app.v2.repositories
    fastmcp
    sqlalchemy
    httpx

# app.v2.registry must not depend on repositories (registry is configuration, not behavior).
[importlinter:contract:v2-registry-indep]
name = app.v2.registry must not depend on repositories
type = forbidden
source_modules =
    app.v2.registry
forbidden_modules =
    app.v2.repositories
    fastmcp

# app.v2.repositories must not import FastMCP / HTTP / tools.
[importlinter:contract:v2-repos-no-transport]
name = app.v2.repositories must not import FastMCP or HTTP
type = forbidden
source_modules =
    app.v2.repositories
forbidden_modules =
    fastmcp
    httpx

# Old app must not import v2 (one-way gate during transition).
[importlinter:contract:v2-backflow-gate]
name = app (legacy) must not import from app.v2
type = forbidden
source_modules =
    app.api
    app.audio
    app.audit
    app.bootstrap
    app.camelot
    app.clients
    app.controllers
    app.core
    app.db
    app.engines
    app.entities
    app.export
    app.infrastructure
    app.optimization
    app.providers
    app.schemas
    app.services
    app.templates
    app.transition
    app.ym
forbidden_modules =
    app.v2
```

- [ ] **Step 3: Run import-linter**

```bash
uv run lint-imports
```
Expected: all contracts PASS (11 total: 6 old + 5 new).

- [ ] **Step 4: Commit**

```bash
git add .importlinter
git commit -m "chore(importlinter): add Phase 1 v2 structural contracts

5 contracts: v2-shared-leaf, v2-config-indep, v2-registry-indep,
v2-repos-no-transport, v2-backflow-gate (one-way legacy→v2 barrier)."
```

---

## Task 17: Full v2 test run + make check

**Files:** none (verification only)

- [ ] **Step 1: Run all v2 tests**

```bash
uv run pytest tests/v2/ -v
```
Expected: all tests pass (~56 total from Tasks 2, 5, 6, 10, 11, 12, 14, 15).

- [ ] **Step 2: Run mypy strict on app/v2/**

```bash
uv run mypy app/v2/
```
Expected: no errors.

- [ ] **Step 3: Run ruff on app/v2/ + tests/v2/**

```bash
uv run ruff check app/v2/ tests/v2/
uv run ruff format --check app/v2/ tests/v2/
```
Expected: clean.

- [ ] **Step 4: Run `make check` (existing + v2)**

```bash
make check
```
Expected: lint + typecheck + import-linter + full test suite pass. This confirms **nothing in `app/` has regressed**.

- [ ] **Step 5: Verify BFS/L5 campaign compatibility (static check)**

```bash
# Ensure no v2 imports leaked into scripts that run on VM.
uv run python -c "import ast, pathlib;
for p in pathlib.Path('scripts').rglob('*.py'):
    src = p.read_text()
    assert 'app.v2' not in src, f'{p} imports app.v2 — Phase 1 forbids this'
print('scripts/ clean')"
```
Expected: `scripts/ clean`.

- [ ] **Step 6: Final Phase 1 tag + commit**

```bash
git tag -a phase-1-foundation -m "Phase 1 complete: v2 foundation shell"
git log --oneline dev..HEAD
```
Expected: Task-by-task commit history, all on branch `worktree-phase-1-foundation`.

---

## Self-Review — Spec Coverage

Checklist against blueprint §15.2 (Phase 1 deliverables):

| Blueprint deliverable | Task(s) |
|---|---|
| Directory layout per §3 | Task 1 |
| `app/v2/shared/errors.py`, `ids.py`, `time.py`, `pagination.py`, `filters.py` | Tasks 2, 3, 4, 5, 6 |
| `app/v2/config/` split (8 domain files + facade) | Tasks 7, 8, 9, 10 |
| `app/v2/registry/entity.py` (EntityConfig + EntityRegistry) | Task 11 |
| `app/v2/registry/provider.py` (Provider Protocol + ProviderRegistry) | Task 12 |
| `app/v2/repositories/base.py` (BaseRepository[M] + Django filter) | Task 14 |
| `app/v2/repositories/unit_of_work.py` | Task 15 |
| `app/v2/` can import from `app/` (not vice versa) — import-linter | Task 16 |
| Unit tests for `BaseRepository.filter()`, UoW lifecycle, EntityRegistry | Tasks 5, 6, 11, 14, 15 |
| Exit: `uv run pytest tests/v2/` green, `app/` untouched | Task 17 |

**Explicitly out of scope for Phase 1** (per blueprint §15.2 — "server scaffold"):
- `app/v2/server/` (bootstrap, middleware, DI) → Phase 5
- Models + entity registration → Phase 2
- Tools + handlers → Phase 3
- Resources + prompts → Phase 4

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-phase-1-foundation.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration, protects my context window. Appropriate for Phase 1 because tasks are self-contained and TDD-disciplined.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review. Appropriate if you want to observe every keystroke or make mid-stream corrections.

**Which approach?**
