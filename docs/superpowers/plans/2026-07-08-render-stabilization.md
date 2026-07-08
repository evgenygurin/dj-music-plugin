# Render Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4 independent workstreams: import-linter contracts, code quality pass (tempfiles/constants/dedup/re-exports), `deliver_set` tool, `render_verify` tool (DJ-adapted mix-verify).

**Architecture:** Sections 1-2 are config + light refactoring. Sections 3-4 add new tools following the existing pattern (tools → handlers → domain/audio). All changes respect bounded contexts.

**Tech Stack:** Python, FastMCP, numpy, librosa, ffmpeg.

## Global Constraints

- `app/domain/` must never import `app/audio/`
- All new tools use `@tool(task=True)` for long-running operations
- All new handlers use `safe_info`/`safe_report_progress` for logging
- Temp files must not hardcode `/tmp/`
- No new external dependencies

---

### Task 1: import-linter contracts

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing
- Produces: `make arch` checkable contracts

- [ ] **Step 1: Add import-linter dependency**

```bash
grep -n "import-linter" pyproject.toml
```
Expected: `"import-linter>=2.11"` already present.

- [ ] **Step 2: Add contract config to pyproject.toml**

```toml
[tool.lint.import-linter]
root_packages = ["app"]

[[tool.lint.import-linter.contracts]]
name = "domain-render-pure"
type = "forbidden_imports"
source_modules = ["app.domain.render"]
forbidden_modules = [
    "app.audio",
    "app.handlers",
    "app.tools",
    "app.server",
]

[[tool.lint.import-linter.contracts]]
name = "audio-render-side-effect"
type = "forbidden_imports"
source_modules = ["app.audio.render"]
forbidden_modules = [
    "app.handlers",
    "app.tools",
    "app.server",
]
```

- [ ] **Step 3: Verify contracts pass**

```bash
uv run lint-imports
```
Expected: exit 0 (no violations).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add import-linter contracts for domain.render and audio.render"
```

---

### Task 2: Code quality pass (constants, re-exports, temp files, workspace dedup)

**Files:**
- Create: `app/audio/render/_constants.py`
- Modify: `app/audio/render/__init__.py`
- Modify: `app/audio/render/kick_phase.py`
- Modify: `app/audio/render/phase_refine.py`
- Modify: `app/audio/render/diagnostics.py`
- Modify: `app/audio/render/levels.py`
- Create: `app/shared/workspace.py`
- Modify: `app/shared/render_studio_data.py`
- Modify: `app/resources/render.py`
- Modify: `app/handlers/render_beatgrid.py`
- Modify: `app/handlers/render_mixdown.py`
- Modify: `app/handlers/render_diagnose.py`

**Interfaces:**
- Consumes: nothing
- Produces: `app.audio.render.detect_kick_trim`, `refine_phase`, `run_render`, `scan_mix`, `diagnose_mix` as re-exports; `app.shared.workspace.render_workspace(version_id) -> Path`

- [ ] **Step 1: Create `app/audio/render/_constants.py`**

```python
"""Shared DSP constants for audio/render modules."""

LP_HZ = 150
ANALYSIS_SR = 22050
HOP_LENGTH = 512
GAIN_CLAMP_DB = 4.0
```

- [ ] **Step 2: Add re-exports to `app/audio/render/__init__.py`**

```python
"""Render engine — kick-phase detection, phase refinement, ffmpeg runner, diagnostics."""

from app.audio.render.diagnostics import diagnose_mix, scan_mix
from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
from app.audio.render.runner import run_render

__all__ = [
    "detect_kick_trim",
    "refine_phase",
    "run_render",
    "scan_mix",
    "diagnose_mix",
]
```

- [ ] **Step 3: Update `kick_phase.py` — use _constants**

Replace:
```python
_LP_HZ = 150
_SR = 22050
```
with:
```python
from app.audio.render._constants import ANALYSIS_SR, LP_HZ
```
Replace all `_LP_HZ` → `LP_HZ` and `_SR` → `ANALYSIS_SR`.

- [ ] **Step 4: Update `phase_refine.py` — use _constants + tempfile**

Replace:
```python
_SR = 22050
_HOP = 512
```
with:
```python
from app.audio.render._constants import ANALYSIS_SR, HOP_LENGTH
```
Replace `_SR` → `ANALYSIS_SR`, `_HOP` → `HOP_LENGTH`.

Replace the hardcoded temp file:
```python
tmp = f"/tmp/_qa_{abs(hash(file_path))}.wav"
```
with:
```python
import tempfile
tmp_fd, tmp = tempfile.mkstemp(suffix=".wav")
os.close(tmp_fd)
```
And in `finally`:
```python
finally:
    if os.path.exists(tmp):
        os.remove(tmp)
```

- [ ] **Step 5: Update `diagnostics.py` — use _constants + tempfile**

Replace:
```python
_SR = 22050
```
with:
```python
from app.audio.render._constants import ANALYSIS_SR
```
Replace `_SR` → `ANALYSIS_SR`.

Replace:
```python
tmp = "/tmp/_scan.f32"
```
with:
```python
import tempfile
tmp_fd, tmp = tempfile.mkstemp(suffix=".f32")
os.close(tmp_fd)
```
And remove the file at the end via `os.remove(tmp)` (or use `NamedTemporaryFile` with `delete=True` wrapped in the subprocess call).

- [ ] **Step 6: Update `levels.py` — use _constants**

Replace:
```python
_CLAMP_DB = 4.0
```
with:
```python
from app.audio.render._constants import GAIN_CLAMP_DB
```
Replace `_CLAMP_DB` → `GAIN_CLAMP_DB`.

- [ ] **Step 7: Create `app/shared/workspace.py`**

```python
"""Shared workspace path helpers — single source of truth."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings


def render_workspace(version_id: int) -> Path:
    """Path to the render workspace dir for a version."""
    s = get_settings()
    return Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
```

- [ ] **Step 8: Update `app/shared/render_studio_data.py`**

Replace the inline `render_studio_workspace` function:
```python
def render_studio_workspace(version_id: int) -> Path:
    s = get_settings()
    return Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
```
with:
```python
from app.shared.workspace import render_workspace
```
And update all calls `render_studio_workspace(version_id)` → `render_workspace(version_id)`.

- [ ] **Step 9: Update `app/resources/render.py`**

Replace the inline `_workspace` function:
```python
def _workspace(version_id: int) -> Path:
    s = get_settings()
    return Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
```
with:
```python
from app.shared.workspace import render_workspace
```
And update all calls `_workspace(version_id)` → `render_workspace(version_id)`.

- [ ] **Step 10: Update handlers to use re-exports**

In `app/handlers/render_beatgrid.py`:
```python
# Replace direct imports:
from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
# With:
from app.audio.render import detect_kick_trim, refine_phase
```

In `app/handlers/render_mixdown.py`:
```python
# Replace:
from app.audio.render.diagnostics import scan_mix
from app.audio.render.runner import run_render
# With:
from app.audio.render import run_render, scan_mix
```

In `app/handlers/render_diagnose.py`:
```python
# Replace:
from app.audio.render.diagnostics import diagnose_mix
# With:
from app.audio.render import diagnose_mix
```

- [ ] **Step 11: Run tests to verify**

```bash
uv run pytest tests/audio/render/ tests/handlers/test_render_* tests/domain/render/ -v --timeout=30
```
Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "refactor: code quality pass — constants, re-exports, tempfile, workspace dedup"
```

---

### Task 3: `deliver_set` tool + handler

**Files:**
- Create: `app/schemas/delivery.py`
- Create: `app/handlers/deliver_set.py`
- Create: `app/tools/render/deliver_set.py`
- Create: `tests/handlers/test_deliver_set.py`

**Interfaces:**
- Consumes: `app.repositories.unit_of_work.UnitOfWork`, `app.server.di.get_uow`,
  `app.domain.render.models.TrackInput`, `app.shared.workspace.render_workspace`,
  `app.config.get_settings`
- Produces: `DeliverSetResult`, `deliver_set_handler`, `deliver_set` tool

- [ ] **Step 1: Create `app/schemas/delivery.py`**

```python
"""Schemas for set delivery."""

from __future__ import annotations

from pydantic import BaseModel


class DeliverSetResult(BaseModel):
    version_id: int
    out_path: str
    files: list[str]
    n_tracks: int
    continuous_mix_included: bool
```

- [ ] **Step 2: Write failing test for `deliver_set_handler`**

```python
# tests/handlers/test_deliver_set.py
"""Test deliver_set handler (mocked IO)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.handlers.deliver_set import deliver_set_handler


