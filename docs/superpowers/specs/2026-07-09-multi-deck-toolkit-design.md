# Multi-Deck Toolkit — Design

> Date: 2026-07-09 · Status: approved · Branch: `feat/multi-deck-toolkit`
>
> Builds on:
> - `docs/superpowers/specs/2026-07-09-l6-deep-track-analysis-design.md` (L6 — stem separation, per-stem features, beatgrids, pgvector, cross-similarity)
> - `docs/superpowers/specs/2026-07-08-transition-render-refactor-design.md` (NeuralMix presets, transition picker, recipe system)
>
> Goal: дать AI-композитору простые инструменты («приборную панель») для свободного multi-deck (4-6 дек) сведения. AI сам решает что и как сводить — мы даём данные и вычисления.

---

## Summary

Текущая архитектура строго линейна: треки идут один за другим, переходы попарные (A→B). При этом в БД уже лежат исчерпывающие данные для multi-deck mixing:
- **StemFeatures** (126 полей на каждый из 4 стемов + original — L6 pipeline)
- **TrackSection** с per-stem энергией (drums/bass/vocals/other per section)
- **Beatgrid** с точным `first_downbeat_ms` (kick-phase + sub-beat refine)
- **CrossSimilarity** — Essentia pairwise DTW alignment
- **TrackEmbedding** — pgvector (5 типов, HNSW индекс)

Данные есть. Не хватает инструментов — MCP-тулов, которые AI дёргает на лету для принятия решений.

Этот spec добавляет 10 инструментов в два этапа:

1. **Разблокировка данных** (entity registration) — AI получает доступ к `stem_features` и `track_section` через generic `entity_list/get/aggregate`, может фильтровать по любым 126+ полям и строить любые хитрые запросы.
2. **Вычислительные тулы** — N-way частотная совместимость, энерго-бюджет, BPM-кратности, unified timeline, поиск лупов, stem-embedding search.

---

## Phase 1 — Entity Registration (разблокировка данных)

### 1.1 `stem_features` как entity

**Задача**: зарегистрировать `StemFeatures` в `EntityRegistry`, чтобы работали `entity_list("stem_features", ...)`, `entity_get("stem_features", id)`, `entity_aggregate("stem_features", ...)`.

**Что нужно:**

1. **View-схема** — Pydantic модель, отображающая все 126+ полей `StemFeatures`. Используем тот же паттерн, что и для `TrackAudioFeaturesComputed` (все поля nullable, `model_config = {"from_attributes": True}`). Схема живёт в `app/schemas/entity/`.

2. **Filter-схема** — Pydantic модель с `extra = "forbid"`. Поля смотреть-апы (`__eq`, `__gte`, `__lte`, `__range`, `__isnull`, `__in`):
   - `stem_name`: str (drums/bass/vocals/other/original)
   - `bpm`: float + range
   - `key_code`: int + range
   - `integrated_lufs`: float + range
   - `energy_mean`, `energy_max`, `energy_std`: float + range
   - 6-band energy values: float + range
   - spectral: float + range
   - rhythm: kick_prominence, onset_rate, pulse_clarity, hp_ratio — float + range
   - L6-only: chords_strength, inharmonicity, saturation_detected, click_detected, drum_bands
   - `analysis_level`: int + range

3. **Create/Update схемы** — минимальные (insert не нужен AI, upsert — через L6 pipeline). Можно заглушки, т.к. CRUD не основной use-case.

4. **Регистрация** в `app/registry/defaults.py`:
   ```python
   entity_registry.register(EntityConfig(
       name="stem_features",
       model=StemFeatures,
       repo_attr="stem_features",
       view_schema=StemFeatureViewSchema,
       filter_schema=StemFeatureFilterSchema,
       create_schema=...,
       update_schema=...,
       field_presets={"id": ["track_id", "stem_name"], "scoring": [...], "full": "*"},
       default_preset="summary",
       searchable_fields=(),
       filterable_fields={...},  # 30+ полей с операторами
       sortable_fields=("bpm", "key_code", "integrated_lufs", "energy_mean", "kick_prominence"),
       relations={},
       tags=frozenset({"namespace:analysis"}),
   ))
   ```

5. **Feature catalog** — добавить `STEM_FEATURE_CATALOG` в `app/resources/_feature_catalog.py`. Каждая запись: `name`, `type`, `unit`, `description_ru` (на русском — чтобы AI понимал что значит поле), `category` (tempo/loudness/energy/spectral/key/rhythm/danceability/quality).

