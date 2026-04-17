# Tiered Audio Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace monolithic 23s/track audio analysis with 4-level lazy pipeline: L1+L2 (5s, triage+placement), L3 (7s, scoring), L4 (3s, delivery). 32x speedup via parallel processing + temp files.

**Architecture:** Add `analysis_level` column to features table. New `TieredPipeline` service coordinates temp downloads, level-appropriate analyzers, and parallel worker pool. Existing MCP tools auto-trigger the minimum level needed. Files are temp-downloaded for L1-L3 and only saved permanently at L4 (deliver).

**Tech Stack:** Python 3.12, asyncio + ProcessPoolExecutor, SQLAlchemy 2.0 async, Alembic, tempfile, existing AnalyzerRegistry + AnalysisPipeline.

**Spec:** `docs/reports/tiered-analysis-design-2026-03-27.md`

---

## File Structure

### New files
| File | Purpose |
|------|---------|
| `app/services/tiered_pipeline.py` | Orchestrates tiered analysis: temp download, level routing, parallel pool |
| `app/audio/temp_download.py` | Download YM track to temp file, auto-cleanup context manager |
| `app/audio/level_config.py` | Defines which analyzers belong to which level (L1, L2, L3) |
| `app/migrations/versions/xxxx_add_analysis_level.py` | Alembic migration for `analysis_level` column |
| `tests/test_services/test_tiered_pipeline.py` | Tests for tiered pipeline service |
| `tests/test_audio/test_temp_download.py` | Tests for temp download utility |
| `tests/test_audio/test_level_config.py` | Tests for level configuration |

### Modified files
| File | Change |
|------|--------|
| `app/models/audio.py` | Add `analysis_level` column to `TrackAudioFeaturesComputed` |
| `app/config.py` | Add tiered pipeline settings (worker counts, clip durations) |
| `app/mcp/dependencies.py` | Add `get_tiered_pipeline` DI factory |
| `app/mcp/tools/curation.py` | `classify_mood`, `audit_playlist` auto-trigger L1+L2 |
| `app/mcp/tools/sets.py` | `build_set`, `score_transitions` auto-trigger L3 |
| `app/mcp/tools/delivery.py` | `deliver_set` auto-trigger L4 (permanent download) |
| `app/mcp/tools/audio.py` | `analyze_track`, `analyze_batch` support `level` parameter |
| `app/repositories/audio.py` | Add `get_tracks_below_level()`, `update_features_level()` |

---

### Task 1: DB Migration — `analysis_level` column

**Files:**
- Modify: `app/models/audio.py` (~line 50, TrackAudioFeaturesComputed class)
- Create: `app/migrations/versions/xxxx_add_analysis_level.py`

- [ ] **Step 1: Add column to model**

In `app/models/audio.py`, add to `TrackAudioFeaturesComputed`:

```python
analysis_level: Mapped[int] = mapped_column(default=0, server_default="0", doc="0=none, 2=L1+L2, 3=L3")
```

- [ ] **Step 2: Generate migration**

```bash
uv run alembic revision --autogenerate -m "add analysis_level to track_audio_features_computed"
```

- [ ] **Step 3: Apply migration**

```bash
uv run alembic upgrade head
```

- [ ] **Step 4: Backfill existing data**

Edit the migration's `upgrade()` to backfill: tracks that already have features get `analysis_level=3` (they had full analysis).

```python
def upgrade():
    op.add_column('track_audio_features_computed',
        sa.Column('analysis_level', sa.Integer(), server_default='0', nullable=False))
    # Backfill: existing features = full analysis
    op.execute("UPDATE track_audio_features_computed SET analysis_level = 3 WHERE bpm IS NOT NULL")
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 6: Commit**

```text
feat(db): add analysis_level column to track_audio_features_computed
```

---

### Task 2: Level Configuration

**Files:**
- Create: `app/audio/level_config.py`
- Create: `tests/test_audio/test_level_config.py`

- [ ] **Step 1: Write test**

```python
# tests/test_audio/test_level_config.py
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level, get_clip_duration

def test_level_enum():
    assert AnalysisLevel.NONE == 0
    assert AnalysisLevel.TRIAGE == 2  # L1+L2 combined
    assert AnalysisLevel.SCORING == 3
    assert AnalysisLevel.TRANSITION == 4

