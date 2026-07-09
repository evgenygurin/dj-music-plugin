# L6 Deep Track Analysis — Design Spec

Date: 2026-07-09
Status: approved (design phase)

## Purpose

Расширить существующий tiered-анализ треков (L0→L5) новым уровнем L6, который
обеспечивает исчерпывающие данные для multi-deck (6-8 дек) mixing, визуализации
треков и их совместимости. L6 = stem separation (Demucs 4-stem) + полный per-stem
анализ (librosa + Essentia ×5) + beatgrid на каждый трек + pgvector эмбеддинги +
CrossSimilarityMatrix + структурный анализ с per-stem энергетикой.

Данные хранятся в PostgreSQL + Supabase Storage (free tier: 500 MB DB, 1 GB Storage).
Аудиостемы (WAV/FLAC) остаются локально — в облаке только аналитика.

L6 запускается **только для треков-кандидатов** (отобраны в сет или как переходные
кандидаты), не для всей библиотеки.

## Scope

### In scope

1. **Stem separation** — Demucs htdemucs (4-stem: vocals, drums, bass, other)
2. **Per-stem features** — полный пайплайн (librosa + Essentia) ×5 прогонов:
   original + 4 стема, ~70 фич каждый → новая таблица `stem_features`
3. **Beatgrid per track** — kick-phase + sub-beat refine → заполняем существующую
   `dj_beatgrids`
4. **Структурный анализ** — расширяем `track_sections`: per-section LUFS,
   spectral_centroid, stem_energy JSONB (энергия каждого стема в секции)
5. **pgvector embeddings** — 5 типов на трек (timbral, harmonic, rhythmic, energy,
   full) + HNSW индекс → новая таблица `track_embeddings`
6. **CrossSimilarityMatrix** — Essentia pairwise similarity для multi-deck
   совместимости + точных mix-точек
7. **Timeseries в Supabase Storage** — энергия, chroma, spectral, beats (NPZ) +
   per-stem → bucket `track-timeseries/`
8. **Waveform в Supabase Storage** — сжатый envelope для визуализации → bucket
   `track-waveforms/`
9. **Новые Essentia алгоритмы** — chords, HPCP entropy/crest, inharmonicity,
   meter, audio defects (clicks, gaps, hum, saturation)
10. **Supabase Storage SDK** — интеграция `supabase-py` для upload/download

### Out of scope

- Стем-аудиофайлы в облаке (остаются локально)
- L6 для всей библиотеки (только для кандидатов)
- Real-time стем-сепарация (только офлайн pre-computed)
- Миграция существующих локальных NPZ в Supabase Storage (только новые L6)
- Визуализация треков (отдельная будущая фаза — использует данные из этой спеки)

## Free Tier Budget

| Ресурс | Лимит | L6 потребление (на 1000 треков) |
|--------|-------|-------------------------------|
| PostgreSQL | 500 MB | ~25 MB (stem_features + embeddings + sections) |
| Storage | 1 GB | ~710 MB (timeseries) + ~10 MB (waveforms) |
| Egress | 5 GB / мес | ~720 MB при полной выгрузке |

## Architecture

### Components

```
app/domain/deep_analysis/
  models.py              — StemFeatures, TrackEmbedding (dataclass-модели)
  orchestrator.py        — L6AnalysisOrchestrator (запуск полного пайплайна)

app/audio/deep/
  demucs_runner.py       — Demucs 4-stem (htdemucs), subprocess
  stem_analyzer.py       — per-stem pipeline ×5 прогонов через AnalyzerRegistry
  beatgrid_builder.py    — kick-phase + sub-beat refine (существующий код из render)
  structure_analyzer.py  — SBic segmentation + per-section stem energy
  embedding_builder.py   — pgvector embedding из фич (numpy → vector)
  cross_similarity.py    — Essentia CrossSimilarityMatrix + mix-point detection
  timeseries_store.py    — загрузка NPZ в Supabase Storage
  waveform_store.py      — генерация + загрузка waveform JSON

app/repositories/
  stem_features.py       — CRUD для stem_features
  track_embedding.py     — CRUD + ANN search (<=> cosine distance)
  supabase_storage.py    — upload/download из Supabase Storage buckets

app/handlers/
  deep_analysis.py       — handler для запуска L6 анализа (фоновый task,
                            паттерн как у render_beatgrid/render_mixdown)

app/providers/supabase/
  storage_client.py      — supabase-py Storage client wrapper
  config.py              — credentials (SUPABASE_URL, SUPABASE_KEY)
```

