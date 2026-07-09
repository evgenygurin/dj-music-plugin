# Multi-Deck Toolkit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать AI-композитору 10 инструментов для свободного multi-deck сведения: доступ к stem_features + track_section через generic entity CRUD + 6 вычислительных MCP-тулов.

**Architecture:** Phase 1 — Pydantic-схемы + регистрация двух новых entities (stem_features, track_section) в EntityRegistry с каталогами полей. Phase 2 — 6 domain-модулей + MCP-тулов в `app/domain/multi_deck/` и `app/tools/multi_deck/`. FileSystemProvider авто-обнаружит тулы в `app/tools/`.

**Tech Stack:** FastMCP v3, SQLAlchemy async, Pydantic, numpy, pgvector (ANN), EntityRegistry

## Global Constraints

- Все python-команды — через `uv run python`
- Тесты — `uv run pytest`
- Линт — `uv run ruff check`
- Typecheck — `uv run mypy`
- Полная проверка — `make check`
- Код коммитим после каждой задачи
- Ответы и комментарии — на русском
- Паттерны: EntityConfig из `app/registry/entity.py`, схемы из `app/schemas/`, репозитории из `app/repositories/`
- Новые тулы авто-обнаруживаются FileSystemProvider'ом в `app/tools/`

---

### Task 1: StemFeatures Schemas (View + Filter + Create + Update)

**Files:**
- Create: `app/schemas/stem_features.py`
- Test: `tests/schemas/test_stem_features.py`

**Interfaces:**
- Produces: `StemFeaturesView`, `StemFeaturesFilter`, `StemFeaturesCreate`, `StemFeaturesUpdate` — все Pydantic BaseModel, `from_attributes=True` для View

- [ ] **Step 1: Написать View-схему**

```python
"""StemFeatures entity schemas (L6 per-stem analysis)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StemFeaturesView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    stem_name: str

    analysis_level: int = 6

    # Tempo
    bpm: float | None = None
    bpm_confidence: float | None = None
    bpm_stability: float | None = None
    variable_tempo: bool | None = None

    # Loudness
    integrated_lufs: float | None = None
    short_term_lufs_mean: float | None = None
    momentary_max: float | None = None
    rms_dbfs: float | None = None
    true_peak_db: float | None = None
    crest_factor_db: float | None = None
    loudness_range_lu: float | None = None

    # Energy — scalars + 6 band absolutes + 6 band ratios
    energy_mean: float | None = None
    energy_max: float | None = None
    energy_std: float | None = None
    energy_slope: float | None = None
    energy_sub: float | None = None
    energy_low: float | None = None
    energy_lowmid: float | None = None
    energy_mid: float | None = None
    energy_highmid: float | None = None
    energy_high: float | None = None
    energy_sub_ratio: float | None = None
    energy_low_ratio: float | None = None
    energy_lowmid_ratio: float | None = None
    energy_mid_ratio: float | None = None
    energy_highmid_ratio: float | None = None
    energy_high_ratio: float | None = None

    # Spectral
    spectral_centroid_hz: float | None = None
    spectral_rolloff_85: float | None = None
    spectral_rolloff_95: float | None = None
    spectral_flatness: float | None = None
    spectral_flux_mean: float | None = None
    spectral_flux_std: float | None = None
    spectral_slope: float | None = None
    spectral_contrast: float | None = None

    # Key / harmonic
    key_code: int | None = None
    key_confidence: float | None = None
    atonality: bool | None = None
    hnr_db: float | None = None
    chroma_entropy: float | None = None

    # Rhythm
    mfcc_vector: str | None = None
    hp_ratio: float | None = None
    onset_rate: float | None = None
    pulse_clarity: float | None = None
    kick_prominence: float | None = None

    # P1 enrichment
    danceability: float | None = None
    dynamic_complexity: float | None = None
    dissonance_mean: float | None = None
    tonnetz_vector: str | None = None
    tempogram_ratio_vector: str | None = None
    beat_loudness_band_ratio: str | None = None

    # P2 enrichment
    spectral_complexity_mean: float | None = None
    pitch_salience_mean: float | None = None
    bpm_histogram_first_peak_weight: float | None = None
    bpm_histogram_second_peak_bpm: float | None = None
    bpm_histogram_second_peak_weight: float | None = None
    dominant_phrase_bars: int | None = None
    phrase_boundaries_ms: str | None = None

    # Beatgrid phase
    first_downbeat_ms: float | None = None

    # L6-only
    chords_strength: float | None = None
    chords_changes_rate: float | None = None
    hpcp_entropy: float | None = None
    hpcp_crest: float | None = None
    inharmonicity: float | None = None
    meter: str | None = None
    click_detected: bool | None = None
    saturation_detected: bool | None = None
    drum_bands: dict | None = None
```

- [ ] **Step 2: Написать Filter-схему**

```python
class StemFeaturesFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    stem_name__eq: str | None = None
    stem_name__in: list[str] | None = None

    bpm__eq: float | None = None
    bpm__gte: float | None = None
    bpm__lte: float | None = None
    bpm__range: list[float] | None = None

    key_code__eq: int | None = None
    key_code__in: list[int] | None = None
    key_code__range: list[int] | None = None

    integrated_lufs__gte: float | None = None
    integrated_lufs__lte: float | None = None

    energy_mean__gte: float | None = None
    energy_mean__lte: float | None = None

    spectral_centroid_hz__gte: float | None = None
    spectral_centroid_hz__lte: float | None = None

    kick_prominence__gte: float | None = None
    kick_prominence__lte: float | None = None
    onset_rate__gte: float | None = None
    onset_rate__lte: float | None = None
    pulse_clarity__gte: float | None = None
    pulse_clarity__lte: float | None = None
    hp_ratio__gte: float | None = None
    hp_ratio__lte: float | None = None

    hnr_db__gte: float | None = None
    hnr_db__lte: float | None = None
    dissonance_mean__gte: float | None = None
    dissonance_mean__lte: float | None = None

    inharmonicity__gte: float | None = None
    inharmonicity__lte: float | None = None
    chords_strength__gte: float | None = None
    chords_strength__lte: float | None = None

    saturation_detected__eq: bool | None = None
    click_detected__eq: bool | None = None

    analysis_level__eq: int | None = None
    analysis_level__gte: int | None = None
```

- [ ] **Step 3: Написать Create + Update схемы (минимальные заглушки)**

```python
class StemFeaturesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    stem_name: str


class StemFeaturesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

- [ ] **Step 4: Написать тест на валидацию View из ORM-строки**

```python
from __future__ import annotations

import pytest
from app.models.stem_features import StemFeatures
from app.schemas.stem_features import StemFeaturesView


def test_stem_features_view_from_orm():
    row = StemFeatures(
        id=1,
        track_id=42,
        stem_name="drums",
        bpm=135.0,
        key_code=7,
        integrated_lufs=-8.5,
        kick_prominence=0.9,
    )
    view = StemFeaturesView.model_validate(row)
    assert view.track_id == 42
    assert view.stem_name == "drums"
    assert view.bpm == 135.0
    assert view.key_code == 7


def test_stem_features_filter_forbids_unknown():
    with pytest.raises(ValueError):
        from app.schemas.stem_features import StemFeaturesFilter
        StemFeaturesFilter(random_field__eq=1)