def test_triage_analyzers():
    names = get_analyzers_for_level(AnalysisLevel.TRIAGE)
    assert set(names) == {"loudness", "energy", "spectral", "bpm", "key", "mfcc"}

def test_scoring_adds_beat():
    names = get_analyzers_for_level(AnalysisLevel.SCORING)
    assert "beat" in names
    assert "loudness" in names  # includes lower levels

def test_clip_duration():
    assert get_clip_duration(AnalysisLevel.TRIAGE) == 30.0
    assert get_clip_duration(AnalysisLevel.SCORING) == 60.0
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/test_audio/test_level_config.py -v
```

- [ ] **Step 3: Implement**

```python
# app/audio/level_config.py
"""Analysis level configuration — which analyzers run at which level."""
from enum import IntEnum
from app.config import settings

class AnalysisLevel(IntEnum):
    NONE = 0
    TRIAGE = 2       # L1+L2 combined: bpm, loudness, energy, spectral, key, mfcc
    SCORING = 3      # L3: + beat analyzer (onset, kick, hp_ratio, pulse)
    TRANSITION = 4   # L4: + structure (sections), permanent file

_LEVEL_ANALYZERS: dict[int, list[str]] = {
    AnalysisLevel.TRIAGE: ["loudness", "energy", "spectral", "bpm", "key", "mfcc"],
    AnalysisLevel.SCORING: ["beat"],
    AnalysisLevel.TRANSITION: ["structure"],
}

def get_analyzers_for_level(target: AnalysisLevel) -> list[str]:
    """Return all analyzer names needed up to and including target level."""
    names: list[str] = []
    for level in sorted(_LEVEL_ANALYZERS):
        if level <= target:
            names.extend(_LEVEL_ANALYZERS[level])
    return names

def get_clip_duration(level: AnalysisLevel) -> float:
    """Return audio clip duration in seconds for analysis level."""
    if level <= AnalysisLevel.TRIAGE:
        return settings.audio_triage_clip_duration
    return settings.audio_beat_analysis_duration  # 60s default
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```text
feat(audio): add analysis level configuration
```

---

### Task 3: Config Settings

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Add settings**

In `app/config.py`, add to Audio Analysis section:

```python
# ── Tiered Analysis ───────────────────────────────
audio_triage_clip_duration: float = 30.0     # seconds, for L1+L2
audio_triage_workers: int = 6                # parallel workers for L1+L2
audio_scoring_workers: int = 4               # parallel workers for L3
audio_download_workers: int = 8              # parallel download threads for L4
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 3: Commit**

```text
feat(config): add tiered analysis settings
```

---

### Task 4: Temp Download Utility

**Files:**
- Create: `app/audio/temp_download.py`
- Create: `tests/test_audio/test_temp_download.py`

- [ ] **Step 1: Write test**

```python
# tests/test_audio/test_temp_download.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_temp_download_creates_and_cleans():
    """Temp download should create file, yield path, then delete."""
    from app.audio.temp_download import temp_download_track

    mock_client = AsyncMock()
    mock_client.download_track = AsyncMock(return_value=1000)

    async with temp_download_track(mock_client, "12345") as tmp_path:
        # File path should be a Path object in temp dir
        assert isinstance(tmp_path, Path)
        assert "12345" in str(tmp_path)
        # Simulate file exists (mock created it)
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(b"fake mp3")
        assert tmp_path.exists()

    # After context exit, file should be deleted
    assert not tmp_path.exists()

@pytest.mark.asyncio
async def test_temp_download_cleans_on_error():
    """Temp file cleaned up even if analysis raises."""
    from app.audio.temp_download import temp_download_track

    mock_client = AsyncMock()
    mock_client.download_track = AsyncMock(return_value=1000)

    with pytest.raises(ValueError):
        async with temp_download_track(mock_client, "12345") as tmp_path:
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(b"fake mp3")
            raise ValueError("analysis failed")

    assert not tmp_path.exists()
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement**

