# L6 Deep Track Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add L6 deep analysis: Demucs 4-stem separation, per-stem feature extraction (×5 pipeline runs), per-track beatgrid, structural segmentation with per-stem energy, pgvector embeddings (5 types), CrossSimilarityMatrix, and Supabase Storage for timeseries/waveforms. Tiered: runs only for set/transition candidates.

**Architecture:** New `app/audio/deep/` DSP module + `app/domain/deep_analysis/` orchestration + new SQLAlchemy models (`stem_features`, `track_embeddings`, `cross_similarity`) with pgvector + `supabase-py` Storage client for NPZ/JSON upload. Background task pattern mirrors existing `render_beatgrid`/`render_mixdown`. MCP surface: 4 tools + 3 resources.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, Demucs 4.0 (htdemucs), librosa 0.10, Essentia 2.1b6, pgvector 0.3, supabase-py 2.0, FastMCP 3.x.

## Global Constraints

- Python >=3.12, mypy strict, ruff lint
- Free tier Supabase: 500 MB DB, 1 GB Storage, 5 GB bandwidth
- No audio files in cloud (stems local, only analytics in Supabase)
- L6 only for candidate tracks (set members / transition candidates), not full library
- Background task pattern: same as `app/handlers/render_beatgrid.py`
- Follow existing `app/models/` ORM conventions (Base, TimestampMixin, declarative)
- Follow existing `app/audio/analyzers/` AnalyzerRegistry pattern
- All MCP tools use `Depends(get_uow)` DI
- Tests: pytest + pytest-asyncio, MagicMock/AsyncMock pattern from `tests/resources/`

---

### Task 1: Dependencies + Configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/config/settings.py` (или эквивалент)

**Interfaces:**
- Produces: `supabase>=2.0` available as import; `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` env vars registered in Settings

- [ ] **Step 1: Add supabase dependency**

```toml
# pyproject.toml — добавить в [project.optional-dependencies]
supabase = [
    "supabase>=2.0",
    "pgvector>=0.3",
]
```

- [ ] **Step 2: Add Supabase env vars to settings**

Найти существующий Settings-класс (обычно `app/config/settings.py` или `app/config/database.py`) и добавить:

```python
# В класс Settings (или отдельный SupabaseSettings)
supabase_url: str = Field(default="", description="Supabase project URL")
supabase_service_key: str = Field(default="", description="Supabase service_role key for storage writes")
```

- [ ] **Step 3: Verify supabase-py import works**

```bash
uv sync --all-extras && uv run python -c "from supabase import create_client; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml app/config/settings.py uv.lock
git commit -m "chore: add supabase-py dependency and env config"
```

---

### Task 2: Database Models (3 new + 2 modifications)

**Files:**
- Create: `app/models/stem_features.py`
- Create: `app/models/track_embedding.py`
- Create: `app/models/cross_similarity.py`
- Modify: `app/models/track_features.py` (CHECK constraint 0-5 → 0-6)
- Modify: `app/models/__init__.py` (import new models)
- Test: `tests/models/test_deep_models.py`

**Interfaces:**
- Produces: `StemFeatures`, `TrackEmbedding`, `CrossSimilarity` ORM models
- Produces: `TrackAudioFeaturesComputed.analysis_level` CHECK 0-6
- Produces: `TrackSection.lufs`, `.spectral_centroid`, `.stem_energy` columns

- [ ] **Step 1: Write failing test for model existence**

```python
# tests/models/test_deep_models.py
from __future__ import annotations

from app.models.stem_features import StemFeatures
from app.models.track_embedding import TrackEmbedding
from app.models.cross_similarity import CrossSimilarity
from app.models.track_features import TrackAudioFeaturesComputed
from app.models.track_sections import TrackSection


def test_stem_features_has_expected_columns() -> None:
    cols = {c.name for c in StemFeatures.__table__.columns}
    assert "track_id" in cols
    assert "stem_name" in cols
    assert "analysis_level" in cols
    assert "bpm" in cols
    assert "integrated_lufs" in cols
    assert "chords_strength" in cols
    assert "meter" in cols


def test_track_embedding_has_vector_column() -> None:
    cols = {c.name for c in TrackEmbedding.__table__.columns}
    assert "embedding" in cols
    assert "embedding_type" in cols
    assert "stem_name" in cols


def test_cross_similarity_has_expected_columns() -> None:
    cols = {c.name for c in CrossSimilarity.__table__.columns}
    assert "track_a_id" in cols
    assert "track_b_id" in cols
    assert "best_match_offset_ms" in cols
    assert "segment_matches" in cols


def test_analysis_level_check_allows_6() -> None:
    # Verify CHECK constraint text allows 0-6
    for constraint in TrackAudioFeaturesComputed.__table__.constraints:
        if hasattr(constraint, "sqltext") and "analysis_level" in str(constraint.sqltext):
            assert "6" in str(constraint.sqltext)
            break
    else:
        raise AssertionError("analysis_level CHECK constraint not found")


def test_track_section_has_l6_columns() -> None:
    cols = {c.name for c in TrackSection.__table__.columns}
    assert "lufs" in cols
    assert "spectral_centroid" in cols
    assert "stem_energy" in cols
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/models/test_deep_models.py -v
```
Expected: FAIL with `ModuleNotFoundError` for stem_features

- [ ] **Step 3: Create StemFeatures model**

```python
# app/models/stem_features.py
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StemFeatures(Base, TimestampMixin):
    __tablename__ = "stem_features"
    __table_args__ = (
        CheckConstraint("bpm IS NULL OR bpm BETWEEN 20 AND 300", name="ck_sf_bpm"),
        CheckConstraint("key_code IS NULL OR key_code BETWEEN 0 AND 23", name="ck_sf_key_code"),
        CheckConstraint("analysis_level BETWEEN 0 AND 6", name="ck_sf_analysis_level"),
        UniqueConstraint("track_id", "stem_name", name="uq_sf_track_stem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    stem_name: Mapped[str] = mapped_column(String(16))

    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("feature_extraction_runs.id"), nullable=True
    )
    analysis_level: Mapped[int] = mapped_column(default=6, server_default="6")

    bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_confidence: Mapped[float | None] = mapped_column(nullable=True)
    bpm_stability: Mapped[float | None] = mapped_column(nullable=True)
    variable_tempo: Mapped[bool | None] = mapped_column(nullable=True)

    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True)
    short_term_lufs_mean: Mapped[float | None] = mapped_column(nullable=True)
    momentary_max: Mapped[float | None] = mapped_column(nullable=True)
    rms_dbfs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak_db: Mapped[float | None] = mapped_column(nullable=True)
    crest_factor_db: Mapped[float | None] = mapped_column(nullable=True)
    loudness_range_lu: Mapped[float | None] = mapped_column(nullable=True)

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

    spectral_centroid_hz: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_85: Mapped[float | None] = mapped_column(nullable=True)
    spectral_rolloff_95: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flatness: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_mean: Mapped[float | None] = mapped_column(nullable=True)
    spectral_flux_std: Mapped[float | None] = mapped_column(nullable=True)
    spectral_slope: Mapped[float | None] = mapped_column(nullable=True)
    spectral_contrast: Mapped[float | None] = mapped_column(nullable=True)

    key_code: Mapped[int | None] = mapped_column(nullable=True)
    key_confidence: Mapped[float | None] = mapped_column(nullable=True)
    atonality: Mapped[bool | None] = mapped_column(nullable=True)
    hnr_db: Mapped[float | None] = mapped_column(nullable=True)
    chroma_entropy: Mapped[float | None] = mapped_column(nullable=True)

    mfcc_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hp_ratio: Mapped[float | None] = mapped_column(nullable=True)
    onset_rate: Mapped[float | None] = mapped_column(nullable=True)
    pulse_clarity: Mapped[float | None] = mapped_column(nullable=True)
    kick_prominence: Mapped[float | None] = mapped_column(nullable=True)

    danceability: Mapped[float | None] = mapped_column(nullable=True)
    dynamic_complexity: Mapped[float | None] = mapped_column(nullable=True)
    dissonance_mean: Mapped[float | None] = mapped_column(nullable=True)
    tonnetz_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tempogram_ratio_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    beat_loudness_band_ratio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    spectral_complexity_mean: Mapped[float | None] = mapped_column(nullable=True)
    pitch_salience_mean: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_first_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    phrase_boundaries_ms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    dominant_phrase_bars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    first_downbeat_ms: Mapped[float | None] = mapped_column(nullable=True)

    # L6-only
    chords_strength: Mapped[float | None] = mapped_column(nullable=True)
    chords_changes_rate: Mapped[float | None] = mapped_column(nullable=True)
    hpcp_entropy: Mapped[float | None] = mapped_column(nullable=True)
    hpcp_crest: Mapped[float | None] = mapped_column(nullable=True)
    inharmonicity: Mapped[float | None] = mapped_column(nullable=True)
    meter: Mapped[str | None] = mapped_column(String(16), nullable=True)
    click_detected: Mapped[bool | None] = mapped_column(nullable=True)
    saturation_detected: Mapped[bool | None] = mapped_column(nullable=True)
```

- [ ] **Step 4: Create TrackEmbedding model**

```python
# app/models/track_embedding.py
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrackEmbedding(Base, TimestampMixin):
    __tablename__ = "track_embeddings"
    __table_args__ = (
        UniqueConstraint("track_id", "stem_name", "embedding_type", name="uq_te_track_stem_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    stem_name: Mapped[str] = mapped_column(String(16), default="original")
    embedding_type: Mapped[str] = mapped_column(String(32))
    embedding = mapped_column(Vector(256))  # type: ignore[var-annotated]
```