```

- [ ] **Step 5: Запустить тесты, убедиться что проходят**

```bash
uv run pytest tests/schemas/test_stem_features.py -v
```

- [ ] **Step 6: Коммит**

```bash
git add app/schemas/stem_features.py tests/schemas/test_stem_features.py
git commit -m "feat: add StemFeatures entity schemas (View, Filter, Create, Update)"
```

---

### Task 2: TrackSection Schemas (View + Filter + Create + Update)

**Files:**
- Create: `app/schemas/track_section.py`
- Test: `tests/schemas/test_track_section.py`

**Interfaces:**
- Produces: `TrackSectionView`, `TrackSectionFilter`, `TrackSectionCreate`, `TrackSectionUpdate`

- [ ] **Step 1: Написать View-схему**

```python
"""TrackSection entity schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TrackSectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    section_type: int
    start_ms: int
    end_ms: int
    energy: float | None = None
    confidence: float | None = None
    lufs: float | None = None
    spectral_centroid: float | None = None
    stem_energy: dict | None = None
```

- [ ] **Step 2: Написать Filter-схему**

```python
class TrackSectionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    section_type__eq: int | None = None
    section_type__in: list[int] | None = None
    section_type__range: list[int] | None = None
    start_ms__gte: int | None = None
    start_ms__lte: int | None = None
    end_ms__gte: int | None = None
    end_ms__lte: int | None = None
    energy__gte: float | None = None
    energy__lte: float | None = None
    lufs__gte: float | None = None
    lufs__lte: float | None = None
```

- [ ] **Step 3: Написать Create + Update схемы (заглушки)**

```python
class TrackSectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: int
    section_type: int
    start_ms: int
    end_ms: int


class TrackSectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

- [ ] **Step 4: Тест**

```python
from __future__ import annotations

import pytest
from app.models.track_features import TrackSection
from app.schemas.track_section import TrackSectionView


def test_track_section_view_from_orm():
    row = TrackSection(
        id=1,
        track_id=42,
        section_type=3,
        start_ms=32000,
        end_ms=64000,
        energy=0.7,
        stem_energy={"drums": 0.8, "bass": 0.6, "vocals": 0.1, "other": 0.3},
    )
    view = TrackSectionView.model_validate(row)
    assert view.track_id == 42
    assert view.section_type == 3
    assert view.stem_energy == {"drums": 0.8, "bass": 0.6, "vocals": 0.1, "other": 0.3}
```

- [ ] **Step 5: Запустить тесты**

```bash
uv run pytest tests/schemas/test_track_section.py -v
```

- [ ] **Step 6: Коммит**

```bash
git add app/schemas/track_section.py tests/schemas/test_track_section.py
git commit -m "feat: add TrackSection entity schemas (View, Filter, Create, Update)"
```

---

### Task 3: Расширить StemFeaturesRepository для generic entity_list

**Files:**
- Modify: `app/repositories/stem_features.py`
- Test: `tests/repositories/test_stem_features_repo.py`

**Interfaces:**
- Consumes: `StemFeatures` ORM model, `AsyncSession`
- Produces: Наследование от `BaseRepository[StemFeatures]` → `get(id)`, `filter(where)`, `count()`, `aggregate()` — предоставляются базовым классом. `model = StemFeatures` + `self.session` (вместо `self._session`). Методы `upsert` и `get_all_for_track` остаются специфичными.

- [ ] **Step 1: Переписать StemFeaturesRepository как наследника BaseRepository**

Ключевое изменение: `_session` → `session`, добавить `model = StemFeatures`.

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.stem_features import StemFeatures
from app.repositories.base import BaseRepository


class StemFeaturesRepository(BaseRepository[StemFeatures]):
    model = StemFeatures

    async def upsert(
        self, track_id: int, stem_name: str, features: dict[str, Any]
    ) -> StemFeatures:
        clean = StemFeatures.filter_features(features)
        existing = await self.session.scalar(
            select(StemFeatures).where(
                StemFeatures.track_id == track_id,
                StemFeatures.stem_name == stem_name,
            )
        )
        if existing is not None:
            for key, val in clean.items():
                setattr(existing, key, val)
            await self.session.flush()
            return existing
        row = StemFeatures(track_id=track_id, stem_name=stem_name, **clean)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_all_for_track(self, track_id: int) -> list[StemFeatures]:
        result = await self.session.scalars(
            select(StemFeatures).where(StemFeatures.track_id == track_id)
        )
        return list(result.all())
```

- [ ] **Step 2: Тест на get() и filter() (из BaseRepository)**

```python
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stem_features import StemFeatures
from app.repositories.stem_features import StemFeaturesRepository


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession):
    repo = StemFeaturesRepository(db_session)
    row = StemFeatures(track_id=1, stem_name="drums", bpm=135.0)
    db_session.add(row)
    await db_session.flush()

    fetched = await repo.get(row.id)
    assert fetched is not None
    assert fetched.stem_name == "drums"


@pytest.mark.asyncio
async def test_filter(db_session: AsyncSession):
    repo = StemFeaturesRepository(db_session)
    r1 = StemFeatures(track_id=1, stem_name="drums")
    r2 = StemFeatures(track_id=1, stem_name="bass")
    r3 = StemFeatures(track_id=2, stem_name="drums")
    db_session.add_all([r1, r2, r3])
    await db_session.flush()

    rows, _ = await repo.filter({"stem_name__eq": "drums"})
    assert len(rows) >= 2
    for r in rows:
        assert r.stem_name == "drums"
```

- [ ] **Step 3: Запустить тесты**

```bash
uv run pytest tests/repositories/test_stem_features_repo.py -v
```

- [ ] **Step 4: Коммит**

```bash
git add app/repositories/stem_features.py tests/repositories/test_stem_features_repo.py
git commit -m "feat: extend StemFeaturesRepository with BaseRepository (generic entity_list support)"
```

---

### Task 4: Создать TrackSectionRepository

**Files:**
- Create: `app/repositories/track_section.py`
- Test: `tests/repositories/test_track_section_repo.py`

**Interfaces:**
- Produces: `TrackSectionRepository(BaseRepository[TrackSection])` с `model = TrackSection`

- [ ] **Step 1: Написать репозиторий**

```python
from __future__ import annotations

from app.models.track_features import TrackSection
from app.repositories.base import BaseRepository


class TrackSectionRepository(BaseRepository[TrackSection]):
    model = TrackSection
```

- [ ] **Step 2: Тест**

```python
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track_features import TrackSection
from app.repositories.track_section import TrackSectionRepository


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession):
    repo = TrackSectionRepository(db_session)
    row = TrackSection(track_id=1, section_type=3, start_ms=0, end_ms=32000)
    db_session.add(row)
    await db_session.flush()

    fetched = await repo.get_by_id(row.id)
    assert fetched is not None
    assert fetched.track_id == 1


@pytest.mark.asyncio
async def test_filter_by_track(db_session: AsyncSession):
    repo = TrackSectionRepository(db_session)
    s1 = TrackSection(track_id=1, section_type=1, start_ms=0, end_ms=16000)
    s2 = TrackSection(track_id=1, section_type=2, start_ms=16000, end_ms=32000)
    db_session.add_all([s1, s2])
    await db_session.flush()

    rows, _ = await repo.filter({"track_id__eq": 1})
    assert len(rows) == 2
```

- [ ] **Step 3: Запустить тесты**

```bash
uv run pytest tests/repositories/test_track_section_repo.py -v
```

- [ ] **Step 4: Коммит**

```bash
git add app/repositories/track_section.py tests/repositories/test_track_section_repo.py
git commit -m "feat: add TrackSectionRepository with BaseRepository"
```

---

### Task 5: Добавить track_sections в UnitOfWork + зарегистрировать entities

**Files:**
- Modify: `app/repositories/unit_of_work.py`
- Modify: `app/registry/defaults.py`
- Modify: `app/tools/entity/list.py`

- [ ] **Step 1: Добавить `track_sections` property в UnitOfWork**

В `app/repositories/unit_of_work.py`, после импорта `TrackSectionRepository`:

```python
from app.repositories.track_section import TrackSectionRepository
```

И добавить property:

```python
@cached_property
def track_sections(self) -> TrackSectionRepository:
    return TrackSectionRepository(self.session)
```

- [ ] **Step 2: Зарегистрировать `stem_features` entity**

В `app/registry/defaults.py`, после блока `track_features` (строка ~474), добавить:

```python
from app.models.stem_features import StemFeatures
from app.schemas.stem_features import (
    StemFeaturesView, StemFeaturesFilter,
    StemFeaturesCreate, StemFeaturesUpdate,
)

EntityRegistry.register(
    EntityConfig(
        name="stem_features",
        model=StemFeatures,
        repo_attr="stem_features",
        view_schema=StemFeaturesView,
        filter_schema=StemFeaturesFilter,
        create_schema=StemFeaturesCreate,
        update_schema=StemFeaturesUpdate,
        allowed_ops=frozenset({"list", "get", "aggregate"}),
        field_presets={
            "id": ["track_id", "stem_name"],
            "summary": [
                "track_id",
                "stem_name",
                "bpm",
                "key_code",
                "integrated_lufs",
                "energy_mean",
                "kick_prominence",
                "onset_rate",
                "pulse_clarity",
            ],
            "full": "*",
        },
        default_preset="summary",
        searchable_fields=(),
        filterable_fields={
            "track_id": ("eq", "in"),
            "stem_name": ("eq", "in"),
            "bpm": ("eq", "gte", "lte", "range"),
            "key_code": ("eq", "in", "range"),
            "integrated_lufs": ("gte", "lte"),
            "energy_mean": ("gte", "lte"),
            "spectral_centroid_hz": ("gte", "lte"),
            "kick_prominence": ("gte", "lte"),
            "onset_rate": ("gte", "lte"),
            "pulse_clarity": ("gte", "lte"),
            "hp_ratio": ("gte", "lte"),
            "hnr_db": ("gte", "lte"),
            "dissonance_mean": ("gte", "lte"),
            "inharmonicity": ("gte", "lte"),
            "chords_strength": ("gte", "lte"),
            "saturation_detected": ("eq",),
            "click_detected": ("eq",),
            "analysis_level": ("eq", "gte"),
        },
        sortable_fields=(
            "track_id", "bpm", "key_code", "integrated_lufs",
            "energy_mean", "kick_prominence", "onset_rate",
        ),
        relations={},
        tags=frozenset({"namespace:analysis"}),
    )
)
```

- [ ] **Step 3: Зарегистрировать `track_section` entity**

```python
from app.models.track_features import TrackSection
from app.schemas.track_section import (
    TrackSectionView, TrackSectionFilter,
    TrackSectionCreate, TrackSectionUpdate,
)

EntityRegistry.register(
    EntityConfig(
        name="track_section",
        model=TrackSection,
        repo_attr="track_sections",
        view_schema=TrackSectionView,
        filter_schema=TrackSectionFilter,
        create_schema=TrackSectionCreate,
        update_schema=TrackSectionUpdate,
        allowed_ops=frozenset({"list", "get", "aggregate"}),
        field_presets={
            "id": ["track_id", "section_type", "start_ms", "end_ms"],
            "summary": ["track_id", "section_type", "start_ms", "end_ms", "energy", "lufs"],
            "full": "*",
        },
        default_preset="summary",
        searchable_fields=(),
        filterable_fields={
            "track_id": ("eq", "in"),
            "section_type": ("eq", "in", "range"),
            "start_ms": ("gte", "lte"),
            "end_ms": ("gte", "lte"),
            "energy": ("gte", "lte"),
            "lufs": ("gte", "lte"),
        },
        sortable_fields=("track_id", "section_type", "start_ms", "energy"),
        relations={},
        tags=frozenset({"namespace:analysis"}),
    )
)
```

- [ ] **Step 4: Добавить в EntityName literal**

В `app/tools/entity/list.py`, строка 21-33:

```python
EntityName = Literal[
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
    "stem_features",       # NEW
    "track_section",       # NEW
]
```

- [ ] **Step 5: Проверить — запустить discover тест**

```bash
uv run python -c "
from app.registry.entity import EntityRegistry
from app.registry.defaults import register_default_entities
register_default_entities()
names = EntityRegistry.names()
assert 'stem_features' in names, f'stem_features not in {names}'
assert 'track_section' in names, f'track_section not in {names}'
print('OK:', names)
"
```

- [ ] **Step 6: Коммит**

```bash
git add app/repositories/unit_of_work.py app/registry/defaults.py app/tools/entity/list.py
git commit -m "feat: register stem_features + track_section as entities in EntityRegistry"
```

---

### Task 6: Feature catalog для stem_features

**Files:**
- Modify: `app/resources/_feature_catalog.py`
- Modify: `app/resources/` — новый ресурс или расширение `_feature_catalog.py`

- [ ] **Step 1: Добавить STEM_FEATURE_CATALOG**

В конец `app/resources/_feature_catalog.py`:

```python
STEM_FEATURE_CATALOG: dict[str, CatalogEntry] = {
    "track_id": {"group": "metadata", "label": "Track ID", "description": "Родительский трек. FK → tracks.id."},
    "stem_name": {"group": "metadata", "label": "Stem", "description": "Тип стема: drums, bass, vocals, other или original."},
    "analysis_level": {"group": "metadata", "label": "Analysis level", "description": "Уровень анализа (6 = L6 полный stem-анализ)."},
    "bpm": {"group": "tempo", "label": "BPM", "description": "Темп стема. Может отличаться от BPM полного трека."},
    "bpm_confidence": {"group": "tempo", "label": "BPM confidence", "description": "Уверенность детекции BPM (0-1)."},
    "bpm_stability": {"group": "tempo", "label": "BPM stability", "description": "Стабильность темпа (0-1). Низкая = переменный темп."},
    "variable_tempo": {"group": "tempo", "label": "Variable tempo", "description": "True если темп значительно меняется."},
    "integrated_lufs": {"group": "loudness", "label": "Integrated LUFS", "description": "Средняя громкость стема по EBU R128. Ключевой параметр для energy budget."},
    "short_term_lufs_mean": {"group": "loudness", "label": "Short-term LUFS mean", "description": "Средняя кратковременная громкость (3s окно)."},
    "momentary_max": {"group": "loudness", "label": "Max momentary LUFS", "description": "Пиковая momentary громкость."},
    "rms_dbfs": {"group": "loudness", "label": "RMS dBFS", "description": "Среднеквадратичная амплитуда в dBFS."},
    "true_peak_db": {"group": "loudness", "label": "True Peak dB", "description": "True peak (intersample). > 0 dBTP = клиппинг."},
    "crest_factor_db": {"group": "loudness", "label": "Crest factor dB", "description": "Пик-фактор. Высокий = динамичный, низкий = сжатый."},
    "loudness_range_lu": {"group": "loudness", "label": "Loudness range LU", "description": "Разброс громкости в LU."},
    "energy_mean": {"group": "energy", "label": "Energy mean", "description": "Средняя энергия стема (нормализованная RMS)."},
    "energy_max": {"group": "energy", "label": "Energy max", "description": "Максимальная энергия."},
    "energy_std": {"group": "energy", "label": "Energy std", "description": "Стандартное отклонение энергии. Низкое = стабильная энергия (лупабельно)."},
    "energy_slope": {"group": "energy", "label": "Energy slope", "description": "Наклон энергии (рост/спад по времени)."},
    "energy_sub": {"group": "energy", "label": "Sub energy (20-60 Hz)", "description": "Энергия в sub-диапазоне. Кик + sub-bass."},
    "energy_low": {"group": "energy", "label": "Low energy (60-250 Hz)", "description": "Энергия в low-диапазоне. Бас и нижняя середина кика."},
    "energy_lowmid": {"group": "energy", "label": "Low-mid energy (250-500 Hz)", "description": "Энергия в low-mid. Теплота, тело звука."},
    "energy_mid": {"group": "energy", "label": "Mid energy (500-2000 Hz)", "description": "Энергия в mid. Основная читаемость, синтезаторы."},
    "energy_highmid": {"group": "energy", "label": "High-mid energy (2-4 kHz)", "description": "Энергия в high-mid. Атака, присутствие, хэты."},
    "energy_high": {"group": "energy", "label": "High energy (4-8 kHz)", "description": "Энергия в high. Воздух, шлейфы, shimmer."},
    "spectral_centroid_hz": {"group": "spectral", "label": "Spectral centroid Hz", "description": "Центр тяжести спектра. Высокий = яркий, низкий = тёмный."},
    "spectral_rolloff_85": {"group": "spectral", "label": "Rolloff 85%", "description": "Частота ниже которой 85% энергии спектра."},
    "spectral_rolloff_95": {"group": "spectral", "label": "Rolloff 95%", "description": "Частота ниже которой 95% энергии спектра."},
    "spectral_contrast": {"group": "spectral", "label": "Spectral contrast", "description": "Контраст пик-провал по октавам."},
    "key_code": {"group": "key", "label": "Key code", "description": "Camelot-код стема (0-23). 0=8B, 23=1B."},
    "key_confidence": {"group": "key", "label": "Key confidence", "description": "Уверенность определения ключа (0-1)."},
    "hnr_db": {"group": "key", "label": "HNR dB", "description": "Harmonics-to-noise ratio. Высокий = гармоничный, низкий = шумный."},
    "chroma_entropy": {"group": "key", "label": "Chroma entropy", "description": "Энтропия хромаграммы. Высокая = много нот, низкая = одна нота/аккорд."},
    "onset_rate": {"group": "rhythm", "label": "Onset rate", "description": "Плотность атак (ударов) в секунду."},
    "pulse_clarity": {"group": "rhythm", "label": "Pulse clarity", "description": "Чёткость пульсации (0-1). Высокая = ровный бит."},
    "kick_prominence": {"group": "rhythm", "label": "Kick prominence", "description": "Выраженность кика (0-1). Высокая = мощный, читаемый кик."},
    "hp_ratio": {"group": "rhythm", "label": "HP ratio", "description": "Доля высокочастотной перкуссии."},
    "danceability": {"group": "danceability", "label": "Danceability", "description": "Танцевальность (0-1)."},
    "dissonance_mean": {"group": "danceability", "label": "Dissonance mean", "description": "Средний диссонанс. >0.3 = резкое, индустриальное звучание."},
    "chords_strength": {"group": "L6", "label": "Chords strength", "description": "Сила аккордовой структуры (Essentia chords)."},
    "chords_changes_rate": {"group": "L6", "label": "Chords changes rate", "description": "Частота смены аккордов."},
    "inharmonicity": {"group": "L6", "label": "Inharmonicity", "description": "Негармоничность спектра. Высокая = колокольность, металличность."},
    "click_detected": {"group": "L6", "label": "Click detected", "description": "Обнаружены ли щелчки/клиппинг в стеме."},
    "saturation_detected": {"group": "L6", "label": "Saturation detected", "description": "Обнаружено ли насыщение/сатурация."},
    "drum_bands": {"group": "L6", "label": "Drum bands", "description": "JSONB: sub_kick, kick_body, snare_clap, hi_hats — энергия и onset_rate per band."},
}
```

- [ ] **Step 2: Проверить импорт**

```bash
uv run python -c "from app.resources._feature_catalog import STEM_FEATURE_CATALOG; print(f'{len(STEM_FEATURE_CATALOG)} entries')"
```

- [ ] **Step 3: Коммит**

```bash
git add app/resources/_feature_catalog.py
git commit -m "feat: add STEM_FEATURE_CATALOG (44 field descriptions for stem_features)"
```

---

### Task 7: Ресурсы — feature-catalog/stem_features + section-types

**Files:**
- Create: `app/resources/multi_deck.py`
- Test: `tests/resources/test_multi_deck_resources.py`

- [ ] **Step 1: Написать ресурсы**

```python
"""Multi-deck toolkit resources: feature catalog + section type reference."""

from __future__ import annotations

from app.resources._feature_catalog import STEM_FEATURE_CATALOG

# Section type enum (mirrors SectionType in models)
SECTION_TYPES: dict[int, dict[str, str]] = {
    0: {"name": "intro", "label": "Intro", "description": "Вступление без кика."},
    1: {"name": "buildup", "label": "Buildup", "description": "Нарастание энергии к дропу."},
    2: {"name": "drop", "label": "Drop", "description": "Основная секция с полным киком и басом."},
    3: {"name": "breakdown", "label": "Breakdown", "description": "Спад энергии, снятие кика."},
    4: {"name": "bridge", "label": "Bridge", "description": "Переходная секция."},
    5: {"name": "drop_variation", "label": "Drop Variation", "description": "Вариация основного дропа."},
    6: {"name": "outro", "label": "Outro", "description": "Завершение, затухание."},
    7: {"name": "fill", "label": "Fill", "description": "Брейк/заполнение, короткая вставка."},
    8: {"name": "drum_only", "label": "Drum Only", "description": "Только ударные, без баса и синтов."},
    9: {"name": "ambient", "label": "Ambient", "description": "Атмосферная секция, пэды и текстуры."},
    10: {"name": "acid_line", "label": "Acid Line", "description": "Кислотная линия TB-303."},
    11: {"name": "unknown", "label": "Unknown", "description": "Неклассифицированная секция."},
}
```

- [ ] **Step 2: Зарегистрировать ресурсы в функции resource()**

Добавить в этот же файл:

```python
from fastmcp import resource

@resource(uri="reference://feature-catalog/stem_features")
def stem_features_catalog() -> dict:
    return {
        "entity": "stem_features",
        "total_fields": len(STEM_FEATURE_CATALOG),
        "fields": [
            {"name": name, **entry}
            for name, entry in STEM_FEATURE_CATALOG.items()
        ],
    }


@resource(uri="reference://section-types")
def section_types() -> dict:
    return {
        "description": "TrackSection type enum (0-11). Mirrors SectionType in models.",
        "types": [
            {"value": code, **info}
            for code, info in SECTION_TYPES.items()
        ],
    }
```

- [ ] **Step 3: Тест**

```python
from __future__ import annotations

from app.resources.multi_deck import stem_features_catalog, section_types


def test_stem_features_catalog():
    result = stem_features_catalog()
    assert result["entity"] == "stem_features"
    assert result["total_fields"] > 10
    assert any(f["name"] == "kick_prominence" for f in result["fields"])


def test_section_types():
    result = section_types()
    assert len(result["types"]) == 12
    names = {t["name"] for t in result["types"]}
    assert "intro" in names
    assert "drop" in names
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/resources/test_multi_deck_resources.py -v
```

- [ ] **Step 5: Коммит**

```bash
git add app/resources/multi_deck.py tests/resources/test_multi_deck_resources.py
git commit -m "feat: add multi-deck resources — stem_features catalog + section types"
```

---

### Task 8: Domain — stem_vertical_compatibility (N-way frequency + key + BPM)

**Files:**
- Create: `app/domain/multi_deck/__init__.py`
- Create: `app/domain/multi_deck/models.py`
- Create: `app/domain/multi_deck/compatibility.py`
- Test: `tests/domain/multi_deck/test_compatibility.py`

**Interfaces:**
- Consumes: `UnitOfWork` для загрузки StemFeatures
- Produces: `compute_stem_compatibility(uow, layers) -> CompatibilityResult`

- [ ] **Step 1: Написать модели**

```python
"""Multi-deck domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StemLayer:
    track_id: int
    stem_name: str