```python
# app/audio/temp_download.py
"""Temp download utility — download YM track to temp file with auto-cleanup."""
from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from app.ym.client import YandexMusicClient

@asynccontextmanager
async def temp_download_track(
    client: YandexMusicClient,
    ym_track_id: str,
    prefer_bitrate: int = 320,
) -> AsyncIterator[Path]:
    """Download track to temp file, yield path, delete on exit.

    Usage:
        async with temp_download_track(client, "12345") as path:
            features = await pipeline.analyze(str(path))
        # file auto-deleted here
    """
    tmp_dir = tempfile.mkdtemp(prefix="dj_analysis_")
    tmp_path = Path(tmp_dir) / f"{ym_track_id}.mp3"
    try:
        await client.download_track(ym_track_id, str(tmp_path), prefer_bitrate)
        yield tmp_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
        tmp_dir_path = Path(tmp_dir)
        if tmp_dir_path.exists():
            tmp_dir_path.rmdir()
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```text
feat(audio): add temp download utility with auto-cleanup
```

---

### Task 5: Repository — Level-Aware Queries

**Files:**
- Modify: `app/repositories/audio.py`
- Create: `tests/test_repositories/test_audio_levels.py`

- [ ] **Step 1: Write test**

```python
# tests/test_repositories/test_audio_levels.py
import pytest
from app.audio.level_config import AnalysisLevel

@pytest.mark.asyncio
async def test_get_tracks_below_level(seeded_db):
    """Should return track IDs that need higher analysis."""
    session = seeded_db
    from app.repositories.audio import AudioRepository
    repo = AudioRepository(session)

    # Get tracks that need at least L3 (SCORING)
    track_ids = [1, 2, 3, 4, 5]
    below = await repo.get_tracks_below_level(track_ids, AnalysisLevel.SCORING)
    # All should need L3 since they have no features
    assert set(below) == set(track_ids)

@pytest.mark.asyncio
async def test_update_analysis_level(seeded_db):
    """Should update analysis_level field."""
    session = seeded_db
    from app.repositories.audio import AudioRepository
    repo = AudioRepository(session)

    await repo.update_analysis_level(track_id=1, level=AnalysisLevel.TRIAGE)
    await session.flush()
    # Verify via query
    row = await repo.get_features(1)
    assert row is not None
    assert row.analysis_level == AnalysisLevel.TRIAGE
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement in `app/repositories/audio.py`**

```python
async def get_tracks_below_level(
    self, track_ids: list[int], target_level: int
) -> list[int]:
    """Return track IDs that have analysis_level below target."""
    if not track_ids:
        return []
    stmt = (
        select(TrackAudioFeaturesComputed.track_id)
        .where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids),
            TrackAudioFeaturesComputed.analysis_level >= target_level,
        )
    )
    result = await self.session.execute(stmt)
    analyzed = {row[0] for row in result.all()}
    # Return IDs that are NOT yet analyzed at target level
    # Include IDs with no features row at all
    return [tid for tid in track_ids if tid not in analyzed]

async def update_analysis_level(self, track_id: int, level: int) -> None:
    """Set analysis_level for a track's features."""
    stmt = (
        update(TrackAudioFeaturesComputed)
        .where(TrackAudioFeaturesComputed.track_id == track_id)
        .values(analysis_level=level)
    )
    await self.session.execute(stmt)
    await self.session.flush()
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```text
feat(repo): add level-aware feature queries
```

---

### Task 6: TieredPipeline Service

**Files:**
- Create: `app/services/tiered_pipeline.py`
- Create: `tests/test_services/test_tiered_pipeline.py`

- [ ] **Step 1: Write test for single track L2 analysis**

```python
# tests/test_services/test_tiered_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.audio.level_config import AnalysisLevel

@pytest.mark.asyncio
async def test_ensure_level_single_track(seeded_db):
    """ensure_level should analyze track if below target level."""
    # This test needs:
    # 1. A track in DB with YM external ID
    # 2. Mock YM client (no real download)
    # 3. Mock pipeline (no real audio analysis)
    # 4. Verify features saved and level updated
    pass  # Detailed implementation depends on seeded_db fixture structure