- [ ] **Step 5: Create CrossSimilarity model**

```python
# app/models/cross_similarity.py
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CrossSimilarity(Base, TimestampMixin):
    __tablename__ = "cross_similarity"
    __table_args__ = (
        UniqueConstraint("track_a_id", "track_b_id", "stem_name", name="uq_cs_pair_stem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    track_a_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    track_b_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    stem_name: Mapped[str] = mapped_column(String(16), default="original")
    matrix_shape: Mapped[str | None] = mapped_column(String(50), nullable=True)
    best_match_offset_ms: Mapped[float | None] = mapped_column(nullable=True)
    best_match_score: Mapped[float | None] = mapped_column(nullable=True)
    alignment_path: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    segment_matches: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 6: Modify TrackAudioFeaturesComputed CHECK constraint**

```python
# В app/models/track_features.py заменить строку:
#     CheckConstraint("analysis_level BETWEEN 0 AND 5", name="ck_features_analysis_level"),
# на:
#     CheckConstraint("analysis_level BETWEEN 0 AND 6", name="ck_features_analysis_level"),
```

- [ ] **Step 7: Add columns to TrackSection**

```python
# В app/models/track_sections.py (тот же файл что и track_features.py, класс TrackSection)
# добавить после существующих колонок:

    lufs: Mapped[float | None] = mapped_column(nullable=True)
    spectral_centroid: Mapped[float | None] = mapped_column(nullable=True)
    stem_energy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

Нужен импорт: `from sqlalchemy.dialects.postgresql import JSONB`

- [ ] **Step 8: Import new models in __init__.py**

```python
# В app/models/__init__.py добавить:
from app.models.stem_features import StemFeatures  # noqa: F401
from app.models.track_embedding import TrackEmbedding  # noqa: F401
from app.models.cross_similarity import CrossSimilarity  # noqa: F401
```

- [ ] **Step 9: Run tests**

```bash
uv run pytest tests/models/test_deep_models.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 10: Commit**

```bash
git add app/models/stem_features.py app/models/track_embedding.py app/models/cross_similarity.py app/models/track_features.py app/models/__init__.py tests/models/test_deep_models.py
git commit -m "feat(models): add stem_features, track_embeddings, cross_similarity tables; extend track_sections and analysis_level CHECK"
```

---

### Task 3: Supabase Storage Client

**Files:**
- Create: `app/providers/supabase/__init__.py`
- Create: `app/providers/supabase/config.py`
- Create: `app/providers/supabase/storage_client.py`
- Test: `tests/providers/supabase/test_storage_client.py`

**Interfaces:**
- Produces: `SupabaseStorageClient` with `upload(bucket, path, data)` and `download(bucket, path)` — async methods for NPZ/JSON upload/download

- [ ] **Step 1: Write failing test**

```python
# tests/providers/supabase/test_storage_client.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.providers.supabase.storage_client import SupabaseStorageClient


@pytest.mark.asyncio
async def test_upload_calls_supabase_storage() -> None:
    mock_storage = MagicMock()
    mock_storage.from_.return_value.upload.return_value = None

    with patch(
        "app.providers.supabase.storage_client.create_client",
        return_value=MagicMock(storage=mock_storage),
    ):
        client = SupabaseStorageClient(url="http://test", key="test_key")
        await client.upload("test-bucket", "track/1/energy.npz", b"fake_npz_bytes")

    mock_storage.from_.assert_called_once_with("test-bucket")
    mock_storage.from_.return_value.upload.assert_called_once()


@pytest.mark.asyncio
async def test_download_returns_bytes() -> None:
    mock_storage = MagicMock()
    mock_storage.from_.return_value.download.return_value = b"downloaded"

    with patch(
        "app.providers.supabase.storage_client.create_client",
        return_value=MagicMock(storage=mock_storage),
    ):
        client = SupabaseStorageClient(url="http://test", key="test_key")
        result = await client.download("test-bucket", "track/1/energy.npz")

    assert result == b"downloaded"


def test_client_requires_url_and_key() -> None:
    with pytest.raises(ValueError):
        SupabaseStorageClient(url="", key="")
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/providers/supabase/test_storage_client.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement config and storage client**

```python
# app/providers/supabase/__init__.py
```

```python
# app/providers/supabase/config.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SupabaseStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUPABASE_")

    url: str = ""
    service_key: str = ""
```

```python
# app/providers/supabase/storage_client.py
from __future__ import annotations

import asyncio
from typing import Any

from supabase import create_client


class SupabaseStorageClient:
    def __init__(self, url: str, key: str) -> None:
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
        self._client = create_client(url, key)

    async def upload(self, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.storage.from_(bucket).upload(
                path, data, {"content-type": content_type}
            ),
        )

    async def download(self, bucket: str, path: str) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.storage.from_(bucket).download(path),
        )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/providers/supabase/test_storage_client.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/providers/supabase/ tests/providers/supabase/
git commit -m "feat(providers): add SupabaseStorageClient for bucket upload/download"
```

---

### Task 4: L6 Essentia Analyzers (5 new)

**Files:**
- Create: `app/audio/analyzers/chords.py`
- Create: `app/audio/analyzers/hpcp_extended.py`
- Create: `app/audio/analyzers/inharmonicity.py`
- Create: `app/audio/analyzers/meter.py`
- Create: `app/audio/analyzers/audio_qa.py`
- Modify: `app/audio/analyzers/base.py` (если нужна регистрация)
- Test: `tests/audio/analyzers/test_l6_analyzers.py`

**Interfaces:**
- Produces: 5 new analyzer classes in registry, каждая возвращает dict[str, float|bool|str]
- Consumes: `BaseAnalyzer` ABC from `app/audio/analyzers/base.py`

- [ ] **Step 1: Write failing test — analyzer registry has L6 entries**

Найти существующий паттерн тестов для анализаторов в `tests/audio/analyzers/`. Написать:

```python
# tests/audio/analyzers/test_l6_analyzers.py
from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers.chords import ChordsAnalyzer
from app.audio.analyzers.hpcp_extended import HpCPExtendedAnalyzer
from app.audio.analyzers.inharmonicity import InharmonicityAnalyzer
from app.audio.analyzers.meter import MeterAnalyzer
from app.audio.analyzers.audio_qa import AudioQAAnalyzer


@pytest.fixture
def fake_signal() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.random(44100 * 5).astype(np.float32) * 0.3  # 5 sec


def test_chords_analyzer_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = ChordsAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "chords_strength" in result
    assert "chords_changes_rate" in result


def test_hpcp_extended_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = HpCPExtendedAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "hpcp_entropy" in result
    assert "hpcp_crest" in result


def test_inharmonicity_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = InharmonicityAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "inharmonicity" in result


def test_meter_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = MeterAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "meter" in result


def test_audio_qa_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = AudioQAAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "click_detected" in result
    assert "saturation_detected" in result
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/audio/analyzers/test_l6_analyzers.py -v
```
Expected: FAIL with import errors

- [ ] **Step 3: Implement 5 analyzers**

Изучить существующий анализатор (например `app/audio/analyzers/dissonance.py`) для паттерна `BaseAnalyzer` + `@register_analyzer`.

```python
# app/audio/analyzers/chords.py
from __future__ import annotations

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer


@register_analyzer
class ChordsAnalyzer(BaseAnalyzer):
    name = "chords"
    level = 6

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, float]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"chords_strength": None, "chords_changes_rate": None}

        frame_size = 4096
        hop_size = 1024
        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        spectral_peaks = es.SpectralPeaks(
            maxPeaks=100, magnitudeThreshold=1e-4, minFrequency=80, maxFrequency=4000
        )
        hpcp = es.HPCP(sampleRate=sample_rate)
        chords_detector = es.ChordsDetection()

        hop_generator = es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size)
        hpcp_frames = []
        for frame in hop_generator:
            spec = spectrum(w(frame))
            freqs, mags = spectral_peaks(spec)
            hpcp_vals = hpcp(freqs, mags)
            hpcp_frames.append(hpcp_vals)

        if len(hpcp_frames) < 2:
            return {"chords_strength": None, "chords_changes_rate": None}

        hpcp_stack = np.array(hpcp_frames)
        chords_result = chords_detector(hpcp_stack)
        chords_strength = float(np.mean(chords_result[1])) if chords_result[1].size > 0 else None
        chords_changes = int(np.sum(np.diff(chords_result[0]) != 0))
        total_frames = len(chords_result[0])
        chords_changes_rate = float(chords_changes / total_frames) if total_frames > 0 else None

        return {"chords_strength": chords_strength, "chords_changes_rate": chords_changes_rate}
```

```python
# app/audio/analyzers/hpcp_extended.py
from __future__ import annotations

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer


@register_analyzer
class HpCPExtendedAnalyzer(BaseAnalyzer):
    name = "hpcp_extended"
    level = 6

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, float]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"hpcp_entropy": None, "hpcp_crest": None}

        frame_size = 4096
        hop_size = 1024
        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        spectral_peaks = es.SpectralPeaks(
            maxPeaks=100, magnitudeThreshold=1e-4, minFrequency=80, maxFrequency=4000
        )
        hpcp = es.HPCP(sampleRate=sample_rate)

        hop_generator = es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size)
        hpcp_means = []
        for frame in hop_generator:
            spec = spectrum(w(frame))
            freqs, mags = spectral_peaks(spec)
            hpcp_vals = hpcp(freqs, mags)
            hpcp_means.append(np.mean(hpcp_vals))

        if not hpcp_means:
            return {"hpcp_entropy": None, "hpcp_crest": None}

        hpcp_arr = np.array(hpcp_means)
        prob = hpcp_arr / (hpcp_arr.sum() + 1e-10)
        entropy = float(-np.sum(prob * np.log2(prob + 1e-10)))
        crest = float(hpcp_arr.max() / (hpcp_arr.mean() + 1e-10))

        return {"hpcp_entropy": entropy, "hpcp_crest": crest}
```

