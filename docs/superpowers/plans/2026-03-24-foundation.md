# Foundation Implementation Plan (Sub-Project #1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data foundation — models, repositories, and core utilities — that all other sub-projects depend on.

**Architecture:** SQLAlchemy 2.0 async models with 44 tables, repository pattern (flush-only), pydantic-settings config, typed error hierarchy. All values from `settings.*` or `constants.py`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, aiosqlite, Pydantic v2, pydantic-settings, Alembic, pytest, pytest-asyncio

**Spec:** @docs/superpowers/specs/2026-03-24-dj-music-plugin-design.md
**Domain Reference:** @docs/domain-glossary.md
**Architecture Reference:** @docs/architecture.md

**CLI Tools:** use `fd` (not find), `rg` (not grep), `ast-grep` for code patterns, `jq`/`yq` for data, `fzf` for interactive selection where useful.

---

## Complete Table Enumeration (44 tables)

All tables must exist after Task 14. Verify with:
```bash
rg "^class.*Base\)" app/models/ --no-heading | wc -l  # should be 44
```

| # | Table | File | Key Constraints |
|---|-------|------|-----------------|
| 1 | `tracks` | track.py | duration_ms > 0, status 0-1 |
| 2 | `artists` | track.py | name unique |
| 3 | `genres` | track.py | parent_id self-FK |
| 4 | `labels` | track.py | name unique |
| 5 | `releases` | track.py | label FK, date |
| 6 | `track_artists` | track.py | track FK + artist FK + role |
| 7 | `track_genres` | track.py | track FK + genre FK |
| 8 | `track_labels` | track.py | track FK + label FK |
| 9 | `track_releases` | track.py | track FK + release FK |
| 10 | `track_external_ids` | track.py | track FK + platform + external_id |
| 11 | `track_audio_features_computed` | audio.py | 47 feature fields, BPM 20-300, confidence 0-1 |
| 12 | `track_sections` | audio.py | type 0-11, energy 0-1 |
| 13 | `embeddings` | audio.py | type, dimensions, vector blob |
| 14 | `timeseries_references` | audio.py | storage_uri, frame_count |
| 15 | `feature_extraction_runs` | audio.py | pipeline name/version, status |
| 16 | `dj_library_items` | library.py | file_path, hash, size, bitrate |
| 17 | `dj_beatgrids` | library.py | BPM 20-300, confidence 0-1 |
| 18 | `dj_beatgrid_change_points` | library.py | beatgrid FK, position |
| 19 | `dj_cue_points` | library.py | kind 0-7, hotcue_index 0-15 |
| 20 | `dj_saved_loops` | library.py | in/out positions, length |
| 21 | `keys` | key.py | key_code 0-23, 24 static rows |
| 22 | `key_edges` | key.py | from/to key FK, distance, weight |
| 23 | `dj_playlists` | playlist.py | name, parent FK, source_of_truth |
| 24 | `dj_playlist_items` | playlist.py | sort_index, track FK |
| 25 | `dj_sets` | set.py | target_duration, bpm_min/max |
| 26 | `dj_set_versions` | set.py | label, quality_score 0-1 |
| 27 | `dj_set_items` | set.py | sort_index, track FK, pinned |
| 28 | `dj_set_constraints` | set.py | type, value JSON |
| 29 | `dj_set_feedback` | set.py | rating 1-5, feedback_type |
| 30 | `transitions` | transition.py | from/to track FK, 8 score fields 0-1 |
| 31 | `transition_candidates` | transition.py | bpm_distance, key_distance |
| 32 | `yandex_metadata` | platform.py | yandex_track_id, album fields |
| 33 | `spotify_metadata` | platform.py | spotify_track_id, popularity |
| 34 | `spotify_album_metadata` | platform.py | album details |
| 35 | `spotify_artist_metadata` | platform.py | artist details |
| 36 | `spotify_playlist_metadata` | platform.py | playlist details |
| 37 | `spotify_audio_features` | platform.py | danceability, energy, etc. |
| 38 | `beatport_metadata` | platform.py | beatport_track_id, genre |
| 39 | `soundcloud_metadata` | platform.py | 20+ fields |
| 40 | `providers` | ingestion.py | 4 static rows |
| 41 | `provider_track_ids` | ingestion.py | track FK + provider FK |
| 42 | `raw_provider_responses` | ingestion.py | raw JSON, fetched_at |
| 43 | `app_exports` | export.py | target_app, format, path, size |
| 44 | `track_external_ids` is #10 — | — | replaced below |