```

- [ ] **Step 2: Implement TieredPipeline**

```python
# app/services/tiered_pipeline.py
"""Tiered analysis pipeline — lazy, level-aware, parallel."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.audio.level_config import AnalysisLevel, get_analyzers_for_level, get_clip_duration
from app.audio.temp_download import temp_download_track
from app.config import settings

if TYPE_CHECKING:
    from app.audio.pipeline import AnalysisPipeline
    from app.repositories.audio import AudioRepository
    from app.repositories.track import TrackRepository
    from app.ym.client import YandexMusicClient

class TieredPipeline:
    """Orchestrates tiered audio analysis with temp downloads."""

    def __init__(
        self,
        audio_repo: AudioRepository,
        track_repo: TrackRepository,
        pipeline: AnalysisPipeline,
        ym_client: YandexMusicClient,
    ) -> None:
        self._audio = audio_repo
        self._tracks = track_repo
        self._pipeline = pipeline
        self._ym = ym_client

    async def ensure_level(
        self,
        track_ids: list[int],
        target_level: AnalysisLevel,
        *,
        progress_callback: Any = None,
    ) -> dict[str, int]:
        """Ensure all tracks have at least target analysis level.

        Returns: {analyzed: N, skipped: N, failed: N}
        """
        # Find tracks that need analysis
        need_analysis = await self._audio.get_tracks_below_level(
            track_ids, target_level
        )
        if not need_analysis:
            return {"analyzed": 0, "skipped": len(track_ids), "failed": 0}

        # Resolve YM IDs for tracks that need analysis
        ym_map = await self._tracks.resolve_local_ids_to_ym(need_analysis)

        # Determine worker count based on level
        if target_level <= AnalysisLevel.TRIAGE:
            max_workers = settings.audio_triage_workers
        else:
            max_workers = settings.audio_scoring_workers

        # Process with semaphore for concurrency control
        sem = asyncio.Semaphore(max_workers)
        analyzed = 0
        failed = 0

        async def process_one(track_id: int) -> bool:
            ym_id = ym_map.get(track_id)
            if not ym_id:
                return False
            async with sem:
                return await self._analyze_at_level(
                    track_id, ym_id, target_level
                )

        tasks = [process_one(tid) for tid in need_analysis]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if r is True:
                analyzed += 1
            else:
                failed += 1

        return {
            "analyzed": analyzed,
            "skipped": len(track_ids) - len(need_analysis),
            "failed": failed,
        }

    async def _analyze_at_level(
        self,
        track_id: int,
        ym_track_id: str,
        level: AnalysisLevel,
    ) -> bool:
        """Download temp → analyze at level → save features → delete temp."""
        analyzers = get_analyzers_for_level(level)
        clip_duration = get_clip_duration(level)

        async with temp_download_track(self._ym, ym_track_id) as tmp_path:
            result = await self._pipeline.analyze(
                str(tmp_path),
                analyzers=analyzers,
            )
            if result.features:
                await self._audio.save_or_update_features(
                    track_id=track_id,
                    features_dict=result.features,
                    level=level,
                )
                return True
        return False
```

- [ ] **Step 3: Add `save_or_update_features` to AudioRepository**

In `app/repositories/audio.py`, add method that creates or updates features row, setting `analysis_level`:

```python
async def save_or_update_features(
    self,
    track_id: int,
    features_dict: dict[str, Any],
    level: int,
) -> TrackAudioFeaturesComputed:
    """Create or update features, setting analysis_level."""
    from app.models.audio import TrackAudioFeaturesComputed as TAFC

    existing = await self.get_features(track_id)
    filtered = TAFC.filter_features(features_dict)

    if existing:
        for key, value in filtered.items():
            if value is not None:
                setattr(existing, key, value)
        existing.analysis_level = max(existing.analysis_level, level)
        await self.session.flush()
        return existing
    else:
        row = TAFC(track_id=track_id, analysis_level=level, **filtered)
        self.session.add(row)
        await self.session.flush()
        return row
```

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```text
feat(services): add TieredPipeline service with parallel processing
```

---

### Task 7: DI Factory for TieredPipeline

**Files:**
- Modify: `app/mcp/dependencies.py`

- [ ] **Step 1: Add factory function**

```python
async def get_tiered_pipeline(
    session: AsyncSession = Depends(get_db_session),
) -> TieredPipeline:
    from app.audio.pipeline import AnalysisPipeline
    from app.audio.registry import AnalyzerRegistry
    from app.repositories.audio import AudioRepository
    from app.repositories.track import TrackRepository
    from app.services.tiered_pipeline import TieredPipeline
    from app.ym.client import get_ym_client

    registry = AnalyzerRegistry()
    registry.discover()
    pipeline = AnalysisPipeline(registry)

    return TieredPipeline(
        audio_repo=AudioRepository(session),
        track_repo=TrackRepository(session),
        pipeline=pipeline,
        ym_client=await get_ym_client(),
    )
```

- [ ] **Step 2: Run tests**

- [ ] **Step 3: Commit**

```text
feat(di): add TieredPipeline dependency factory
```

---

### Task 8: Integrate — classify_mood + audit_playlist auto-trigger L2

**Files:**
- Modify: `app/mcp/tools/curation.py`
- Modify: `app/services/curation_service.py` (if analysis logic lives there)

- [ ] **Step 1: Write integration test**

```python
# tests/test_mcp/test_tiered_curation.py
@pytest.mark.asyncio
async def test_classify_mood_auto_analyzes(mcp_client):
    """classify_mood should auto-trigger L1+L2 for tracks without features."""
    # Import tracks (metadata only)
    # Call classify_mood
    # Verify features were created at level >= 2
    pass
```

- [ ] **Step 2: Modify classify_mood tool**

In `app/mcp/tools/curation.py`, add `TieredPipeline` dependency and call `ensure_level` before classification:

```python
@tool(tags={"curation"}, annotations={"readOnlyHint": False})
async def classify_mood(
    track_ids: Any = None,
    playlist_id: int | None = None,
    reclassify: bool = False,
    svc: CurationService = Depends(get_curation_service),
    tiered: TieredPipeline = Depends(get_tiered_pipeline),
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Classify tracks by 15 techno subgenres. Auto-analyzes if needed."""
    # Resolve track IDs
    ids = await svc.resolve_track_ids(track_ids, playlist_id)

    # Auto-analyze at L2 (triage + placement)
    analysis_result = await tiered.ensure_level(ids, AnalysisLevel.TRIAGE)
    if ctx and analysis_result["analyzed"] > 0:
        await ctx.info(f"Analyzed {analysis_result['analyzed']} tracks at L1+L2")

    return await svc.classify_mood(
        track_ids=ids,
        reclassify=reclassify,
    )