@pytest.mark.asyncio
async def test_deliver_set_handler_creates_bundle(tmp_path: Path) -> None:
    """Handler copies tracks + MIX.mp3 + generates M3U8."""
    version_id = 1
    out_dir = str(tmp_path / "deliver" / "v1")

    # Mock UoW
    uow = AsyncMock()
    uow.set_versions.get_render_inputs.return_value = [
        AsyncMock(track_id=1, yandex_id=123, title="Artist - Track A", bpm=130.0,
                  key_code=12, file_path="/fake/a.mp3"),
        AsyncMock(track_id=2, yandex_id=456, title="Artist - Track B", bpm=128.0,
                  key_code=13, file_path="/fake/b.mp3"),
    ]

    # Mock render workspace with MIX.mp3
    ws = tmp_path / "render" / "v1"
    ws.mkdir(parents=True)
    mix = ws / "MIX.mp3"
    mix.write_text("fake mp3 data")

    # Fake source files
    src_a = Path("/fake/a.mp3")
    src_b = Path("/fake/b.mp3")
    src_a.parent.mkdir(parents=True, exist_ok=True)
    src_b.parent.mkdir(parents=True, exist_ok=True)
    src_a.write_text("fake data")
    src_b.write_text("fake data")

    with patch("app.shared.workspace.render_workspace", return_value=ws), \
         patch("app.config.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.delivery.copy_audio_files = True
        settings.delivery.emit_m3u8 = True
        settings.delivery.emit_rekordbox_xml = False
        settings.delivery.emit_continuous_mix = True
        settings.delivery.emit_cheatsheet = False
        settings.delivery.emit_json_guide = False
        settings.delivery.icloud_min_download_ratio = 0.9

        result = await deliver_set_handler(
            ctx=None, uow=uow, version_id=version_id, out_dir=out_dir
        )

    assert result.version_id == version_id
    assert result.n_tracks == 2
    assert result.continuous_mix_included is True
    assert result.out_path == out_dir
    assert len(result.files) >= 2  # at least MIX.mp3 + some tracks

    # MIX.mp3 was copied
    assert (Path(out_dir) / "MIX.mp3").exists()
    # Tracks were copied
    assert list((Path(out_dir) / "tracks").iterdir())


@pytest.mark.asyncio
async def test_deliver_set_skips_missing_mix(tmp_path: Path) -> None:
    """When MIX.mp3 is missing, continuous_mix_included=False."""
    version_id = 1
    out_dir = str(tmp_path / "deliver" / "v1")

    uow = AsyncMock()
    uow.set_versions.get_render_inputs.return_value = []

    ws = tmp_path / "render" / "v1"
    ws.mkdir(parents=True)
    # NO MIX.mp3

    with patch("app.shared.workspace.render_workspace", return_value=ws), \
         patch("app.config.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.delivery.copy_audio_files = False
        settings.delivery.emit_m3u8 = False
        settings.delivery.emit_rekordbox_xml = False
        settings.delivery.emit_continuous_mix = True
        settings.delivery.emit_cheatsheet = False
        settings.delivery.emit_json_guide = False

        result = await deliver_set_handler(
            ctx=None, uow=uow, version_id=version_id, out_dir=out_dir
        )

    assert result.continuous_mix_included is False
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/handlers/test_deliver_set.py -v --timeout=10
```
Expected: FAIL (module not found).

- [ ] **Step 4: Create `app/handlers/deliver_set.py`**

```python
"""Handler: deliver a rendered set — bundle tracks, M3U8, rekordbox XML, MIX.mp3."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from app.config import get_settings
from app.schemas.delivery import DeliverSetResult
from app.shared.workspace import render_workspace

# Camelot → musical key for rekordbox XML
_CAMELOT_TO_KEY = {
    "7A": "Dm", "7B": "F", "8A": "Am", "8B": "C",
    "9A": "Em", "9B": "G", "10A": "Bm", "10B": "D",
    "11A": "F#m", "11B": "A", "12A": "C#m", "12B": "E",
    "1A": "Ebm", "1B": "Gb", "2A": "Bbm", "2B": "Db",
    "3A": "Fm", "3B": "Ab", "4A": "Cm", "4B": "Eb",
    "5A": "Gm", "5B": "Bb", "6A": "Dm", "6B": "F",
}


def _safe_filename(s: str) -> str:
    return s.replace("/", "-")


def _is_real_file(path: Path, ratio: float) -> bool:
    """Check file is not an iCloud stub."""
    try:
        stat = os.stat(path)
        return stat.st_blocks * 512 >= stat.st_size * ratio
    except OSError:
        return False


async def deliver_set_handler(
    *, ctx: Any, uow: Any, version_id: int, out_dir: str | None = None
) -> DeliverSetResult:
    s = get_settings()
    d = s.delivery

    if out_dir is None:
        out_dir = str(Path(d.output_dir) / "deliver" / f"v{version_id}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = render_workspace(version_id)

    files: list[str] = []

    # Copy source audio files
    if d.copy_audio_files:
        tracks_dir = out / "tracks"
        tracks_dir.mkdir(exist_ok=True)
        for k, ti in enumerate(inputs, 1):
            src = Path(ti.file_path)
            if not src.exists():
                continue
            if not _is_real_file(src, d.icloud_min_download_ratio):
                continue
            dst_name = f"{k:02d}_{_safe_filename(ti.title)}.mp3"
            shutil.copy2(str(src), str(tracks_dir / dst_name))
            files.append(f"tracks/{dst_name}")

    # Generate M3U8
    if d.emit_m3u8:
        m3u_lines = ["#EXTM3U", f"#PLAYLIST:version {version_id}"]
        for k, ti in enumerate(inputs, 1):
            m3u_lines.append(f"#EXTINF:0,{ti.title}")
            m3u_lines.append(f"tracks/{k:02d}_{_safe_filename(ti.title)}.mp3")
        (out / "playlist.m3u8").write_text("\n".join(m3u_lines) + "\n")
        files.append("playlist.m3u8")

    # Generate rekordbox XML
    if d.emit_rekordbox_xml:
        n = len(inputs)
        coll_lines = [f'  <COLLECTION Entries="{n}">']
        for k, ti in enumerate(inputs, 1):
            artist, _, name = ti.title.partition(" - ")
            cam_str = _camelot_str(ti.key_code)
            tonality = _CAMELOT_TO_KEY.get(cam_str, "")
            loc = "file://localhost" + quote(
                str((out / "tracks" / f"{k:02d}_{_safe_filename(ti.title)}.mp3").resolve())
            )
            coll_lines.append(
                f'    <TRACK TrackID="{k}" Name={quoteattr(name or ti.title)} '
                f'Artist={quoteattr(artist)} Kind="MP3 File" AverageBpm="{ti.bpm:.2f}" '
                f"Tonality={quoteattr(tonality)} Location={quoteattr(loc)}/>"
            )
        coll_lines.append("  </COLLECTION>")
        pl_lines = [
            "  <PLAYLISTS>",
            '    <NODE Type="0" Name="ROOT" Count="1">',
            f'      <NODE Name="Version {version_id}" Type="1" KeyType="0" Entries="{n}">',
        ]
        pl_lines += [f'        <TRACK Key="{k}"/>' for k in range(1, n + 1)]
        pl_lines += ["      </NODE>", "    </NODE>", "  </PLAYLISTS>"]
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<DJ_PLAYLISTS Version="1.0.0">',
            '  <PRODUCT Name="rekordbox" Version="6.0.0" Company="AlphaTheta"/>',
            *coll_lines,
            *pl_lines,
            "</DJ_PLAYLISTS>",
        ]
        (out / "rekordbox.xml").write_text("\n".join(xml_parts) + "\n")
        files.append("rekordbox.xml")

    # Copy continuous mix
    mix_included = False
    if d.emit_continuous_mix:
        mix_src = ws / "MIX.mp3"
        if mix_src.exists():
            shutil.copy2(str(mix_src), str(out / "MIX.mp3"))
            files.append("MIX.mp3")
            mix_included = True

    return DeliverSetResult(
        version_id=version_id,
        out_path=str(out),
        files=files,
        n_tracks=len(inputs),
        continuous_mix_included=mix_included,
    )


def _camelot_str(key_code: int | None) -> str:
    """Convert numeric key_code (12=7A ...) to Camelot string."""
    if key_code is None:
        return ""
    mapping = {
        1: "1A", 2: "1B", 3: "2A", 4: "2B", 5: "3A", 6: "3B",
        7: "4A", 8: "4B", 9: "5A", 10: "5B", 11: "6A", 12: "6B",
        13: "7A", 14: "7B", 15: "8A", 16: "8B", 17: "9A", 18: "9B",
        19: "10A", 20: "10B", 21: "11A", 22: "11B", 23: "12A", 24: "12B",
    }
    return mapping.get(key_code, "")
```

- [ ] **Step 5: Create `app/tools/render/deliver_set.py`**

```python
"""deliver_set — bundle a rendered set version for export."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.deliver_set import deliver_set_handler
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(
    name="deliver_set",
    tags={"namespace:render", "render"},
    description=(
        "Bundle a rendered set version: copy source tracks, generate M3U8 / "
        "rekordbox XML / cheatsheet / JSON guide, include the continuous MIX.mp3. "
        "Respects DeliverySettings toggles."
    ),
    task=True,
)
async def deliver_set(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    out_dir: Annotated[
        str | None, Field(description="Override output directory (default: generated-sets/deliver/v{id})")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> dict:
    result = await deliver_set_handler(
        ctx=ctx, uow=uow, version_id=version_id, out_dir=out_dir
    )
    return result.model_dump()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/handlers/test_deliver_set.py -v --timeout=10
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add deliver_set tool + handler"
```

---

### Task 4: `render_verify` — DJ-adapted verify module

**Files:**
- Create: `app/audio/render/verify/__init__.py`
- Create: `app/audio/render/verify/manifest.py`
- Create: `app/audio/render/verify/analysis.py`
- Create: `app/audio/render/verify/checks.py`
- Create: `app/audio/render/verify/report.py`
- Modify: `app/schemas/render.py`
- Create: `tests/audio/render/verify/test_checks.py`

**Interfaces:**
- Consumes: `app.domain.render.models.RenderPlan`, `app.domain.render.timeline.build_render_plan`
- Produces: `verify.RenderVerifyReport`, `verify.run_verify(version_plan, beatgrid, src_measures, output_path) -> RenderVerifyReport`

- [ ] **Step 1: Create `app/audio/render/verify/__init__.py`**

```python
"""DJ-adapted mix verification — ported from scripts/verify_mix/."""
```

- [ ] **Step 2: Create `app/audio/render/verify/manifest.py`**

```python
"""DJ-specific manifest dataclass — built from RenderPlan + beatgrid."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.domain.render.models import BeatgridEntry, RenderPlan, TrackSegment


@dataclass(frozen=True, slots=True)
class DJSource:
    """One source track for verification."""

    index: int
    track_id: int
    file_path: str
    title: str
    bpm: float
    trim_start_s: float
    gain_db: float
    tempo_ratio: float


@dataclass(frozen=True, slots=True)
class DJManifest:
    """Verification context: plan + per-track beatgrid entries."""

    version_id: int
    target_bpm: float
    sources: list[DJSource] = field(default_factory=list)
    n_segments: int = 0
    expected_duration_s: float = 0.0
    segment_start_s: list[float] = field(default_factory=list)
    segment_lengths_s: list[float] = field(default_factory=list)


def build_verify_manifest(
    inputs: list,
    plan: RenderPlan,
    grid: dict[int, BeatgridEntry],
) -> DJManifest:
    sources = []
    for seg in plan.segments:
        g = grid.get(seg.track_id)
        sources.append(
            DJSource(
                index=seg.index,
                track_id=seg.track_id,
                file_path=seg.file_path,
                title=_find_title(inputs, seg.track_id),
                bpm=_find_bpm(inputs, seg.track_id),
                trim_start_s=seg.trim_start_s,
                gain_db=seg.gain_db,
                tempo_ratio=seg.tempo_ratio,
            )
        )
    return DJManifest(
        version_id=0,
        target_bpm=plan.target_bpm,
        sources=sources,
        n_segments=plan.n,
        expected_duration_s=plan.segments[-1].start_s + plan.segments[-1].length_s if plan.segments else 0.0,
        segment_start_s=[s.start_s for s in plan.segments],
        segment_lengths_s=[s.length_s for s in plan.segments],
    )


def _find_title(inputs: list, track_id: int) -> str:
    for ti in inputs:
        if ti.track_id == track_id:
            return ti.title
    return ""


def _find_bpm(inputs: list, track_id: int) -> float:
    for ti in inputs:
        if ti.track_id == track_id:
            return ti.bpm
    return 0.0
```

- [ ] **Step 3: Create `app/audio/render/verify/analysis.py`**

```python
"""Measurement primitives for DJ mix verification."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.audio.render._constants import ANALYSIS_SR, HOP_LENGTH

_FFMPEG_TIMEOUT_S = 300.0
_EBUR128_I_RE = None  # compiled lazily


@dataclass(slots=True)
class SourceMeasure:
    path: str
    exists: bool = False
    decoded_duration: float | None = None
    ffprobe_dur: float | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None


@dataclass(slots=True)
class OutputMeasure:
    path: str
    exists: bool = False
    decoded_duration: float | None = None
    rms_db: np.ndarray | None = None
    rms_times: np.ndarray | None = None
    low_rms_db: np.ndarray | None = None
    low_rms_times: np.ndarray | None = None
    max_volume: float | None = None
    sample_peak_db: float | None = None
    clipped_sample_count: int = 0
    channel_rms_db: tuple[float, float] | None = None
    stereo_correlation: float | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None
    bpm_stability: float | None = None
    crest_factor: float | None = None
    energy_range_db: float | None = None
    energy_dip_count: int = 0
    kick_drop_count: int = 0
    kick_drop_events: list[tuple[float, float]] = field(default_factory=list)
    segments: list[tuple[float, float, float | None]] = field(default_factory=list)
    first_clip_time: float | None = None


def load_audio(path: str, sr: int = ANALYSIS_SR) -> tuple[np.ndarray, int]:
    import librosa
    samples, out_sr = librosa.load(path, sr=sr, mono=True)
    return samples.astype(np.float32, copy=False), int(out_sr)


def load_audio_channels(path: str, sr: int = ANALYSIS_SR) -> tuple[np.ndarray, int]:
    import librosa
    samples, out_sr = librosa.load(path, sr=sr, mono=False)
    channels = np.asarray(samples, dtype=np.float32)
    if channels.ndim == 1:
        channels = channels[np.newaxis, :]
    return channels, int(out_sr)


def ffprobe_duration(path: str) -> float | None:
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT_S, check=False,
        )
        raw = json.loads(proc.stdout or "{}").get("format", {}).get("duration")
        return float(raw) if raw is not None else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def estimate_bpm(samples: np.ndarray, sr: int, *, min_bpm: float = 100.0, max_bpm: float = 200.0) -> tuple[float, float]:
    from app.audio.core.rhythm import tempo_from_onset_autocorrelation
    import librosa
    env = librosa.onset.onset_strength(y=samples, sr=sr, hop_length=HOP_LENGTH)
    env = np.asarray(env, dtype=np.float64)
    est = tempo_from_onset_autocorrelation(env, sr, HOP_LENGTH, min_bpm=min_bpm, max_bpm=max_bpm)
    return est.bpm, est.confidence


def rms_series(samples: np.ndarray, sr: int, *, window_s: float = 0.4, hop_s: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    win = max(1, int(window_s * sr))
    hop = max(1, int(hop_s * sr))
    if len(samples) < win:
        rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if len(samples) else 0.0
        return np.array([len(samples) / (2 * sr)]), np.array([_to_db(rms)])
    starts = np.arange(0, len(samples) - win + 1, hop)
    times = (starts + win / 2) / sr
    rms_db = np.empty(len(starts), dtype=np.float64)
    for i, s in enumerate(starts):
        chunk = samples[s : s + win].astype(np.float64)
        rms_db[i] = _to_db(float(np.sqrt(np.mean(np.square(chunk)))))
    return times, rms_db


def band_rms_series(samples: np.ndarray, sr: int, band_hz: tuple[float, float], *, window_s: float = 2.0, hop_s: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    filtered = _filter_band(samples, sr, band_hz)
    return rms_series(filtered, sr, window_s=window_s, hop_s=hop_s)


def stereo_summary(channels: np.ndarray) -> tuple[tuple[float, float] | None, float | None]:
    if channels.ndim != 2 or channels.shape[0] < 2 or channels.shape[1] == 0:
        return None, None
    left = channels[0].astype(np.float64)
    right = channels[1].astype(np.float64)
    left_db = _to_db(float(np.sqrt(np.mean(np.square(left)))))
    right_db = _to_db(float(np.sqrt(np.mean(np.square(right)))))
    if float(np.std(left)) < 1e-9 or float(np.std(right)) < 1e-9:
        corr = None
    else:
        corr = float(np.corrcoef(left, right)[0, 1])
    return (left_db, right_db), corr


def segment_lufs(path: str, start_s: float, duration_s: float) -> float | None:
    import re
    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-ss", f"{start_s:.3f}",
             "-t", f"{duration_s:.3f}", "-i", path,
             "-filter_complex", "ebur128", "-f", "null", "-"],
            capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    matches = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", proc.stderr)
    return float(matches[-1]) if matches else None


def max_volume_db(path: str) -> float | None:
    import re
    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-i", path,
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", proc.stderr)
    return float(match.group(1)) if match else None


def measure_source(path: str, *, bpm_hint: float | None, min_bpm: float = 100.0, max_bpm: float = 200.0) -> SourceMeasure:
    m = SourceMeasure(path=path)
    if not Path(path).is_file():
        return m
    m.exists = True
    m.ffprobe_dur = ffprobe_duration(path)
    samples, sr = load_audio(path)
    m.decoded_duration = len(samples) / sr
    m.bpm, m.bpm_confidence = estimate_bpm(samples, sr, min_bpm=min_bpm, max_bpm=max_bpm)
    return m


def measure_output(path: str, segment_boundaries: list[float], *, min_bpm: float = 100.0, max_bpm: float = 200.0, min_segment_s: float = 3.0) -> OutputMeasure:
    out = OutputMeasure(path=path)
    if not Path(path).is_file():
        return out
    out.exists = True
    channels, out_sr = load_audio_channels(path)
    samples = np.mean(channels, axis=0)
    out.decoded_duration = len(samples) / out_sr
    out.rms_times, out.rms_db = rms_series(samples, out_sr)
    out.low_rms_times, out.low_rms_db = band_rms_series(samples, out_sr, (25.0, 150.0))
    out.max_volume = max_volume_db(path)
    peak = float(np.max(np.abs(channels))) if channels.size else 0.0
    out.sample_peak_db = _to_db(peak)
    out.clipped_sample_count = int(np.count_nonzero(np.abs(channels) >= 0.999))
    if out.clipped_sample_count > 0:
        clip_mask = np.any(np.abs(channels) >= 0.999, axis=0)
        out.first_clip_time = int(np.argmax(clip_mask)) / out_sr
    out.channel_rms_db, out.stereo_correlation = stereo_summary(channels)
    out.bpm, out.bpm_confidence = estimate_bpm(samples, out_sr, min_bpm=min_bpm, max_bpm=max_bpm)

    if out.sample_peak_db is not None and len(out.rms_db) > 0:
        out.crest_factor = out.sample_peak_db - float(np.mean(out.rms_db))

    # Segment LUFS
    for start, end in zip(segment_boundaries[:-1], segment_boundaries[1:]):
        if end - start < min_segment_s:
            continue
        out.segments.append((start, end, segment_lufs(path, start, end - start)))

    # BPM stability across 30s windows
    total_s = len(samples) / out_sr
    window_s = 30.0
    hop_w = int(window_s * out_sr)
    bpms = []
    for st in range(0, len(samples) - hop_w + 1, hop_w):
        chunk = samples[st : st + hop_w]
        bpm, conf = estimate_bpm(chunk, out_sr, min_bpm=min_bpm, max_bpm=max_bpm)
        if bpm > 0 and conf > 0.1:
            bpms.append(bpm)
    if len(bpms) >= 3:
        out.bpm_stability = float(np.std(bpms))

    # Kick consistency
    if out.low_rms_db is not None and len(out.low_rms_db) >= 3 and out.rms_db is not None:
        low_median = float(np.median(out.low_rms_db))
        kick_floor = low_median - 8.0
        low_t = out.low_rms_times
        full_at_low = np.interp(low_t, out.rms_times, out.rms_db)
        mix_playing = full_at_low > -30.0
        kick_gone = (out.low_rms_db < kick_floor) & mix_playing
        runs = _true_runs(kick_gone)
        hop_s = float(low_t[1] - low_t[0]) if len(low_t) >= 2 else 1.0
        events = [(float(low_t[a]), float(low_t[b - 1])) for a, b in runs if (b - a) * hop_s >= 4.0]
        out.kick_drop_events = events
        out.kick_drop_count = len(events)

    # Energy range
    if out.rms_db is not None and len(out.rms_db) > 0:
        out.energy_range_db = float(np.max(out.rms_db) - np.min(out.rms_db))

    return out


def segment_boundaries(segment_start_s: list[float], segment_lengths_s: list[float], total_duration: float) -> list[float]:
    points = {0.0, total_duration}
    for s, l in zip(segment_start_s, segment_lengths_s):
        for t in (s, s + l):
            if 0.0 < t < total_duration:
                points.add(round(t, 3))
    return sorted(points)


def _filter_band(samples: np.ndarray, sr: int, band_hz: tuple[float, float]) -> np.ndarray:
    from scipy.signal import butter, sosfiltfilt
    if len(samples) < 64:
        return samples.astype(np.float32, copy=False)
    low, high = band_hz
    nyquist = sr / 2.0
    if low <= 0 and high >= nyquist:
        return samples.astype(np.float32, copy=False)
    if low <= 0:
        sos = butter(4, high, btype="lowpass", fs=sr, output="sos")
    elif high >= nyquist:
        sos = butter(4, low, btype="highpass", fs=sr, output="sos")
    else:
        sos = butter(4, (low, high), btype="bandpass", fs=sr, output="sos")
    return np.asarray(sosfiltfilt(sos, samples), dtype=np.float32)


def _to_db(linear: float) -> float:
    return 20.0 * float(np.log10(max(linear, 1e-10)))


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    runs = []
    start = None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs
```

- [ ] **Step 4: Create `app/audio/render/verify/checks.py`**

```python
"""14 DJ-adapted mix verification checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

from .analysis import DJManifest, DJSource, OutputMeasure, SourceMeasure


class Status(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: Status
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerifyConfig:
    duration_mismatch_pct: float = 2.0
    bpm_confidence_warn: float = 0.25
    declared_bpm_fail: float = 2.0
    declared_bpm_warn: float = 0.5
    trim_tolerance_s: float = 0.05
    output_duration_warn_s: float = 1.0
    output_duration_fail_s: float = 2.0
    clipping_dbfs: float = -0.1
    dropout_rms_db: float = -50.0
    dropout_min_s: float = 0.5
    lufs_spread_fail_lu: float = 6.0
    lufs_spread_warn_lu: float = 3.0
    low_band_drop_fail_db: float = 10.0
    low_band_floor_db: float = -42.0
    low_band_min_s: float = 4.0
    stereo_imbalance_warn_db: float = 2.0
    stereo_imbalance_fail_db: float = 4.0
    stereo_correlation_warn: float = 0.0
    stereo_correlation_fail: float = -0.30
    bpm_stability_warn: float = 2.0
    bpm_stability_fail: float = 5.0
    kick_drop_warn_s: float = 16.0
    kick_drop_fail_s: float = 32.0
    energy_range_warn_db: float = 30.0
    energy_range_fail_db: float = 38.0
    min_segment_s: float = 3.0


def _missing(name: str, path: str) -> CheckResult:
    return CheckResult(name, Status.WARN, f"{path}: source missing - check skipped", {"path": path})


def check_honest_duration(manifest: DJManifest, src_measures: dict[int, SourceMeasure], cfg: VerifyConfig) -> list[CheckResult]:
    name = "honest_duration"
    results = []
    for src in manifest.sources:
        m = src_measures.get(src.track_id)
        if m is None or not m.exists:
            results.append(_missing(name, src.file_path))
            continue
        if m.decoded_duration is None or m.ffprobe_dur is None:
            results.append(CheckResult(name, Status.WARN, f"{src.file_path}: durations unavailable", {}))
            continue
        ref = max(m.decoded_duration, 1e-6)
        diff_pct = abs(m.ffprobe_dur - m.decoded_duration) / ref * 100.0
        status = Status.FAIL if diff_pct > cfg.duration_mismatch_pct else Status.PASS
        results.append(CheckResult(name, status, f"{src.file_path}: decoded {m.decoded_duration:.1f}s vs ffprobe {m.ffprobe_dur:.1f}s (Δ{diff_pct:.1f}%)", {"decoded_s": m.decoded_duration, "ffprobe_s": m.ffprobe_dur}))
    return results


def check_bpm_reliability(manifest: DJManifest, src_measures: dict[int, SourceMeasure], cfg: VerifyConfig) -> list[CheckResult]:
    name = "bpm_reliability"
    results = []
    for src in manifest.sources:
        m = src_measures.get(src.track_id)
        if m is None or not m.exists:
            results.append(_missing(name, src.file_path))
            continue
        if m.bpm is None or m.bpm <= 0:
            results.append(CheckResult(name, Status.WARN, f"{src.file_path}: BPM undetectable, declared {src.bpm:.2f}", {}))
            continue
        delta = _bpm_delta(m.bpm, src.bpm)
        detail = {"declared_bpm": src.bpm, "measured_bpm": m.bpm, "confidence": m.bpm_confidence}
        if delta > cfg.declared_bpm_fail:
            results.append(CheckResult(name, Status.FAIL, f"{src.file_path}: measured {m.bpm:.2f} vs declared {src.bpm:.2f} (Δ{delta:.2f})", detail))
        elif (m.bpm_confidence or 0) < cfg.bpm_confidence_warn:
            results.append(CheckResult(name, Status.WARN, f"{src.file_path}: BPM {m.bpm:.2f} confidence {m.bpm_confidence:.2f}", detail))
        else:
            status = Status.WARN if delta > cfg.declared_bpm_warn else Status.PASS
            results.append(CheckResult(name, status, f"{src.file_path}: {m.bpm:.2f} vs {src.bpm:.2f} (Δ{delta:.2f})", detail))
    return results


def check_source_trim_bounds(manifest: DJManifest, src_measures: dict[int, SourceMeasure], cfg: VerifyConfig) -> list[CheckResult]:
    name = "source_trim_bounds"
    results = []
    for src in manifest.sources:
        m = src_measures.get(src.track_id)
        if m is None or not m.exists:
            results.append(_missing(name, src.file_path))
            continue
        if m.decoded_duration is None:
            results.append(CheckResult(name, Status.WARN, f"{src.file_path}: decoded duration unavailable", {}))
            continue
        over_by = src.trim_start_s + 24.0 - m.decoded_duration  # 24s is render chunk
        if src.trim_start_s < -cfg.trim_tolerance_s or over_by > cfg.trim_tolerance_s:
            results.append(CheckResult(name, Status.FAIL, f"{src.file_path}: trim {src.trim_start_s:.2f}s outside source {m.decoded_duration:.2f}s", {}))
        else:
            results.append(CheckResult(name, Status.PASS, f"{src.file_path}: trim fits", {}))
    return results


def check_timeline(manifest: DJManifest, src_measures: dict[int, SourceMeasure], cfg: VerifyConfig) -> list[CheckResult]:
    name = "timeline"
    if manifest.n_segments < 2:
        return [CheckResult(name, Status.PASS, "single segment", {})]
    results = []
    # Check no negative gaps between segments
    for i in range(manifest.n_segments - 1):
        end = manifest.segment_start_s[i] + (manifest.sources[i].trim_start_s + 24.0) if i < len(manifest.sources) else 0
        next_start = manifest.segment_start_s[i + 1]
        if next_start < end - 0.1:
            results.append(CheckResult(name, Status.WARN, f"segments {i} and {i+1} overlap by {end - next_start:.1f}s", {}))
    if not results:
        results.append(CheckResult(name, Status.PASS, "no timeline issues", {}))
    return results


def check_output_duration(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "output_duration"
    if not out.exists or out.decoded_duration is None:
        return [CheckResult(name, Status.WARN, "output unavailable", {})]
    expected = manifest.expected_duration_s
    if expected <= 0:
        return [CheckResult(name, Status.WARN, "expected duration unknown", {})]
    delta = out.decoded_duration - expected
    abs_delta = abs(delta)
    if abs_delta > cfg.output_duration_fail_s:
        status = Status.FAIL
    elif abs_delta > cfg.output_duration_warn_s:
        status = Status.WARN
    else:
        status = Status.PASS
    return [CheckResult(name, status, f"output {out.decoded_duration:.2f}s vs expected {expected:.2f}s (Δ{delta:+.2f}s)", {"actual_s": out.decoded_duration, "expected_s": expected})]


def check_clipping(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "clipping"
    if not out.exists:
        return [CheckResult(name, Status.WARN, "output unavailable", {})]
    peak = max(v for v in (out.max_volume, out.sample_peak_db) if v is not None)
    if peak is None:
        return [CheckResult(name, Status.WARN, "no peak measurement", {})]
    clipped = out.clipped_sample_count
    status = Status.FAIL if peak >= cfg.clipping_dbfs or clipped > 0 else Status.PASS
    msg = f"peak {peak:.1f} dBFS, clipped samples {clipped}"
    if out.first_clip_time is not None:
        msg += f"; first clip at {out.first_clip_time:.0f}s"
    return [CheckResult(name, status, msg, {"peak_db": peak, "clipped": clipped})]


def check_dropouts(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "dropouts"
    if not out.exists or out.rms_times is None or out.rms_db is None:
        return [CheckResult(name, Status.WARN, "output unavailable", {})]
    silent = out.rms_db < cfg.dropout_rms_db
    runs = _true_runs(silent)
    hop = float(out.rms_times[1] - out.rms_times[0]) if len(out.rms_times) >= 2 else 0.2
    dropouts = [(float(out.rms_times[a]), float(out.rms_times[b - 1])) for a, b in runs if (b - a) * hop >= cfg.dropout_min_s]
    if dropouts:
        return [CheckResult(name, Status.FAIL, f"{len(dropouts)} silent window(s) ≥ {cfg.dropout_min_s}s, first at {dropouts[0][0]:.1f}s", {"dropouts": dropouts})]
    return [CheckResult(name, Status.PASS, "no silent windows", {})]


def check_loudness_consistency(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "loudness_consistency"
    if not out.exists:
        return [CheckResult(name, Status.WARN, "output unavailable", {})]
    values = [(s, e, l) for s, e, l in out.segments if l is not None]
    if len(values) < 2:
        return [CheckResult(name, Status.PASS, "fewer than 2 measurable segments", {"segments": len(values)})]
    lufs = [v[2] for v in values]
    spread = max(lufs) - min(lufs)
    if spread > cfg.lufs_spread_fail_lu:
        status = Status.FAIL
    elif spread > cfg.lufs_spread_warn_lu:
        status = Status.WARN
    else:
        status = Status.PASS
    return [CheckResult(name, status, f"segment LUFS spread {spread:.1f} LU across {len(values)} segments", {"spread_lu": spread})]


def check_low_band_holes(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "low_band_holes"
    if not out.exists or out.low_rms_times is None or out.low_rms_db is None:
        return [CheckResult(name, Status.WARN, "output unavailable", {})]
    values = out.low_rms_db
    if len(values) < 2:
        return [CheckResult(name, Status.PASS, "low-band series too short", {})]
    median = float(np.median(values))
    low = (values < median - cfg.low_band_drop_fail_db) & (values < cfg.low_band_floor_db)
    runs = _true_runs(low)
    hop = float(out.low_rms_times[1] - out.low_rms_times[0]) if len(out.low_rms_times) >= 2 else 1.0
    holes = [(float(out.low_rms_times[a]), float(out.low_rms_times[b - 1])) for a, b in runs if (b - a) * hop >= cfg.low_band_min_s]
    if holes:
        return [CheckResult(name, Status.FAIL, f"{len(holes)} low-band hole(s) ≥ {cfg.low_band_min_s}s, first at {holes[0][0]:.1f}s", {"holes": holes})]
    return [CheckResult(name, Status.PASS, "no low-band holes", {})]


def check_stereo_balance(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "stereo_balance"
    if not out.exists:
        return [CheckResult(name, Status.WARN, "output unavailable", {})]
    if out.channel_rms_db is None:
        return [CheckResult(name, Status.PASS, "mono output or unavailable", {})]
    left, right = out.channel_rms_db
    imbalance = abs(left - right)
    corr = out.stereo_correlation
    if imbalance > cfg.stereo_imbalance_fail_db or (corr is not None and corr < cfg.stereo_correlation_fail):
        status = Status.FAIL
    elif imbalance > cfg.stereo_imbalance_warn_db or (corr is not None and corr < cfg.stereo_correlation_warn):
        status = Status.WARN
    else:
        status = Status.PASS
    corr_text = "n/a" if corr is None else f"{corr:.2f}"
    return [CheckResult(name, status, f"L/R {left:.1f}/{right:.1f} dB (Δ{imbalance:.1f}), correlation {corr_text}", {})]


def check_bpm_stability(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "bpm_stability"
    if not out.exists or out.bpm_stability is None:
        return [CheckResult(name, Status.WARN, "output unavailable or stability unavailable", {})]
    v = out.bpm_stability
    status = Status.FAIL if v > cfg.bpm_stability_fail else (Status.WARN if v > cfg.bpm_stability_warn else Status.PASS)
    return [CheckResult(name, status, f"BPM spread σ={v:.2f}", {"bpm_stability": v})]


def check_kick_consistency(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "kick_consistency"
    if not out.exists or out.kick_drop_count == 0:
        return [CheckResult(name, Status.PASS, "no kick drop-outs detected", {})]
    worst_dur = max(e[1] - e[0] for e in out.kick_drop_events)
    status = Status.FAIL if worst_dur > cfg.kick_drop_fail_s else (Status.WARN if worst_dur > cfg.kick_drop_warn_s else Status.PASS)
    msg = f"{out.kick_drop_count} kick drop-out(s), longest {worst_dur:.0f}s"
    return [CheckResult(name, status, msg, {"drop_count": out.kick_drop_count, "longest_s": worst_dur})]


def check_energy_range(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure, cfg: VerifyConfig) -> list[CheckResult]:
    name = "energy_range"
    if not out.exists or out.energy_range_db is None:
        return [CheckResult(name, Status.WARN, "output unavailable", {})]
    v = out.energy_range_db
    status = Status.FAIL if v > cfg.energy_range_fail_db else (Status.WARN if v > cfg.energy_range_warn_db else Status.PASS)
    return [CheckResult(name, status, f"RMS spread {v:.1f} dB", {"energy_range_db": v})]


PRE_CHECKS = [check_honest_duration, check_bpm_reliability, check_source_trim_bounds, check_timeline]
POST_CHECKS = [check_output_duration, check_clipping, check_dropouts, check_loudness_consistency, check_low_band_holes, check_stereo_balance, check_bpm_stability, check_kick_consistency, check_energy_range]


def run_checks(manifest: DJManifest, src_measures: dict[int, SourceMeasure], out: OutputMeasure | None, cfg: VerifyConfig, *, skip_post: bool = False) -> list[CheckResult]:
    results = []
    for check in PRE_CHECKS:
        results.extend(check(manifest, src_measures, cfg))
    if not skip_post and out is not None:
        for check in POST_CHECKS:
            results.extend(check(manifest, src_measures, out, cfg))
    return results


def _bpm_delta(a: float, b: float) -> float:
    return min(abs(a - b), abs(a * 2 - b), abs(a / 2 - b))


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    runs = []
    start = None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs
```

- [ ] **Step 5: Create `app/audio/render/verify/report.py`**

```python
"""Aggregate check results — same shape as scripts/verify_mix/report.py."""

from __future__ import annotations

from .checks import CheckResult, Status


class VerifyReport:
    def __init__(self, results: list[CheckResult]) -> None:
        self.results = tuple(results)

    @property
    def counts(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Status}
        for r in self.results:
            counts[r.status.value] += 1
        return counts

    @property
    def exit_code(self) -> int:
        return 1 if any(r.status is Status.FAIL for r in self.results) else 0

    def to_text(self) -> str:
        width = max((len(r.name) for r in self.results), default=0)
        lines = [f"  [{r.status.value:<4}] {r.name:<{width}}  {r.message}" for r in self.results]
        c = self.counts
        lines.append(f"{c['PASS']} PASS, {c['WARN']} WARN, {c['FAIL']} FAIL -> exit {self.exit_code}")
        return "\n".join(lines)
```

- [ ] **Step 6: Write tests for verify checks (synthetic)**

```python
# tests/audio/render/verify/test_checks.py
"""Tests for render_verify checks with synthetic data."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.render.verify.analysis import DJManifest, DJSource, OutputMeasure, SourceMeasure
from app.audio.render.verify.checks import (
    POST_CHECKS,
    PRE_CHECKS,
    CheckResult,
    Status,
    VerifyConfig,
    check_clipping,
    check_output_duration,
    check_stereo_balance,
    run_checks,
)


def _make_manifest(n: int = 3) -> DJManifest:
    sources = [DJSource(index=i, track_id=i+1, file_path=f"/fake/{i+1}.mp3", title=f"Track {i+1}", bpm=130.0, trim_start_s=0.0, gain_db=0.0, tempo_ratio=1.0) for i in range(n)]
    return DJManifest(version_id=1, target_bpm=130.0, sources=sources, n_segments=n, expected_duration_s=360.0, segment_start_s=[i * 120.0 for i in range(n)])


def _make_src_measures(manifest: DJManifest, bpm: float = 130.0) -> dict[int, SourceMeasure]:
    return {s.track_id: SourceMeasure(path=s.file_path, exists=True, decoded_duration=300.0, ffprobe_dur=300.0, bpm=bpm, bpm_confidence=0.8) for s in manifest.sources}


def _make_output(exists: bool = True) -> OutputMeasure:
    out = OutputMeasure(path="/fake/mix.mp3", exists=exists)
    if exists:
        out.decoded_duration = 360.0
        out.max_volume = -1.0
        out.sample_peak_db = -1.0
        out.clipped_sample_count = 0
        out.channel_rms_db = (-12.0, -11.5)
        out.stereo_correlation = 0.85
        out.rms_times = np.linspace(0, 360, 180)
        out.rms_db = np.full(180, -18.0)
        out.low_rms_times = np.linspace(0, 360, 360)
        out.low_rms_db = np.full(360, -24.0)
        out.bpm_stability = 0.5
        out.segments = [(0.0, 120.0, -11.0), (120.0, 240.0, -11.5), (240.0, 360.0, -10.8)]
    return out


def test_pre_checks_all_pass() -> None:
    manifest = _make_manifest()
    src_measures = _make_src_measures(manifest)
    cfg = VerifyConfig()
    results = run_checks(manifest, src_measures, None, cfg, skip_post=True)
    assert all(r.status is Status.PASS for r in results)


def test_bpm_mismatch_fails() -> None:
    manifest = _make_manifest()
    src_measures = _make_src_measures(manifest, bpm=125.0)
    cfg = VerifyConfig()
    results = run_checks(manifest, src_measures, None, cfg, skip_post=True)
    bpm_results = [r for r in results if r.name == "bpm_reliability"]
    assert any(r.status is Status.FAIL for r in bpm_results), f"BPM delta 5.0 should fail: {[r.status for r in bpm_results]}"


def test_clipping_detected() -> None:
    manifest = _make_manifest()
    src_measures = _make_src_measures(manifest)
    out = _make_output()
    out.max_volume = -0.05  # above -0.1 threshold
    out.clipped_sample_count = 3
    results = check_clipping(manifest, src_measures, out, VerifyConfig())
    assert results[0].status is Status.FAIL


def test_stereo_balance_pass() -> None:
    manifest = _make_manifest()
    src_measures = _make_src_measures(manifest)
    out = _make_output()
    results = check_stereo_balance(manifest, src_measures, out, VerifyConfig())
    assert results[0].status is Status.PASS


def test_stereo_imbalance_fails() -> None:
    manifest = _make_manifest()
    src_measures = _make_src_measures(manifest)
    out = _make_output()
    out.channel_rms_db = (-8.0, -14.0)  # 6 dB imbalance
    results = check_stereo_balance(manifest, src_measures, out, VerifyConfig())
    assert results[0].status is Status.FAIL


def test_output_duration_within_tolerance() -> None:
    manifest = _make_manifest()
    src_measures = _make_src_measures(manifest)
    out = _make_output()
    out.decoded_duration = 360.5  # 0.5s delta, within 1s warn
    results = check_output_duration(manifest, src_measures, out, VerifyConfig())
    assert results[0].status is Status.PASS


def test_output_duration_too_long() -> None:
    manifest = _make_manifest()
    src_measures = _make_src_measures(manifest)
    out = _make_output()
    out.decoded_duration = 365.0  # 5s delta
    results = check_output_duration(manifest, src_measures, out, VerifyConfig())
    assert results[0].status is Status.FAIL
```

- [ ] **Step 7: Add `RenderVerifyResult` to `app/schemas/render.py`**

Find the existing schemas file and add after the last class:

```python
class RenderVerifyResult(BaseModel):
    """Result of running render_verify on a set version."""
    version_id: int
    passed: int = 0
    warned: int = 0
    failed: int = 0
    exit_code: int = 0
    summary: str = ""
    results: list[dict] = []
```

- [ ] **Step 8: Run verify tests**

```bash
uv run pytest tests/audio/render/verify/test_checks.py -v --timeout=10
```
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: add render_verify module (DJ-adapted mix-verify checks)"
```

---

### Task 5: `render_verify` handler + tool

**Files:**
- Create: `app/handlers/render_verify.py`
- Create: `app/tools/render/render_verify.py`
- Create: `tests/handlers/test_render_verify.py`
- Create: `tests/tools/render/test_render_verify_tool.py`

**Interfaces:**
- Consumes: `app.domain.render.timeline.build_render_plan`, `app.audio.render.verify.*`, `app.shared.workspace.render_workspace`
- Produces: `render_verify_handler`, `render_verify` tool

- [ ] **Step 1: Write failing tests**

```python
# tests/handlers/test_render_verify.py
"""Test render_verify handler (mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.handlers.render_verify import render_verify_handler
from app.schemas.render import RenderVerifyResult


@pytest.mark.asyncio
async def test_render_verify_handler_runs_checks() -> None:
    version_id = 1
    uow = AsyncMock()
    uow.set_versions.get_render_inputs.return_value = [
        AsyncMock(track_id=1, yandex_id=123, title="Track A", bpm=130.0,
                  key_code=12, file_path="/fake/a.mp3", integrated_lufs=-11.5,
                  mix_in_ms=0),
        AsyncMock(track_id=2, yandex_id=456, title="Track B", bpm=128.0,
                  key_code=13, file_path="/fake/b.mp3", integrated_lufs=-10.8,
                  mix_in_ms=500),
    ]

    with patch("app.handlers.render_verify.render_beatgrid_handler", new=AsyncMock(return_value=None)), \
         patch("app.handlers.render_verify.json.loads", return_value=[
             {"track_id": 1, "trim_start_s": 0.3, "refined_trim_s": 0.35, "gain_db": 0.5, "phase_ms": 5.0},
             {"track_id": 2, "trim_start_s": 0.7, "refined_trim_s": 0.72, "gain_db": 0.3, "phase_ms": 2.0},
         ]), \
         patch("app.shared.workspace.render_workspace"), \
         patch("app.audio.render.verify.analysis.measure_source") as mock_ms, \
         patch("app.audio.render.verify.analysis.measure_output") as mock_mo:

        from app.audio.render.verify.analysis import (
            MeasureOutput, MeasureSource, SourceMeasure, OutputMeasure,
        )

        def fake_source(path, **kw):
            tid = 1 if "a.mp3" in path else 2
            return SourceMeasure(path=path, exists=True, decoded_duration=300.0, ffprobe_dur=300.0, bpm=130.0, bpm_confidence=0.9)
        mock_ms.side_effect = fake_source

        def fake_output(path, **kw):
            return OutputMeasure(path=path, exists=True, decoded_duration=360.0, max_volume=-1.0, sample_peak_db=-1.0)
        mock_mo.side_effect = fake_output

        result = await render_verify_handler(ctx=None, uow=uow, version_id=version_id, skip_post=False)

    assert isinstance(result, RenderVerifyResult)
    assert result.version_id == version_id
    assert result.passed >= 0
    assert result.failed >= 0
    assert isinstance(result.summary, str)


@pytest.mark.asyncio
async def test_render_verify_skip_post() -> None:
    uow = AsyncMock()
    uow.set_versions.get_render_inputs.return_value = []

    with patch("app.handlers.render_verify.render_beatgrid_handler", new=AsyncMock()), \
         patch("app.handlers.render_verify.json.loads", return_value=[]), \
         patch("app.shared.workspace.render_workspace"), \
         patch("app.audio.render.verify.analysis.measure_source", return_value=SourceMeasure(path="/f.mp3", exists=False)), \
         patch("app.audio.render.verify.analysis.measure_output") as mock_mo:

        result = await render_verify_handler(ctx=None, uow=uow, version_id=1, skip_post=True)
        mock_mo.assert_not_called()
```

- [ ] **Step 2: Create `app/handlers/render_verify.py`**

```python
"""Handler: run DJ-adapted mix verification for a set version."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.verify.analysis import (
    DJManifest,
    build_verify_manifest,
    measure_source,
    measure_output,
    segment_boundaries,
)
from app.audio.render.verify.checks import VerifyConfig, run_checks
from app.audio.render.verify.report import VerifyReport
from app.domain.render.timeline import build_render_plan
from app.handlers._context_log import safe_info
from app.handlers.render_beatgrid import render_beatgrid_handler
from app.schemas.render import RenderVerifyResult
from app.shared.workspace import render_workspace


async def render_verify_handler(
    *, ctx: Any, uow: Any, version_id: int, skip_post: bool = False
) -> RenderVerifyResult:
    if ctx is not None:
        await safe_info(ctx, f"render_verify: version {version_id} pre{' + post' if not skip_post else ''}")

    cfg = VerifyConfig()
    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = render_workspace(version_id)
    grid_path = ws / "beatgrid.json"

    # Ensure beatgrid exists
    if not grid_path.exists():
        await render_beatgrid_handler(ctx=ctx, uow=uow, version_id=version_id, workspace=str(ws))

    grid = json.loads(grid_path.read_text())
    grid_by_track: dict[int, dict] = {g["track_id"]: g for g in grid}
    beatgrid_entries: dict[int, Any] = {}
    for g in grid:
        from app.domain.render.models import BeatgridEntry
        beatgrid_entries[g["track_id"]] = BeatgridEntry(
            track_id=g["track_id"],
            trim_start_s=g["trim_start_s"],
            refined_trim_s=g.get("refined_trim_s"),
            gain_db=g.get("gain_db", 0.0),
            phase_ms=g.get("phase_ms", 0.0),
        )

    rs = __import__("app.config", fromlist=["get_settings"]).get_settings().render
    plan = build_render_plan(
        inputs, beatgrid_entries,
        target_bpm=rs.target_bpm, body_bars=rs.body_bars,
        transition_bars=rs.transition_bars, xsplit_hz=rs.xsplit_hz,
        low_swap_bars=rs.low_swap_bars, outro_fade_bars=rs.outro_fade_bars,
        limiter_ceiling=rs.limiter_ceiling,
    )

    manifest = build_verify_manifest(inputs, plan, beatgrid_entries)

    # Pre-render: measure each source
    src_measures: dict[int, Any] = {}
    for src in manifest.sources:
        src_measures[src.track_id] = measure_source(
            src.file_path, bpm_hint=src.bpm,
            min_bpm=cfg.min_bpm, max_bpm=cfg.max_bpm,
        )

    # Post-render: measure output
    out_measure = None
    if not skip_post:
        mix_path = str(ws / "MIX.mp3")
        bounds = segment_boundaries(
            manifest.segment_start_s,
            [s.trim_start_s + 24.0 for s in manifest.sources],
            manifest.expected_duration_s,
        )
        out_measure = measure_output(mix_path, bounds, min_bpm=cfg.min_bpm, max_bpm=cfg.max_bpm)

    results = run_checks(manifest, src_measures, out_measure, cfg, skip_post=skip_post)
    report = VerifyReport(results)
    result = RenderVerifyResult(
        version_id=version_id,
        passed=report.counts.get("PASS", 0),
        warned=report.counts.get("WARN", 0),
        failed=report.counts.get("FAIL", 0),
        exit_code=report.exit_code,
        summary=report.to_text(),
        results=[{"name": r.name, "status": r.status.value, "message": r.message, "detail": r.detail} for r in results],
    )
    if ctx is not None:
        await safe_info(ctx, f"render_verify: {result.passed}P {result.warned}W {result.failed}F")
    return result
```

Wait, I'm overcomplicating the handler. Let me simplify — the handler doesn't need to import `__import__`. It should use normal imports. Let me fix this.

Actually, looking at the handler more carefully, it needs access to `RenderSettings`. It can import `get_settings` from `app.config`. Let me clean this up.

- [ ] **Step 2: Create `app/handlers/render_verify.py` (cleaned)**

```python
"""Handler: run DJ-adapted mix verification for a set version."""

from __future__ import annotations

import json
from typing import Any

from app.audio.render.verify.analysis import (
    build_verify_manifest, measure_output, measure_source, segment_boundaries,
)
from app.audio.render.verify.checks import VerifyConfig, run_checks
from app.audio.render.verify.report import VerifyReport
from app.config import get_settings
from app.domain.render.models import BeatgridEntry
from app.domain.render.timeline import build_render_plan
from app.handlers._context_log import safe_info
from app.handlers.render_beatgrid import render_beatgrid_handler
from app.schemas.render import RenderVerifyResult
from app.shared.workspace import render_workspace


async def render_verify_handler(
    *, ctx: Any, uow: Any, version_id: int, skip_post: bool = False
) -> RenderVerifyResult:
    if ctx is not None:
        await safe_info(ctx, f"render_verify: version {version_id} pre{' + post' if not skip_post else ''}")

    cfg = VerifyConfig()
    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = render_workspace(version_id)
    grid_path = ws / "beatgrid.json"

    if not grid_path.exists():
        await render_beatgrid_handler(ctx=ctx, uow=uow, version_id=version_id, workspace=str(ws))

    raw_grid = json.loads(grid_path.read_text())
    beatgrid_entries: dict[int, BeatgridEntry] = {}
    for g in raw_grid:
        beatgrid_entries[g["track_id"]] = BeatgridEntry(
            track_id=g["track_id"],
            trim_start_s=g["trim_start_s"],
            refined_trim_s=g.get("refined_trim_s"),
            gain_db=g.get("gain_db", 0.0),
            phase_ms=g.get("phase_ms", 0.0),
        )

    rs = get_settings().render
    plan = build_render_plan(
        inputs, beatgrid_entries,
        target_bpm=rs.target_bpm, body_bars=rs.body_bars,
        transition_bars=rs.transition_bars, xsplit_hz=rs.xsplit_hz,
        low_swap_bars=rs.low_swap_bars, outro_fade_bars=rs.outro_fade_bars,
        limiter_ceiling=rs.limiter_ceiling,
    )

    manifest = build_verify_manifest(inputs, plan, beatgrid_entries)

    src_measures: dict[int, Any] = {}
    for src in manifest.sources:
        src_measures[src.track_id] = measure_source(
            src.file_path, bpm_hint=src.bpm,
        )

    out_measure = None
    if not skip_post:
        mix_path = str(ws / "MIX.mp3")
        bounds = segment_boundaries(
            manifest.segment_start_s,
            manifest.segment_lengths_s,
            manifest.expected_duration_s,
        )
        out_measure = measure_output(mix_path, bounds)

    results = run_checks(manifest, src_measures, out_measure, cfg, skip_post=skip_post)
    report = VerifyReport(results)

    result = RenderVerifyResult(
        version_id=version_id,
        passed=report.counts.get("PASS", 0),
        warned=report.counts.get("WARN", 0),
        failed=report.counts.get("FAIL", 0),
        exit_code=report.exit_code,
        summary=report.to_text(),
        results=[{"name": r.name, "status": r.status.value, "message": r.message, "detail": r.detail} for r in results],
    )

    if ctx is not None:
        await safe_info(ctx, f"render_verify: {result.passed}P {result.warned}W {result.failed}F")
    return result
```

- [ ] **Step 3: Create tool**

```python
# app/tools/render/render_verify.py
"""render_verify — DJ-adapted mix verification tool."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_verify import render_verify_handler
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow


@tool(
    name="render_verify",
    tags={"namespace:render", "render"},
    description=(
        "Run DJ-adapted mix verification on a set version: pre-render checks "
        "(source file integrity, BPM, trim bounds, timeline) and post-render "
        "checks (clipping, dropouts, LUFS consistency, stereo, low-band holes, "
        "BPM stability, kick consistency, energy range). Returns PASS/WARN/FAIL "
        "per check with measured values and thresholds."
    ),
)
async def render_verify(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    skip_post: Annotated[
        bool, Field(description="Only run pre-render checks (no MIX.mp3 needed)")
    ] = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> dict:
    result = await render_verify_handler(
        ctx=ctx, uow=uow, version_id=version_id, skip_post=skip_post
    )
    return result.model_dump()
```

- [ ] **Step 4: Run all verify tests**

```bash
uv run pytest tests/audio/render/verify/ tests/handlers/test_render_verify.py -v --timeout=30
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add render_verify handler + tool"
```

---

### Task 6: Update docs (golden script + tool catalog)

**Files:**
- Modify: `generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py`
- Modify: `docs/render-pipeline.md`

- [ ] **Step 1: Add superseded notice to golden script header**

Add after line 5 in `render_pipeline.py`:
```python
# NOTE 2026-07-08: This script is superseded by the MCP tools render_beatgrid,
# render_mixdown, render_diagnose, render_verify, and deliver_set. The golden
# numbers and algorithm reference are kept here as the source of truth for the
# ported implementation. For new sets use the MCP tools.
```

- [ ] **Step 2: Update `docs/render-pipeline.md` with verify + deliver**

Add sections:
- `render_verify` — DJ-adapted mix verification (14 checks), pre/post render
- `deliver_set` — bundle tracks, M3U8, rekordbox XML, MIX.mp3
- References to new config toggles

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: mark golden script superseded, update render-pipeline.md"
```

---

### Task 7: `make check` — verify everything passes

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v --timeout=60 -x
```
Expected: all tests pass.

- [ ] **Step 2: Run lint + typecheck**

```bash
uv run ruff check app/ tests/
uv run pyright app/
```
Expected: exit 0.

- [ ] **Step 3: Run arch-linter checks**

```bash
uv run lint-imports
```
Expected: exit 0.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: finalize render stabilization — lint + test pass"
```