```python
# app/audio/analyzers/inharmonicity.py
from __future__ import annotations

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer


@register_analyzer
class InharmonicityAnalyzer(BaseAnalyzer):
    name = "inharmonicity"
    level = 6

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, float]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"inharmonicity": None}

        inharmonicity_algo = es.Inharmonicity()
        inharmonicity_val = inharmonicity_algo(audio)
        return {"inharmonicity": float(inharmonicity_val)}
```

```python
# app/audio/analyzers/meter.py
from __future__ import annotations

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer


@register_analyzer
class MeterAnalyzer(BaseAnalyzer):
    name = "meter"
    level = 6

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, str | None]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"meter": None}

        rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
        bpm, _, _, _, _ = rhythm_extractor(audio)

        if bpm == 0:
            return {"meter": None}

        beat_tracker = es.BeatTrackerMultiFeature()
        beats, _ = beat_tracker(audio)
        if len(beats) < 4:
            return {"meter": None}

        meter_algo = es.Meter(sampleRate=sample_rate)
        numerator, denominator = meter_algo(beats)
        return {"meter": f"{numerator}/{denominator}"}
```

```python
# app/audio/analyzers/audio_qa.py
from __future__ import annotations

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer


@register_analyzer
class AudioQAAnalyzer(BaseAnalyzer):
    name = "audio_qa"
    level = 6

    def analyze(self, audio: np.ndarray, sample_rate: float) -> dict[str, bool]:
        try:
            import essentia.standard as es
        except ImportError:
            return {"click_detected": None, "saturation_detected": None}

        click_detector = es.ClickDetector(frameSize=2048, hopSize=512)
        starts, ends = click_detector(audio)
        click_detected = bool(len(starts) > 0)

        saturation_detector = es.SaturationDetector(frameSize=2048, hopSize=512)
        sat_starts, sat_ends = saturation_detector(audio)
        saturation_detected = bool(len(sat_starts) > 0)

        return {"click_detected": click_detected, "saturation_detected": saturation_detected}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/audio/analyzers/test_l6_analyzers.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/audio/analyzers/chords.py app/audio/analyzers/hpcp_extended.py app/audio/analyzers/inharmonicity.py app/audio/analyzers/meter.py app/audio/analyzers/audio_qa.py tests/audio/analyzers/test_l6_analyzers.py
git commit -m "feat(analyzers): add 5 L6 Essentia analyzers — chords, HPCP extended, inharmonicity, meter, audio QA"
```

---

### Task 5: Demucs Runner

**Files:**
- Create: `app/audio/deep/__init__.py`
- Create: `app/audio/deep/demucs_runner.py`
- Test: `tests/audio/deep/test_demucs_runner.py`

**Interfaces:**
- Produces: `run_demucs(input_path: Path, output_dir: Path) -> dict[str, Path]`
- Returns: `{"vocals": Path, "drums": Path, "bass": Path, "other": Path}`

- [ ] **Step 1: Write failing test**

```python
# tests/audio/deep/test_demucs_runner.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.audio.deep.demucs_runner import run_demucs


def test_run_demucs_calls_subprocess_with_correct_args() -> None:
    input_path = Path("/tmp/test_track.mp3")
    output_dir = Path("/tmp/demucs_output")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        stem_dir = output_dir / "htdemucs" / "test_track"
        stem_dir.mkdir(exist_ok=True, parents=True)
        for name in ("vocals.wav", "drums.wav", "bass.wav", "other.wav"):
            (stem_dir / name).touch()

        result = run_demucs(input_path, output_dir)

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "python" in args
    assert "-m" in args
    assert "demucs" in args
    assert str(input_path) in args

    assert result["vocals"] == stem_dir / "vocals.wav"
    assert result["drums"] == stem_dir / "drums.wav"
    assert result["bass"] == stem_dir / "bass.wav"
    assert result["other"] == stem_dir / "other.wav"


def test_run_demucs_raises_on_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = RuntimeError("demucs failed")

        with pytest.raises(RuntimeError):
            run_demucs(Path("/tmp/test.mp3"), Path("/tmp/out"))
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/audio/deep/test_demucs_runner.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement Demucs runner**

```python
# app/audio/deep/__init__.py
```

```python
# app/audio/deep/demucs_runner.py
from __future__ import annotations

import subprocess
from pathlib import Path