```

- [ ] **Step 3: Apply same pattern to `audit_playlist`**

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```text
feat(tools): classify_mood and audit_playlist auto-trigger L1+L2 analysis
```

---

### Task 9: Integrate — build_set + score_transitions auto-trigger L3

**Files:**
- Modify: `app/mcp/tools/sets.py`

- [ ] **Step 1: Modify build_set**

Add `TieredPipeline` dependency, call `ensure_level(track_ids, AnalysisLevel.SCORING)` before building:

```python
@tool(tags={"sets"}, annotations={"readOnlyHint": False}, timeout=120.0)
async def build_set(
    playlist_id: int,
    name: str,
    template: str | None = None,
    target_duration_min: int | None = None,
    algorithm: str = "greedy",
    dry_run: bool = False,
    svc: SetService = Depends(get_set_service),
    tiered: TieredPipeline = Depends(get_tiered_pipeline),
    ctx: Context | None = None,
) -> dict:
    """Build optimized DJ set. Auto-analyzes tracks at L3 if needed."""
    # Get playlist track IDs
    track_ids = await svc.get_playlist_track_ids(playlist_id)

    # Ensure L3 for all candidates
    analysis = await tiered.ensure_level(track_ids, AnalysisLevel.SCORING)
    if ctx and analysis["analyzed"] > 0:
        await ctx.info(f"Analyzed {analysis['analyzed']} tracks at L3 for scoring")

    # Build set (existing logic)
    dj_set, version, quality, used_algorithm = await svc.build_set(
        playlist_id=playlist_id, name=name,
        template=template, target_duration_min=target_duration_min,
        algorithm=algorithm,
    )
    # ... return response
```

- [ ] **Step 2: Apply same pattern to score_transitions**

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```text
feat(tools): build_set and score_transitions auto-trigger L3 analysis
```

---

### Task 10: Integrate — deliver_set auto-trigger L4 (permanent download)

**Files:**
- Modify: `app/mcp/tools/delivery.py`

- [ ] **Step 1: Modify deliver_set**

Before file operations, ensure all tracks have permanent MP3 files. Download missing ones:

```python
# In deliver_set, after loading set data:
track_ids = [item.track_id for item in items]

# Ensure all tracks have L3 features
await tiered.ensure_level(track_ids, AnalysisLevel.SCORING)

# Download permanent files for tracks without library items
missing = await delivery_svc.get_tracks_without_files(track_ids)
if missing:
    ym_map = await track_repo.resolve_local_ids_to_ym(missing)
    downloaded = await delivery_svc.download_permanent(ym_map)
    if ctx:
        await ctx.info(f"Downloaded {downloaded} tracks for delivery")