@dataclass
class BandScore:
    score: float
    clash: bool
    culprits: list[str] = field(default_factory=list)


@dataclass
class CompatibilityResult:
    overall_score: float
    hard_reject: bool
    per_band: dict[str, BandScore]
    key_compatibility: dict
    bpm_compatibility: dict
    recommendations: list[str] = field(default_factory=list)
```

- [ ] **Step 2: Написать алгоритм**

```python
"""N-way stem vertical compatibility scorer."""

from __future__ import annotations

import numpy as np

from app.domain.multi_deck.models import BandScore, CompatibilityResult, StemLayer
from app.domain.transition.kernels.bpm_distance import bpm_gauss
from app.domain.transition.kernels.camelot_lookup import key_distance
from app.repositories.unit_of_work import UnitOfWork

_BANDS = ["sub", "low", "lowmid", "mid", "highmid", "high"]
_ENERGY_COLS = {
    "sub": "energy_sub",
    "low": "energy_low",
    "lowmid": "energy_lowmid",
    "mid": "energy_mid",
    "highmid": "energy_highmid",
    "high": "energy_high",
}
_CLASH_THRESHOLD = 0.5  # high energy in same band → clash warning


async def compute_stem_compatibility(
    uow: UnitOfWork,
    layers: list[StemLayer],
) -> CompatibilityResult:
    if len(layers) < 2:
        return CompatibilityResult(
            overall_score=1.0, hard_reject=False,
            per_band={b: BandScore(score=1.0, clash=False) for b in _BANDS},
            key_compatibility={"score": 1.0},
            bpm_compatibility={"score": 1.0},
        )

    features = {}
    for layer in layers:
        rows = await uow.stem_features.get_all_for_track(layer.track_id)
        match = [r for r in rows if r.stem_name == layer.stem_name]
        if match:
            f = match[0]
            features[(layer.track_id, layer.stem_name)] = f

    # BPM compatibility — minimum pairwise gauss
    bpms = [
        features[k].bpm for k in features
        if features[k].bpm is not None
    ]
    bpm_min = 1.0
    if len(bpms) >= 2:
        for i in range(len(bpms)):
            for j in range(i + 1, len(bpms)):
                bpm_min = min(bpm_min, bpm_gauss(bpms[i], bpms[j]))

    # Key compatibility — minimum pairwise Camelot distance
    keys = [
        features[k].key_code for k in features
        if features[k].key_code is not None
    ]
    key_min = 1.0
    if len(keys) >= 2:
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                kd = key_distance(keys[i], keys[j])
                key_min = min(key_min, 1.0 - kd / 12.0)

    # Hard constraints
    hard_reject = bpm_min < 0.05 or key_min < 0.01

    # Per-band clash detection
    per_band = {}
    for band in _BANDS:
        col = _ENERGY_COLS[band]
        band_energies = []
        for k, f in features.items():
            val = getattr(f, col, None)
            if val is not None:
                band_energies.append((k, val))
        high = [(k, e) for k, e in band_energies if (e or 0) > _CLASH_THRESHOLD]
        clash = len(high) >= 2
        per_band[band] = BandScore(
            score=0.4 if clash else 0.85 + 0.15 * (1.0 - max((e for _, e in band_energies), default=0)),
            clash=clash,
            culprits=[f"{tid}:{stem}" for (tid, stem), _ in high] if clash else [],
        )

    recommendations = []
    for band, bs in per_band.items():
        if bs.clash:
            rec = f"{band} band clash between {', '.join(bs.culprits)}"
            if band == "low":
                rec += " — consider EQ cut at 150-250 Hz on one stem"
            elif band == "sub":
                rec += " — reduce gain on one kick or apply low-shelf"
            recommendations.append(rec)

    band_scores = [bs.score for bs in per_band.values()]
    overall = 0.3 * bpm_min + 0.3 * key_min + 0.4 * np.mean(band_scores)

    return CompatibilityResult(
        overall_score=round(float(overall), 4),
        hard_reject=hard_reject,
        per_band={b: per_band[b] for b in _BANDS},
        key_compatibility={"score": round(key_min, 4), "keys": [features[k].key_code for k in features]},
        bpm_compatibility={"score": round(bpm_min, 4), "bpms": [features[k].bpm for k in features]},
        recommendations=recommendations,
    )