### Data Flow

```
Track selected for set / transition candidate
        │
        ▼
   deep_analysis(track_id, level=6)
        │
        ├─► [1] Demucs 4-stem → WAV локально
        │
        ├─► [2] Pipeline ×5 (original + vocals/drums/bass/other)
        │        └─► stem_features (PostgreSQL)
        │
        ├─► [3] Beatgrid (kick-phase + phase-refine)
        │        └─► dj_beatgrids (PostgreSQL)
        │
        ├─► [4] SBic segmentation + per-section per-stem energy
        │        └─► track_sections (PostgreSQL, расширенная)
        │
        ├─► [5] Embedding extraction (5 типов × 5 стемов)
        │        └─► track_embeddings (PostgreSQL, pgvector)
        │
        ├─► [6] CrossSimilarityMatrix (pairwise vs. пул кандидатов)
        │        └─► cross_similarity (PostgreSQL)
        │
        ├─► [7] Timeseries NPZ → Supabase Storage
        │        └─► timeseries_references.storage_uri обновлён
        │
        └─► [8] Waveform JSON → Supabase Storage
                 └─► (Storage-only, резолвится по конвенции:
                      track-waveforms/{track_id}/waveform.json)
```

## Database Changes

### New Tables

#### stem_features

```sql
CREATE TABLE stem_features (
    id SERIAL PRIMARY KEY,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    stem_name VARCHAR(16) NOT NULL CHECK (stem_name IN (
        'original', 'vocals', 'drums', 'bass', 'other'
    )),
    pipeline_run_id INTEGER REFERENCES feature_extraction_runs(id),
    analysis_level INTEGER DEFAULT 6 CHECK (analysis_level BETWEEN 0 AND 6),

    -- Tempo (4)
    bpm FLOAT, bpm_confidence FLOAT, bpm_stability FLOAT, variable_tempo BOOLEAN,
    -- Loudness (7)
    integrated_lufs FLOAT, short_term_lufs_mean FLOAT, momentary_max FLOAT,
    rms_dbfs FLOAT, true_peak_db FLOAT, crest_factor_db FLOAT, loudness_range_lu FLOAT,
    -- Energy (16)
    energy_mean FLOAT, energy_max FLOAT, energy_std FLOAT, energy_slope FLOAT,
    energy_sub FLOAT, energy_low FLOAT, energy_lowmid FLOAT, energy_mid FLOAT,
    energy_highmid FLOAT, energy_high FLOAT,
    energy_sub_ratio FLOAT, energy_low_ratio FLOAT, energy_lowmid_ratio FLOAT,
    energy_mid_ratio FLOAT, energy_highmid_ratio FLOAT, energy_high_ratio FLOAT,
    -- Spectral (8)
    spectral_centroid_hz FLOAT, spectral_rolloff_85 FLOAT, spectral_rolloff_95 FLOAT,
    spectral_flatness FLOAT, spectral_flux_mean FLOAT, spectral_flux_std FLOAT,
    spectral_slope FLOAT, spectral_contrast FLOAT,
    -- Key (5)
    key_code INTEGER, key_confidence FLOAT, atonality BOOLEAN,
    hnr_db FLOAT, chroma_entropy FLOAT,
    -- Rhythm (5)
    mfcc_vector VARCHAR(500), hp_ratio FLOAT, onset_rate FLOAT,
    pulse_clarity FLOAT, kick_prominence FLOAT,
    -- P1 Essentia (6)
    danceability FLOAT, dynamic_complexity FLOAT, dissonance_mean FLOAT,
    tonnetz_vector VARCHAR(500), tempogram_ratio_vector VARCHAR(500),
    beat_loudness_band_ratio VARCHAR(500),
    -- P2 Essentia (8)
    spectral_complexity_mean FLOAT, pitch_salience_mean FLOAT,
    bpm_histogram_first_peak_weight FLOAT, bpm_histogram_second_peak_bpm FLOAT,
    bpm_histogram_second_peak_weight FLOAT, phrase_boundaries_ms VARCHAR(2000),
    dominant_phrase_bars SMALLINT, first_downbeat_ms FLOAT,
    -- NEW: L6-only Essentia
    chords_strength FLOAT, chords_changes_rate FLOAT,
    hpcp_entropy FLOAT, hpcp_crest FLOAT,
    inharmonicity FLOAT,
    meter VARCHAR(16),         -- '4/4', '3/4', etc.
    click_detected BOOLEAN,    -- audio QA
    saturation_detected BOOLEAN,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(track_id, stem_name)
);

CREATE INDEX idx_stem_features_track ON stem_features(track_id);
```