```

- [ ] **Step 2: Run tests**

- [ ] **Step 3: Commit**

```bash
feat(tools): deliver_set auto-downloads permanent files for delivery
```

---

### Task 11: Update analyze_track / analyze_batch with level parameter

**Files:**
- Modify: `app/mcp/tools/audio.py`

- [ ] **Step 1: Add `level` parameter**

```python
@tool(tags={"audio"}, annotations={"readOnlyHint": False}, timeout=120.0)
async def analyze_track(
    track_id: int | None = None,
    track_query: str | None = None,
    analyzers: Any = None,
    force: bool = False,
    level: int = 3,  # NEW: default L3 (full scoring features)
    svc: AudioService = Depends(get_audio_service),
    tiered: TieredPipeline = Depends(get_tiered_pipeline),
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis. level: 2=triage, 3=scoring (default), 4=full."""
    # If tiered pipeline available and track has YM ID, use it
    # Otherwise fall back to existing behavior (analyze from file on disk)
```

- [ ] **Step 2: Same for analyze_batch**

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```text
feat(tools): analyze_track and analyze_batch support level parameter
```

---

### Task 12: Clip Duration in Pipeline

**Files:**
- Modify: `app/audio/pipeline.py`

- [ ] **Step 1: Add clip_duration parameter to `analyze()`**

The pipeline's `_load_audio()` should accept a `max_duration` parameter to truncate audio to N seconds before passing to analyzers:

```python
async def analyze(
    self,
    file_path: str,
    analyzers: list[str] | None = None,
    max_duration: float | None = None,  # NEW: truncate audio to N seconds
) -> PipelineResult:
    audio = self._load_audio(file_path, max_duration=max_duration)
    # ... rest unchanged
```

In `_load_audio`:
```python
if max_duration and len(samples) > int(max_duration * sr):
    samples = samples[:int(max_duration * sr)]
```

- [ ] **Step 2: TieredPipeline passes clip_duration to pipeline.analyze()**

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```bash
feat(audio): pipeline supports max_duration for clip-based analysis
```

---

### Task 13: End-to-End Integration Test

**Files:**
- Create: `tests/test_e2e/test_tiered_flow.py`

- [ ] **Step 1: Write E2E test**

Test the full flow: import → classify (auto L2) → build_set (auto L3) → verify levels in DB.

Uses mocked YM client (no real downloads) and synthetic audio fixtures.

```python
@pytest.mark.asyncio
async def test_full_tiered_flow(mcp_client):
    """E2E: import → classify → build_set → verify analysis levels."""
    # 1. Import tracks (metadata only)
    # 2. Verify: analysis_level = 0
    # 3. classify_mood → auto L2
    # 4. Verify: analysis_level = 2, mood assigned
    # 5. build_set → auto L3
    # 6. Verify: analysis_level = 3 for set tracks
```

- [ ] **Step 2: Run E2E test**

```bash
uv run pytest tests/test_e2e/test_tiered_flow.py -v
```

- [ ] **Step 3: Commit**

```bash
test: add E2E test for tiered analysis flow
```

---

### Task 14: Run Full Test Suite + Lint

- [ ] **Step 1: Lint**

```bash
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
```

- [ ] **Step 2: Type check**

```bash
uv run mypy app/
```

- [ ] **Step 3: Full test suite**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 4: Fix any failures**

- [ ] **Step 5: Final commit**

```bash
chore: pass lint, typecheck, and full test suite for tiered analysis
```

---

## Task Dependency Graph

```text
Task 1 (migration) ──→ Task 5 (repo queries) ──→ Task 6 (TieredPipeline) ──→ Task 7 (DI)
Task 2 (level config) ─┘                         ↑                           │
Task 3 (config) ──────────────────────────────────┘                           │
Task 4 (temp download) ───────────────────────────────────────────────────────┘
                                                                              │
                                              ┌───────────────────────────────┘
                                              ↓
                                    Task 8 (curation tools)
                                    Task 9 (set tools)
                                    Task 10 (delivery tool)
                                    Task 11 (audio tools)
                                    Task 12 (clip duration)
                                              │
                                              ↓
                                    Task 13 (E2E test)
                                    Task 14 (lint + full suite)
```

**Parallel tracks**: Tasks 1-4 are independent and can be done in parallel. Tasks 8-12 are independent after Task 7. Task 13-14 are final gates.