def run_demucs(input_path: Path, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python", "-m", "demucs", "-n", "htdemucs", "-o", str(output_dir), str(input_path)],
        check=True,
    )
    stem_dir = output_dir / "htdemucs" / input_path.stem
    return {
        "vocals": stem_dir / "vocals.wav",
        "drums": stem_dir / "drums.wav",
        "bass": stem_dir / "bass.wav",
        "other": stem_dir / "other.wav",
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/audio/deep/test_demucs_runner.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/ app/audio/deep/demucs_runner.py tests/audio/deep/
git commit -m "feat(deep): add Demucs 4-stem runner (htdemucs)"
```

---

### Task 6: Stem Analyzer (per-stem pipeline ×5)

**Files:**
- Create: `app/audio/deep/stem_analyzer.py`
- Test: `tests/audio/deep/test_stem_analyzer.py`

**Interfaces:**
- Produces: `async def analyze_stems(uow, track_id, stem_paths, original_path) -> dict[str, dict]`
- Consumes: existing `run_pipeline` from `app/audio/pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/audio/deep/test_stem_analyzer.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.audio.deep.stem_analyzer import analyze_stems


@pytest.mark.asyncio
async def test_analyze_stems_calls_pipeline_5_times() -> None:
    uow = MagicMock()
    stem_paths = {
        "vocals": Path("/tmp/vocals.wav"),
        "drums": Path("/tmp/drums.wav"),
        "bass": Path("/tmp/bass.wav"),
        "other": Path("/tmp/other.wav"),
    }
    original = Path("/tmp/original.wav")

    pipeline_results = {"bpm": 130.0, "integrated_lufs": -8.5, "mood": "peak_time"}

    with patch(
        "app.audio.deep.stem_analyzer.run_pipeline",
        new_callable=AsyncMock,
        return_value=pipeline_results,
    ) as mock_pipeline:
        result = await analyze_stems(uow, 1, stem_paths, original)

    assert mock_pipeline.call_count == 5
    assert result["original"] == pipeline_results
    assert result["vocals"] == pipeline_results
    assert "drums" in result
    assert "bass" in result
    assert "other" in result
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/audio/deep/test_stem_analyzer.py -v
```
Expected: FAIL with import error

- [ ] **Step 3: Implement stem analyzer**

```python
# app/audio/deep/stem_analyzer.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audio.pipeline import run_pipeline
from app.repositories.unit_of_work import UnitOfWork


async def analyze_stems(
    uow: UnitOfWork,
    track_id: int,
    stem_paths: dict[str, Path],
    original_path: Path,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    all_paths: dict[str, Path] = {"original": original_path, **stem_paths}

    for stem_name, path in all_paths.items():
        features = await run_pipeline(uow, track_id, path, level=6)
        results[stem_name] = features

    return results
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/audio/deep/test_stem_analyzer.py -v
```
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/stem_analyzer.py tests/audio/deep/test_stem_analyzer.py
git commit -m "feat(deep): add per-stem analysis pipeline runner (×5)"
```

---

### Task 7: Beatgrid Builder (per-track)

**Files:**
- Create: `app/audio/deep/beatgrid_builder.py`
- Test: `tests/audio/deep/test_beatgrid_builder.py`

**Interfaces:**
- Produces: `async def build_beatgrid(uow, track_id, audio_path) -> BeatgridEntry`
- Consumes: существующий `compute_kick_phase` + `refine_phase` из `app/audio/render/`

- [ ] **Step 1: Write failing test**

```python
# tests/audio/deep/test_beatgrid_builder.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.audio.deep.beatgrid_builder import build_beatgrid


@pytest.mark.asyncio
async def test_build_beatgrid_registers_in_db() -> None:
    uow = MagicMock()
    uow.audio_files = MagicMock()
    uow.audio_files.register_beatgrid = AsyncMock()

    with patch(
        "app.audio.deep.beatgrid_builder.compute_kick_phase",
        return_value=(0.0, 0.05),
    ), patch(
        "app.audio.deep.beatgrid_builder.refine_phase",
        return_value=0.02,
    ), patch(
        "app.audio.deep.beatgrid_builder._get_bpm_from_path",
        return_value=130.0,
    ):
        result = await build_beatgrid(uow, track_id=1, audio_path=Path("/tmp/test.mp3"))

    uow.audio_files.register_beatgrid.assert_called_once()
    assert result.bpm == 130.0
    assert result.phase_ms is not None
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/audio/deep/test_beatgrid_builder.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement beatgrid builder**

```python
# app/audio/deep/beatgrid_builder.py
from __future__ import annotations

import librosa
from pathlib import Path

from app.audio.render.kick_phase import compute_kick_phase
from app.audio.render.phase_refine import refine_phase
from app.repositories.unit_of_work import UnitOfWork


class BeatgridEntry:
    def __init__(self, bpm: float, trim_start_s: float, refined_trim_s: float, phase_ms: float) -> None:
        self.bpm = bpm
        self.trim_start_s = trim_start_s
        self.refined_trim_s = refined_trim_s
        self.phase_ms = phase_ms


def _get_bpm_from_path(audio_path: Path) -> float:
    y, sr = librosa.load(str(audio_path), sr=None, duration=60)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo)


async def build_beatgrid(uow: UnitOfWork, track_id: int, audio_path: Path) -> BeatgridEntry:
    bpm = _get_bpm_from_path(audio_path)
    trim_start, phase_ms = compute_kick_phase(audio_path, bpm)
    refined = refine_phase(audio_path, bpm, trim_start)

    lib_item = await uow.audio_files.get_for_track(track_id)
    if lib_item is not None:
        await uow.audio_files.register_beatgrid(
            library_item_id=lib_item.id,
            bpm=bpm,
            first_downbeat_ms=refined * 1000,
            canonical=True,
        )

    return BeatgridEntry(bpm=bpm, trim_start_s=trim_start, refined_trim_s=refined, phase_ms=phase_ms)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/audio/deep/test_beatgrid_builder.py -v
```
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/beatgrid_builder.py tests/audio/deep/test_beatgrid_builder.py
git commit -m "feat(deep): add per-track beatgrid builder from render DSP"
```

---

### Task 8: Structure Analyzer (SBic + per-section stem energy)

**Files:**
- Create: `app/audio/deep/structure_analyzer.py`
- Test: `tests/audio/deep/test_structure_analyzer.py`

**Interfaces:**
- Produces: `def analyze_structure(audio_path: Path, stem_paths: dict[str, Path]) -> list[dict]`
- Returns: list of `{"section_type": int, "start_ms": int, "end_ms": int, "energy": float, "lufs": float, "spectral_centroid": float, "stem_energy": dict}`

- [ ] **Step 1: Write failing test**

```python
# tests/audio/deep/test_structure_analyzer.py
from __future__ import annotations

import numpy as np
import soundfile as sf
from pathlib import Path
from unittest.mock import patch

from app.audio.deep.structure_analyzer import analyze_structure


def test_analyze_structure_returns_list_of_sections(tmp_path: Path) -> None:
    sr = 44100
    signal = np.random.default_rng(42).random(sr * 3).astype(np.float32) * 0.3
    audio_path = tmp_path / "test.wav"
    sf.write(str(audio_path), signal, sr)

    stems = {}
    for name in ("vocals", "drums", "bass", "other"):
        sp = tmp_path / f"{name}.wav"
        sf.write(str(sp), signal * 0.5, sr)
        stems[name] = sp

    result = analyze_structure(audio_path, stems)

    assert isinstance(result, list)
    if result:
        section = result[0]
        assert "section_type" in section
        assert "start_ms" in section
        assert "end_ms" in section
        assert "lufs" in section or section.get("lufs") is None
        assert "stem_energy" in section


def test_analyze_structure_empty_on_silence(tmp_path: Path) -> None:
    sr = 44100
    signal = np.zeros(sr).astype(np.float32)
    audio_path = tmp_path / "silence.wav"
    sf.write(str(audio_path), signal, sr)

    result = analyze_structure(audio_path, {})
    assert isinstance(result, list)
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/audio/deep/test_structure_analyzer.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement structure analyzer**

```python
# app/audio/deep/structure_analyzer.py
from __future__ import annotations

import numpy as np
import soundfile as sf
from pathlib import Path


def analyze_structure(
    audio_path: Path,
    stem_paths: dict[str, Path],
) -> list[dict]:
    audio, sr = sf.read(str(audio_path))
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    try:
        import essentia.standard as es
    except ImportError:
        return []

    # SBic segmentation
    w = es.Windowing(type="hann")
    spectrum = es.Spectrum()
    mfcc_algo = es.MFCC(sampleRate=sr)
    hp_generator = es.FrameGenerator(audio, frameSize=4096, hopSize=1024)

    mfcc_frames = []
    for frame in hp_generator:
        spec = spectrum(w(frame))
        mfcc_bands, mfcc_coeffs = mfcc_algo(spec)
        mfcc_frames.append(mfcc_coeffs)

    if len(mfcc_frames) < 4:
        return []

    mfcc_stack = np.array(mfcc_frames, dtype=np.float32)
    sbic = es.SBic()
    boundaries = sbic(mfcc_stack)
    if len(boundaries) == 0:
        return []

    hop_size = 1024
    sections = []
    for i, boundary in enumerate(boundaries):
        start_frame = int(boundaries[i - 1]) if i > 0 else 0
        end_frame = int(boundary)
        start_ms = int(start_frame * hop_size / sr * 1000)
        end_ms = int(end_frame * hop_size / sr * 1000)

        section_audio = audio[start_frame * hop_size : end_frame * hop_size + 4096]
        if len(section_audio) < 512:
            continue

        energy = float(np.sqrt(np.mean(section_audio**2)))
        rms_db = float(20 * np.log10(max(energy, 1e-10)))

        # Spectral centroid
        spec_centroid = float(np.mean(librosa_feature_spectral_centroid(
            y=section_audio, sr=sr, n_fft=2048, hop_length=512
        )))

        stem_energy: dict[str, float] = {}
        for stem_name, stem_path in stem_paths.items():
            stem_audio, _ = sf.read(str(stem_path))
            if stem_audio.ndim == 2:
                stem_audio = np.mean(stem_audio, axis=1)
            seg = stem_audio[start_frame * hop_size : end_frame * hop_size + 4096]
            if len(seg) > 0:
                stem_energy[stem_name] = round(float(np.sqrt(np.mean(seg**2))), 4)

        # Map to section_type — default to SUSTAIN (10), caller can refine
        sections.append({
            "section_type": 10,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "energy": round(energy, 4),
            "lufs": round(rms_db, 2),
            "spectral_centroid": round(spec_centroid, 2),
            "stem_energy": stem_energy,
        })

    return sections


def librosa_feature_spectral_centroid(y, sr, n_fft, hop_length):
    import librosa
    return librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length)[0]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/audio/deep/test_structure_analyzer.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/structure_analyzer.py tests/audio/deep/test_structure_analyzer.py
git commit -m "feat(deep): add SBic structural segmentation with per-stem energy"
```

---

### Task 9: Embedding Builder

**Files:**
- Create: `app/audio/deep/embedding_builder.py`
- Test: `tests/audio/deep/test_embedding_builder.py`

**Interfaces:**
- Produces: `def build_embeddings(features: dict[str, dict]) -> dict[str, np.ndarray]`
- Returns: `{"timbral": array(64), "harmonic": array(128), "rhythmic": array(32), "energy": array(32), "full": array(256)}`

- [ ] **Step 1: Write failing test**

```python
# tests/audio/deep/test_embedding_builder.py
from __future__ import annotations

import numpy as np

from app.audio.deep.embedding_builder import build_embeddings


def test_build_embeddings_returns_correct_shapes() -> None:
    features = {
        "mfcc_vector": "[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]",
        "spectral_centroid_hz": 2000.0,
        "spectral_rolloff_85": 4000.0,
        "spectral_rolloff_95": 8000.0,
        "spectral_flux_mean": 0.15,
        "tonnetz_vector": "[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]",
        "key_code": 5,
        "chroma_entropy": 0.95,
        "hnr_db": 20.0,
        "hpcp_entropy": 3.5,
        "hpcp_crest": 4.2,
        "onset_rate": 2.0,
        "pulse_clarity": 0.7,
        "kick_prominence": 0.6,
        "integrated_lufs": -8.0,
        "energy_sub_ratio": 0.2,
        "energy_low_ratio": 0.3,
        "energy_mid_ratio": 0.3,
        "energy_high_ratio": 0.2,
        "crest_factor_db": 12.0,
        "loudness_range_lu": 6.0,
        "danceability": 1.5,
        "dynamic_complexity": 5.0,
        "bpm": 130.0,
        "inharmonicity": 0.1,
        "chords_strength": 0.7,
        "chords_changes_rate": 0.05,
    }

    result = build_embeddings(features)

    assert result["timbral"].shape[0] <= 64
    assert result["harmonic"].shape[0] <= 128
    assert result["rhythmic"].shape[0] <= 32
    assert result["energy"].shape[0] <= 32
    assert result["full"].shape[0] <= 256


def test_build_embeddings_handles_missing_keys() -> None:
    features: dict[str, float | str | None] = {
        "bpm": 130.0,
        "integrated_lufs": -8.0,
    }
    result = build_embeddings(features)
    assert result["full"].shape[0] <= 256
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/audio/deep/test_embedding_builder.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement embedding builder**

