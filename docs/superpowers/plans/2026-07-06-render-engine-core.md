# Render Engine Core — Implementation Plan (1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the hardcoded `generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py` into a generic, set-version-driven render engine that lives inside the project's bounded contexts (`app/config`, `app/domain/render`, `app/audio/render`, `app/repositories`, `app/schemas`, `app/handlers`) — callable and testable, with NO MCP surface yet (that is Plan 2) and NO Prefab UI yet (Plan 3).

**Architecture:** Pure math (timeline, ffmpeg filter-graph string, LUFS→gain) in `app/domain/render/` (no IO). Side-effect DSP (librosa kick detect, phase refine, ffmpeg subprocess, diagnostics) in `app/audio/render/` (imported only by handlers). A batch DB query (`SetVersionRepository.get_render_inputs`) replaces the script's hardcoded `TRACKS`/`DB_LUFS`. Three handlers orchestrate DB→engine→workspace files + an in-process `RenderJobRegistry` for progress.

**Tech Stack:** Python 3.12, FastMCP v3, SQLAlchemy 2.0 async, Pydantic v2, librosa/scipy/soundfile (`[audio]` extra), ffmpeg+librubberband (external), pytest + in-memory SQLite.

**Reference (source of truth for the numbers):** `generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py` — do NOT delete it; the golden tests assert against its exact math.

**Branch:** `feat/render-mcp-surface` (already created).

---

## File Structure

**Create:**
- `app/config/render.py` — `RenderSettings` (target BPM, bars, XSPLIT, limiter).
- `app/domain/render/__init__.py` — public re-exports.
- `app/domain/render/models.py` — `TrackInput`, `TrackSegment`, `RenderPlan`, `BeatgridEntry` dataclasses.
- `app/domain/render/timeline.py` — segment/overlap math + `build_render_plan`.
- `app/domain/render/levels.py` — `gain_to_median` LUFS math.
- `app/domain/render/graph.py` — ffmpeg `filter_complex` string builder.
- `app/audio/render/__init__.py`
- `app/audio/render/kick_phase.py` — kick-grid detection.
- `app/audio/render/phase_refine.py` — sub-beat phase refine + flags.
- `app/audio/render/runner.py` — ffmpeg command assembly + subprocess run.
- `app/audio/render/diagnostics.py` — `scan` + `diagnose`.
- `app/schemas/render.py` — result models.
- `app/handlers/_render_registry.py` — in-process `RenderJobRegistry`.
- `app/handlers/render_beatgrid.py`, `app/handlers/render_mixdown.py`, `app/handlers/render_diagnose.py`.
- Tests mirroring each under `tests/`.

**Modify:**
- `app/config/__init__.py` — register `RenderSettings` on the `Settings` aggregate.
- `app/repositories/set.py` — add `SetVersionRepository.get_render_inputs`.
- `.importlinter` — add a contract keeping `app.domain.render` pure.

---

## Task 1: RenderSettings config

**Files:**
- Create: `app/config/render.py`
- Modify: `app/config/__init__.py`
- Test: `tests/config/test_render_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/config/test_render_settings.py
from app.config import get_settings, reset_settings_cache
from app.config.render import RenderSettings

def test_render_settings_defaults():
    s = RenderSettings()
    assert s.target_bpm == 130.0
    assert s.transition_bars == 32
    assert s.body_bars == 24
    assert s.xsplit_hz == 180
    assert s.low_swap_bars == 2
    assert s.outro_fade_bars == 12
    assert s.limiter_ceiling == 0.85
    # beat/bar helpers
    assert round(s.beat_s, 4) == 0.4615
    assert round(s.bar_s, 4) == 1.8462

def test_render_settings_on_aggregate():
    reset_settings_cache()
    assert get_settings().render.target_bpm == 130.0

def test_render_env_override(monkeypatch):
    monkeypatch.setenv("DJ_RENDER_TARGET_BPM", "128")
    assert RenderSettings().target_bpm == 128.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_render_settings.py -v`