#### track_embeddings

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE track_embeddings (
    id SERIAL PRIMARY KEY,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    stem_name VARCHAR(16) DEFAULT 'original',
    embedding_type VARCHAR(32) NOT NULL CHECK (embedding_type IN (
        'timbral',    -- MFCC + spectral centroid/flux/rolloff → 64 dims
        'harmonic',   -- Tonnetz + HPCP + chroma + key → 128 dims
        'rhythmic',   -- onset rate + pulse clarity + kick + beat-loudness → 32 dims
        'energy',     -- LUFS + energy band ratios + crest → 32 dims
        'full'        -- конкатенация всех фич → 256 dims
    )),
    embedding vector(256),  -- max dims, smaller embeddings zero-padded
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(track_id, stem_name, embedding_type)
);

CREATE INDEX idx_track_embeddings_hnsw
    ON track_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
```

#### cross_similarity

```sql
CREATE TABLE cross_similarity (
    id SERIAL PRIMARY KEY,
    track_a_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    track_b_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    stem_name VARCHAR(16) DEFAULT 'original',
    -- CrossSimilarityMatrix output: N×M matrix of frame-level similarities
    matrix_shape VARCHAR(50),            -- "N_frames_a x M_frames_b"
    best_match_offset_ms FLOAT,          -- where track B best aligns to A
    best_match_score FLOAT,              -- similarity at best alignment
    alignment_path JSONB,                -- DTW alignment path [(i,j), ...]
    segment_matches JSONB,               -- per-section matches:
                                         -- [{"a_section": "build_up", "b_section": "intro",
                                         --   "offset_ms": 240000, "score": 0.87}, ...]
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(track_a_id, track_b_id, stem_name)
);

CREATE INDEX idx_cross_similarity_a ON cross_similarity(track_a_id);
CREATE INDEX idx_cross_similarity_b ON cross_similarity(track_b_id);
```

### Modified Tables

#### track_audio_features_computed

```sql
-- Изменить CHECK constraint:
-- Было:  CHECK (analysis_level BETWEEN 0 AND 5)
-- Стало: CHECK (analysis_level BETWEEN 0 AND 6)
```

#### track_sections

```sql
ALTER TABLE track_sections ADD COLUMN lufs FLOAT;
ALTER TABLE track_sections ADD COLUMN spectral_centroid FLOAT;
ALTER TABLE track_sections ADD COLUMN stem_energy JSONB;
-- stem_energy: {"vocals": 0.12, "drums": 0.89, "bass": 0.73, "other": 0.34}
```

#### dj_beatgrids

Без изменений схемы. L6-анализ заполняет существующие колонки:
`bpm`, `first_downbeat_ms`, `grid_offset_ms`, `confidence`, `variable_tempo`,
`canonical` через `uow.audio_file.register_beatgrid()`.

#### timeseries_references

Без изменений схемы. L6-анализ обновляет `storage_uri` на Supabase Storage URL:
`s3://track-timeseries/{track_id}/energy.npz`