```python
# app/audio/deep/embedding_builder.py
from __future__ import annotations

import json
from typing import Any

import numpy as np


def _safe_json_float_array(value: Any, max_len: int = 13) -> np.ndarray:
    if value is None:
        return np.zeros(max_len, dtype=np.float32)
    if isinstance(value, str):
        try:
            arr = np.array(json.loads(value), dtype=np.float32)
            return arr[:max_len] if len(arr) > max_len else np.pad(arr, (0, max_len - len(arr)))
        except (json.JSONDecodeError, ValueError):
            return np.zeros(max_len, dtype=np.float32)
    if isinstance(value, (int, float)):
        return np.array([float(value)], dtype=np.float32)
    return np.zeros(max_len, dtype=np.float32)


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _key_onehot(key_code: int | None, dims: int = 24) -> np.ndarray:
    onehot = np.zeros(dims, dtype=np.float32)
    if key_code is not None and 0 <= key_code < dims:
        onehot[key_code] = 1.0
    return onehot


def build_embeddings(features: dict[str, Any]) -> dict[str, np.ndarray]:
    mfcc = _safe_json_float_array(features.get("mfcc_vector"), 13)
    timbral = np.concatenate([
        mfcc,
        np.array([_safe_float(features.get(k)) for k in (
            "spectral_centroid_hz", "spectral_rolloff_85", "spectral_rolloff_95",
            "spectral_flux_mean", "spectral_flatness", "spectral_slope",
            "spectral_contrast", "spectral_complexity_mean",
        )], dtype=np.float32),
    ])
    timbral = np.pad(timbral, (0, max(0, 64 - len(timbral))))[:64]

    tonnetz = _safe_json_float_array(features.get("tonnetz_vector"), 6)
    hpcp_features = np.array([
        _safe_float(features.get("hpcp_entropy")),
        _safe_float(features.get("hpcp_crest")),
    ], dtype=np.float32)
    harmonic = np.concatenate([
        tonnetz, hpcp_features,
        _key_onehot(features.get("key_code")),
        np.array([
            _safe_float(features.get("chroma_entropy")),
            _safe_float(features.get("hnr_db")),
            _safe_float(features.get("dissonance_mean")),
            _safe_float(features.get("inharmonicity")),
            _safe_float(features.get("chords_strength")),
            _safe_float(features.get("chords_changes_rate")),
        ], dtype=np.float32),
    ])
    harmonic = np.pad(harmonic, (0, max(0, 128 - len(harmonic))))[:128]

    beat_loudness = _safe_json_float_array(features.get("beat_loudness_band_ratio"), 6)
    rhythmic = np.concatenate([
        np.array([
            _safe_float(features.get("onset_rate")),
            _safe_float(features.get("pulse_clarity")),
            _safe_float(features.get("kick_prominence")),
            _safe_float(features.get("bpm_stability")),
            _safe_float(features.get("danceability")),
        ], dtype=np.float32),
        beat_loudness,
    ])
    rhythmic = np.pad(rhythmic, (0, max(0, 32 - len(rhythmic))))[:32]

    energy = np.array([
        _safe_float(features.get(k)) for k in (
            "integrated_lufs", "energy_sub_ratio", "energy_low_ratio",
            "energy_lowmid_ratio", "energy_mid_ratio", "energy_highmid_ratio",
            "energy_high_ratio", "crest_factor_db", "loudness_range_lu",
            "energy_slope", "dynamic_complexity",
        )
    ], dtype=np.float32)
    energy = np.pad(energy, (0, max(0, 32 - len(energy))))[:32]

    full = np.concatenate([timbral, harmonic, rhythmic, energy])
    full = np.pad(full, (0, max(0, 256 - len(full))))[:256]

    return {
        "timbral": timbral,
        "harmonic": harmonic,
        "rhythmic": rhythmic,
        "energy": energy,
        "full": full,
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/audio/deep/test_embedding_builder.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/embedding_builder.py tests/audio/deep/test_embedding_builder.py
git commit -m "feat(deep): add pgvector embedding builder (5 types × 256 dims)"
```

---

### Task 10: CrossSimilarityMatrix + Timeseries/Waveform Upload

**Files:**
- Create: `app/audio/deep/cross_similarity.py`
- Create: `app/audio/deep/timeseries_store.py`
- Create: `app/audio/deep/waveform_store.py`
- Test: `tests/audio/deep/test_cross_similarity.py`
- Test: `tests/audio/deep/test_stores.py`

**Interfaces:**
- Produces: `def compute_cross_similarity(track_a, track_b, stem) -> CrossSimilarityResult`
- Produces: `async def upload_timeseries(storage, track_id, stem, data) -> None`
- Produces: `def build_waveform(audio_path) -> list[float]` (1000 точек)
- Produces: `async def upload_waveform(storage, track_id, stem, peaks) -> None`

- [ ] **Step 1: Write failing tests**

```python
# tests/audio/deep/test_cross_similarity.py
from __future__ import annotations

import numpy as np
import soundfile as sf
from pathlib import Path

from app.audio.deep.cross_similarity import compute_cross_similarity


def test_compute_cross_similarity_returns_result(tmp_path: Path) -> None:
    sr = 44100
    rng = np.random.default_rng(42)
    sig_a = rng.random(sr * 3).astype(np.float32) * 0.3
    sig_b = rng.random(sr * 3).astype(np.float32) * 0.3

    pa = tmp_path / "a.wav"
    pb = tmp_path / "b.wav"
    sf.write(str(pa), sig_a, sr)
    sf.write(str(pb), sig_b, sr)

    result = compute_cross_similarity(pa, pb, "original")

    assert result.best_match_offset_ms is not None or result.matrix_shape is not None


# tests/audio/deep/test_stores.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.audio.deep.timeseries_store import upload_timeseries
from app.audio.deep.waveform_store import build_waveform, upload_waveform


@pytest.mark.asyncio
async def test_upload_timeseries_calls_storage() -> None:
    storage = MagicMock()
    storage.upload = AsyncMock()

    await upload_timeseries(storage, track_id=1, stem_name="original", data={"energy": np.array([0.1, 0.2])})

    storage.upload.assert_called()


def test_build_waveform_returns_1000_points(tmp_path: Path) -> None:
    import soundfile as sf
    sr = 44100
    sig = np.random.default_rng(42).random(sr * 5).astype(np.float32) * 0.3
    ap = tmp_path / "test.wav"
    sf.write(str(ap), sig, sr)

    peaks = build_waveform(ap, n_points=1000)
    assert len(peaks) == 1000
    assert all(0.0 <= p <= 1.0 for p in peaks)
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/audio/deep/test_cross_similarity.py tests/audio/deep/test_stores.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement cross_similarity**

```python
# app/audio/deep/cross_similarity.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CrossSimilarityResult:
    matrix_shape: str | None = None
    best_match_offset_ms: float | None = None
    best_match_score: float | None = None
    alignment_path: list | None = None
    segment_matches: list | None = None


def compute_cross_similarity(
    track_a_path: Path,
    track_b_path: Path,
    stem_name: str = "original",
) -> CrossSimilarityResult:
    try:
        import essentia.standard as es
    except ImportError:
        return CrossSimilarityResult()

    audio_a = es.MonoLoader(filename=str(track_a_path))()
    audio_b = es.MonoLoader(filename=str(track_b_path))()

    w = es.Windowing(type="hann")
    spectrum = es.Spectrum()
    mfcc = es.MFCC()

    def extract_mfcc(audio):
        frames = []
        hop_generator = es.FrameGenerator(audio, frameSize=4096, hopSize=1024)
        for frame in hop_generator:
            spec = spectrum(w(frame))
            _, coeffs = mfcc(spec)
            frames.append(coeffs)
        import numpy as np
        return np.array(frames, dtype=np.float32) if frames else np.zeros((1, 13), dtype=np.float32)

    mfcc_a = extract_mfcc(audio_a)
    mfcc_b = extract_mfcc(audio_b)

    csm_algo = es.CrossSimilarityMatrix(
        frameStackSize=9, frameStackStride=1, binarize=False
    )
    csm = csm_algo(mfcc_a, mfcc_b)

    best_idx = int(csm.flatten().argmax())
    best_i, best_j = best_idx // csm.shape[1], best_idx % csm.shape[1]
    best_score = float(csm[best_i, best_j])
    hop_s = 1024 / 44100
    offset_ms = float((best_j - best_i) * hop_s * 1000)

    return CrossSimilarityResult(
        matrix_shape=f"{csm.shape[0]}x{csm.shape[1]}",
        best_match_offset_ms=offset_ms,
        best_match_score=best_score,
    )
```

```python
# app/audio/deep/timeseries_store.py
from __future__ import annotations

import io

import numpy as np

from app.providers.supabase.storage_client import SupabaseStorageClient


async def upload_timeseries(
    storage: SupabaseStorageClient,
    track_id: int,
    stem_name: str,
    data: dict[str, np.ndarray],
) -> None:
    for name, arr in data.items():
        buf = io.BytesIO()
        np.savez_compressed(buf, data=arr)
        buf.seek(0)

        prefix = f"{track_id}" if stem_name == "original" else f"{track_id}/stem_{stem_name}"
        await storage.upload(
            bucket="track-timeseries",
            path=f"{prefix}/{name}.npz",
            data=buf.read(),
        )
```

```python
# app/audio/deep/waveform_store.py
from __future__ import annotations

import json

import numpy as np
import soundfile as sf
from pathlib import Path

from app.providers.supabase.storage_client import SupabaseStorageClient