6. **Ресурс** `reference://feature-catalog/stem_features` — отдаёт каталог полей stem_features, чтобы AI мог узнать что значат все 126 полей перед построением запроса.

### 1.2 `track_section` как entity

**Задача**: зарегистрировать `TrackSection` для поиска секций по типу, энергии, per-stem раскладке.

**View-схема**: `track_id`, `section_type` (0-11), `start_ms`, `end_ms`, `energy`, `confidence`, `lufs`, `spectral_centroid`, `stem_energy` (JSONB — dict с ключами drums/bass/vocals/other).

**Filter-схема**:
- `track_id`: int
- `section_type`: int + range
- `energy`: float + range
- `start_ms`, `end_ms`: int + range
- `lufs`: float + range

**Field presets**:
- `id`: `["track_id", "section_type", "start_ms", "end_ms"]`
- `summary`: `["track_id", "section_type", "start_ms", "end_ms", "energy", "lufs"]`
- `full`: `"*"`

**Ресурс** `reference://section-types` — маппинг section_type (0-11) → название, описание (intro, breakdown, buildup, drop, outro, etc.).

### 1.3 `EntityName` literal type

Добавить `"stem_features"` и `"track_section"` в `Literal[EntityName]` в `app/tools/entity/list.py` (строка 21-33) и везде, где используется этот тип.

### 1.4 JOIN-фильтрация stem_features по родителю

AI должен мочь: «найди все кики из треков с mood=peak_time, BPM 133-138».

**Подход**: двухшаговый. AI сам делает:
1. `entity_list("track_features", filters={"mood__eq": "peak_time", "bpm__gte": 133, "bpm__lte": 138}, fields=["track_id"])` → получает список track_id
2. `entity_list("stem_features", filters={"stem_name__eq": "drums", "track_id__in": [1,2,3,...]})` → получает stems

Generic JOIN не строим — это усложнит `BaseRepository.filter` без пропорциональной пользы. AI справляется с двухшаговыми запросами.

---

## Phase 2 — Computational Tools (вычислительные инструменты)

### 2.1 `stem_vertical_compatibility` — N-way совместимость

**Назначение**: «Можно ли играть эти N stem-ов одновременно? Где частотные конфликты?»

**Вход**:
```json
{
  "layers": [
    {"track_id": 1, "stem_name": "drums"},
    {"track_id": 2, "stem_name": "bass"},
    {"track_id": 3, "stem_name": "other"},
    {"track_id": 4, "stem_name": "vocals"}
  ]
}
```

**Выход**:
```json
{
  "overall_score": 0.78,
  "hard_reject": false,
  "per_band": {
    "sub": {"score": 0.85, "clash": false},
    "low": {"score": 0.62, "clash": true, "culprits": ["drums", "bass"]},
    "lowmid": {"score": 0.91, "clash": false},
    "mid": {"score": 0.74, "clash": false},
    "highmid": {"score": 0.88, "clash": false},
    "high": {"score": 0.95, "clash": false}
  },
  "key_compatibility": {"score": 0.7, "keys": ["4A", "4A", "4A", "7A"]},
  "bpm_compatibility": {"score": 0.92, "bpms": [135.0, 134.8, 135.1, 135.2]},
  "recommendations": ["low band clash between drums and bass — consider EQ cut at 150Hz on bass stem"]
}
```

**Алгоритм**:
1. Загрузить `StemFeatures` для всех слоёв из БД
2. **BPM**: Gauss-сравнение всех пар (расширение `bpm_distance` kernel на N-way → минимальная pairwise дистанция)
3. **Key**: Camelot-дистанция всех пар (расширение `camelot_lookup` на N-way)
4. **Per-band**: для каждой из 6 полос — pairwise overlap энергетических профилей. Если в одной полосе >1 stem с высокой энергией — clash.
5. **Overall**: взвешенная сумма per-band + key + bpm, с применением hard-constraints (Camelot > 5 → reject, BPM Δ > 10 → reject)

**Расположение**: `app/domain/multi_deck/compatibility.py`

### 2.2 `energy_budget` — бюджет энергии

**Назначение**: «Суммарный LUFS всех активных дек, per-band раскладка, headroom.»