Expected: FAIL (`ModuleNotFoundError: app.config.render`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/config/render.py
"""Render pipeline settings (beatmatch + EQ bass-swap mixdown)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class RenderSettings(BaseSettings):
    """Musical + DSP constants for the render engine.

    Removes the magic numbers that were inline in
    ``generated-sets/hypnotic-roller-90-FINAL/render_pipeline.py``.
    """

    model_config = SettingsConfigDict(
        env_prefix="DJ_RENDER_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    target_bpm: float = Field(default=130.0, gt=0, description="All tracks stretched to this.")
    transition_bars: int = Field(default=32, gt=0, description="Overlap length between tracks.")
    body_bars: int = Field(default=24, gt=0, description="Solo time per track between blends.")
    xsplit_hz: int = Field(default=180, gt=0, description="Low/high crossover for the bass swap.")
    low_swap_bars: int = Field(default=2, gt=0, description="Low-band crossfade window (bars).")
    outro_fade_bars: int = Field(default=12, gt=0, description="End-of-mix fade length (bars).")
    limiter_ceiling: float = Field(
        default=0.85, gt=0, le=1.0, description="alimiter limit (-1.4 dBFS headroom)."
    )
    workspace_subdir: str = Field(
        default="render", description="Subdir under DeliverySettings.output_dir for job files."
    )

    @property
    def beat_s(self) -> float:
        """One beat in seconds at the target tempo."""
        return 60.0 / self.target_bpm

    @property
    def bar_s(self) -> float:
        """One 4/4 bar in seconds."""
        return 4.0 * self.beat_s
```

Then register it on the aggregate. In `app/config/__init__.py`:

Add import next to the others:
```python
from app.config.render import RenderSettings
```
Add `"RenderSettings"` to `__all__`.
Add the field to the `Settings` dataclass body (after `mcp: MCPSettings`):
```python
    render: RenderSettings
```
Add to `__init__`:
```python
        object.__setattr__(self, "render", RenderSettings())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_render_settings.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/config/render.py app/config/__init__.py tests/config/test_render_settings.py
git commit -m "feat(render): add RenderSettings config"
```

---

## Task 2: domain/render models + import-linter contract

**Files:**
- Create: `app/domain/render/__init__.py`, `app/domain/render/models.py`
- Modify: `.importlinter`
- Test: `tests/domain/render/test_models.py`, `tests/domain/render/__init__.py` (empty)

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/render/test_models.py
from app.domain.render.models import BeatgridEntry, RenderPlan, TrackInput, TrackSegment

def test_track_input_roundtrip():
    ti = TrackInput(
        track_id=5435, yandex_id=49353955, title="Edit Select - Vault 2015",
        bpm=130.0, key_code=13, mix_in_ms=0, integrated_lufs=-12.33,
        file_path="/tmp/dj_audio/01 - x [49353955].mp3",
    )
    assert ti.tempo_ratio(130.0) == 1.0

def test_beatgrid_entry_effective_trim():
    e = BeatgridEntry(track_id=1, trim_start_s=0.4, refined_trim_s=0.42, gain_db=1.5, phase_ms=20.0)
    assert e.effective_trim == 0.42
    e2 = BeatgridEntry(track_id=1, trim_start_s=0.4, refined_trim_s=None, gain_db=0.0, phase_ms=0.0)
    assert e2.effective_trim == 0.4

def test_render_plan_holds_segments():
    seg = TrackSegment(index=0, track_id=1, file_path="/x.mp3", tempo_ratio=1.0,
                       trim_start_s=0.4, gain_db=0.0, body_bars=24,
                       d_in_s=0.0, d_out_s=59.0, length_s=103.0, start_s=0.0)
    plan = RenderPlan(target_bpm=130.0, xsplit_hz=180, low_swap_bars=2,
                      outro_fade_bars=12, limiter_ceiling=0.85, segments=[seg])
    assert plan.segments[0].index == 0
    assert plan.n == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: app.domain.render`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/domain/render/__init__.py
"""Pure render-plan compute (no IO). See docs/render-pipeline.md."""

from app.domain.render.models import (
    BeatgridEntry,
    RenderPlan,
    TrackInput,
    TrackSegment,
)

__all__ = ["BeatgridEntry", "RenderPlan", "TrackInput", "TrackSegment"]
```

```python
# app/domain/render/models.py
"""Pure dataclasses for the render engine — no IO, no librosa, no ffmpeg."""

from __future__ import annotations

from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class TrackInput:
    """One set-version track as the engine needs it (pulled from the DB)."""

    track_id: int
    yandex_id: int | None
    title: str
    bpm: float
    key_code: int | None
    mix_in_ms: int
    integrated_lufs: float | None
    file_path: str

    def tempo_ratio(self, target_bpm: float) -> float:
        """Stretch ratio to reach ``target_bpm`` (>1 speeds a slow track up)."""
        return target_bpm / self.bpm

@dataclass(frozen=True, slots=True)
class BeatgridEntry:
    """Per-track kick anchor + QA corrections (the beatgrid.json row)."""

    track_id: int
    trim_start_s: float
    refined_trim_s: float | None
    gain_db: float
    phase_ms: float

    @property
    def effective_trim(self) -> float:
        """Refined kick trim when QA ran, else the raw kick anchor."""
        return self.refined_trim_s if self.refined_trim_s is not None else self.trim_start_s

@dataclass(frozen=True, slots=True)
class TrackSegment:
    """A track placed on the mix timeline (stretched, kick-aligned)."""

    index: int
    track_id: int
    file_path: str
    tempo_ratio: float
    trim_start_s: float
    gain_db: float
    body_bars: int
    d_in_s: float
    d_out_s: float
    length_s: float
    start_s: float

@dataclass(frozen=True, slots=True)
class RenderPlan:
    """A fully-resolved render: ordered segments + DSP constants."""

    target_bpm: float
    xsplit_hz: int
    low_swap_bars: int
    outro_fade_bars: int
    limiter_ceiling: float
    segments: list[TrackSegment] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.segments)
```

Add the import-linter contract in `.importlinter` (append):
```ini
# ── Contract: domain.render stays pure (no IO) ──────────────────────
[importlinter:contract:v2-render-domain-pure]
name = app.domain.render must not import audio, DB, providers, handlers, tools, or server
type = forbidden
source_modules =
    app.domain.render
forbidden_modules =
    app.audio
    app.db
    app.repositories
    app.providers
    app.handlers
    app.tools
    app.server
    librosa
    scipy
    soundfile
```

- [ ] **Step 4: Run test + arch check**

Run: `uv run pytest tests/domain/render/test_models.py -v && uv run lint-imports`
Expected: tests PASS; import-linter reports the new contract KEPT.
(If `lint-imports` isn't the alias, use `uv run python -m importlinter.cli lint` or `make arch`.)

- [ ] **Step 5: Commit**

```bash
git add app/domain/render/ tests/domain/render/ .importlinter
git commit -m "feat(render): pure render-plan dataclasses + arch contract"
```

---

## Task 3: domain/render timeline math

Ports `_segment_sequence`, `_transition_bars`, and the `T += L - d_out` loop from `render_pipeline.py` into a pure `build_render_plan`, plus a `timeline_windows` helper (from `boundaries()`).

**Files:**
- Create: `app/domain/render/timeline.py`
- Test: `tests/domain/render/test_timeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/render/test_timeline.py
from app.domain.render.models import BeatgridEntry, TrackInput
from app.domain.render.timeline import build_render_plan, timeline_windows

# Two identical 130-BPM tracks, 24-bar bodies, 32-bar transitions.
BAR = 4 * (60.0 / 130.0)

def _inputs(n):
    return [
        TrackInput(track_id=i, yandex_id=i, title=f"t{i}", bpm=130.0, key_code=None,
                   mix_in_ms=0, integrated_lufs=-12.0, file_path=f"/x{i}.mp3")
        for i in range(n)
    ]

def _grid(n):
    return {i: BeatgridEntry(track_id=i, trim_start_s=0.0, refined_trim_s=0.0,
                             gain_db=0.0, phase_ms=0.0) for i in range(n)}

def test_single_segment_no_transitions():
    plan = build_render_plan(_inputs(1), _grid(1), target_bpm=130.0, body_bars=24,
                             transition_bars=32, xsplit_hz=180, low_swap_bars=2,
                             outro_fade_bars=12, limiter_ceiling=0.85)
    seg = plan.segments[0]
    assert seg.d_in_s == 0.0 and seg.d_out_s == 0.0
    assert round(seg.length_s, 4) == round(24 * BAR, 4)
    assert seg.start_s == 0.0

def test_two_segments_overlap():
    plan = build_render_plan(_inputs(2), _grid(2), target_bpm=130.0, body_bars=24,
                             transition_bars=32, xsplit_hz=180, low_swap_bars=2,
                             outro_fade_bars=12, limiter_ceiling=0.85)
    s0, s1 = plan.segments
    # middle-of-nothing: first segment has no incoming, has outgoing 32 bars
    assert s0.d_in_s == 0.0
    assert round(s0.d_out_s, 4) == round(32 * BAR, 4)
    assert round(s0.length_s, 4) == round((24 + 32) * BAR, 4)
    # second starts (s0.length - d_out) earlier = at body-only offset
    assert round(s1.start_s, 4) == round(s0.length_s - s0.d_out_s, 4)
    assert round(s1.start_s, 4) == round(24 * BAR, 4)

def test_timeline_windows_reports_transitions():
    wins = timeline_windows(_inputs(3), target_bpm=130.0, body_bars=24, transition_bars=32)
    # 3 tracks => 2 transition windows
    assert len(wins.transitions) == 2
    assert wins.transitions[0].from_index == 0 and wins.transitions[0].to_index == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_timeline.py -v`
Expected: FAIL (`ModuleNotFoundError: app.domain.render.timeline`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/domain/render/timeline.py
"""Pure timeline math: place stretched, kick-aligned segments on one line.

Ported verbatim (numbers-preserving) from render_pipeline.py:
``_segment_sequence`` + the ``render`` overlap loop + ``boundaries``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.render.models import BeatgridEntry, RenderPlan, TrackInput, TrackSegment

@dataclass(frozen=True, slots=True)
class TransitionWindow:
    from_index: int
    to_index: int
    start_s: float
    end_s: float

@dataclass(frozen=True, slots=True)
class TimelineWindows:
    segments: list[tuple[int, float, float]] = field(default_factory=list)  # (index, start, end)
    transitions: list[TransitionWindow] = field(default_factory=list)

def _durations(n: int, transition_bars: int, bar_s: float) -> list[float]:
    """Per-transition length D_i (seconds) between segment i and i+1."""
    return [transition_bars * bar_s for _ in range(n - 1)]

def build_render_plan(
    inputs: list[TrackInput],
    grid: dict[int, BeatgridEntry],
    *,
    target_bpm: float,
    body_bars: int,
    transition_bars: int,
    xsplit_hz: int,
    low_swap_bars: int,
    outro_fade_bars: int,
    limiter_ceiling: float,
) -> RenderPlan:
    """Resolve ordered inputs + beatgrid into a RenderPlan of placed segments."""
    bar_s = 4.0 * (60.0 / target_bpm)
    n = len(inputs)
    d = _durations(n, transition_bars, bar_s)
    segments: list[TrackSegment] = []
    running_t = 0.0
    for i, ti in enumerate(inputs):
        d_in = d[i - 1] if i > 0 else 0.0
        d_out = d[i] if i < n - 1 else 0.0
        length = body_bars * bar_s + d_in + d_out
        g = grid.get(ti.track_id)
        trim = g.effective_trim if g is not None else 0.0
        gain = g.gain_db if g is not None else 0.0
        segments.append(
            TrackSegment(
                index=i, track_id=ti.track_id, file_path=ti.file_path,
                tempo_ratio=ti.tempo_ratio(target_bpm), trim_start_s=trim,
                gain_db=gain, body_bars=body_bars, d_in_s=d_in, d_out_s=d_out,
                length_s=length, start_s=running_t,
            )
        )
        running_t += length - d_out
    return RenderPlan(
        target_bpm=target_bpm, xsplit_hz=xsplit_hz, low_swap_bars=low_swap_bars,
        outro_fade_bars=outro_fade_bars, limiter_ceiling=limiter_ceiling, segments=segments,
    )

def timeline_windows(
    inputs: list[TrackInput], *, target_bpm: float, body_bars: int, transition_bars: int
) -> TimelineWindows:
    """Map segments + transition windows onto the timeline (from ``boundaries``)."""
    bar_s = 4.0 * (60.0 / target_bpm)
    n = len(inputs)
    d = _durations(n, transition_bars, bar_s)
    segs: list[tuple[int, float, float]] = []
    trans: list[TransitionWindow] = []
    running_t = 0.0
    starts: list[tuple[float, float]] = []  # (start, d_in)
    for i in range(n):
        d_in = d[i - 1] if i > 0 else 0.0
        d_out = d[i] if i < n - 1 else 0.0
        length = body_bars * bar_s + d_in + d_out
        segs.append((i, running_t, running_t + length))
        starts.append((running_t, d_in))
        running_t += length - d_out
    for i in range(1, n):
        start, d_in = starts[i]
        trans.append(TransitionWindow(from_index=i - 1, to_index=i,
                                      start_s=start, end_s=start + d_in))
    return TimelineWindows(segments=segs, transitions=trans)
```

Re-export in `app/domain/render/__init__.py`: add `build_render_plan`, `timeline_windows`, `TimelineWindows`, `TransitionWindow` to imports + `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/render/test_timeline.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/domain/render/timeline.py app/domain/render/__init__.py tests/domain/render/test_timeline.py
git commit -m "feat(render): pure timeline + transition-window math"
```

---

## Task 4: domain/render levels (LUFS → gain)

Ports the `qa()` level block: gain each track toward the median LUFS, clamped ±4 dB.

**Files:**
- Create: `app/domain/render/levels.py`
- Test: `tests/domain/render/test_levels.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/render/test_levels.py
from app.domain.render.levels import gains_to_median

def test_gain_toward_median():
    lufs = {1: -12.0, 2: -10.0, 3: -14.0}  # median -12
    g = gains_to_median(lufs)
    assert g[1] == 0.0
    assert g[2] == -2.0  # louder track pulled down
    assert g[3] == 2.0   # quieter track pushed up

def test_gain_clamped_to_4db():
    lufs = {1: -12.0, 2: -30.0}  # median -21 -> track1 gain -9 clamps to -4
    g = gains_to_median(lufs)
    assert g[1] == -4.0
    assert g[2] == 4.0

def test_missing_lufs_zero_gain():
    g = gains_to_median({1: None, 2: -12.0})
    assert g[1] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_levels.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/domain/render/levels.py
"""Per-track loudness match: gain toward the median integrated LUFS.

Full-track integrated LUFS is far more reliable than a short-chunk RMS
(the script's note: measuring an intro chunk mis-fired). Clamp ±4 dB.
"""

from __future__ import annotations

from statistics import median

_CLAMP_DB = 4.0

def gains_to_median(lufs_by_track: dict[int, float | None]) -> dict[int, float]:
    """Return per-track gain (dB, clamped ±4) that moves each toward the median.

    Tracks with a missing (None) LUFS get 0.0 gain. The median is taken over
    the tracks that DO have a LUFS value.
    """
    known = [v for v in lufs_by_track.values() if v is not None]
    if not known:
        return {tid: 0.0 for tid in lufs_by_track}
    med = float(median(known))
    out: dict[int, float] = {}
    for tid, v in lufs_by_track.items():
        if v is None:
            out[tid] = 0.0
            continue
        out[tid] = round(max(-_CLAMP_DB, min(_CLAMP_DB, med - v)), 2)
    return out
```

Re-export `gains_to_median` in `app/domain/render/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/render/test_levels.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/domain/render/levels.py app/domain/render/__init__.py tests/domain/render/test_levels.py
git commit -m "feat(render): LUFS-to-median gain math"
```

---

## Task 5: domain/render ffmpeg filter-graph builder (golden)

Ports the `render()` `filter_complex` assembly into a pure string builder. This is the highest-value pure test: a golden snapshot pins the exact filtergraph.

**Files:**
- Create: `app/domain/render/graph.py`
- Test: `tests/domain/render/test_graph.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/render/test_graph.py
from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderPlan, TrackSegment

BAR = 4 * (60.0 / 130.0)

def _plan(n):
    segs = []
    t = 0.0
    d_trans = 32 * BAR
    for i in range(n):
        d_in = d_trans if i > 0 else 0.0
        d_out = d_trans if i < n - 1 else 0.0
        length = 24 * BAR + d_in + d_out
        segs.append(TrackSegment(index=i, track_id=i, file_path=f"/x{i}.mp3",
                                 tempo_ratio=1.0, trim_start_s=0.4, gain_db=0.0,
                                 body_bars=24, d_in_s=d_in, d_out_s=d_out,
                                 length_s=length, start_s=t))
        t += length - d_out
    return RenderPlan(target_bpm=130.0, xsplit_hz=180, low_swap_bars=2,
                      outro_fade_bars=12, limiter_ceiling=0.85, segments=segs)

def test_filtergraph_single_track_shape():
    parts = build_filtergraph(_plan(1))
    joined = ";".join(parts)
    # per-segment stages present
    assert "asplit=2[s0a][s0b]" in joined
    assert "lowpass=f=180[lo0]" in joined
    assert "highpass=f=180[hi0]" in joined
    # single track: no incoming/outgoing crossfade, but an outro fade of 12 bars
    assert "afade=t=out:curve=qsin" in joined
    # final limiter
    assert "alimiter=level_in=1:level_out=1:limit=0.85" in joined
    assert joined.endswith("[mix]")

def test_filtergraph_two_tracks_has_incoming_fade_and_delay():
    parts = build_filtergraph(_plan(2))
    joined = ";".join(parts)
    # second segment's high band fades IN over the incoming transition
    assert "[hi1]afade=t=in:curve=qsin:st=0" in joined
    # amix + adelay wiring for segment 1 (delayed to its slot)
    assert "adelay=" in joined
    assert "amix=inputs=2:normalize=0[mix]".split("[mix]")[0][:5] in joined  # amix present

def test_filtergraph_is_deterministic():
    assert build_filtergraph(_plan(3)) == build_filtergraph(_plan(3))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_graph.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

Port `render()`'s filter assembly exactly (same afade/lowpass/amix/adelay/alimiter). Note the per-input `atrim/rubberband/volume` "source" stage references `[{i}:a]` — that input index maps 1:1 to segment index (the runner passes `-i file` per segment in order).

```python
# app/domain/render/graph.py
"""Pure builder for the ffmpeg ``filter_complex`` graph.

Ported from render_pipeline.py ``render()`` — string assembly only, no IO.
Each segment i reads ffmpeg input ``[i:a]`` (the runner supplies ``-i`` per
segment, in order). Returns the list of graph statements; the runner joins
them with ';'.
"""

from __future__ import annotations

from app.domain.render.models import RenderPlan

def build_filtergraph(plan: RenderPlan) -> list[str]:
    n = plan.n
    xsplit = plan.xsplit_hz
    bar_s = 4.0 * (60.0 / plan.target_bpm)
    low_x = plan.low_swap_bars * bar_s
    parts: list[str] = []
    mixlabels: list[str] = []
    running_t = 0.0

    for seg in plan.segments:
        i = seg.index
        d_in = seg.d_in_s
        d_out = seg.d_out_s
        length = seg.length_s

        base = (
            f"[{i}:a]atrim=start={seg.trim_start_s:.4f}:"
            f"duration={length / seg.tempo_ratio + 1.0:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={seg.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={length:.3f},asetpts=PTS-STARTPTS,volume={seg.gain_db:.2f}dB,"
            f"aformat=sample_rates=44100:channel_layouts=stereo"
        )
        parts.append(f"{base}[s{i}]")

        parts.append(f"[s{i}]asplit=2[s{i}a][s{i}b]")
        parts.append(f"[s{i}a]lowpass=f={xsplit}[lo{i}]")
        parts.append(f"[s{i}b]highpass=f={xsplit}[hi{i}]")

        fd = min(plan.outro_fade_bars * bar_s, length)
        h: list[str] = []
        if i > 0:
            h.append(f"afade=t=in:curve=qsin:st=0:d={d_in:.3f}")
        if i < n - 1:
            h.append(f"afade=t=out:curve=qsin:st={length - d_out:.3f}:d={d_out:.3f}")
        else:
            h.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[hi{i}]{','.join(h) if h else 'acopy'}[H{i}]")

        lo: list[str] = []
        if i > 0:
            st = max(0.0, d_in / 2 - low_x / 2)
            lo.append(f"afade=t=in:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        if i < n - 1:
            st = length - d_out / 2 - low_x / 2
            lo.append(f"afade=t=out:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        else:
            lo.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[lo{i}]{','.join(lo) if lo else 'acopy'}[Lo{i}]")

        t_ms = int(running_t * 1000)
        parts.append(f"[H{i}][Lo{i}]amix=inputs=2:normalize=0,adelay={t_ms}|{t_ms}[m{i}]")
        mixlabels.append(f"[m{i}]")
        running_t += length - d_out

    parts.append(
        "".join(mixlabels) + f"amix=inputs={n}:normalize=0,"
        f"alimiter=level_in=1:level_out=1:limit={plan.limiter_ceiling}:"
        "attack=5:release=60:asc=1[mix]"
    )
    return parts
```

Re-export `build_filtergraph` in `app/domain/render/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/render/test_graph.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/domain/render/graph.py app/domain/render/__init__.py tests/domain/render/test_graph.py
git commit -m "feat(render): pure ffmpeg filter_complex builder"
```

---

## Task 6: SetVersionRepository.get_render_inputs

Replaces the script's hardcoded `TRACKS`/`DB_LUFS` with one batch query returning `TrackInput`-shaped rows (title, bpm, key_code, mix_in_ms, integrated_lufs, file_path).

**Files:**
- Modify: `app/repositories/set.py`
- Test: `tests/repositories/test_set_render_inputs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/repositories/test_set_render_inputs.py
import pytest

from app.models.audio_file import DjLibraryItem
from app.models.set import DjSet, DjSetItem, DjSetVersion
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.unit_of_work import UnitOfWork

@pytest.mark.asyncio
async def test_get_render_inputs_orders_and_joins(session):
    # seed parents first (FK on)
    t = Track(id=5435, title="Edit Select - Vault 2015")
    session.add(t)
    session.add(TrackAudioFeaturesComputed(track_id=5435, bpm=130.0, key_code=13,
                                           integrated_lufs=-12.33))
    session.add(DjLibraryItem(track_id=5435, file_path="/tmp/dj_audio/01 [49353955].mp3"))
    s = DjSet(id=1, name="S")
    session.add(s)
    v = DjSetVersion(id=131, set_id=1, label="v131")
    session.add(v)
    session.add(DjSetItem(version_id=131, track_id=5435, sort_index=0, mix_in_point_ms=0))
    await session.flush()

    uow = UnitOfWork(session)
    rows = await uow.set_versions.get_render_inputs(131)
    assert len(rows) == 1
    r = rows[0]
    assert r.track_id == 5435
    assert r.title == "Edit Select - Vault 2015"
    assert r.bpm == 130.0
    assert r.key_code == 13
    assert r.mix_in_ms == 0
    assert r.integrated_lufs == -12.33
    assert r.file_path.endswith("[49353955].mp3")

@pytest.mark.asyncio
async def test_get_render_inputs_missing_audio_raises(session):
    session.add(Track(id=9, title="No File"))
    session.add(TrackAudioFeaturesComputed(track_id=9, bpm=130.0, key_code=1,
                                           integrated_lufs=-11.0))
    session.add(DjSet(id=2, name="S2"))
    session.add(DjSetVersion(id=200, set_id=2, label="v"))
    session.add(DjSetItem(version_id=200, track_id=9, sort_index=0, mix_in_point_ms=0))
    await session.flush()
    uow = UnitOfWork(session)
    with pytest.raises(Exception) as exc:  # ValidationError from app.shared.errors
        await uow.set_versions.get_render_inputs(200)
    assert "audio_file" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/repositories/test_set_render_inputs.py -v`
Expected: FAIL (`AttributeError: 'SetVersionRepository' object has no attribute 'get_render_inputs'`).

- [ ] **Step 3: Write minimal implementation**

Add to `app/repositories/set.py` on `SetVersionRepository` (imports at top of file: `from sqlalchemy import select`; `from app.domain.render.models import TrackInput`; `from app.shared.errors import ValidationError`; the ORM models). `yandex_id` is parsed from the on-disk filename `... [YID].mp3` (best-effort; None when absent).

```python
    async def get_render_inputs(self, version_id: int) -> list[TrackInput]:
        """Ordered render inputs for a version: title/bpm/key/mix-in/LUFS/file.

        One batch query joining dj_set_items ⋈ tracks ⋈
        track_audio_features_computed ⋈ dj_library_items. Raises
        ValidationError when a track has no registered audio file (download
        first — mirrors the L5 finalization contract).
        """
        import re

        from app.models.audio_file import DjLibraryItem
        from app.models.set import DjSetItem
        from app.models.track import Track
        from app.models.track_features import TrackAudioFeaturesComputed

        stmt = (
            select(
                DjSetItem.track_id,
                DjSetItem.sort_index,
                DjSetItem.mix_in_point_ms,
                Track.title,
                TrackAudioFeaturesComputed.bpm,
                TrackAudioFeaturesComputed.key_code,
                TrackAudioFeaturesComputed.integrated_lufs,
                DjLibraryItem.file_path,
            )
            .join(Track, Track.id == DjSetItem.track_id)
            .join(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == DjSetItem.track_id,
                isouter=True,
            )
            .join(DjLibraryItem, DjLibraryItem.track_id == DjSetItem.track_id, isouter=True)
            .where(DjSetItem.version_id == version_id)
            .order_by(DjSetItem.sort_index)
        )
        result = await self.session.execute(stmt)
        out: list[TrackInput] = []
        for row in result.all():
            if row.file_path is None:
                raise ValidationError(
                    f"audio_file not found for track {row.track_id} in version "
                    f"{version_id} — download first via "
                    "entity_create(entity='audio_file', data={'track_ids': [...]})"
                )
            if row.bpm is None:
                raise ValidationError(
                    f"track {row.track_id} has no bpm feature — analyze first (level>=2)"
                )
            m = re.search(r"\[(\d+)\]", row.file_path)
            yandex_id = int(m.group(1)) if m else None
            out.append(
                TrackInput(
                    track_id=row.track_id,
                    yandex_id=yandex_id,
                    title=row.title,
                    bpm=float(row.bpm),
                    key_code=row.key_code,
                    mix_in_ms=int(row.mix_in_point_ms or 0),
                    integrated_lufs=row.integrated_lufs,
                    file_path=row.file_path,
                )
            )
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/repositories/test_set_render_inputs.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/repositories/set.py tests/repositories/test_set_render_inputs.py
git commit -m "feat(render): SetVersionRepository.get_render_inputs batch query"
```

---

## Task 7: audio/render kick-phase detection

Ports `analyze()`: low-pass to ~150 Hz, onset+beat track, first kick as the trim anchor.

**Files:**
- Create: `app/audio/render/__init__.py`, `app/audio/render/kick_phase.py`
- Test: `tests/audio/render/test_kick_phase.py`, `tests/audio/render/__init__.py` (empty)

- [ ] **Step 1: Write the failing test**

```python
# tests/audio/render/test_kick_phase.py
import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")

def _click_track(path, bpm=130, sr=22050, dur=24.0, first_kick_s=0.4):
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    beat = 60.0 / bpm
    t = first_kick_s
    while t < dur:
        i = int(t * sr)
        # 40ms low sine burst = a "kick"
        k = int(0.04 * sr)
        env = np.hanning(k)
        y[i:i + k] += (0.9 * env * np.sin(2 * np.pi * 55 * np.arange(k) / sr)).astype("float32")
        t += beat
    sf.write(path, y, sr)
    return path

def test_detect_first_kick(tmp_path):
    from app.audio.render.kick_phase import detect_kick_trim

    f = _click_track(str(tmp_path / "k.wav"), first_kick_s=0.4)
    trim = detect_kick_trim(f, start_s=0.0, bpm=130.0)
    assert 0.30 <= trim <= 0.55  # near the planted 0.4 s kick
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/audio/render/test_kick_phase.py -v`
Expected: FAIL (`ModuleNotFoundError: app.audio.render.kick_phase`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/audio/render/__init__.py
"""Side-effect render DSP (librosa/scipy/ffmpeg). Imported only by handlers."""
```

```python
# app/audio/render/kick_phase.py
"""Kick-grid detection for the render engine (ported from analyze()).

Low-pass to ~150 Hz to isolate the kick, run librosa onset+beat tracking on
that band, take the first detected kick as the phase anchor. We anchor on the
KICK (not any onset) because a melodic pickup before the downbeat would make
the beats not line up.
"""

from __future__ import annotations

_LP_HZ = 150
_SR = 22050

def detect_kick_trim(file_path: str, *, start_s: float, bpm: float) -> float:
    """Return the render trim (seconds into the FILE) where the first kick lands.

    ``start_s`` is the track's mix-in offset; the returned value is
    ``start_s + first_kick_offset`` so ``render`` starts exactly on a kick.
    """
    import librosa
    import numpy as np
    from scipy.signal import butter, sosfiltfilt

    sos = butter(4, _LP_HZ, btype="low", fs=_SR, output="sos")
    y, _ = librosa.load(file_path, sr=_SR, offset=start_s, duration=24.0, mono=True)
    low = sosfiltfilt(sos, y).astype(np.float32)
    env = librosa.onset.onset_strength(y=low, sr=_SR)
    _, beats = librosa.beat.beat_track(
        onset_envelope=env, sr=_SR, start_bpm=bpm, units="time", tightness=140
    )
    beats = np.asarray(beats, dtype=float)
    cand = beats[beats >= 0.03]
    first_kick = float(cand[0]) if len(cand) else 0.0
    return round(start_s + first_kick, 4)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/audio/render/test_kick_phase.py -v`
Expected: PASS (1 passed). (Requires the `[audio]` extra; if librosa absent the test skips.)

- [ ] **Step 5: Commit**

```bash
git add app/audio/render/__init__.py app/audio/render/kick_phase.py tests/audio/render/
git commit -m "feat(render): kick-phase detection (analyze port)"
```

---

## Task 8: audio/render phase refine + flags

Ports the `qa()` phase block: stretch a 24 s chunk to target BPM, cross-correlate the kick onset envelope against an ideal pulse comb, return the sub-beat delta (ms) and the refined trim. Combined with `gains_to_median` (Task 4) this yields the full beatgrid.

**Files:**
- Create: `app/audio/render/phase_refine.py`
- Test: `tests/audio/render/test_phase_refine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/audio/render/test_phase_refine.py
import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")

def _click_track(path, bpm=130, sr=22050, dur=26.0, first_kick_s=0.0):
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    beat = 60.0 / bpm
    t = first_kick_s
    while t < dur:
        i = int(t * sr)
        k = int(0.04 * sr)
        env = np.hanning(k)
        y[i:i + k] += (0.9 * env * np.sin(2 * np.pi * 55 * np.arange(k) / sr)).astype("float32")
        t += beat
    sf.write(path, y, sr)
    return path

def test_phase_delta_small_for_ongrid_track(tmp_path):
    from app.audio.render.phase_refine import refine_phase

    f = _click_track(str(tmp_path / "g.wav"), bpm=130, first_kick_s=0.0)
    delta_ms, refined = refine_phase(f, base_trim_s=0.0, bpm=130.0)
    assert abs(delta_ms) < 40.0            # already on grid -> tiny nudge
    assert abs(refined - 0.0) < 0.05
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/audio/render/test_phase_refine.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

Port `qa()`'s per-track phase block (uses ffmpeg rubberband to pre-stretch, then a pulse-comb search). Requires ffmpeg present; the test above uses an already-130 track so `tempo=1.0` still exercises the path.

```python
# app/audio/render/phase_refine.py
"""Sub-beat kick-phase refinement (ported from qa()).

Stretch a 24 s chunk to the target BPM, take the kick onset envelope, and
cross-correlate it with an ideal target-BPM pulse comb to find the exact
sub-beat offset, so every track's kicks land on the SAME grid.
"""

from __future__ import annotations

import os
import subprocess

_SR = 22050
_HOP = 512

def refine_phase(file_path: str, *, base_trim_s: float, bpm: float, target_bpm: float = 130.0) -> tuple[float, float]:
    """Return (phase_delta_ms, refined_trim_s) for one track.

    ``base_trim_s`` is the raw kick anchor from ``detect_kick_trim``.
    """
    import librosa
    import numpy as np
    from scipy.signal import butter, sosfiltfilt

    beat_s = 60.0 / target_bpm
    fpb = beat_s * _SR / _HOP  # onset-env frames per beat
    tempo = target_bpm / bpm
    sos = butter(4, 150, btype="low", fs=_SR, output="sos")

    tmp = f"/tmp/_qa_{abs(hash(file_path))}.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{base_trim_s}", "-t", f"{24 * bpm / target_bpm + 1:.1f}",
         "-i", file_path, "-af", f"rubberband=tempo={tempo:.5f}", "-ar", str(_SR),
         "-ac", "1", tmp],
        stderr=subprocess.DEVNULL, check=False,
    )
    try:
        y, _ = librosa.load(tmp, sr=_SR, mono=True, duration=24.0)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    low = sosfiltfilt(sos, y).astype(np.float32)
    env = librosa.onset.onset_strength(y=low, sr=_SR, hop_length=_HOP)
    best_s, best_phi = -1.0, 0
    for phi in range(round(fpb)):
        idx = np.round(phi + np.arange(0, len(env) - 1, fpb)).astype(int)
        idx = idx[idx < len(env)]
        s = float(env[idx].sum())
        if s > best_s:
            best_s, best_phi = s, phi
    phase_s = best_phi * _HOP / _SR
    delta = phase_s if phase_s <= beat_s / 2 else phase_s - beat_s
    return round(delta * 1000.0, 1), round(base_trim_s + delta, 4)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/audio/render/test_phase_refine.py -v`
Expected: PASS (1 passed; needs ffmpeg + librosa, else skip).

- [ ] **Step 5: Commit**

```bash
git add app/audio/render/phase_refine.py tests/audio/render/test_phase_refine.py
git commit -m "feat(render): sub-beat phase refine (qa port)"
```

---

## Task 9: audio/render ffmpeg runner

Assembles the `-i file` inputs (one per segment, in order) + the `filter_complex` (from `domain/render/graph.py`) and runs ffmpeg. Typed error on failure or missing ffmpeg.

**Files:**
- Create: `app/audio/render/runner.py`
- Test: `tests/audio/render/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/audio/render/test_runner.py
from app.audio.render.runner import build_ffmpeg_cmd
from app.domain.render.models import RenderPlan, TrackSegment

BAR = 4 * (60.0 / 130.0)

def _plan():
    segs = [TrackSegment(index=0, track_id=1, file_path="/a.mp3", tempo_ratio=1.0,
                         trim_start_s=0.4, gain_db=0.0, body_bars=24, d_in_s=0.0,
                         d_out_s=0.0, length_s=24 * BAR, start_s=0.0)]
    return RenderPlan(target_bpm=130.0, xsplit_hz=180, low_swap_bars=2,
                      outro_fade_bars=12, limiter_ceiling=0.85, segments=segs)

def test_cmd_has_one_input_per_segment_and_mapping():
    cmd = build_ffmpeg_cmd(_plan(), "/out.mp3")
    assert cmd[0] == "ffmpeg"
    assert cmd.count("-i") == 1
    assert "/a.mp3" in cmd
    assert "-filter_complex" in cmd
    assert cmd[-1] == "/out.mp3"
    assert "[mix]" in cmd  # -map [mix]
    assert "libmp3lame" in cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/audio/render/test_runner.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/audio/render/runner.py
"""Assemble + run the ffmpeg render command. Ported from render()."""

from __future__ import annotations

import shutil
import subprocess

from app.domain.render.graph import build_filtergraph
from app.domain.render.models import RenderPlan

def build_ffmpeg_cmd(plan: RenderPlan, out_path: str) -> list[str]:
    """One ``-i`` per segment (in index order) + the filtergraph + mp3 out."""
    inputs: list[str] = []
    for seg in plan.segments:
        inputs += ["-i", seg.file_path]
    graph = ";".join(build_filtergraph(plan))
    return [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", graph,
        "-map", "[mix]",
        "-c:a", "libmp3lame", "-b:a", "320k",
        out_path,
    ]

def run_render(plan: RenderPlan, out_path: str) -> None:
    """Run ffmpeg. Raises RuntimeError on missing binary or non-zero exit."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found — install ffmpeg built with librubberband "
            "(brew install ffmpeg)."
        )
    cmd = build_ffmpeg_cmd(plan, out_path)
    r = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        tail = (r.stderr or "")[-2000:]
        raise RuntimeError(f"ffmpeg render failed: {tail}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/audio/render/test_runner.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/audio/render/runner.py tests/audio/render/test_runner.py
git commit -m "feat(render): ffmpeg runner (command assembly + run)"
```

---

## Task 10: audio/render diagnostics (scan + diagnose)

Ports `scan()` (coarse whole-file) + `diagnose()` (per-4s sweep) into functions returning structured data (no printing).

**Files:**
- Create: `app/audio/render/diagnostics.py`
- Test: `tests/audio/render/test_diagnostics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/audio/render/test_diagnostics.py
import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")

def _mix_with_dropout(path, sr=22050, dur=40.0):
    n = int(sr * dur)
    y = (0.3 * np.random.RandomState(1).randn(n)).astype("float32")
    # inject a near-silent hole 20-24 s
    y[int(20 * sr):int(24 * sr)] *= 0.02
    sf.write(path, y, sr)
    return path

def test_scan_reports_peak_and_duration(tmp_path):
    from app.audio.render.diagnostics import scan_mix

    f = _mix_with_dropout(str(tmp_path / "m.wav"))
    rep = scan_mix(f)
    assert rep.duration_s >= 39
    assert rep.true_peak_db <= 0.0

def test_diagnose_flags_dropout(tmp_path):
    from app.audio.render.diagnostics import diagnose_mix

    f = _mix_with_dropout(str(tmp_path / "m.wav"))
    rep = diagnose_mix(f)
    tags = [t for w in rep.windows for t in w.tags]
    assert any("DROPOUT" in t for t in tags)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/audio/render/test_diagnostics.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

Port `scan()` + `diagnose()`, returning dataclasses instead of printing. (Keep the `volumedetect` true-peak and the per-4s librosa sweep logic verbatim.)

```python
# app/audio/render/diagnostics.py
"""Post-render defect analysis (ported from scan() + diagnose())."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_SR = 22050

@dataclass(frozen=True, slots=True)
class ScanReport:
    name: str
    duration_s: float
    true_peak_db: float
    clip_risk: bool
    level_jumps: list[tuple[int, float]] = field(default_factory=list)
    near_silent_s: list[int] = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class DiagWindow:
    offset_s: float
    rms_db: float
    low_db: float
    tags: list[str] = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class DiagnoseReport:
    name: str
    duration_s: float
    overall_rms_db: float
    windows: list[DiagWindow] = field(default_factory=list)
    flagged: int = 0

def scan_mix(path: str) -> ScanReport:
    import numpy as np

    tmp = "/tmp/_scan.f32"
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "8000", "-f", "f32le", tmp],
        stderr=subprocess.DEVNULL, check=False,
    )
    y = np.fromfile(tmp, dtype="<f4")
    sr = 8000
    win = sr
    rms = np.array([
        20 * np.log10(np.sqrt(np.mean(y[i:i + win] ** 2)) + 1e-9)
        for i in range(0, len(y) - win, win)
    ])
    vd = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "volumedetect",
         "-f", "null", "-"],
        stderr=subprocess.PIPE, text=True, check=False,
    ).stderr
    peak_db = 0.0
    for line in vd.splitlines():
        if "max_volume" in line:
            peak_db = float(line.split("max_volume:")[1].split("dB")[0])
    jumps = [(i, float(rms[i + 1] - rms[i])) for i in range(len(rms) - 1)
             if abs(rms[i + 1] - rms[i]) > 6.0]
    sil = [i for i in range(len(rms)) if rms[i] < -45]
    return ScanReport(
        name=Path(path).name, duration_s=len(y) / sr, true_peak_db=peak_db,
        clip_risk=peak_db >= -0.1, level_jumps=jumps, near_silent_s=sil,
    )

def diagnose_mix(path: str) -> DiagnoseReport:
    import librosa
    import numpy as np
    from scipy.signal import butter, sosfiltfilt

    win, sr = 4.0, _SR
    losos = butter(4, 150, btype="low", fs=sr, output="sos")
    dur = librosa.get_duration(path=path)
    rows = []
    for i in range(int((dur - win) // win)):
        off = i * win
        y, _ = librosa.load(path, sr=sr, offset=off, duration=win, mono=True)
        rms = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9)
        low = sosfiltfilt(losos, y).astype(np.float32)
        lo_rms = 20 * np.log10(np.sqrt(np.mean(low ** 2)) + 1e-9)
        rows.append((off, float(rms), float(lo_rms)))

    rms_arr = np.array([r[1] for r in rows]) if rows else np.array([0.0])
    mean = float(rms_arr.mean())
    windows: list[DiagWindow] = []
    flagged = 0
    for i, (off, r, lo) in enumerate(rows):
        tags: list[str] = []
        if i > 0 and abs(r - rows[i - 1][1]) > 5:
            tags.append(f"LEVEL-JUMP {r - rows[i - 1][1]:+.0f}dB")
        if r < mean - 7:
            tags.append(f"DROPOUT {r:.0f}dB")
        if lo < r - 22:
            tags.append("bass-thin")
        if tags:
            flagged += 1
        windows.append(DiagWindow(offset_s=off, rms_db=r, low_db=lo, tags=tags))
    return DiagnoseReport(name=Path(path).name, duration_s=dur,
                          overall_rms_db=mean, windows=windows, flagged=flagged)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/audio/render/test_diagnostics.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/audio/render/diagnostics.py tests/audio/render/test_diagnostics.py
git commit -m "feat(render): scan + diagnose defect analysis"
```

---

## Task 11: RenderJobRegistry (in-process progress)

**Files:**
- Create: `app/handlers/_render_registry.py`
- Test: `tests/handlers/test_render_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/handlers/test_render_registry.py
from app.handlers._render_registry import RENDER_JOBS, RenderJob

def test_register_update_read():
    RENDER_JOBS.clear()
    job = RENDER_JOBS.start(job_id="v131-abc", version_id=131, phase="beatgrid")
    assert isinstance(job, RenderJob)
    RENDER_JOBS.update("v131-abc", phase="mixdown", progress=3, total=15, message="track 3")
    got = RENDER_JOBS.get("v131-abc")
    assert got.phase == "mixdown"
    assert got.progress == 3 and got.total == 15
    assert got.message == "track 3"

def test_get_unknown_returns_none():
    RENDER_JOBS.clear()
    assert RENDER_JOBS.get("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/handlers/test_render_registry.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/handlers/_render_registry.py
"""In-process render-job status registry.

The Prefab studio (Plan 3) and the ``local://render/jobs/{id}/status``
resource (Plan 2) read this so live status works independent of whether the
host supports the MCP task protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

@dataclass
class RenderJob:
    job_id: str
    version_id: int
    phase: str = "pending"
    progress: int = 0
    total: int = 0
    message: str = ""
    out_path: str | None = None
    error: str | None = None
    done: bool = False

class RenderJobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, RenderJob] = {}
        self._lock = Lock()

    def start(self, *, job_id: str, version_id: int, phase: str = "pending") -> RenderJob:
        with self._lock:
            job = RenderJob(job_id=job_id, version_id=version_id, phase=phase)
            self._jobs[job_id] = job
            return job

    def update(self, job_id: str, **fields: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for k, v in fields.items():
                setattr(job, k, v)

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()

RENDER_JOBS = RenderJobRegistry()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/handlers/test_render_registry.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/handlers/_render_registry.py tests/handlers/test_render_registry.py
git commit -m "feat(render): in-process RenderJobRegistry"
```

---

## Task 12: render result schemas

**Files:**
- Create: `app/schemas/render.py`
- Test: `tests/schemas/test_render_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/schemas/test_render_schemas.py
from app.schemas.render import (
    RenderBeatgridResult,
    RenderDiagnosticsResult,
    RenderMixdownResult,
)

def test_beatgrid_result_shape():
    r = RenderBeatgridResult(version_id=131, tracks=[
        {"track_id": 1, "trim_start_s": 0.4, "refined_trim_s": 0.42,
         "gain_db": 1.5, "phase_ms": 20.0, "flags": ["fixed"]},
    ])
    assert r.version_id == 131 and r.tracks[0]["track_id"] == 1

def test_mixdown_result_shape():
    r = RenderMixdownResult(job_id="v131-abc", version_id=131,
                            out_path="/x/MIX.mp3", duration_s=5400.0,
                            true_peak_db=-1.4, level_jumps=0, near_silent_s=0)
    assert r.out_path.endswith("MIX.mp3")

def test_diagnostics_result_shape():
    r = RenderDiagnosticsResult(job_id="v131-abc", overall_rms_db=-11.0,
                                flagged=2, windows=[{"offset_s": 20.0, "tags": ["DROPOUT -30dB"]}])
    assert r.flagged == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/schemas/test_render_schemas.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/schemas/render.py
"""Structured-output models for the render tools (Plan 2 surface)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class RenderBeatgridResult(BaseModel):
    version_id: int
    tracks: list[dict[str, Any]] = Field(default_factory=list)

class RenderMixdownResult(BaseModel):
    job_id: str
    version_id: int
    out_path: str
    duration_s: float
    true_peak_db: float | None = None
    level_jumps: int = 0
    near_silent_s: int = 0

class RenderDiagnosticsResult(BaseModel):
    job_id: str
    overall_rms_db: float
    flagged: int = 0
    windows: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/schemas/test_render_schemas.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/render.py tests/schemas/test_render_schemas.py
git commit -m "feat(render): result schemas for render tools"
```

---

## Task 13: render_beatgrid handler

Orchestrates: pull inputs → detect kick trim → refine phase → gains → write `beatgrid.json` → result. Uses `RENDER_JOBS` + `safe_report_progress`. Audio DSP is injected so the handler can be unit-tested without librosa.

**Files:**
- Create: `app/handlers/render_beatgrid.py`
- Test: `tests/handlers/test_render_beatgrid.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/handlers/test_render_beatgrid.py
import json

import pytest

from app.handlers.render_beatgrid import render_beatgrid_handler
from app.domain.render.models import TrackInput

class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs
        self.set_versions = _SV()

@pytest.mark.asyncio
async def test_beatgrid_writes_file_and_result(tmp_path, monkeypatch):
    inputs = [TrackInput(track_id=1, yandex_id=9, title="t1", bpm=130.0, key_code=1,
                         mix_in_ms=0, integrated_lufs=-12.0, file_path="/a.mp3"),
              TrackInput(track_id=2, yandex_id=8, title="t2", bpm=130.0, key_code=1,
                         mix_in_ms=0, integrated_lufs=-10.0, file_path="/b.mp3")]
    # stub the DSP so no librosa/ffmpeg needed
    monkeypatch.setattr("app.handlers.render_beatgrid.detect_kick_trim",
                        lambda f, start_s, bpm: 0.4)
    monkeypatch.setattr("app.handlers.render_beatgrid.refine_phase",
                        lambda f, base_trim_s, bpm: (10.0, 0.41))

    res = await render_beatgrid_handler(
        ctx=None, uow=_StubUow(inputs), version_id=131,
        workspace=str(tmp_path), refresh=True,
    )
    assert res.version_id == 131
    assert len(res.tracks) == 2
    grid = json.loads((tmp_path / "beatgrid.json").read_text())
    assert grid[0]["refined_trim_s"] == 0.41
    # median LUFS of (-12,-10) is -11 -> track1 gain +1, track2 gain -1
    g = {r["track_id"]: r["gain_db"] for r in res.tracks}
    assert g[1] == 1.0 and g[2] == -1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/handlers/test_render_beatgrid.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/handlers/render_beatgrid.py
"""Handler: compute the beatgrid (kick trim + phase refine + LUFS gain).

DSP functions are module-level so tests can monkeypatch them without
importing librosa/ffmpeg.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
from app.domain.render.levels import gains_to_median
from app.handlers._context_log import safe_info, safe_report_progress
from app.schemas.render import RenderBeatgridResult

async def render_beatgrid_handler(
    *, ctx: Any, uow: Any, version_id: int, workspace: str, refresh: bool = False
) -> RenderBeatgridResult:
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    grid_path = ws / "beatgrid.json"

    inputs = await uow.set_versions.get_render_inputs(version_id)
    gains = gains_to_median({ti.track_id: ti.integrated_lufs for ti in inputs})

    if grid_path.exists() and not refresh:
        rows = json.loads(grid_path.read_text())
        return RenderBeatgridResult(version_id=version_id, tracks=rows)

    safe_info(ctx, "render_beatgrid: %d tracks for version %s", len(inputs), version_id)
    rows: list[dict[str, Any]] = []
    for i, ti in enumerate(inputs):
        trim = detect_kick_trim(ti.file_path, start_s=ti.mix_in_ms / 1000.0, bpm=ti.bpm)
        delta_ms, refined = refine_phase(ti.file_path, base_trim_s=trim, bpm=ti.bpm)
        gain = gains[ti.track_id]
        flags = ["fixed"] if abs(delta_ms) > 40 or abs(gain) > 1.5 else []
        rows.append({
            "track_id": ti.track_id, "trim_start_s": trim, "refined_trim_s": refined,
            "gain_db": gain, "phase_ms": delta_ms, "flags": flags,
        })
        await safe_report_progress(ctx, progress=i + 1, total=len(inputs))

    grid_path.write_text(json.dumps(rows, indent=1))
    safe_info(ctx, "render_beatgrid: wrote %s", grid_path)
    return RenderBeatgridResult(version_id=version_id, tracks=rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/handlers/test_render_beatgrid.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/handlers/render_beatgrid.py tests/handlers/test_render_beatgrid.py
git commit -m "feat(render): render_beatgrid handler"
```

---

## Task 14: render_mixdown handler

Orchestrates: ensure beatgrid → build `RenderPlan` → run ffmpeg → scan → register job → result.

**Files:**
- Create: `app/handlers/render_mixdown.py`
- Test: `tests/handlers/test_render_mixdown.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/handlers/test_render_mixdown.py
import pytest

from app.domain.render.models import TrackInput
from app.handlers._render_registry import RENDER_JOBS
from app.handlers.render_mixdown import render_mixdown_handler

class _StubUow:
    def __init__(self, inputs):
        class _SV:
            async def get_render_inputs(self, vid):
                return inputs
        self.set_versions = _SV()

@pytest.mark.asyncio
async def test_mixdown_builds_plan_runs_and_registers(tmp_path, monkeypatch):
    RENDER_JOBS.clear()
    inputs = [TrackInput(track_id=i, yandex_id=i, title=f"t{i}", bpm=130.0, key_code=1,
                         mix_in_ms=0, integrated_lufs=-12.0, file_path=f"/x{i}.mp3")
              for i in range(2)]
    # pre-seed a beatgrid so no DSP runs
    import json
    (tmp_path / "beatgrid.json").write_text(json.dumps([
        {"track_id": 0, "trim_start_s": 0.4, "refined_trim_s": 0.4, "gain_db": 0.0, "phase_ms": 0.0},
        {"track_id": 1, "trim_start_s": 0.4, "refined_trim_s": 0.4, "gain_db": 0.0, "phase_ms": 0.0},
    ]))

    captured = {}
    def _fake_run(plan, out_path):
        captured["n"] = plan.n
        captured["out"] = out_path
        # simulate ffmpeg producing a file
        from pathlib import Path
        Path(out_path).write_bytes(b"ID3fake")
    monkeypatch.setattr("app.handlers.render_mixdown.run_render", _fake_run)
    monkeypatch.setattr("app.handlers.render_mixdown.scan_mix",
                        lambda p: type("S", (), {"duration_s": 100.0, "true_peak_db": -1.4,
                                                 "level_jumps": [], "near_silent_s": []})())

    res = await render_mixdown_handler(
        ctx=None, uow=_StubUow(inputs), version_id=131, workspace=str(tmp_path),
        out_name="MIX.mp3", timestamp="20260706-000000",
    )
    assert captured["n"] == 2
    assert res.out_path.endswith("MIX.mp3")
    assert res.job_id == "v131-20260706-000000"
    assert RENDER_JOBS.get(res.job_id).done is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/handlers/test_render_mixdown.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

The `timestamp` param is injected by the caller (Plan 2 tool) so the handler stays testable — the domain/pure layers never call the clock.

```python
# app/handlers/render_mixdown.py
"""Handler: render the continuous beatmatched mix for a set version."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import scan_mix
from app.audio.render.runner import run_render
from app.config import get_settings
from app.domain.render.models import BeatgridEntry
from app.domain.render.timeline import build_render_plan
from app.handlers._context_log import safe_info
from app.handlers._render_registry import RENDER_JOBS
from app.handlers.render_beatgrid import render_beatgrid_handler
from app.schemas.render import RenderMixdownResult

async def render_mixdown_handler(
    *, ctx: Any, uow: Any, version_id: int, workspace: str, timestamp: str,
    out_name: str | None = None, transition_bars: int | None = None,
    body_bars: int | None = None, refresh_grid: bool = False,
) -> RenderMixdownResult:
    rs = get_settings().render
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    grid_path = ws / "beatgrid.json"

    # ensure beatgrid exists (auto-run, like sequence_optimize auto-scores)
    if refresh_grid or not grid_path.exists():
        await render_beatgrid_handler(ctx=ctx, uow=uow, version_id=version_id,
                                      workspace=workspace, refresh=refresh_grid)

    inputs = await uow.set_versions.get_render_inputs(version_id)
    grid_rows = json.loads(grid_path.read_text())
    grid = {
        r["track_id"]: BeatgridEntry(
            track_id=r["track_id"], trim_start_s=r["trim_start_s"],
            refined_trim_s=r.get("refined_trim_s"), gain_db=r.get("gain_db", 0.0),
            phase_ms=r.get("phase_ms", 0.0),
        )
        for r in grid_rows
    }

    plan = build_render_plan(
        inputs, grid, target_bpm=rs.target_bpm, body_bars=body_bars or rs.body_bars,
        transition_bars=transition_bars or rs.transition_bars, xsplit_hz=rs.xsplit_hz,
        low_swap_bars=rs.low_swap_bars, outro_fade_bars=rs.outro_fade_bars,
        limiter_ceiling=rs.limiter_ceiling,
    )

    job_id = f"v{version_id}-{timestamp}"
    RENDER_JOBS.start(job_id=job_id, version_id=version_id, phase="mixdown")
    RENDER_JOBS.update(job_id, total=plan.n, message="rendering")

    out_path = str(ws / (out_name or "MIX.mp3"))
    safe_info(ctx, "render_mixdown: %d segments -> %s", plan.n, out_path)
    try:
        run_render(plan, out_path)
    except Exception as exc:  # noqa: BLE001 — record + re-raise
        RENDER_JOBS.update(job_id, error=str(exc), done=True)
        raise

    sr = scan_mix(out_path)
    RENDER_JOBS.update(job_id, phase="done", out_path=out_path,
                       progress=plan.n, done=True, message="complete")
    return RenderMixdownResult(
        job_id=job_id, version_id=version_id, out_path=out_path,
        duration_s=sr.duration_s, true_peak_db=sr.true_peak_db,
        level_jumps=len(sr.level_jumps), near_silent_s=len(sr.near_silent_s),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/handlers/test_render_mixdown.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/handlers/render_mixdown.py tests/handlers/test_render_mixdown.py
git commit -m "feat(render): render_mixdown handler"
```

---

## Task 15: render_diagnose handler

**Files:**
- Create: `app/handlers/render_diagnose.py`
- Test: `tests/handlers/test_render_diagnose.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/handlers/test_render_diagnose.py
import json

import pytest

from app.handlers.render_diagnose import render_diagnose_handler

@pytest.mark.asyncio
async def test_diagnose_writes_report(tmp_path, monkeypatch):
    out = tmp_path / "MIX.mp3"
    out.write_bytes(b"fake")

    class _Rep:
        name = "MIX.mp3"; overall_rms_db = -11.0; flagged = 1
        windows = [type("W", (), {"offset_s": 20.0, "rms_db": -30.0, "low_db": -40.0,
                                  "tags": ["DROPOUT -30dB"]})()]
    monkeypatch.setattr("app.handlers.render_diagnose.diagnose_mix", lambda p: _Rep())

    res = await render_diagnose_handler(ctx=None, job_id="v131-x",
                                        mix_path=str(out), workspace=str(tmp_path))
    assert res.flagged == 1
    saved = json.loads((tmp_path / "diagnostics.json").read_text())
    assert saved["flagged"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/handlers/test_render_diagnose.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# app/handlers/render_diagnose.py
"""Handler: run scan + diagnose on a rendered mix, persist the report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import diagnose_mix
from app.handlers._context_log import safe_info
from app.schemas.render import RenderDiagnosticsResult

async def render_diagnose_handler(
    *, ctx: Any, job_id: str, mix_path: str, workspace: str
) -> RenderDiagnosticsResult:
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    safe_info(ctx, "render_diagnose: %s", mix_path)
    rep = diagnose_mix(mix_path)
    windows = [
        {"offset_s": w.offset_s, "rms_db": w.rms_db, "low_db": w.low_db, "tags": list(w.tags)}
        for w in rep.windows
    ]
    payload = {"job_id": job_id, "overall_rms_db": rep.overall_rms_db,
               "flagged": rep.flagged, "windows": windows}
    (ws / "diagnostics.json").write_text(json.dumps(payload, indent=1))
    return RenderDiagnosticsResult(
        job_id=job_id, overall_rms_db=rep.overall_rms_db, flagged=rep.flagged, windows=windows
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/handlers/test_render_diagnose.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/handlers/render_diagnose.py tests/handlers/test_render_diagnose.py
git commit -m "feat(render): render_diagnose handler"
```

---

## Task 16: Full gate + docs stub

**Files:**
- Create: `docs/render-pipeline.md` (engine overview; surface sections filled in Plan 2/3)
- Test: whole suite + arch + lint + types

- [ ] **Step 1: Write the docs stub**

Create `docs/render-pipeline.md` documenting: the pure/side-effect split, the beatgrid (kick trim + phase refine + gain), the filtergraph (EQ bass-swap), diagnostics, and the workspace layout `generated-sets/render/v{version_id}/`. One paragraph per module. Note "MCP surface — see Plan 2; Prefab studio — see Plan 3".

- [ ] **Step 2: Run the full gate**

Run: `make check`
Expected: lint + mypy + `lint-imports` (new `v2-render-domain-pure` contract KEPT) + full pytest all PASS. Audio-dependent render tests pass when the `[audio]` extra + ffmpeg are present; otherwise they skip (never fail).

- [ ] **Step 3: Fix any failures**

If mypy flags the `Any`-typed `uow`/`ctx` in handlers, that matches the existing handler style (`set_version_build_handler` uses `Any`) — keep consistent. If `lint-imports` flags `app.repositories.set -> app.domain.render.models`, that edge is allowed (repositories may import domain models — same as other repos importing domain types); if a contract forbids it, add an `ignore_imports` line mirroring the existing `transition_persist` entries.

- [ ] **Step 4: Commit**

```bash
git add docs/render-pipeline.md
git commit -m "docs(render): engine core overview"
```

---

## Self-Review

**Spec coverage (Plan 1 scope = §2 code layer + §5 tests, engine only):**
- RenderSettings (§2 config) → Task 1. ✓
- domain/render models/timeline/graph/levels (§2 pure) → Tasks 2–5. ✓
- get_render_inputs (§2 repositories) → Task 6. ✓
- audio/render kick_phase/phase_refine/runner/diagnostics (§2 side-effect) → Tasks 7–10. ✓
- RenderJobRegistry (§3 hybrid status) → Task 11. ✓
- schemas (§2) → Task 12. ✓
- handlers beatgrid/mixdown/diagnose (§2) → Tasks 13–15. ✓
- arch contract + full gate (§5) → Tasks 2, 16. ✓
- **Deferred to Plan 2:** tools, resources, prompt, tasks wiring (`FastMCP(tasks=True)`), delivery toggle, `KNOWN_NAMESPACES`/`ALWAYS_VISIBLE_TOOLS`. **Deferred to Plan 3:** `ui_render_studio` + app-helper.

**Type consistency:** `TrackInput`, `BeatgridEntry`, `TrackSegment`, `RenderPlan` names identical across Tasks 2–14. Handler DSP function names (`detect_kick_trim`, `refine_phase`, `run_render`, `scan_mix`, `diagnose_mix`) match their module definitions (Tasks 7–10) and their monkeypatch targets (Tasks 13–15). `RENDER_JOBS` singleton + `RenderJob` fields consistent (Tasks 11, 14). `job_id` format `v{version_id}-{timestamp}` consistent (Tasks 14, 15). Result-schema field names match handler constructions.

**Placeholder scan:** no TBD/TODO; every code step contains full code; every test has real assertions.

---

## Next plans

- **Plan 2 — Render MCP surface:** `app/tools/render/` (3 `task=True` tools) + `app/resources/render.py` (5 resources) + `render_set_workflow` prompt + `FastMCP(tasks=True)` wiring + `fastmcp[tasks]` extra + `emit_continuous_mix` delivery toggle + `KNOWN_NAMESPACES`/`ALWAYS_VISIBLE_TOOLS` + `tests/prompts` content-correctness + `docs/tool-catalog.md` counts.
- **Plan 3 — Prefab render studio:** `ui_render_studio` (`app=True`) + hidden `render_studio_panel` app-helper + `RenderStudioFallback` + `tests/tools/ui/test_render_studio.py`.