## Supabase Storage

### Buckets

```
track-timeseries/        (private)
  {track_id}/
    energy.npz           — energy envelope, shape (N_frames,)
    chroma.npz           — chromagram, shape (12, N_frames)
    spectral.npz         — spectral centroid+rolloff+flux over time
    beats.npz            — beat positions + confidence
    stem_{name}/          — per-stem timeseries
      energy.npz
      chroma.npz
      spectral.npz

track-waveforms/         (private)
  {track_id}/
    waveform.json        — {"track_id": N, "duration_ms": M,
                            "peaks": [0.0..1.0], "n_points": 1000,
                            "color": "original"}
    stem_{name}/
      waveform.json      — per-stem waveform envelope
```

### Integration

Используем `supabase-py` (добавить в `[project.optional-dependencies] supabase`):

```python
from supabase import create_client, Client

storage: StorageClient = supabase.storage

# Upload
storage.from_("track-timeseries").upload(
    f"{track_id}/energy.npz",
    npz_bytes,
    {"content-type": "application/octet-stream"}
)

# Download
data = storage.from_("track-timeseries").download(f"{track_id}/energy.npz")
```

Конфигурация через env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (нужен service_key
для server-side upload, анонимного ключа недостаточно для записи в приватный бакет).

## pgvector — ANN Search Use Cases

### Поиск похожих треков

```sql
-- Найти 10 треков, наиболее похожих по тембру на выбранный
SELECT t.id, t.title,
       1 - (e.embedding <=> $query_embedding) AS similarity
FROM track_embeddings e
JOIN tracks t ON t.id = e.track_id
WHERE e.embedding_type = 'timbral'
  AND e.stem_name = 'original'
ORDER BY e.embedding <=> $query_embedding
LIMIT 10;
```

### Multi-deck совместимость

```sql
-- Какие 5 треков лучше всего лягут на комбинацию из 3 уже играющих?
-- Конструируем query vector как взвешенную сумму эмбеддингов активных деков
SELECT t.id, t.title,
       1 - (e.embedding <=> $composite_query) AS compatibility
FROM track_embeddings e
JOIN tracks t ON t.id = e.track_id
WHERE e.embedding_type = 'full'
  AND e.track_id NOT IN ($active_deck_ids)
ORDER BY e.embedding <=> $composite_query
LIMIT 5;
```

## L6 Pipeline — Step by Step

### Pre-requisites

Трек должен иметь:
- `DjLibraryItem` с `file_path` (локальный аудиофайл)
- `TrackAudioFeaturesComputed` с `analysis_level >= 3` (L3+)
- Быть отобранным в сет или как кандидат перехода

### Step 1: Demucs 4-stem separation

```python
# app/audio/deep/demucs_runner.py
import subprocess
from pathlib import Path

def run_demucs(input_path: Path, output_dir: Path) -> dict[str, Path]:
    """
    Запускает python -m demucs --two-stems=vocals -n htdemucs
    Возвращает пути к 4 стемам + original.
    """
    subprocess.run([
        "python", "-m", "demucs",
        "-n", "htdemucs",
        "-o", str(output_dir),
        str(input_path),
    ], check=True)
    # demucs создаёт output_dir/htdemucs/{track_name}/
    # с файлами vocals.wav, drums.wav, bass.wav, other.wav
    stem_dir = output_dir / "htdemucs" / input_path.stem
    return {
        "vocals": stem_dir / "vocals.wav",
        "drums": stem_dir / "drums.wav",
        "bass": stem_dir / "bass.wav",
        "other": stem_dir / "other.wav",
    }
```

### Step 2: Per-stem analysis pipeline