> Note: `track_external_ids` (#10) may be merged with `provider_track_ids` (#41) depending on implementation. If merged, add one more Spotify sub-table to reach 44. Verify final count after implementation.

---

## File Map

### Core Infrastructure
- Create: `app/__init__.py`
- Create: `app/config.py` — Settings class (pydantic-settings)
- Create: `app/core/__init__.py`
- Create: `app/core/constants.py` — enums, Camelot keys, domain constants
- Create: `app/core/errors.py` — DJMusicError hierarchy
- Create: `app/core/pagination.py` — cursor-based pagination
- Create: `app/core/entity_resolver.py` — flexible entity reference resolution
- Create: `app/core/camelot.py` — Camelot wheel logic
- Create: `app/core/schemas.py` — shared Pydantic response models (TrackBrief, TrackStandard, etc.)

### Models (44 tables across 11 files)
- Create: `app/models/__init__.py`
- Create: `app/models/base.py` — DeclarativeBase, TimestampMixin
- Create: `app/models/track.py` — 10 tables (Track + related)
- Create: `app/models/audio.py` — 5 tables (features, sections, embeddings)
- Create: `app/models/library.py` — 5 tables (items, beatgrid, cues, loops)
- Create: `app/models/key.py` — 2 tables (Key, KeyEdge)
- Create: `app/models/playlist.py` — 2 tables (Playlist, PlaylistItem)
- Create: `app/models/set.py` — 5 tables (Set, Version, Item, Constraint, Feedback)
- Create: `app/models/transition.py` — 2 tables (Transition, Candidate)
- Create: `app/models/platform.py` — 8 tables (YM, Spotify×5, Beatport, SoundCloud)
- Create: `app/models/ingestion.py` — 3 tables (Provider, ProviderTrackId, RawResponse)
- Create: `app/models/export.py` — 1 table (AppExport)

### Repositories (7 files)
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/base.py` — BaseRepository (async CRUD + pagination)
- Create: `app/repositories/track.py` — TrackRepository (search, filter)
- Create: `app/repositories/playlist.py` — PlaylistRepository (items management)
- Create: `app/repositories/set.py` — SetRepository (versions, items)
- Create: `app/repositories/feature.py` — FeatureRepository
- Create: `app/repositories/transition.py` — TransitionRepository
- Create: `app/repositories/export.py` — ExportRepository

### Tests
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` — async DB fixtures, seeded data
- Create: `tests/test_core/{test_constants,test_errors,test_camelot,test_pagination,test_entity_resolver,test_schemas}.py`
- Create: `tests/test_models/{test_base,test_track,test_audio,test_library,test_key,test_playlist,test_set,test_transition,test_platform}.py`
- Create: `tests/test_repositories/{test_base,test_track,test_playlist,test_set}.py`

### Alembic
- Create: `app/migrations/env.py`
- Modify: `alembic.ini`

---

## Task 1: Project Setup & Dependencies

**Files:**
- Modify: `pyproject.toml` (verify deps)
- Create: `app/__init__.py`
- Create: `alembic.ini`
- Create: `app/migrations/env.py`

- [ ] **Step 1: Install dependencies**

```bash
uv sync --extra dev
```

- [ ] **Step 2: Verify key packages**

```bash
uv run python -c "
import sqlalchemy, fastmcp, pydantic, pydantic_settings
print(f'SQLAlchemy {sqlalchemy.__version__}')
print(f'FastMCP {fastmcp.__version__}')
print(f'Pydantic {pydantic.__version__}')
"
```

- [ ] **Step 3: Initialize Alembic**

```bash
uv run alembic init app/migrations
```

Edit `alembic.ini`: set `script_location = app/migrations`.
Edit `app/migrations/env.py`: async engine, import all models.

- [ ] **Step 4: Verify test runner**

```bash
mkdir -p tests && touch tests/__init__.py
uv run pytest --co -q  # should show "no tests ran"
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock alembic.ini app/__init__.py app/migrations/
git commit -m "chore: initialize project with dependencies and Alembic

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Core — Config, Constants, Errors

**Files:**
- Create: `app/config.py`, `app/core/__init__.py`, `app/core/constants.py`, `app/core/errors.py`
- Test: `tests/test_core/test_constants.py`, `tests/test_core/test_errors.py`

- [ ] **Step 1: Write tests for constants**

```python
# tests/test_core/test_constants.py
from app.core.constants import (
    TrackStatus, SectionType, CueKind, TechnoSubgenre,
    ExportFormat, TargetApp, Provider, SetTemplate,
    CAMELOT_KEYS, BPM_MIN, BPM_MAX, DEFAULT_TRANSITION_WEIGHTS,
)

def test_track_status_values():
    assert TrackStatus.ACTIVE == 0
    assert TrackStatus.ARCHIVED == 1

def test_techno_subgenres_count_and_order():
    subs = list(TechnoSubgenre)
    assert len(subs) == 15
    assert subs[0] == TechnoSubgenre.AMBIENT_DUB
    assert subs[-1] == TechnoSubgenre.HARD_TECHNO

def test_camelot_keys_24_valid():
    assert len(CAMELOT_KEYS) == 24
    for code, (camelot, name) in CAMELOT_KEYS.items():
        assert 0 <= code <= 23
        assert camelot[-1] in ("A", "B")
        assert 1 <= int(camelot[:-1]) <= 12

def test_section_types_12():
    """REQUIREMENTS §10.2: section types 0-11."""
    assert len(SectionType) == 12

def test_cue_kinds_8():
    """REQUIREMENTS §10.2: cue kinds 0-7."""
    assert len(CueKind) == 8
    assert CueKind.CUE == 0
    assert max(CueKind) == 7

def test_set_templates_8():
    assert len(SetTemplate) == 8

def test_providers_4():
    assert len(Provider) == 4

def test_transition_weights_sum_and_keys():
    assert abs(sum(DEFAULT_TRANSITION_WEIGHTS.values()) - 1.0) < 0.001
    assert set(DEFAULT_TRANSITION_WEIGHTS.keys()) == {
        "bpm", "harmonic", "energy", "spectral", "groove"
    }
```

- [ ] **Step 2: Run tests — fail**

```bash
uv run pytest tests/test_core/test_constants.py -v
```

- [ ] **Step 3: Implement constants.py**

Per design spec §14.3. **Important fixes from review:**
- `SectionType`: 12 values (0-11), add `SECTION_11 = 11` or appropriate name
- `CueKind`: exactly 8 values (0-7), no MEMORY=8

- [ ] **Step 4: Run tests — pass**

- [ ] **Step 5: Write tests for errors**

```python
# tests/test_core/test_errors.py
from app.core.errors import (
    DJMusicError, NotFoundError, ValidationError, ConflictError,
    PipelineError, AnalyzerUnavailableError, AnalysisTimeoutError,
    YandexMusicError, RateLimitedError, AuthFailedError, APIError,
    ExportError,
)

def test_hierarchy():
    assert issubclass(NotFoundError, DJMusicError)
    assert issubclass(AnalyzerUnavailableError, PipelineError)
    assert issubclass(PipelineError, DJMusicError)
    assert issubclass(RateLimitedError, YandexMusicError)
    assert issubclass(YandexMusicError, DJMusicError)
    assert issubclass(ExportError, DJMusicError)

def test_not_found_message():
    err = NotFoundError("Track", 42)
    assert "Track" in str(err) and "42" in str(err)

def test_rate_limited_retry_after():
    err = RateLimitedError(retry_after=5.0)
    assert err.retry_after == 5.0
```

- [ ] **Step 6: Implement errors.py, run tests**

- [ ] **Step 7: Implement config.py**

Full `Settings` class per spec §14.1. Verify:
```bash
uv run python -c "from app.config import settings; print(settings.database_url)"
```

- [ ] **Step 8: Commit**

```bash
git add app/config.py app/core/ tests/test_core/
git commit -m "feat(core): add config, constants, and error hierarchy

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Core — Camelot Wheel

**Files:**
- Create: `app/core/camelot.py`
- Test: `tests/test_core/test_camelot.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_core/test_camelot.py
import pytest
from app.core.camelot import (
    key_code_to_camelot, camelot_to_key_code,
    camelot_distance, is_compatible,
)

@pytest.mark.parametrize("code,expected", [
    (0, "1A"), (14, "8A"), (15, "8B"), (23, "12B"),
])
def test_key_code_to_camelot(code, expected):
    assert key_code_to_camelot(code) == expected

@pytest.mark.parametrize("notation,expected", [
    ("1A", 0), ("8A", 14), ("8B", 15), ("12B", 23),
])
def test_camelot_to_key_code(notation, expected):
    assert camelot_to_key_code(notation) == expected

def test_invalid_camelot():
    with pytest.raises(ValueError):
        camelot_to_key_code("13A")

def test_distance_same(): assert camelot_distance(14, 14) == 0
def test_distance_adjacent(): assert camelot_distance(14, 12) == 1
def test_distance_relative(): assert camelot_distance(14, 15) == 1
def test_distance_wraps(): assert camelot_distance(0, 22) == 1
def test_distance_max(): assert camelot_distance(0, 12) == 6

def test_compatible_yes(): assert is_compatible(14, 12) is True
def test_compatible_no(): assert is_compatible(0, 12) is False

@pytest.mark.parametrize("code", range(24))
def test_roundtrip(code):
    assert camelot_to_key_code(key_code_to_camelot(code)) == code
```

- [ ] **Step 2: Run fail, implement, run pass**
- [ ] **Step 3: Commit**

```bash
git add app/core/camelot.py tests/test_core/test_camelot.py
git commit -m "feat(core): add Camelot wheel logic

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Core — Pagination

**Files:**
- Create: `app/core/pagination.py`
- Test: `tests/test_core/test_pagination.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_core/test_pagination.py
import pytest
from app.core.pagination import encode_cursor, decode_cursor, CursorPage

def test_encode_decode_roundtrip():
    assert decode_cursor(encode_cursor(42)) == 42

def test_decode_invalid():
    with pytest.raises(ValueError):
        decode_cursor("not-valid-base64-cursor")

def test_cursor_page_generic():
    page: CursorPage[int] = CursorPage(items=[1, 2], next_cursor="x", total=5)
    assert len(page.items) == 2
    assert page.total == 5

def test_cursor_page_last():
    page: CursorPage[str] = CursorPage(items=["a"], next_cursor=None, total=1)
    assert page.next_cursor is None
```

- [ ] **Step 2: Run fail, implement, run pass, commit**

```bash
git commit -m "feat(core): add cursor-based pagination

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Core — Entity Resolver & Schemas

**Files:**
- Create: `app/core/entity_resolver.py`
- Create: `app/core/schemas.py`
- Test: `tests/test_core/test_entity_resolver.py`
- Test: `tests/test_core/test_schemas.py`

- [ ] **Step 1: Write tests for EntityResolver**

```python
# tests/test_core/test_entity_resolver.py
import pytest
from app.core.entity_resolver import parse_entity_ref, EntityRef

def test_parse_numeric_int():
    ref = parse_entity_ref(42)
    assert ref.type == "id" and ref.value == 42

def test_parse_numeric_string():
    ref = parse_entity_ref("42")
    assert ref.type == "id" and ref.value == 42

def test_parse_ym_prefix():
    ref = parse_entity_ref("ym:12345")
    assert ref.type == "ym_id" and ref.value == "12345"

def test_parse_text_query():
    ref = parse_entity_ref("Aphex Twin - Xtal")
    assert ref.type == "query" and ref.value == "Aphex Twin - Xtal"

def test_parse_empty_raises():
    with pytest.raises(ValueError):
        parse_entity_ref("")
```

- [ ] **Step 2: Write tests for schemas**

```python
# tests/test_core/test_schemas.py
from app.core.schemas import TrackBrief, TrackStandard, PaginatedResponse

def test_track_brief_fields():
    t = TrackBrief(id=1, title="X", artist_names=["A"], bpm=128.0,
                   key_camelot="8A", duration_ms=300000)
    assert t.id == 1

def test_paginated_response():
    r = PaginatedResponse[TrackBrief](
        items=[], next_cursor=None, total=0
    )
    assert r.total == 0
```

- [ ] **Step 3: Implement entity_resolver.py**

`EntityRef` dataclass with `type: Literal["id", "ym_id", "query"]` and `value`.
`parse_entity_ref(ref: int | str) -> EntityRef` — parse logic.

- [ ] **Step 4: Implement schemas.py**

Pydantic models: `TrackBrief`, `TrackStandard`, `TrackFull`, `PlaylistSummary`, `SetSummary`, `PaginatedResponse[T]`. These are response schemas used by MCP tools.

- [ ] **Step 5: Run tests, commit**

```bash
git add app/core/entity_resolver.py app/core/schemas.py tests/test_core/test_entity_resolver.py tests/test_core/test_schemas.py
git commit -m "feat(core): add EntityResolver and shared response schemas

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Test Fixtures (conftest.py)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Implement async fixtures**

All fixtures use **async** SQLAlchemy (consistent with production code):

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base

@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db(async_engine) -> AsyncSession:
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def seeded_db(db):
    """Async session with 24 keys + 4 providers seeded."""
    from app.core.constants import CAMELOT_KEYS
    from app.models.key import Key

    for code, (camelot, name) in CAMELOT_KEYS.items():
        pitch_class = code % 12
        mode = 1 if camelot.endswith("B") else 0
        db.add(Key(key_code=code, pitch_class=pitch_class,
                    mode=mode, name=name, camelot=camelot))
    await db.flush()
    yield db
```

**Note:** `pitch_class = code % 12` is a placeholder. Real mapping in Key model should use the actual pitch class from CAMELOT_KEYS data.

- [ ] **Step 2: Verify fixture works**

```bash
uv run pytest --co -q  # should collect fixtures without error
```

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add async DB fixtures for in-memory SQLite

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Base Model & TimestampMixin

**Files:**
- Create: `app/models/__init__.py`, `app/models/base.py`
- Test: `tests/test_models/test_base.py`

- [ ] **Step 1: Write test for TimestampMixin**

```python
# tests/test_models/test_base.py
import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin

class _TestModel(Base, TimestampMixin):
    __tablename__ = "test_timestamps"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

async def test_timestamp_auto_populated(db):
    obj = _TestModel(name="test")
    db.add(obj)
    await db.flush()
    assert obj.created_at is not None
    assert obj.updated_at is not None
```

- [ ] **Step 2: Run fail, implement base.py, run pass, commit**

```bash
git commit -m "feat(models): add Base and TimestampMixin

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Track & Related Models (10 tables)

**Files:**
- Create: `app/models/track.py`
- Test: `tests/test_models/test_track.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_models/test_track.py
import pytest
from app.models.track import Track, Artist, Genre, Label, Release, TrackArtist

async def test_create_track(db):
    track = Track(title="Test Track", duration_ms=300000)
    db.add(track)
    await db.flush()
    assert track.id is not None
    assert track.status == 0  # TrackStatus.ACTIVE

async def test_track_default_status(db):
    track = Track(title="T")
    db.add(track)
    await db.flush()
    assert track.status == 0

async def test_create_artist(db):
    artist = Artist(name="Aphex Twin")
    db.add(artist)
    await db.flush()
    assert artist.id is not None

async def test_genre_hierarchy(db):
    parent = Genre(name="Techno")
    db.add(parent)
    await db.flush()
    child = Genre(name="Acid Techno", parent_id=parent.id)
    db.add(child)
    await db.flush()
    assert child.parent_id == parent.id

async def test_track_artist_association(db):
    track = Track(title="T")
    artist = Artist(name="A")
    db.add_all([track, artist])
    await db.flush()
    assoc = TrackArtist(track_id=track.id, artist_id=artist.id, role="primary")
    db.add(assoc)
    await db.flush()
    assert assoc.role == "primary"

async def test_track_has_timestamps(db):
    track = Track(title="T")
    db.add(track)
    await db.flush()
    assert track.created_at is not None
```

- [ ] **Step 2: Run fail, implement track.py, run pass**

10 tables: Track, Artist, Genre, Label, Release, TrackArtist, TrackGenre, TrackLabel, TrackRelease, TrackExternalId.

- [ ] **Step 3: Verify table count**

```bash
rg "class.*\(Base" app/models/track.py | wc -l  # should be 10
```

- [ ] **Step 4: Commit**

```bash
git add app/models/track.py tests/test_models/
git commit -m "feat(models): add Track, Artist, Genre, Label, Release + junction tables

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Key Models (2 tables)

**Files:** `app/models/key.py`, `tests/test_models/test_key.py`

- [ ] **Step 1: Write tests**

```python
async def test_create_key(db):
    from app.models.key import Key
    key = Key(key_code=14, pitch_class=9, mode=0, name="A minor", camelot="8A")
    db.add(key)
    await db.flush()
    assert key.key_code == 14

async def test_key_edge(db):
    from app.models.key import Key, KeyEdge
    k1 = Key(key_code=14, pitch_class=9, mode=0, name="Am", camelot="8A")
    k2 = Key(key_code=12, pitch_class=2, mode=0, name="Dm", camelot="7A")
    db.add_all([k1, k2])
    await db.flush()
    edge = KeyEdge(from_key_code=14, to_key_code=12, distance=1, weight=0.9, rule_name="adjacent")
    db.add(edge)
    await db.flush()
    assert edge.distance == 1
```

- [ ] **Step 2: Run fail, implement, run pass, commit**

---

## Task 10: Audio Feature Models (5 tables)

**Files:** `app/models/audio.py`, `tests/test_models/test_audio.py`

- [ ] **Step 1: Write tests**

```python
async def test_audio_features_constraints(db):
    from app.models.audio import TrackAudioFeaturesComputed
    from app.models.track import Track
    track = Track(title="T")
    db.add(track)
    await db.flush()
    feat = TrackAudioFeaturesComputed(
        track_id=track.id, bpm=128.0, bpm_confidence=0.95,
        bpm_stability=0.9, variable_tempo=False,
        integrated_lufs=-8.0, energy_mean=0.65,
        key_code=14, key_confidence=0.8,
        # ... all 47 fields
    )
    db.add(feat)
    await db.flush()
    assert feat.bpm == 128.0

async def test_track_section_type_range(db):
    from app.models.audio import TrackSection
    from app.models.track import Track
    track = Track(title="T")
    db.add(track)
    await db.flush()
    section = TrackSection(
        track_id=track.id, section_type=4,  # DROP
        start_ms=60000, end_ms=120000, energy=0.8, confidence=0.9
    )
    db.add(section)
    await db.flush()
    assert section.section_type == 4
```

- [ ] **Step 2: Implement audio.py — 5 tables, all 47 feature fields**
- [ ] **Step 3: Run pass, commit**

---

## Task 11: Library Models (5 tables)

**Files:** `app/models/library.py`, `tests/test_models/test_library.py`

- [ ] **Step 1: Write tests**

```python
async def test_library_item(db):
    from app.models.library import LibraryItem
    from app.models.track import Track
    track = Track(title="T")
    db.add(track)
    await db.flush()
    item = LibraryItem(
        track_id=track.id, file_path="/music/track.mp3",
        file_hash="abc123", file_size=5000000, mime_type="audio/mpeg",
        bitrate=320, sample_rate=44100, channels=2, source_app="rekordbox"
    )
    db.add(item)
    await db.flush()
    assert item.file_size == 5000000

async def test_cue_point_kind_range(db):
    from app.models.library import CuePoint, LibraryItem
    from app.models.track import Track
    track = Track(title="T")
    db.add(track)
    await db.flush()
    item = LibraryItem(track_id=track.id, file_path="/t.mp3",
                        file_hash="x", file_size=1000)
    db.add(item)
    await db.flush()
    cue = CuePoint(library_item_id=item.id, position_ms=30000,
                    kind=1, hotcue_index=0, label="Drop")
    db.add(cue)
    await db.flush()
    assert cue.kind == 1  # HOT_CUE_1
```

- [ ] **Step 2: Implement, test, commit**

---

## Task 12: Playlist Models (2 tables)

**Files:** `app/models/playlist.py`, `tests/test_models/test_playlist.py`

- [ ] **Step 1: Write tests**

```python
async def test_playlist_hierarchy(db):
    from app.models.playlist import Playlist
    parent = Playlist(name="DJ Sets", source_of_truth="local")
    db.add(parent)
    await db.flush()
    child = Playlist(name="Techno Sets", parent_id=parent.id, source_of_truth="local")
    db.add(child)
    await db.flush()
    assert child.parent_id == parent.id

async def test_playlist_item_ordering(db):
    from app.models.playlist import Playlist, PlaylistItem
    from app.models.track import Track
    pl = Playlist(name="Test")
    t1, t2 = Track(title="T1"), Track(title="T2")
    db.add_all([pl, t1, t2])
    await db.flush()
    db.add(PlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=0))
    db.add(PlaylistItem(playlist_id=pl.id, track_id=t2.id, sort_index=1))
    await db.flush()
```

- [ ] **Step 2: Implement, test, commit**

---

## Task 13: Set Models (5 tables)

**Files:** `app/models/set.py`, `tests/test_models/test_set.py`

- [ ] **Step 1: Write tests**

```python
async def test_set_version_quality_score(db):
    from app.models.set import DJSet, SetVersion
    s = DJSet(name="Peak Hour", target_duration_ms=3600000)
    db.add(s)
    await db.flush()
    v = SetVersion(set_id=s.id, label="v1", quality_score=0.82)
    db.add(v)
    await db.flush()
    assert 0.0 <= v.quality_score <= 1.0

async def test_set_item_pinned(db):
    from app.models.set import DJSet, SetVersion, SetItem
    from app.models.track import Track
    s = DJSet(name="S")
    db.add(s)
    await db.flush()
    v = SetVersion(set_id=s.id, label="v1")
    t = Track(title="T")
    db.add_all([v, t])
    await db.flush()
    item = SetItem(version_id=v.id, track_id=t.id, sort_index=0, pinned=True)
    db.add(item)
    await db.flush()
    assert item.pinned is True

async def test_set_feedback_rating_range(db):
    from app.models.set import DJSet, SetVersion, SetFeedback
    s = DJSet(name="S")
    db.add(s)
    await db.flush()
    v = SetVersion(set_id=s.id, label="v1")
    db.add(v)
    await db.flush()
    fb = SetFeedback(version_id=v.id, rating=4, feedback_type="manual")
    db.add(fb)
    await db.flush()
    assert fb.rating == 4
```

- [ ] **Step 2: Implement, test, commit**

---

## Task 14: Transition Models (2 tables)

**Files:** `app/models/transition.py`, `tests/test_models/test_transition.py`

- [ ] **Step 1: Write tests**

```python
async def test_transition_scores(db):
    from app.models.transition import Transition
    from app.models.track import Track
    t1, t2 = Track(title="A"), Track(title="B")
    db.add_all([t1, t2])
    await db.flush()
    tr = Transition(
        from_track_id=t1.id, to_track_id=t2.id,
        overlap_ms=16000, bpm_score=0.95, energy_score=0.8,
        harmonic_score=0.9, spectral_score=0.7, groove_score=0.6,
        key_distance_weighted=0.85, overall_quality=0.84,
    )
    db.add(tr)
    await db.flush()
    assert 0.0 <= tr.overall_quality <= 1.0
```

- [ ] **Step 2: Implement, test, commit**

---

## Task 15: Platform Metadata Models (8 tables)

**Files:** `app/models/platform.py`, `tests/test_models/test_platform.py`

- [ ] **Step 1: Write tests**

```python
async def test_yandex_metadata(db):
    from app.models.platform import YandexMetadata
    from app.models.track import Track
    t = Track(title="T")
    db.add(t)
    await db.flush()
    ym = YandexMetadata(track_id=t.id, yandex_track_id="12345",
                         album_title="Album", duration_ms=300000)
    db.add(ym)
    await db.flush()
    assert ym.yandex_track_id == "12345"

async def test_spotify_metadata(db):
    from app.models.platform import SpotifyMetadata
    from app.models.track import Track
    t = Track(title="T")
    db.add(t)
    await db.flush()
    sp = SpotifyMetadata(track_id=t.id, spotify_track_id="abc",
                          popularity=75)
    db.add(sp)
    await db.flush()
    assert sp.popularity == 75
```

8 tables: YandexMetadata, SpotifyMetadata, SpotifyAlbumMetadata, SpotifyArtistMetadata, SpotifyPlaylistMetadata, SpotifyAudioFeatures, BeatportMetadata, SoundCloudMetadata.

- [ ] **Step 2: Implement, test, commit**

---

## Task 16: Ingestion & Export Models (4 tables)

**Files:** `app/models/ingestion.py`, `app/models/export.py`

- [ ] **Step 1: Write tests**

```python
async def test_provider_track_id(db):
    from app.models.ingestion import ProviderModel, ProviderTrackId
    from app.models.track import Track
    p = ProviderModel(name="yandex_music")
    t = Track(title="T")
    db.add_all([p, t])
    await db.flush()
    link = ProviderTrackId(track_id=t.id, provider_id=p.id, provider_track_id="ym:123")
    db.add(link)
    await db.flush()
    assert link.provider_track_id == "ym:123"

async def test_app_export(db):
    from app.models.export import AppExport
    exp = AppExport(target_app="rekordbox", export_format="rekordbox_xml",
                     file_path="/out/set.xml", file_size=50000)
    db.add(exp)
    await db.flush()
    assert exp.target_app == "rekordbox"
```

- [ ] **Step 2: Implement both, test, commit**

---

## Task 17: Models __init__ & Alembic Migration

**Files:** `app/models/__init__.py`, `app/migrations/env.py`

- [ ] **Step 1: Update models __init__.py with all imports**

- [ ] **Step 2: Generate migration**

```bash
uv run alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 3: Apply and verify**

```bash
uv run alembic upgrade head
# Verify table count:
uv run python -c "
import sqlite3, json
conn = sqlite3.connect('dj_music.db')
tables = [r[0] for r in conn.execute(
    \"SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'\"
).fetchall()]
print(json.dumps({'count': len(tables), 'tables': sorted(tables)}, indent=2))
conn.close()
" | jq '.count'
# Expected: 44
```

- [ ] **Step 4: Commit**

```bash
git add app/models/__init__.py app/migrations/
git commit -m "feat(db): add initial Alembic migration with 44 tables

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: Base Repository

**Files:** `app/repositories/__init__.py`, `app/repositories/base.py`, `tests/test_repositories/test_base.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_repositories/test_base.py
import pytest
from app.models.track import Track
from app.repositories.base import BaseRepository

@pytest.fixture
def track_repo(db):
    return BaseRepository(db, Track)

async def test_create_and_get(track_repo):
    track = Track(title="Test", duration_ms=180000)
    created = await track_repo.create(track)
    assert created.id is not None
    fetched = await track_repo.get_by_id(created.id)
    assert fetched.title == "Test"

async def test_get_nonexistent(track_repo):
    assert await track_repo.get_by_id(999) is None

async def test_list_paginated(track_repo):
    for i in range(5):
        await track_repo.create(Track(title=f"Track {i}"))
    page = await track_repo.list_all(limit=3)
    assert len(page.items) == 3
    assert page.next_cursor is not None
    assert page.total == 5
    page2 = await track_repo.list_all(limit=3, cursor=page.next_cursor)
    assert len(page2.items) == 2
    assert page2.next_cursor is None
    # No overlap
    ids1 = {t.id for t in page.items}
    ids2 = {t.id for t in page2.items}
    assert ids1.isdisjoint(ids2)

async def test_delete(track_repo):
    t = await track_repo.create(Track(title="Del"))
    await track_repo.delete(t.id)
    assert await track_repo.get_by_id(t.id) is None
```

- [ ] **Step 2: Implement base.py with async CRUD + cursor pagination**
- [ ] **Step 3: Run pass, commit**

---

## Task 19: Domain Repositories

**Files:**
- Create: `app/repositories/track.py`, `playlist.py`, `set.py`, `feature.py`, `transition.py`, `export.py`
- Test: `tests/test_repositories/test_track.py`, `test_playlist.py`, `test_set.py`

- [ ] **Step 1: Write TrackRepository tests**

```python
async def test_search_by_text(track_repo, seeded_db):
    # Seed tracks
    seeded_db.add(Track(title="Aphex Twin - Xtal"))
    seeded_db.add(Track(title="Autechre - Gantz Graf"))
    await seeded_db.flush()
    results = await track_repo.search_by_text("Aphex")
    assert len(results) >= 1
    assert "Aphex" in results[0].title

async def test_filter_by_bpm_range(track_repo, seeded_db):
    # Requires tracks with features — test with seeded data
    pass  # implement with feature-aware query
```

- [ ] **Step 2: Write PlaylistRepository and SetRepository tests**

- [ ] **Step 3: Implement all 7 repositories** (track, playlist, set, feature, transition, export)

Each extends `BaseRepository` with domain-specific methods.

- [ ] **Step 4: Run all repo tests**

```bash
uv run pytest tests/test_repositories/ -v
```

- [ ] **Step 5: Commit**

```bash
git add app/repositories/ tests/test_repositories/
git commit -m "feat(repos): add domain repositories (track, playlist, set, feature, transition, export)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 20: Full Verification

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v --tb=short
```

- [ ] **Step 2: Lint**

```bash
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
```

- [ ] **Step 3: Type check**

```bash
uv run mypy app/
```

- [ ] **Step 4: Verify file structure**

```bash
# All expected model files exist:
fd "\.py$" app/models/ | sort

# All expected repo files exist:
fd "\.py$" app/repositories/ | sort

# All expected core files exist:
fd "\.py$" app/core/ | sort

# Count model classes:
rg "class\s+\w+\(.*Base" app/models/ --no-heading | wc -l
# Expected: 44

# Count repo classes:
rg "class\s+\w+Repository" app/repositories/ --no-heading | wc -l
# Expected: 7 (Base + 6 domain)
```

- [ ] **Step 5: Fix any issues, commit**

```bash
uv run ruff format app/ tests/
git add app/ tests/
git commit -m "style: fix lint and type errors in foundation

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Completion Checklist

- [ ] `app/config.py` — Settings with 50+ typed fields
- [ ] `app/core/constants.py` — all enums (SectionType 0-11, CueKind 0-7), Camelot, weights
- [ ] `app/core/errors.py` — full error hierarchy (12 classes)
- [ ] `app/core/camelot.py` — distance, compatibility, encode/decode
- [ ] `app/core/pagination.py` — cursor encode/decode + CursorPage[T]
- [ ] `app/core/entity_resolver.py` — parse_entity_ref
- [ ] `app/core/schemas.py` — TrackBrief, TrackStandard, TrackFull, PaginatedResponse
- [ ] `app/models/` — 44 tables across 11 files with CheckConstraints
- [ ] `app/repositories/` — BaseRepository + 6 domain repos
- [ ] `app/migrations/` — initial Alembic migration
- [ ] `tests/conftest.py` — async fixtures (db, seeded_db)
- [ ] All tests pass: `uv run pytest -v`
- [ ] Lint clean: `uv run ruff check`
- [ ] Types clean: `uv run mypy app/`
- [ ] Table count verified: `rg "class.*Base" app/models/ | wc -l` == 44