**Вход**:
```json
{
  "layers": [
    {"track_id": 1, "stem_name": "drums", "gain_db": 0},
    {"track_id": 2, "stem_name": "bass", "gain_db": -2},
    {"track_id": 3, "stem_name": "other", "gain_db": -4}
  ],
  "target_lufs": -8.0
}
```

**Выход**:
```json
{
  "total_lufs": -7.2,
  "headroom_db": 0.8,
  "per_band": {
    "sub": {"total_lufs": -10.1, "headroom_db": -2.1, "warning": true},
    "low": {"total_lufs": -8.5, "headroom_db": -0.5, "warning": false},
    ...
  },
  "recommendation": "Sub-band overloaded. Reduce drums gain by 2 dB or apply low-shelf EQ on bass."
}
```

**Алгоритм**:
1. Загрузить per-stem `integrated_lufs` + `energy_sub` через `energy_high`
2. Применить gain_db к каждому слою
3. Суммировать для каждой полосы: `total_energy_band = sum(energy_band_i * 10^(gain_i / 10))`
4. Конвертировать обратно в LUFS для отчёта
5. Сравнить с target_lufs для каждой полосы — warning при превышении

**Расположение**: `app/domain/multi_deck/energy_budget.py`

### 2.3 `bpm_ratio_analyzer` — полиритмия

**Назначение**: «Какие BPM-пары дают музыкально интересные полиритмы? Где совпадают даунбиты?»

**Вход**:
```json
{
  "bpm_a": 130.0,
  "bpm_range": [120, 145],
  "ratios_of_interest": ["3:4", "2:3", "3:2", "4:3", "5:4", "4:5"]
}
```

**Выход**:
```json
{
  "bpm_a": 130.0,
  "matches": [
    {
      "bpm_b": 97.5,
      "ratio": 0.75,
      "ratio_label": "3:4",
      "error_pct": 0.0,
      "bars_to_align": 3,
      "seconds_to_align": 5.54
    },
    {
      "bpm_b": 173.33,
      "ratio": 1.333,
      "ratio_label": "4:3",
      "error_pct": 0.0,
      "bars_to_align": 4,
      "seconds_to_align": 5.54
    }
  ],
  "library_pairs": [
    {"bpm_b": 97.3, "track_title": "Deep State", "ratio_label": "3:4", "error_pct": 0.2}
  ]
}
```

**Алгоритм**:
1. Для каждого `ratio_of_interest` (например, `3:4` = 0.75), вычислить целевой BPM: `bpm_b = bpm_a * ratio` или `bpm_b = bpm_a / ratio`
2. Искать ближайшие BPM в библиотеке через `entity_aggregate(track_features, operation="histogram", field="bpm")`
3. `bars_to_align = lcm(numerator, denominator) * 4` (в долях)
4. `seconds_to_align = bars_to_align * (60 / bpm_a)`

**Расположение**: `app/domain/multi_deck/bpm_ratio.py`

### 2.4 `timeline_overlay` — unified timeline

**Назначение**: «Покажи секции нескольких треков на одном таймлайне с синхронизацией по даунбитам.»

**Вход**:
```json
{
  "track_ids": [1, 2, 3],
  "align_mode": "downbeat"
}
```

**Выход**:
```json
{
  "tracks": [
    {
      "track_id": 1,
      "title": "Dark Matter",
      "bpm": 135.0,
      "duration_ms": 360000,
      "sections": [
        {"type": "intro", "start_ms": 0, "end_ms": 32000, "energy": 0.3, "stem_energy": {"drums": 0.2, "bass": 0.1, ...}},
        {"type": "breakdown", "start_ms": 32000, ...}
      ]
    },
    ...
  ],
  "common_timeline": {
    "start_ms": 0,
    "end_ms": 420000,
    "bars": [...]
  }
}
```

**Алгоритм**:
1. Загрузить `TrackSection` для всех треков через `uow.track_sections.get_all_for_track(track_id)`
2. Загрузить `first_downbeat_ms` из `dj_beatgrids`
3. Выровнять: старт общего таймлайна = минимальный `first_downbeat_ms`, всё сдвигается относительно него
4. Отдать sections каждого трека в абсолютных ms

**Расположение**: `app/domain/multi_deck/timeline.py`

### 2.5 `find_loops` — поиск лупов

**Назначение**: «Где в этом треке стабильные 8-16 bar участки без вокала?»