```python
# app/audio/deep/stem_analyzer.py
async def analyze_stems(
    uow: UnitOfWork,
    track_id: int,
    stem_paths: dict[str, Path],
    original_path: Path,
) -> dict[str, dict]:
    """
    Прогоняет существующий AnalyzerRegistry (librosa + Essentia)
    на каждом из 5 аудио: original + 4 стема.
    Возвращает dict[stem_name, features_dict].
    """
    results = {}
    for stem_name, path in {"original": original_path, **stem_paths}.items():
        features = await run_pipeline(uow, track_id, path, level=6)
        results[stem_name] = features
    return results
```

Используем существующий `app/audio/pipeline.py` — он уже поддерживает
`AnalyzerRegistry` и `ProcessPool`. Добавляем новые L6-only анализаторы
(chords, HPCP, inharmonicity, meter, audio defects) в реестр.

### Step 3: Beatgrid

Используем существующий код из `app/audio/render/kick_phase.py` +
`phase_refine.py`, но результат пишем не в `beatgrid.json` для set-version,
а в `dj_beatgrids` через `uow.audio_file.register_beatgrid()`.

### Step 4: Structural segmentation

```python
# app/audio/deep/structure_analyzer.py
def analyze_structure(
    audio_path: Path,
    stem_paths: dict[str, Path],
) -> list[Section]:
    """
    1. SBic segmentation (Essentia) — находит границы секций
    2. Per-section per-stem energy — для каждого стема вычисляет среднюю
       энергию в каждой секции
    3. Сохраняет в track_sections с заполненными lufs, spectral_centroid,
       stem_energy
    """
```

### Step 5: Embedding extraction

```python
# app/audio/deep/embedding_builder.py
def build_embeddings(features: dict[str, dict]) -> dict[str, np.ndarray]:
    """
    Из фич строит 5 типов эмбеддингов:
    - timbral:    np.concat([mfcc, spectral_centroid, flux, rolloff])
    - harmonic:   np.concat([tonnetz, hpcp, chroma, key_onehot])
    - rhythmic:   np.concat([onset_rate, pulse_clarity, kick_prominence, ...])
    - energy:     np.concat([lufs, energy_bands, crest_factor, ...])
    - full:       np.concat(all above) — 256 dims

    Стандартизация: numpy (mean/std по библиотеке), sklearn не нужен —
    размерность мала для сложной нормализации.
    """
```

### Step 6: CrossSimilarityMatrix

```python
# app/audio/deep/cross_similarity.py
def compute_cross_similarity(
    track_a_path: Path,
    track_b_path: Path,
    stem_name: str = "original",
) -> CrossSimilarityResult:
    """
    Essentia CrossSimilarityMatrix между двумя треками.
    Возвращает:
    - matrix_shape
    - best_match_offset_ms — лучшее смещение трека B относительно A
    - alignment_path — DTW путь
    - segment_matches — какие секции трека A совпадают с какими секциями B
    """
```

Для multi-deck: вычисляется не для всех N×(N-1) пар, а для пула кандидатов
(треки в сете + соседи по pgvector ANN).

### Step 7-8: Timeseries + waveform upload

```python
# app/audio/deep/timeseries_store.py
async def upload_timeseries(
    storage: SupabaseStorage,
    track_id: int,
    stem_name: str,
    timeseries: dict[str, np.ndarray],
) -> None:
    for name, data in timeseries.items():
        npz_bytes = _to_npz_bytes(data)
        storage.upload(
            bucket="track-timeseries",
            path=f"{track_id}/stem_{stem_name}/{name}.npz"
            if stem_name != "original"
            else f"{track_id}/{name}.npz",
            data=npz_bytes,
        )
    # Обновить timeseries_references.storage_uri
```

## MCP Surface

### New Tools