```

- [ ] **Step 3: Тест**

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.multi_deck.compatibility import compute_stem_compatibility
from app.domain.multi_deck.models import StemLayer


@pytest.mark.asyncio
async def test_two_compatible_stems():
    mock_stem_a = MagicMock(
        track_id=1, stem_name="drums",
        bpm=135.0, key_code=7,
        energy_sub=0.3, energy_low=0.4, energy_lowmid=0.3,
        energy_mid=0.2, energy_highmid=0.1, energy_high=0.05,
    )
    mock_stem_b = MagicMock(
        track_id=2, stem_name="bass",
        bpm=134.8, key_code=7,
        energy_sub=0.2, energy_low=0.5, energy_lowmid=0.3,
        energy_mid=0.1, energy_highmid=0.05, energy_high=0.02,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(
        side_effect=lambda tid: [mock_stem_a] if tid == 1 else [mock_stem_b]
    )

    result = await compute_stem_compatibility(uow, [
        StemLayer(track_id=1, stem_name="drums"),
        StemLayer(track_id=2, stem_name="bass"),
    ])
    assert not result.hard_reject
    assert result.overall_score > 0.5


@pytest.mark.asyncio
async def test_clash_detection():
    mock_a = MagicMock(
        track_id=1, stem_name="drums",
        bpm=135.0, key_code=7,
        energy_sub=0.8, energy_low=0.9, energy_lowmid=0.3,
        energy_mid=0.2, energy_highmid=0.1, energy_high=0.05,
    )
    mock_b = MagicMock(
        track_id=2, stem_name="bass",
        bpm=135.0, key_code=7,
        energy_sub=0.2, energy_low=0.85, energy_lowmid=0.3,
        energy_mid=0.1, energy_highmid=0.05, energy_high=0.02,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(
        side_effect=lambda tid: [mock_a] if tid == 1 else [mock_b]
    )

    result = await compute_stem_compatibility(uow, [
        StemLayer(track_id=1, stem_name="drums"),
        StemLayer(track_id=2, stem_name="bass"),
    ])
    assert result.per_band["low"].clash
    assert len(result.recommendations) >= 1


@pytest.mark.asyncio
async def test_single_stem():
    uow = MagicMock()
    result = await compute_stem_compatibility(uow, [
        StemLayer(track_id=1, stem_name="drums"),
    ])
    assert result.overall_score == 1.0
    assert not result.hard_reject
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/domain/multi_deck/test_compatibility.py -v
```