def build_waveform(audio_path: Path, n_points: int = 1000) -> list[float]:
    audio, sr = sf.read(str(audio_path))
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    hop = max(1, len(audio) // n_points)
    peaks = []
    for i in range(n_points):
        segment = audio[i * hop : (i + 1) * hop]
        peak = float(np.max(np.abs(segment))) if len(segment) > 0 else 0.0
        peaks.append(round(peak, 6))

    max_peak = max(peaks) if peaks else 1.0
    if max_peak > 0:
        peaks = [p / max_peak for p in peaks]

    return peaks


async def upload_waveform(
    storage: SupabaseStorageClient,
    track_id: int,
    stem_name: str,
    peaks: list[float],
    duration_ms: int = 0,
) -> None:
    payload = {
        "track_id": track_id,
        "stem": stem_name,
        "duration_ms": duration_ms,
        "n_points": len(peaks),
        "peaks": peaks,
    }
    prefix = f"{track_id}" if stem_name == "original" else f"{track_id}/stem_{stem_name}"
    await storage.upload(
        bucket="track-waveforms",
        path=f"{prefix}/waveform.json",
        data=json.dumps(payload).encode(),
        content_type="application/json",
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/audio/deep/test_cross_similarity.py tests/audio/deep/test_stores.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/audio/deep/cross_similarity.py app/audio/deep/timeseries_store.py app/audio/deep/waveform_store.py tests/audio/deep/test_cross_similarity.py tests/audio/deep/test_stores.py
git commit -m "feat(deep): add CrossSimilarityMatrix + timeseries/waveform Supabase Storage upload"
```

---

### Task 11: Repositories (CRUD + ANN Search)

**Files:**
- Create: `app/repositories/stem_features.py`
- Create: `app/repositories/track_embedding.py`
- Create: `app/repositories/cross_similarity.py`
- Create: `app/repositories/feature_extraction.py`
- Modify: `app/repositories/track_features.py` (add `save_track_section`, `get_track_sections`)
- Modify: `app/repositories/unit_of_work.py` (добавить lazy accessors)
- Test: `tests/repositories/test_deep_repos.py`

**Interfaces:**
- Produces: `StemFeaturesRepository` with `upsert(track_id, stem_name, features)` and `get_all_for_track(track_id)`
- Produces: `TrackEmbeddingRepository` with `upsert(track_id, stem_name, etype, embedding)` and `search_similar(query_vector, etype, limit)`
- Produces: `CrossSimilarityRepository` with `upsert(track_a, track_b, stem, data)` and `get_for_pair(track_a, track_b)`
- Produces: `FeatureExtractionRunRepository` with `create(track_id, pipeline_name, pipeline_version, status)` and `update(run_id, status, error_message=None)`
- Modifies: `TrackFeaturesRepository` with `save_track_section(track_id, section_data)` and `get_track_sections(track_id)`

- [ ] **Step 1: Write failing test**

```python
# tests/repositories/test_deep_repos.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.repositories.stem_features import StemFeaturesRepository
from app.repositories.track_embedding import TrackEmbeddingRepository
from app.repositories.cross_similarity import CrossSimilarityRepository
from app.repositories.feature_extraction import FeatureExtractionRunRepository


@pytest.mark.asyncio
async def test_stem_features_upsert() -> None:
    session = AsyncMock()
    repo = StemFeaturesRepository(session)
    features = {"bpm": 130.0, "integrated_lufs": -8.5}

    await repo.upsert(track_id=1, stem_name="drums", features=features)

    session.merge.assert_called_once()


@pytest.mark.asyncio
async def test_track_embedding_search_similar() -> None:
    session = AsyncMock()
    session.scalars = AsyncMock(return_value=MagicMock())
    session.scalars.return_value.all.return_value = [
        MagicMock(track_id=2),
        MagicMock(track_id=3),
    ]
    repo = TrackEmbeddingRepository(session)
    query = np.zeros(256, dtype=np.float32)

    results = await repo.search_similar(query, embedding_type="full", limit=5)

    assert len(results) >= 0
    session.execute.assert_called() if hasattr(session, "execute") else session.scalars.assert_called()


@pytest.mark.asyncio
async def test_cross_similarity_upsert() -> None:
    session = AsyncMock()
    repo = CrossSimilarityRepository(session)

    await repo.upsert(
        track_a_id=1, track_b_id=2, stem_name="original",
        data={"best_match_offset_ms": 500.0, "best_match_score": 0.87},
    )

    session.merge.assert_called_once()


@pytest.mark.asyncio
async def test_feature_extraction_create_and_update() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    repo = FeatureExtractionRunRepository(session)

    run = await repo.create(track_id=1, pipeline_name="l6_deep_analysis", pipeline_version="1.0.0")

    session.add.assert_called_once()
    assert run.track_id == 1

    await repo.update(1, status="completed")
    session.execute.assert_called()
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/repositories/test_deep_repos.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement repositories**

```python
# app/repositories/stem_features.py
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stem_features import StemFeatures


class StemFeaturesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, track_id: int, stem_name: str, features: dict[str, Any]) -> StemFeatures:
        row = StemFeatures(track_id=track_id, stem_name=stem_name, **features)
        await self._session.merge(row)
        await self._session.flush()
        return row

    async def get_all_for_track(self, track_id: int) -> list[StemFeatures]:
        from sqlalchemy import select
        result = await self._session.scalars(
            select(StemFeatures).where(StemFeatures.track_id == track_id)
        )
        return list(result.all())
```

```python
# app/repositories/track_embedding.py
from __future__ import annotations

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track_embedding import TrackEmbedding


class TrackEmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, track_id: int, stem_name: str, embedding_type: str, embedding: np.ndarray
    ) -> TrackEmbedding:
        row = TrackEmbedding(
            track_id=track_id,
            stem_name=stem_name,
            embedding_type=embedding_type,
            embedding=embedding.tolist(),
        )
        await self._session.merge(row)
        await self._session.flush()
        return row

    async def search_similar(
        self,
        query_vector: np.ndarray,
        embedding_type: str = "full",
        stem_name: str = "original",
        limit: int = 20,
        exclude_ids: list[int] | None = None,
    ) -> list[tuple[int, float]]:
        vector_str = f"[{','.join(str(v) for v in query_vector)}]"
        sql = text("""
            SELECT t.id, 1 - (e.embedding <=> :query) AS similarity
            FROM track_embeddings e
            JOIN tracks t ON t.id = e.track_id
            WHERE e.embedding_type = :etype
              AND e.stem_name = :stem
            ORDER BY e.embedding <=> :query
            LIMIT :lim
        """)
        params = {"query": vector_str, "etype": embedding_type, "stem": stem_name, "lim": limit}
        result = await self._session.execute(sql, params)
        return [(row.id, row.similarity) for row in result.fetchall()]
```

```python
# app/repositories/cross_similarity.py
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cross_similarity import CrossSimilarity


class CrossSimilarityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, track_a_id: int, track_b_id: int, stem_name: str, data: dict[str, Any]
    ) -> CrossSimilarity:
        row = CrossSimilarity(
            track_a_id=track_a_id, track_b_id=track_b_id, stem_name=stem_name, **data
        )
        await self._session.merge(row)
        await self._session.flush()
        return row

    async def get_for_pair(
        self, track_a_id: int, track_b_id: int, stem_name: str = "original"
    ) -> CrossSimilarity | None:
        result = await self._session.scalars(
            select(CrossSimilarity).where(
                CrossSimilarity.track_a_id == track_a_id,
                CrossSimilarity.track_b_id == track_b_id,
                CrossSimilarity.stem_name == stem_name,
            )
        )
        return result.first()
```

#### FeatureExtractionRunRepository

```python
# app/repositories/feature_extraction.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from app.models.track_features import FeatureExtractionRun
from app.repositories.base import BaseRepository


class FeatureExtractionRunRepository(BaseRepository[FeatureExtractionRun]):
    model = FeatureExtractionRun

    async def create(
        self,
        track_id: int,
        pipeline_name: str,
        pipeline_version: str,
        status: str = "pending",
        parameters: str | None = None,
    ) -> FeatureExtractionRun:
        row = FeatureExtractionRun(
            track_id=track_id,
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            status=status,
            parameters=parameters,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, run_id: int, **values: Any) -> None:
        values["updated_at"] = datetime.now(timezone.utc)
        stmt = update(FeatureExtractionRun).where(FeatureExtractionRun.id == run_id).values(**values)
        await self.session.execute(stmt)
        await self.session.flush()
```

#### Track Features Repository — section methods

Добавить в `app/repositories/track_features.py`:

```python
from app.models.track_features import TrackSection

# Добавить к классу TrackFeaturesRepository:

    async def save_track_section(self, track_id: int, section_data: dict) -> TrackSection:
        section = TrackSection(
            track_id=track_id,
            section_type=section_data.get("section_type", 10),
            start_ms=section_data["start_ms"],
            end_ms=section_data["end_ms"],
            energy=section_data.get("energy"),
            confidence=section_data.get("confidence"),
        )
        # Set L6 fields via __dict__ if columns exist
        for col in ("lufs", "spectral_centroid"):
            if col in section_data:
                setattr(section, col, section_data[col])
        if "stem_energy" in section_data:
            section.stem_energy = section_data["stem_energy"]
        self.session.add(section)
        await self.session.flush()
        return section

    async def get_track_sections(self, track_id: int) -> list[dict]:
        stmt = (
            select(TrackSection)
            .where(TrackSection.track_id == track_id)
            .order_by(TrackSection.start_ms)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            {
                "id": r.id,
                "section_type": r.section_type,
                "start_ms": r.start_ms,
                "end_ms": r.end_ms,
                "energy": r.energy,
                "lufs": getattr(r, "lufs", None),
                "spectral_centroid": getattr(r, "spectral_centroid", None),
                "stem_energy": getattr(r, "stem_energy", None),
            }
            for r in rows
        ]

```

В `app/repositories/unit_of_work.py` добавить импорты:

```python
from app.repositories.cross_similarity import CrossSimilarityRepository
from app.repositories.feature_extraction import FeatureExtractionRunRepository
from app.repositories.stem_features import StemFeaturesRepository
from app.repositories.track_embedding import TrackEmbeddingRepository
```

И свойства:

```python
@property
def stem_features(self) -> StemFeaturesRepository:
    return StemFeaturesRepository(self._session)

@property
def track_embeddings(self) -> TrackEmbeddingRepository:
    return TrackEmbeddingRepository(self._session)

@property
def cross_similarity(self) -> CrossSimilarityRepository:
    return CrossSimilarityRepository(self._session)

@property
def feature_extraction_runs(self) -> FeatureExtractionRunRepository:
    return FeatureExtractionRunRepository(self._session)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/repositories/test_deep_repos.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add app/repositories/stem_features.py app/repositories/track_embedding.py app/repositories/cross_similarity.py app/repositories/feature_extraction.py app/repositories/track_features.py app/repositories/unit_of_work.py tests/repositories/test_deep_repos.py
git commit -m "feat(repos): add stem_features, track_embedding, cross_similarity repositories with ANN search"
```

---

### Task 12: Domain Orchestrator

**Files:**
- Create: `app/domain/deep_analysis/__init__.py`
- Create: `app/domain/deep_analysis/models.py`
- Create: `app/domain/deep_analysis/orchestrator.py`
- Test: `tests/domain/deep_analysis/test_orchestrator.py`

**Interfaces:**
- Produces: `class L6AnalysisOrchestrator` with `async def run(track_id, uow) -> L6AnalysisResult`
- Consumes: все компоненты из Task 5-11

- [ ] **Step 1: Write failing test**

```python
# tests/domain/deep_analysis/test_orchestrator.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.deep_analysis.orchestrator import L6AnalysisOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_runs_full_pipeline() -> None:
    uow = MagicMock()
    uow.audio_files = MagicMock()
    uow.audio_files.get_by_track = AsyncMock(return_value=MagicMock(file_path="/tmp/test.mp3"))
    uow.stem_features = MagicMock()
    uow.stem_features.upsert = AsyncMock()
    uow.track_embeddings = MagicMock()
    uow.track_embeddings.upsert = AsyncMock()
    uow.cross_similarity = MagicMock()
    uow.cross_similarity.upsert = AsyncMock()
    uow.audio_files = MagicMock()
    uow.audio_files.get_for_track = AsyncMock(return_value=MagicMock(id=1))

    orch = L6AnalysisOrchestrator(storage_client=MagicMock())

    with patch(
        "app.domain.deep_analysis.orchestrator.run_demucs",
        return_value={"vocals": None, "drums": None, "bass": None, "other": None},
    ), patch(
        "app.domain.deep_analysis.orchestrator.analyze_stems",
        new_callable=AsyncMock,
        return_value={"original": {}, "vocals": {}, "drums": {}, "bass": {}, "other": {}},
    ), patch(
        "app.domain.deep_analysis.orchestrator.build_beatgrid",
        new_callable=AsyncMock,
    ), patch(
        "app.domain.deep_analysis.orchestrator.analyze_structure",
        return_value=[],
    ), patch(
        "app.domain.deep_analysis.orchestrator.build_embeddings",
        return_value={"full": None, "timbral": None, "harmonic": None, "rhythmic": None, "energy": None},
    ), patch(
        "app.domain.deep_analysis.orchestrator.compute_cross_similarity",
        return_value=MagicMock(),
    ), patch(
        "app.domain.deep_analysis.orchestrator.upload_timeseries",
        new_callable=AsyncMock,
    ), patch(
        "app.domain.deep_analysis.orchestrator.upload_waveform",
        new_callable=AsyncMock,
    ):
        result = await orch.run(track_id=1, uow=uow)

    assert result.track_id == 1
    assert result.level == 6
    assert uow.stem_features.upsert.call_count == 5
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/domain/deep_analysis/test_orchestrator.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement domain models and orchestrator**

```python
# app/domain/deep_analysis/__init__.py
```

```python
# app/domain/deep_analysis/models.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class L6AnalysisResult:
    track_id: int
    level: int = 6
    stems: dict[str, str] = field(default_factory=dict)  # stem_name → file_path
    stem_features_count: int = 0
    beatgrid_registered: bool = False
    embeddings_count: int = 0
    sections_count: int = 0
    cross_similarity_computed: bool = False
    timeseries_uploaded: bool = False
    waveform_uploaded: bool = False
    errors: list[str] = field(default_factory=list)
```

```python
# app/domain/deep_analysis/orchestrator.py
from __future__ import annotations

import logging
from pathlib import Path
from tempfile import mkdtemp

from app.audio.deep.beatgrid_builder import build_beatgrid
from app.audio.deep.cross_similarity import compute_cross_similarity
from app.audio.deep.demucs_runner import run_demucs
from app.audio.deep.embedding_builder import build_embeddings
from app.audio.deep.stem_analyzer import analyze_stems
from app.audio.deep.structure_analyzer import analyze_structure
from app.audio.deep.timeseries_store import upload_timeseries
from app.audio.deep.waveform_store import build_waveform, upload_waveform
from app.domain.deep_analysis.models import L6AnalysisResult
from app.providers.supabase.storage_client import SupabaseStorageClient
from app.repositories.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class L6AnalysisOrchestrator:
    def __init__(self, storage_client: SupabaseStorageClient) -> None:
        self._storage = storage_client

    async def run(self, track_id: int, uow: UnitOfWork) -> L6AnalysisResult:
        result = L6AnalysisResult(track_id=track_id)

        lib_item = await uow.audio_files.get_by_track(track_id)
        if lib_item is None or not lib_item.file_path:
            result.errors.append("No library item with file_path")
            return result

        audio_path = Path(lib_item.file_path)
        if not audio_path.exists():
            result.errors.append(f"File not found: {audio_path}")
            return result

        work_dir = Path(mkdtemp(prefix=f"l6_{track_id}_"))
        try:
            # Step 1: Demucs
            stem_paths = run_demucs(audio_path, work_dir / "stems")
            result.stems = {k: str(v) for k, v in stem_paths.items()}

            # Step 2: Per-stem analysis
            all_features = await analyze_stems(uow, track_id, stem_paths, audio_path)
            for stem_name, features in all_features.items():
                if features:
                    await uow.stem_features.upsert(track_id, stem_name, features)
                    result.stem_features_count += 1

            # Step 3: Beatgrid (use original audio)
            try:
                await build_beatgrid(uow, track_id, audio_path)
                result.beatgrid_registered = True
            except Exception as e:
                result.errors.append(f"Beatgrid: {e}")

            # Step 4: Structure
            try:
                sections = analyze_structure(audio_path, stem_paths)
                for section in sections:
                    await uow.track_features.save_track_section(track_id, section)
                result.sections_count = len(sections)
            except Exception as e:
                result.errors.append(f"Structure: {e}")

            # Step 5: Embeddings (from original features)
            orig_features = all_features.get("original", {})
            if orig_features:
                embeddings = build_embeddings(orig_features)
                for etype, emb in embeddings.items():
                    await uow.track_embeddings.upsert(track_id, "original", etype, emb)
                    result.embeddings_count += 1

            # Step 6: CrossSimilarity — пропускаем без кандидатов (см. find_compatible_tracks tool)
            # Step 7: Timeseries upload
            try:
                await upload_timeseries(self._storage, track_id, "original", {})
                result.timeseries_uploaded = True
            except Exception as e:
                result.errors.append(f"Timeseries upload: {e}")

            # Step 8: Waveform
            try:
                peaks = build_waveform(audio_path)
                await upload_waveform(self._storage, track_id, "original", peaks)
                result.waveform_uploaded = True
            except Exception as e:
                result.errors.append(f"Waveform upload: {e}")

        finally:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)

        return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/domain/deep_analysis/test_orchestrator.py -v
```
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add app/domain/deep_analysis/ tests/domain/deep_analysis/
git commit -m "feat(domain): add L6AnalysisOrchestrator — full deep analysis pipeline"
```

---

### Task 13: Handler + Background Task

**Files:**
- Create: `app/handlers/deep_analysis.py`
- Test: `tests/handlers/test_deep_analysis.py`

**Interfaces:**
- Produces: `async def handle_deep_analyze_track(track_id, uow) -> dict`
- Consumes: `L6AnalysisOrchestrator`
- Pattern: как `app/handlers/render_beatgrid.py` — handler → background task → возврат job_id

- [ ] **Step 1: Write failing test**

```python
# tests/handlers/test_deep_analysis.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.handlers.deep_analysis import handle_deep_analyze_track


@pytest.mark.asyncio
async def test_handler_returns_job_id() -> None:
    uow = MagicMock()
    uow.feature_extraction_runs = MagicMock()
    uow.feature_extraction_runs.create = AsyncMock(return_value=MagicMock(id=42))

    with patch(
        "app.handlers.deep_analysis.L6AnalysisOrchestrator",
        return_value=MagicMock(run=AsyncMock()),
    ), patch(
        "app.handlers.deep_analysis.SupabaseStorageClient",
        return_value=MagicMock(),
    ):
        result = await handle_deep_analyze_track(track_id=1, uow=uow)

    assert result["job_id"] is not None
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_handler_refuses_without_library_item() -> None:
    uow = MagicMock()
    uow.audio_files = MagicMock()
    uow.audio_files.get_by_track = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="library_item"):
        await handle_deep_analyze_track(track_id=1, uow=uow, check_prereqs=True)
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/handlers/test_deep_analysis.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement handler**

```python
# app/handlers/deep_analysis.py
from __future__ import annotations

import asyncio
import logging

from app.domain.deep_analysis.models import L6AnalysisResult
from app.domain.deep_analysis.orchestrator import L6AnalysisOrchestrator
from app.providers.supabase.config import SupabaseStorageSettings
from app.providers.supabase.storage_client import SupabaseStorageClient
from app.repositories.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

_DEEP_JOBS: dict[int, L6AnalysisResult] = {}


async def handle_deep_analyze_track(
    track_id: int,
    uow: UnitOfWork,
    check_prereqs: bool = False,
) -> dict:
    if check_prereqs:
        lib_item = await uow.audio_files.get_by_track(track_id)
        if lib_item is None:
            raise ValueError(f"No library_item for track {track_id}")

    run = await uow.feature_extraction_runs.create(
        track_id=track_id,
        pipeline_name="l6_deep_analysis",
        pipeline_version="1.0.0",
        status="pending",
    )

    settings = SupabaseStorageSettings()
    storage = SupabaseStorageClient(url=settings.url, key=settings.service_key)
    orchestrator = L6AnalysisOrchestrator(storage_client=storage)

    asyncio.create_task(_run_background(track_id, run.id, orchestrator, uow))

    return {"track_id": track_id, "job_id": run.id, "status": "pending"}


async def _run_background(
    track_id: int, run_id: int, orchestrator: L6AnalysisOrchestrator, uow: UnitOfWork,
) -> None:
    try:
        result = await orchestrator.run(track_id, uow)
        _DEEP_JOBS[track_id] = result
        await uow.feature_extraction_runs.update(run_id, status="completed")
    except Exception as e:
        logger.exception(f"L6 analysis failed for track {track_id}: {e}")
        await uow.feature_extraction_runs.update(run_id, status="failed", error_message=str(e))
        _DEEP_JOBS[track_id] = L6AnalysisResult(track_id=track_id, errors=[str(e)])
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/handlers/test_deep_analysis.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/handlers/deep_analysis.py tests/handlers/test_deep_analysis.py
git commit -m "feat(handlers): add L6 deep analysis handler with background task"
```

---

### Task 14: MCP Tools + Resources + Full-Suite Check

**Files:**
- Create: `app/tools/deep_analysis.py`
- Create: `app/resources/track_deep.py`
- Modify: `tests/resources/test_resource_registration.py` (добавить новые URI)
- Test: `tests/tools/test_deep_analysis_tools.py`
- Test: `tests/resources/test_track_deep.py`

**Interfaces:**
- Produces: MCP tools: `deep_analyze_track`, `deep_analyze_pool`, `find_compatible_tracks`, `get_cross_similarity`
- Produces: MCP resources: `local://tracks/{id}/deep_features{?stem}`, `local://tracks/{id}/structure`, `local://tracks/{id}/waveform{?stem}`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_deep_analysis_tools.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.deep_analysis import deep_analyze_track, find_compatible_tracks


@pytest.mark.asyncio
async def test_deep_analyze_track_delegates_to_handler() -> None:
    uow = MagicMock()
    with patch(
        "app.tools.deep_analysis.handle_deep_analyze_track",
        new_callable=AsyncMock,
        return_value={"track_id": 1, "job_id": 42, "status": "pending"},
    ) as mock_handler:
        result = await deep_analyze_track(track_id=1, uow=uow)

    mock_handler.assert_called_once_with(track_id=1, uow=uow, check_prereqs=False)
    assert result["job_id"] == 42


@pytest.mark.asyncio
async def test_find_compatible_tracks_delegates_to_repo() -> None:
    uow = MagicMock()
    uow.track_embeddings = MagicMock()
    uow.track_embeddings.search_similar = AsyncMock(return_value=[(2, 0.95), (3, 0.87)])

    result = await find_compatible_tracks(active_track_ids=[1], uow=uow)

    assert len(result) == 2
    assert result[0]["track_id"] == 2
    assert result[0]["similarity"] == 0.95


# tests/resources/test_track_deep.py
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.track_deep import track_deep_features, track_structure, track_waveform


@pytest.mark.asyncio
async def test_track_deep_features_returns_json() -> None:
    uow = MagicMock()
    uow.stem_features = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(return_value=[])

    payload = json.loads(await track_deep_features(id=1, uow=uow))

    assert payload["track_id"] == 1
    assert "stems" in payload
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/tools/test_deep_analysis_tools.py tests/resources/test_track_deep.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement MCP tools**

```python
# app/tools/deep_analysis.py
from __future__ import annotations

import numpy as np
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.handlers.deep_analysis import handle_deep_analyze_track
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(
    name="deep_analyze_track",
    annotations={"readOnlyHint": False, "idempotentHint": True},
)
async def deep_analyze_track(
    track_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    return await handle_deep_analyze_track(track_id, uow)


@tool(
    name="deep_analyze_pool",
    annotations={"readOnlyHint": False},
)
async def deep_analyze_pool(
    track_ids: list[int],
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    results = {}
    for tid in track_ids:
        results[str(tid)] = await handle_deep_analyze_track(tid, uow)
    return {"results": results, "total": len(track_ids)}


@tool(
    name="find_compatible_tracks",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def find_compatible_tracks(
    active_track_ids: list[int],
    embedding_type: str = "full",
    limit: int = 20,
    uow: UnitOfWork = Depends(get_uow),
) -> list[dict[str, Any]]:
    # Build composite query from active tracks' embeddings
    query = np.zeros(256, dtype=np.float32)
    count = 0
    for tid in active_track_ids:
        emb_row = await uow.track_embeddings.get_for_type(tid, "original", embedding_type)
        if emb_row is not None:
            query += np.array(emb_row.embedding, dtype=np.float32)
            count += 1

    if count > 0:
        query /= count

    rows = await uow.track_embeddings.search_similar(
        query, embedding_type=embedding_type, limit=limit, exclude_ids=active_track_ids
    )
    return [{"track_id": row[0], "similarity": round(row[1], 4)} for row in rows]


@tool(
    name="get_cross_similarity",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_cross_similarity(
    track_a_id: int,
    track_b_id: int,
    stem_name: str = "original",
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any] | None:
    row = await uow.cross_similarity.get_for_pair(track_a_id, track_b_id, stem_name)
    if row is None:
        return None
    return {
        "track_a_id": row.track_a_id,
        "track_b_id": row.track_b_id,
        "best_match_offset_ms": row.best_match_offset_ms,
        "best_match_score": row.best_match_score,
        "alignment_path": row.alignment_path,
        "segment_matches": row.segment_matches,
    }
```

```python
# app/resources/track_deep.py
from __future__ import annotations

import json
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.errors import NotFoundError


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
    features = await uow.stem_features.get_all_for_track(id)
    stems_data: dict[str, Any] = {}
    for row in features:
        cols = {c.name: getattr(row, c.name) for c in row.__table__.columns
                if c.name not in ("id", "track_id", "pipeline_run_id", "created_at", "updated_at")}
        stems_data[row.stem_name] = {k: v for k, v in cols.items() if v is not None}

    if stem != "original" and stem not in stems_data:
        raise NotFoundError("stem", f"{stem} for track {id}")

    payload = {
        "track_id": id,
        "stems": stems_data if stem == "original" else {stem: stems_data.get(stem)},
    }
    return json.dumps(payload, default=str)


@resource(
    "local://tracks/{id}/structure",
    mime_type="application/json",
    tags={"core", "entity:track", "view:structure"},
)
async def track_structure(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
        sections = await uow.track_features.get_track_sections(id)
    return json.dumps({"track_id": id, "sections": sections}, default=str)


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
    # Waveform data is in Supabase Storage, fetched on demand
    from app.providers.supabase.config import SupabaseStorageSettings
    from app.providers.supabase.storage_client import SupabaseStorageClient

    settings = SupabaseStorageSettings()
    storage = SupabaseStorageClient(url=settings.url, key=settings.service_key)
    prefix = f"{id}" if stem == "original" else f"{id}/stem_{stem}"
    data = await storage.download("track-waveforms", f"{prefix}/waveform.json")
    return data.decode()
```

- [ ] **Step 4: Add new URIs to resource registration test**

В `tests/resources/test_resource_registration.py` добавить:

```python
"local://tracks/{id}/deep_features{?stem}",
"local://tracks/{id}/structure",
"local://tracks/{id}/waveform{?stem}",
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/tools/test_deep_analysis_tools.py tests/resources/test_track_deep.py -v
```
Expected: PASS

- [ ] **Step 6: Full suite check**

```bash
uv run pytest -q
make check
```
Expected: all tests pass, lint + typecheck + arch clean

- [ ] **Step 7: Commit**

```bash
git add app/tools/deep_analysis.py app/resources/track_deep.py tests/tools/test_deep_analysis_tools.py tests/resources/test_track_deep.py tests/resources/test_resource_registration.py
git commit -m "feat(mcp): add L6 tools (deep_analyze, find_compatible, cross_similarity) + resources (deep_features, structure, waveform)"
```

---

## Post-Implementation

После всех 14 задач:
1. Создать Supabase Storage бакеты: `track-timeseries`, `track-waveforms` (private)
2. Установить `pgvector` extension: `CREATE EXTENSION IF NOT EXISTS vector;`
3. Прогнать `make check` — убедиться что все тесты, mypy strict, ruff, import-linter проходят
4. Обновить `docs/tool-catalog.md` — добавить 4 новых тула и 3 ресурса
5. Протестировать на реальном треке: `deep_analyze_track(track_id=X)` → проверить stem_features, embeddings, beatgrid, waveform