**Вход**:
```json
{
  "track_id": 1,
  "min_bars": 8,
  "max_bars": 32,
  "exclude_vocals": true,
  "min_energy_stability": 0.7
}
```

**Выход**:
```json
{
  "track_id": 1,
  "bpm": 135.0,
  "bar_duration_ms": 1778,
  "loops": [
    {
      "section_id": 42,
      "section_type": "drop",
      "start_ms": 64000,
      "end_ms": 120000,
      "bars": 31.5,
      "energy_stability": 0.92,
      "stem_energy": {"drums": 0.8, "bass": 0.7, "vocals": 0.05, "other": 0.4},
      "loopable": true,
      "cue_point_ms": 64000
    }
  ]
}
```

**Алгоритм**:
1. Загрузить `TrackSection` для трека
2. Фильтровать по длине (`end_ms - start_ms >= min_bars * bar_duration_ms`)
3. Если `exclude_vocals`: `stem_energy.vocals < 0.15`
4. `energy_stability` = 1 - `energy_std` (нормализованная) — чем стабильнее энергия внутри секции, тем она лупабельнее
5. Сортировать по `energy_stability` desc

**Расположение**: `app/domain/multi_deck/loop_finder.py`

### 2.6 `stem_embedding_search` — pgvector по stem-ам

**Назначение**: «Найди басовые линии, похожие на эту, но с большей энергией.»

**Вход**:
```json
{
  "track_id": 1,
  "stem_name": "bass",
  "embedding_type": "timbral",
  "limit": 10,
  "exclude_track_ids": [1]
}
```

**Выход**: список `{track_id, stem_name, similarity, distance}`.

**Алгоритм**:
1. Загрузить embedding для `(track_id, stem_name, embedding_type)` из `track_embeddings`
2. `uow.track_embeddings.search_similar(query, embedding_type, limit, exclude_ids)` — уже есть
3. JOIN с `stem_features` для дополнительных фильтров (energy, key)

**Расположение**: расширение `app/tools/deep_analysis.py` — добавить параметр `stem_name` в `find_compatible_tracks` или новый тул.

---

## Architecture

### File structure (additions)

```
app/
  domain/
    multi_deck/
      __init__.py
      models.py              — MultiDeckLayer, CompatibilityResult, EnergyBudget, TimelineOverlay
      compatibility.py       — N-way stem vertical compatibility
      energy_budget.py       — combined energy dashboard
      bpm_ratio.py           — polyrhythm BPM ratio analyzer
      timeline.py            — unified section timeline
      loop_finder.py         — loopable section detector
  tools/
    multi_deck.py            — MCP tool definitions (6 new tools)
  schemas/
    entity/
      stem_features.py       — View/Filter/Create/Update Pydantic schemas
      track_section.py       — View/Filter/Create/Update Pydantic schemas
  resources/
    _feature_catalog.py      — + STEM_FEATURE_CATALOG
    multi_deck.py            — resources: feature-catalog/stem_features, section-types
  repositories/
    track_section.py         — TrackSectionRepository (CRUD, get_all_for_track)
  registry/
    defaults.py              — register stem_features + track_section entities
  models/
    (no changes — StemFeatures and TrackSection already exist)
```

### Tool surface

| Tool | Read-only | Idempotent | Namespace |
|------|-----------|------------|-----------|
| `entity_list("stem_features", ...)` | yes | yes | `crud:read` |
| `entity_list("track_section", ...)` | yes | yes | `crud:read` |
| `stem_vertical_compatibility` | yes | yes | default |
| `energy_budget` | yes | yes | default |
| `bpm_ratio_analyzer` | yes | yes | default |
| `timeline_overlay` | yes | yes | default |
| `find_loops` | yes | yes | default |
| `stem_embedding_search` | yes | yes | default |

---

## Out of Scope

- Multi-deck **composition logic** — AI сам решает что и как сводить. Инструменты только предоставляют данные
- Multi-deck **render pipeline** — рендер остаётся линейным. Мульти-дечный рендер (FFmpeg multi-stream) — отдельная будущая фаза
- Real-time stem separation — офлайн pre-computed через L6
- Изменение модели `DjSetVersion` / `DjSetItem` — пока остаётся линейной
- BPM-синхронизация при рендере (rubberband для разных BPM в параллельных слоях) — отдельная фаза