- [ ] **Step 5: Коммит**

```bash
git add app/domain/multi_deck/ tests/domain/multi_deck/
git commit -m "feat: add stem_vertical_compatibility — N-way frequency/key/BPM scorer"
```

---

### Task 9: Domain — energy_budget

**Files:**
- Create: `app/domain/multi_deck/energy_budget.py`
- Test: `tests/domain/multi_deck/test_energy_budget.py`

**Interfaces:**
- Produces: `compute_energy_budget(uow, layers, target_lufs) -> EnergyBudgetResult`

- [ ] **Step 1: Добавить модель в models.py**

```python
@dataclass
class BandBudget:
    total_lufs: float
    headroom_db: float
    warning: bool


@dataclass
class EnergyBudgetResult:
    total_lufs: float
    headroom_db: float
    per_band: dict[str, BandBudget]
    recommendation: str
```

- [ ] **Step 2: Реализовать**

```python
"""Energy budget calculator — combined LUFS + per-band allocation."""

from __future__ import annotations

import numpy as np

from app.domain.multi_deck.models import BandBudget, EnergyBudgetResult, StemLayer
from app.repositories.unit_of_work import UnitOfWork

_BANDS = ["sub", "low", "lowmid", "mid", "highmid", "high"]
_ENERGY_COLS = {
    "sub": "energy_sub", "low": "energy_low",
    "lowmid": "energy_lowmid", "mid": "energy_mid",
    "highmid": "energy_highmid", "high": "energy_high",
}


async def compute_energy_budget(
    uow: UnitOfWork,
    layers: list[StemLayer],
    gain_db: list[float] | None = None,
    target_lufs: float = -8.0,
) -> EnergyBudgetResult:
    if gain_db is None:
        gain_db = [0.0] * len(layers)

    features = {}
    for layer in layers:
        rows = await uow.stem_features.get_all_for_track(layer.track_id)
        match = [r for r in rows if r.stem_name == layer.stem_name]
        if match:
            features[(layer.track_id, layer.stem_name)] = match[0]

    total_lufs = 0.0
    per_band_energy: dict[str, float] = {b: 0.0 for b in _BANDS}

    for i, layer in enumerate(layers):
        f = features.get((layer.track_id, layer.stem_name))
        if f is None or f.integrated_lufs is None:
            continue
        gain_linear = 10.0 ** (gain_db[i] / 20.0)
        total_lufs += f.integrated_lufs * gain_linear
        for band in _BANDS:
            col = _ENERGY_COLS[band]
            val = getattr(f, col, None) or 0.0
            per_band_energy[band] += val * gain_linear

    headroom_db = target_lufs - total_lufs
    per_band = {}
    for band in _BANDS:
        band_lufs = per_band_energy[band]
        band_headroom = target_lufs - band_lufs
        per_band[band] = BandBudget(
            total_lufs=round(band_lufs, 1),
            headroom_db=round(band_headroom, 1),
            warning=band_headroom < 0,
        )

    recommendations = []
    for band, bb in per_band.items():
        if bb.warning:
            recommendations.append(f"{band} band overloaded. Reduce gain on stems contributing to {band}.")
    if not recommendations and headroom_db < 1.0:
        recommendations.append(f"Low overall headroom ({headroom_db:.1f} dB). Consider reducing gain.")

    return EnergyBudgetResult(
        total_lufs=round(total_lufs, 1),
        headroom_db=round(headroom_db, 1),
        per_band=per_band,
        recommendation="; ".join(recommendations) if recommendations else "All bands within budget.",
    )
```