```python
# app/tools/deep_analysis.py

@tool(
    "deep_analyze_track",
    description="Run L6 deep analysis on a track: stems + per-stem features + beatgrid + embeddings + cross-similarity. Heavy — background task.",
    annotations={"destructiveHint": False, "idempotentHint": True},
)
async def deep_analyze_track(
    track_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> DeepAnalysisResult:
    """Запускает L6 анализ. Если уже есть — возвращает существующий."""
    ...

@tool(
    "deep_analyze_pool",
    description="Run L6 deep analysis on a pool of candidate tracks (set members or transition candidates). Batch background task.",
    annotations={"destructiveHint": False},
)
async def deep_analyze_pool(
    track_ids: list[int],
    uow: UnitOfWork = Depends(get_uow),
) -> DeepAnalysisPoolResult:
    ...

@tool(
    "find_compatible_tracks",
    description="ANN search for tracks compatible with a given set of active deck tracks. Uses pgvector embeddings for fast similarity search across 6-8 deck scenarios.",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def find_compatible_tracks(
    active_track_ids: list[int],
    embedding_type: str = "full",
    limit: int = 20,
    uow: UnitOfWork = Depends(get_uow),
) -> list[CompatibleTrack]:
    ...

@tool(
    "get_cross_similarity",
    description="Get CrossSimilarityMatrix analysis between two tracks: best alignment offset, DTW path, per-section segment matches.",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_cross_similarity(
    track_a_id: int,
    track_b_id: int,
    stem_name: str = "original",
    uow: UnitOfWork = Depends(get_uow),
) -> CrossSimilarityResult:
    ...
```

### New Resources

```python
# app/resources/track_deep.py

@resource(
    "local://tracks/{id}/deep_features{?stem}",
    mime_type="application/json",
    tags={"core", "entity:track", "view:deep_analysis"},
)
async def track_deep_features(
    id: int,
    stem: str = "original",
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Per-stem features for a track (L6). Defaults to original mix,
    pass stem=vocals|drums|bass|other for stem-specific."""
    ...

@resource(
    "local://tracks/{id}/structure",
    mime_type="application/json",
    tags={"core", "entity:track", "view:structure"},
)
async def track_structure(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Track sections with per-section LUFS, spectral centroid, per-stem energy."""
    ...

@resource(
    "local://tracks/{id}/waveform{?stem}",
    mime_type="application/json",
    tags={"core", "entity:track", "view:waveform"},
)
async def track_waveform(
    id: int,
    stem: str = "original",
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Pre-computed waveform envelope for visualization (1000 points)."""
    ...
```

## Error Handling

- Трек без `DjLibraryItem` → `NotFoundError("library_item", track_id)`
- Трек без L3+ анализа → `PreconditionError("L3+ analysis required before L6")`
- Demucs crash / GPU out of memory → `DeepAnalysisError("stem separation failed", cause)`
- Supabase Storage upload fail → retry 3× с exponential backoff, затем
  `StorageError("upload failed for track {id}")`
- pgvector extension не установлен → `ConfigurationError("CREATE EXTENSION vector")`
- L6 уже выполнен → возвращаем существующие данные (idempotent)

## Non-goals / Explicit Deferrals

- **Stem audio in cloud** — файлы WAV/FLAC остаются локально
- **Real-time stem separation** — только офлайн pre-computed
- **Full library L6** — только для кандидатов в сеты и переходы
- **Migration of existing local NPZ** — только новые L6 треки пишутся в Supabase Storage
- **Visualization UI** — отдельная фаза, потребляет данные из этой спеки
- **Streaming/download from Supabase Storage** — данные читаются сервером, кешируются, отдаются клиенту через MCP ресурсы

## Dependencies

Добавить в `pyproject.toml`:

```toml
[project.optional-dependencies]
supabase = [
    "supabase>=2.0",       # supabase-py (пакет называется 'supabase' на PyPI)
    "pgvector>=0.3",       # уже есть в postgres extras
]
```

Уже есть и используются:
- `demucs>=4.0` (stems extras)
- `torch>=2.0` (stems extras)
- `librosa>=0.10` (audio extras)
- `essentia==2.1b6.dev1389` (audio extras)
- `scipy>=1.12` (audio extras)
- `numpy>=1.26`