- [ ] **Step 3: Тест**

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.multi_deck.energy_budget import compute_energy_budget
from app.domain.multi_deck.models import StemLayer


@pytest.mark.asyncio
async def test_energy_budget():
    mock_a = MagicMock(
        integrated_lufs=-10.0,
        energy_sub=0.3, energy_low=0.4, energy_lowmid=0.3,
        energy_mid=0.2, energy_highmid=0.1, energy_high=0.05,
    )
    mock_b = MagicMock(
        integrated_lufs=-12.0,
        energy_sub=0.1, energy_low=0.3, energy_lowmid=0.2,
        energy_mid=0.1, energy_highmid=0.05, energy_high=0.02,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(
        side_effect=lambda tid: [mock_a] if tid == 1 else [mock_b]
    )

    result = await compute_energy_budget(uow, [
        StemLayer(track_id=1, stem_name="drums"),
        StemLayer(track_id=2, stem_name="bass"),
    ], target_lufs=-8.0)

    assert result.total_lufs < -8.0  # сумма должна быть тише целевой
    assert result.headroom_db > 0
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/domain/multi_deck/test_energy_budget.py -v
```

- [ ] **Step 5: Коммит**

```bash
git add app/domain/multi_deck/energy_budget.py app/domain/multi_deck/models.py tests/domain/multi_deck/test_energy_budget.py
git commit -m "feat: add energy_budget — combined LUFS + per-band allocation calculator"
```

---

### Task 10: Domain — bpm_ratio_analyzer

**Files:**
- Create: `app/domain/multi_deck/bpm_ratio.py`
- Test: `tests/domain/multi_deck/test_bpm_ratio.py`

- [ ] **Step 1: Добавить модели**

```python
@dataclass
class BpmRatioMatch:
    bpm_b: float
    ratio: float
    ratio_label: str
    error_pct: float
    bars_to_align: int
    seconds_to_align: float


@dataclass
class BpmRatioResult:
    bpm_a: float
    matches: list[BpmRatioMatch]
    library_pairs: list[dict]
```

- [ ] **Step 2: Реализовать**

```python
"""BPM ratio analyzer — polyrhythm and dual-BPM storytelling."""

from __future__ import annotations

import math

from app.domain.multi_deck.models import BpmRatioMatch, BpmRatioResult
from app.repositories.unit_of_work import UnitOfWork

_RATIOS = {
    "3:4": (3, 4, 0.75),
    "2:3": (2, 3, 0.6667),
    "3:2": (3, 2, 1.5),
    "4:3": (4, 3, 1.3333),
    "5:4": (5, 4, 0.8),
    "4:5": (4, 5, 1.25),
    "3:5": (3, 5, 0.6),
    "5:3": (5, 3, 1.6667),
}


def _bars_to_align(num: int, den: int) -> int:
    return math.lcm(num, den)


async def analyze_bpm_ratio(
    uow: UnitOfWork,
    bpm_a: float,
    bpm_range: tuple[float, float] = (40, 200),
    ratios_of_interest: list[str] | None = None,
) -> BpmRatioResult:
    if ratios_of_interest is None:
        ratios_of_interest = list(_RATIOS.keys())

    matches = []
    for label in ratios_of_interest:
        entry = _RATIOS.get(label)
        if entry is None:
            continue
        num, den, ratio = entry

        target_bpm = bpm_a * ratio if ratio < 1 else bpm_a / (2.0 - ratio) if ratio > 1 else bpm_a
        # Try both directions
        for candidate in [bpm_a * ratio, bpm_a / ratio]:
            if bpm_range[0] <= candidate <= bpm_range[1]:
                bar_duration_s = 240.0 / bpm_a
                align_bars = _bars_to_align(num, den)
                target_bar_s = 240.0 / candidate
                match = BpmRatioMatch(
                    bpm_b=round(candidate, 2),
                    ratio=round(ratio, 4),
                    ratio_label=label,
                    error_pct=0.0,
                    bars_to_align=align_bars,
                    seconds_to_align=round(align_bars * bar_duration_s, 2),
                )
                matches.append(match)

    return BpmRatioResult(
        bpm_a=bpm_a,
        matches=sorted(matches, key=lambda m: abs(1.0 - m.ratio)),
        library_pairs=[],
    )
```

- [ ] **Step 3: Тест**

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.domain.multi_deck.bpm_ratio import analyze_bpm_ratio


@pytest.mark.asyncio
async def test_bpm_ratio_3to4():
    uow = MagicMock()
    result = await analyze_bpm_ratio(uow, 135.0)
    labels = {m.ratio_label for m in result.matches}
    assert "4:3" in labels
    assert "3:4" in labels

    match_34 = [m for m in result.matches if m.ratio_label == "3:4"]
    assert len(match_34) >= 1
    assert abs(match_34[0].bpm_b - 101.25) < 0.5  # 135 * 3/4


@pytest.mark.asyncio
async def test_bpm_ratio_range_respected():
    uow = MagicMock()
    result = await analyze_bpm_ratio(uow, 60.0, bpm_range=(100, 200))
    for m in result.matches:
        assert 100 <= m.bpm_b <= 200
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/domain/multi_deck/test_bpm_ratio.py -v
```

- [ ] **Step 5: Коммит**

```bash
git add app/domain/multi_deck/bpm_ratio.py app/domain/multi_deck/models.py tests/domain/multi_deck/test_bpm_ratio.py
git commit -m "feat: add bpm_ratio_analyzer — polyrhythm BPM pair finder"
```

---

### Task 11: Domain — timeline_overlay + find_loops + stem_embedding_search

**Files:**
- Create: `app/domain/multi_deck/timeline.py`
- Create: `app/domain/multi_deck/loop_finder.py`
- Test: `tests/domain/multi_deck/test_timeline.py`
- Test: `tests/domain/multi_deck/test_loop_finder.py`

**Interfaces:**
- Produces: `build_timeline_overlay(uow, track_ids, align_mode) -> TimelineResult`
- Produces: `find_loops(uow, track_id, min_bars, exclude_vocals, ...) -> LoopResult`

- [ ] **Step 1: timeline.py**

```python
"""Unified timeline overlay for multi-deck synchronization."""

from __future__ import annotations

from app.domain.multi_deck.models import TimelineOverlay, TimelineTrack
from app.repositories.unit_of_work import UnitOfWork


async def build_timeline_overlay(
    uow: UnitOfWork,
    track_ids: list[int],
    align_mode: str = "downbeat",
) -> dict:
    tracks = []
    min_start = None

    for tid in track_ids:
        sections = await uow.track_features.get_track_sections(tid)
        # Get beatgrid for alignment
        beatgrids = await uow.audio_files.get_beatgrids(tid)
        first_downbeat_ms = 0
        for bg in (beatgrids or []):
            if getattr(bg, "canonical", False) and bg.first_downbeat_ms:
                first_downbeat_ms = bg.first_downbeat_ms
                break

        bpm = None
        features_row = await uow.track_features.get_by_track_id(tid)
        if features_row:
            bpm = features_row.bpm

        tracks.append({
            "track_id": tid,
            "first_downbeat_ms": first_downbeat_ms,
            "bpm": bpm,
            "sections": sections,
        })

    return {
        "tracks": tracks,
        "description": "Aligned by first downbeat. Use start_ms + offset for sync.",
    }
```

- [ ] **Step 2: loop_finder.py**

```python
"""Loopable section finder for sustained multi-deck layering."""

from __future__ import annotations

from app.repositories.unit_of_work import UnitOfWork


async def find_loops(
    uow: UnitOfWork,
    track_id: int,
    min_bars: int = 8,
    max_bars: int = 32,
    exclude_vocals: bool = True,
    min_energy_stability: float = 0.7,
) -> dict:
    sections = await uow.track_features.get_track_sections(track_id)
    features_row = await uow.track_features.get_by_track_id(track_id)
    bpm = features_row.bpm if features_row else 120.0
    bar_duration_ms = 240_000.0 / bpm

    loops = []
    for sec in sections:
        length_ms = sec.get("end_ms", 0) - sec.get("start_ms", 0)
        bars = length_ms / bar_duration_ms
        if bars < min_bars or bars > max_bars:
            continue

        stem_energy = sec.get("stem_energy") or {}
        vocals_energy = stem_energy.get("vocals", 0)
        if exclude_vocals and vocals_energy > 0.15:
            continue

        # energy_stability heuristic: higher energy, low vocals → loopable
        energy = sec.get("energy") or 0.5
        energy_stability = energy * (1.0 - vocals_energy)

        if energy_stability >= min_energy_stability:
            loops.append({
                "section_type": sec.get("section_type"),
                "start_ms": sec.get("start_ms"),
                "end_ms": sec.get("end_ms"),
                "bars": round(bars, 1),
                "energy_stability": round(energy_stability, 3),
                "stem_energy": stem_energy,
                "loopable": True,
                "cue_point_ms": sec.get("start_ms"),
            })

    loops.sort(key=lambda l: l["energy_stability"], reverse=True)

    return {
        "track_id": track_id,
        "bpm": round(bpm, 1),
        "bar_duration_ms": round(bar_duration_ms, 1),
        "loops": loops,
    }
```

- [ ] **Step 3: Тесты**

```python
@pytest.mark.asyncio
async def test_find_loops():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(return_value=[
        {"section_type": 2, "start_ms": 32000, "end_ms": 96000, "energy": 0.8, "stem_energy": {"vocals": 0.05, "drums": 0.9}},
        {"section_type": 3, "start_ms": 96000, "end_ms": 128000, "energy": 0.3, "stem_energy": {"vocals": 0.6, "drums": 0.1}},
    ])
    uow.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(bpm=128.0))

    result = await find_loops(uow, 1, min_bars=4)
    assert len(result["loops"]) >= 1
    assert result["loops"][0]["loopable"] is True


@pytest.mark.asyncio
async def test_build_timeline():
    uow = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(return_value=[
        {"section_type": 0, "start_ms": 0, "end_ms": 32000, "energy": 0.3},
        {"section_type": 2, "start_ms": 32000, "end_ms": 96000, "energy": 0.8},
    ])
    uow.audio_files.get_beatgrids = AsyncMock(return_value=[
        MagicMock(canonical=True, first_downbeat_ms=1000.0)
    ])
    uow.track_features.get_by_track_id = AsyncMock(return_value=MagicMock(bpm=135.0))

    result = await build_timeline_overlay(uow, [1])
    assert len(result["tracks"]) == 1
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/domain/multi_deck/test_loop_finder.py tests/domain/multi_deck/test_timeline.py -v
```

- [ ] **Step 5: Коммит**

```bash
git add app/domain/multi_deck/timeline.py app/domain/multi_deck/loop_finder.py tests/domain/multi_deck/
git commit -m "feat: add timeline_overlay + find_loops domain modules"
```

---

### Task 12: MCP Tools — все 6 вычислительных тулов

**Files:**
- Create: `app/tools/multi_deck/__init__.py`
- Create: `app/tools/multi_deck/compatibility.py`
- Create: `app/tools/multi_deck/energy_budget.py`
- Create: `app/tools/multi_deck/bpm_ratio.py`
- Create: `app/tools/multi_deck/timeline.py`
- Create: `app/tools/multi_deck/loop_finder.py`
- Create: `app/tools/multi_deck/stem_embedding.py`
- Test: `tests/tools/multi_deck/test_tools.py`

**Interfaces:**
- Produces: 6 MCP-тулов, авто-обнаруживаемых FileSystemProvider'ом в `app/tools/`

- [ ] **Step 1: Написать compatibility tool**

```python
"""MCP tool: stem_vertical_compatibility."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.compatibility import compute_stem_compatibility
from app.domain.multi_deck.models import StemLayer
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="stem_vertical_compatibility", annotations={"readOnlyHint": True, "idempotentHint": True})
async def stem_vertical_compatibility(
    layers: list[dict[str, str | int]],
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Check N-way stem frequency/key/BPM compatibility for simultaneous playback.

    Args:
        layers: List of {track_id: int, stem_name: str} — stems to check.
    """
    stem_layers = [StemLayer(track_id=int(l["track_id"]), stem_name=str(l["stem_name"])) for l in layers]
    result = await compute_stem_compatibility(uow, stem_layers)
    return {
        "overall_score": result.overall_score,
        "hard_reject": result.hard_reject,
        "per_band": {band: {"score": bs.score, "clash": bs.clash, "culprits": bs.culprits} for band, bs in result.per_band.items()},
        "key_compatibility": result.key_compatibility,
        "bpm_compatibility": result.bpm_compatibility,
        "recommendations": result.recommendations,
    }
```

- [ ] **Step 2: Написать energy_budget tool**

```python
"""MCP tool: energy_budget."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.energy_budget import compute_energy_budget
from app.domain.multi_deck.models import StemLayer
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="energy_budget", annotations={"readOnlyHint": True, "idempotentHint": True})
async def energy_budget(
    layers: list[dict[str, str | int]],
    gain_db: list[float] | None = None,
    target_lufs: float = -8.0,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Compute combined energy budget across active decks.

    Args:
        layers: List of {track_id: int, stem_name: str}.
        gain_db: Per-layer gain adjustment in dB (same order as layers).
        target_lufs: Target integrated LUFS (default -8.0).
    """
    stem_layers = [StemLayer(track_id=int(l["track_id"]), stem_name=str(l["stem_name"])) for l in layers]
    result = await compute_energy_budget(uow, stem_layers, gain_db, target_lufs)
    return {
        "total_lufs": result.total_lufs,
        "headroom_db": result.headroom_db,
        "per_band": {band: {"total_lufs": bb.total_lufs, "headroom_db": bb.headroom_db, "warning": bb.warning} for band, bb in result.per_band.items()},
        "recommendation": result.recommendation,
    }
```

- [ ] **Step 3: Написать bpm_ratio tool**

```python
"""MCP tool: bpm_ratio_analyzer."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.bpm_ratio import analyze_bpm_ratio
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="bpm_ratio_analyzer", annotations={"readOnlyHint": True, "idempotentHint": True})
async def bpm_ratio_analyzer(
    bpm_a: float,
    bpm_min: float = 40,
    bpm_max: float = 200,
    ratios: list[str] | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Find musically useful BPM ratios (3:4, 2:3, etc.) for dual-BPM storytelling.

    Args:
        bpm_a: Source BPM.
        bpm_min/max: BPM search range.
        ratios: List of ratio labels (e.g. ["3:4", "2:3"]). Default: all.
    """
    result = await analyze_bpm_ratio(uow, bpm_a, (bpm_min, bpm_max), ratios)
    return {
        "bpm_a": result.bpm_a,
        "matches": [
            {
                "bpm_b": m.bpm_b,
                "ratio": m.ratio,
                "ratio_label": m.ratio_label,
                "error_pct": m.error_pct,
                "bars_to_align": m.bars_to_align,
                "seconds_to_align": m.seconds_to_align,
            }
            for m in result.matches
        ],
    }
```

- [ ] **Step 4: Написать timeline_overlay + find_loops tools**

```python
"""MCP tools: timeline_overlay, find_loops."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.domain.multi_deck.loop_finder import find_loops as _find_loops
from app.domain.multi_deck.timeline import build_timeline_overlay
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="timeline_overlay", annotations={"readOnlyHint": True, "idempotentHint": True})
async def timeline_overlay(
    track_ids: list[int],
    align_mode: str = "downbeat",
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Show sections of multiple tracks on a unified timeline aligned by downbeat.

    Args:
        track_ids: Track IDs to overlay.
        align_mode: Alignment mode (only "downbeat" currently).
    """
    return await build_timeline_overlay(uow, track_ids, align_mode)


@tool(name="find_loops", annotations={"readOnlyHint": True, "idempotentHint": True})
async def find_loops(
    track_id: int,
    min_bars: int = 8,
    max_bars: int = 32,
    exclude_vocals: bool = True,
    min_energy_stability: float = 0.7,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """Find loopable sections in a track for sustained multi-deck layering.

    Args:
        track_id: Track to scan.
        min_bars/max_bars: Loop length range.
        exclude_vocals: Skip sections with vocal energy > 0.15.
        min_energy_stability: Minimum energy stability (0-1).
    """
    return await _find_loops(uow, track_id, min_bars, max_bars, exclude_vocals, min_energy_stability)
```

- [ ] **Step 5: Написать stem_embedding_search tool**

```python
"""MCP tool: stem_embedding_search."""

from __future__ import annotations

from typing import Any

import numpy as np
from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(name="stem_embedding_search", annotations={"readOnlyHint": True, "idempotentHint": True})
async def stem_embedding_search(
    track_id: int,
    stem_name: str = "bass",
    embedding_type: str = "timbral",
    limit: int = 10,
    uow: UnitOfWork = Depends(get_uow),
) -> list[dict[str, Any]]:
    """Find similar stems using pgvector ANN search.

    Args:
        track_id: Source track to find similar stems to.
        stem_name: Which stem to match (drums/bass/vocals/other/original).
        embedding_type: Embedding type (timbral/harmonic/rhythmic/energy/full).
        limit: Max results.
    """
    emb_row = await uow.track_embeddings.get_for_type(track_id, stem_name, embedding_type)
    if emb_row is None:
        return []

    query = np.array(emb_row.embedding, dtype=np.float32)
    rows = await uow.track_embeddings.search_similar(
        query, embedding_type=embedding_type, stem_name=stem_name, limit=limit, exclude_ids=[track_id]
    )
    return [{"track_id": int(row[0]), "stem_name": stem_name, "similarity": round(row[1], 4)} for row in rows]
```

- [ ] **Step 6: Написать тест-дым на все тулы**

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stem_vertical_compatibility_tool():
    from app.tools.multi_deck.compatibility import stem_vertical_compatibility

    with patch("app.tools.multi_deck.compatibility.compute_stem_compatibility") as mock:
        mock.return_value = MagicMock(
            overall_score=0.8, hard_reject=False,
            per_band={},
            key_compatibility={"score": 0.9},
            bpm_compatibility={"score": 0.9},
            recommendations=[],
        )
        # Manually inject uow since DI won't work in unit test
        uow = MagicMock()
        result = await stem_vertical_compatibility.fn(
            layers=[{"track_id": 1, "stem_name": "drums"}],
            uow=uow,
        )
        assert result["overall_score"] == 0.8


@pytest.mark.asyncio
async def test_energy_budget_tool():
    from app.tools.multi_deck.energy_budget import energy_budget

    with patch("app.tools.multi_deck.energy_budget.compute_energy_budget") as mock:
        mock.return_value = MagicMock(
            total_lufs=-10.0, headroom_db=2.0,
            per_band={},
            recommendation="OK",
        )
        uow = MagicMock()
        result = await energy_budget.fn(
            layers=[{"track_id": 1, "stem_name": "drums"}],
            uow=uow,
        )
        assert result["total_lufs"] == -10.0


@pytest.mark.asyncio
async def test_all_tools_registered():
    import importlib
    import app.tools.multi_deck.compatibility  # noqa: F401
    import app.tools.multi_deck.energy_budget  # noqa: F401
    import app.tools.multi_deck.bpm_ratio  # noqa: F401
    import app.tools.multi_deck.timeline  # noqa: F401
    import app.tools.multi_deck.loop_finder  # noqa: F401
    import app.tools.multi_deck.stem_embedding  # noqa: F401
```

- [ ] **Step 7: Запустить тесты**

```bash
uv run pytest tests/tools/multi_deck/test_tools.py -v
```

- [ ] **Step 8: Коммит**

```bash
git add app/tools/multi_deck/ tests/tools/multi_deck/
git commit -m "feat: add 6 multi-deck MCP tools (compatibility, energy_budget, bpm_ratio, timeline, loops, stem_embedding)"
```

---

### Task 13: Интеграционный тест и финальная проверка

- [ ] **Step 1: End-to-end тест**

```python
"""Integration test: entity_list + tools work together."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_stem_entity_registered():
    from app.registry.entity import EntityRegistry
    from app.registry.defaults import register_default_entities

    register_default_entities()
    assert "stem_features" in EntityRegistry.names()
    assert "track_section" in EntityRegistry.names()


@pytest.mark.asyncio
async def test_stem_features_view_has_key_fields():
    from app.schemas.stem_features import StemFeaturesView
    fields = StemFeaturesView.model_fields
    assert "kick_prominence" in fields
    assert "bpm" in fields
    assert "key_code" in fields
    assert "stem_name" in fields
    assert "integrated_lufs" in fields
    assert "inharmonicity" in fields  # L6 field


@pytest.mark.asyncio
async def test_track_section_view_has_stem_energy():
    from app.schemas.track_section import TrackSectionView
    fields = TrackSectionView.model_fields
    assert "stem_energy" in fields
    assert "section_type" in fields
```

- [ ] **Step 2: Полная проверка**

```bash
uv run ruff check && uv run mypy && uv run pytest -x -q
```

- [ ] **Step 3: Финальный коммит**

```bash
git add tests/
git commit -m "test: add integration tests for multi-deck toolkit"
```

- [ ] **Step 4: Проверить make check**

```bash
make check
```
