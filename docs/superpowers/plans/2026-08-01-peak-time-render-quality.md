# Peak-time render quality: phrase-alignment, energy micro-arc, soft Camelot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make peak_time_techno renders sound "right" per techno DJ best practices: phrase-aligned track entry, an energy micro-arc in track order, and soft Camelot (warning, not hard reject) in the set builder.

**Architecture:** Three additive features. (1) A pure `snap_trim_to_phrase` helper shifts a beatgrid trim to the nearest phrase boundary only for whole-bar (grid-safe) moves, applied in `place_segments` and reported in `render_plan.json` + diagnose. (2) A `peak_only_arc` preset (with a subtle rise-peak-ease micro-arc) drives a new `energy_arc="peak_time"` path on `sequence_optimize` that returns a `fit_tracks_to_arc` order. (3) A `soft_camelot` flag threads through the hard-constraint chain → scorer → GA/bulk reject masks, downgrading a Camelot hard-reject into a `TransitionScore.warnings` entry; strict mode (default) is unchanged.

**Tech Stack:** Python 3.12, FastMCP v3 tools (`@tool`), SQLAlchemy async, pydantic, numpy, pytest + pytest-asyncio, ruff, mypy strict, import-linter. Run everything via `uv run ...`.

## Global Constraints

- **Use `uv` only** — never `python`/`pip`/`pytest`/`ruff`/`mypy` directly: `uv run pytest ...`, `uv run ruff check`, `make check`.
- **`make check`** = ruff lint + mypy strict + pytest + import-linter. MUST pass before every commit.
- **Strict mode is byte-for-byte unchanged**: `camelot_mode="strict"` (default) must produce identical reject/order behaviour to today. Every soft-camelot branch is additive behind a flag.
- **Render engine DSP and `SubgenreRenderPreset` values are NOT touched** (additive only).
- **Do NOT add comments to code** unless the surrounding file already uses them for structure (mirror existing style).
- **Language of commits/messages:** Russian-friendly conventional commits (`feat:`, `test:`, `refactor:`), matching repo style.
- **No CI** — local gates only; `hooks/pre-push` runs `make check` automatically.
- Spec: `docs/superpowers/specs/2026-08-01-peak-time-render-quality-design.md` (Approved, commit `9314eac1`).

---
## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `app/domain/render/models.py` | `TrackInput`, `SegmentGeometry`, `RenderPlan`, `TrackSegment`, `StemSegment` | `TrackInput` +2 phrase fields; `SegmentGeometry.phrase_aligned`; `RenderPlan.phrase_align_count` |
| `app/domain/render/phrase_align.py` | **NEW** pure `snap_trim_to_phrase` helper | create |
| `app/domain/render/timeline.py` | `place_segments` timeline geometry | apply phrase snap + set `phrase_aligned` |
| `app/domain/render/plan_assembler.py` | `RenderPlanner.assemble` | compute `phrase_align_count` |
| `app/repositories/set.py` | `get_render_inputs` | select + parse phrase columns |
| `app/handlers/_orchestrator/render_executor.py` | `_persist_plan` | write `phrase_align`/`phrase_align_count` |
| `app/tools/render/render_diagnose.py` + `app/handlers/render_diagnose.py` + `app/audio/render/diagnostics.py` | structural flow report | report phrase-aligned count |
| `app/domain/performance/energy_arc.py` | arc presets + `fit_tracks_to_arc` | `peak_only_arc` factory, micro-arc curve |
| `app/tools/compute/sequence_optimize.py` | set-order tool | `energy_arc` + `camelot_mode` params |
| `app/schemas/tool_responses.py` | tool result schemas | `algorithm` Literal + `"peak_time"` |
| `app/domain/transition/score.py` | `TransitionScore` | `warnings` field |
| `app/domain/transition/constraints/specs/camelot_distance.py` (+ `bpm_difference.py`, `energy_gap.py`) | hard-constraint specs | `check(soft=)` tuple return; uniform `soft` kwarg |
| `app/domain/transition/constraints/chain.py` | `HardConstraintChain` | `soft_camelot` + warnings |
| `app/domain/transition/hard_constraints.py` | `check_hard_constraints` | `soft_camelot` forward |
| `app/domain/transition/scorer.py` + `neural_mix/scorer.py` | scoring engine | `soft_camelot` forward + merge warnings |
| `app/domain/transition/bulk_scorer.py` | vectorised scorer | `soft_camelot` on mask + `score_pairs_bulk` |
| `app/domain/optimization/genetic.py` / `greedy.py` / `constructive.py` / `fitness.py` | optimizers | `soft_camelot` ctor + forward |
| `app/server/lifespan.py` | `optimizer_builder` DI | accept `soft_camelot` |

---

### Task 1: Feature 1 — TrackInput phrase fields + repository read

**Files:**
- Modify: `app/domain/render/models.py` (`TrackInput`, lines 29-45)
- Modify: `app/repositories/set.py` (`get_render_inputs`, lines 89-163)
- Test: `tests/repositories/test_set_render_inputs.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `TrackInput.phrase_boundaries_ms: list[int] | None = None`, `TrackInput.dominant_phrase_bars: int | None = None` — consumed by Task 3 (`place_segments`).

- [ ] **Step 1: Write the failing test**

Append to `tests/repositories/test_set_render_inputs.py`:

```python
@pytest.mark.asyncio
async def test_get_render_inputs_reads_phrase_features(session):
    await _create_tables(session)
    session.add(Track(id=77, title="Phrase Test"))
    session.add(DjSet(id=3, name="S3"))
    session.add(DjSetVersion(id=300, set_id=3, label="v"))
    await session.flush()
    session.add(
        TrackAudioFeaturesComputed(
            track_id=77,
            bpm=130.0,
            key_code=8,
            integrated_lufs=-11.0,
            phrase_boundaries_ms="[96000, 128000, 160000]",
            dominant_phrase_bars=16,
        )
    )
    session.add(
        DjLibraryItem(
            track_id=77, file_path="/tmp/dj_audio/01 [77].mp3", file_hash="h", file_size=1
        )
    )
    session.add(DjSetItem(version_id=300, track_id=77, sort_index=0, mix_in_point_ms=0))
    await session.flush()
    uow = UnitOfWork(session)
    rows = await uow.set_versions.get_render_inputs(300)
    r = rows[0]
    assert r.phrase_boundaries_ms == [96000, 128000, 160000]
    assert r.dominant_phrase_bars == 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/repositories/test_set_render_inputs.py::test_get_render_inputs_reads_phrase_features -v`
Expected: FAIL — `'TrackInput' object has no attribute 'phrase_boundaries_ms'`.

- [ ] **Step 3: Implement**

In `app/domain/render/models.py`, extend the `TrackInput` dataclass (after `duration_ms`):

```python
    duration_ms: int | None = None
    phrase_boundaries_ms: list[int] | None = None
    dominant_phrase_bars: int | None = None
```

In `app/repositories/set.py`, in `get_render_inputs` add the two columns to the `select(...)` list (after `TrackAudioFeaturesComputed.integrated_lufs`):

```python
                TrackAudioFeaturesComputed.integrated_lufs,
                TrackAudioFeaturesComputed.phrase_boundaries_ms,
                TrackAudioFeaturesComputed.dominant_phrase_bars,
                file_path_subq,
```

Then parse + populate in the row loop. The `import re` line already exists inside the method; add `import json` next to it:

```python
        import json
        import re
```

And inside the loop, before `out.append(...)`:

```python
            phrase_ms = None
            if row.phrase_boundaries_ms:
                phrase_ms = json.loads(row.phrase_boundaries_ms)
```

And extend the `TrackInput(...)` constructor call:

```python
                    duration_ms=row.duration_ms,
                    phrase_boundaries_ms=phrase_ms,
                    dominant_phrase_bars=row.dominant_phrase_bars,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/repositories/test_set_render_inputs.py -v`
Expected: PASS (both old and new tests).

- [ ] **Step 5: Commit**

```bash
git add app/domain/render/models.py app/repositories/set.py tests/repositories/test_set_render_inputs.py
git commit -m "feat: TrackInput carries phrase-boundary data from repo"
```

---

### Task 2: Feature 1 — `snap_trim_to_phrase` pure helper

**Files:**
- Create: `app/domain/render/phrase_align.py`
- Test: `tests/domain/render/test_phrase_align.py`

**Interfaces:**
- Consumes: nothing (pure math).
- Produces: `snap_trim_to_phrase(trim_s: float, phrase_boundaries_ms: list[int] | None, source_bpm: float, *, window_bars: int = 4) -> float` — consumed by Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/domain/render/test_phrase_align.py`:

```python
from app.domain.render.phrase_align import snap_trim_to_phrase

# source_bpm=120 → one 4/4 bar = 4*60/120 = 2.0 s, so whole-bar shifts are
# exact multiples of 2000 ms. Makes the whole-bar arithmetic readable.
BPM = 120.0


def test_whole_bar_shift_applied():
    # trim at 10.0s, boundary at 12.0s → +1 bar (2000ms), in-window
    assert snap_trim_to_phrase(10.0, [12000], BPM) == 12.0


def test_two_bar_shift_applied():
    assert snap_trim_to_phrase(8.0, [12000], BPM) == 12.0


def test_four_bar_shift_at_window_edge():
    # exactly window_bars=4 → accepted
    assert snap_trim_to_phrase(4.0, [12000], BPM) == 12.0


def test_non_whole_bar_shift_rejected():
    # delta 3000ms = 1.5 bars → not within 0.05 of an integer → unchanged
    assert snap_trim_to_phrase(9.0, [12000], BPM) == 9.0


def test_out_of_window_rejected():
    # delta 10000ms = 5 bars > window_bars=4 → unchanged
    assert snap_trim_to_phrase(2.0, [12000], BPM) == 2.0


def test_no_boundaries_noop():
    assert snap_trim_to_phrase(10.0, [], BPM) == 10.0


def test_none_boundaries_noop():
    assert snap_trim_to_phrase(10.0, None, BPM) == 10.0


def test_near_whole_bar_within_tolerance_applied():
    # delta 1900ms = 0.95 bars → within 0.05 of 1 bar → accepted
    assert snap_trim_to_phrase(10.1, [12000], BPM) == 12.0


def test_nearest_boundary_wins():
    # boundaries at 11.5s and 16.0s; trim 12.4s → nearest 11.5s (−0.9s,
    # not whole-bar) → unchanged
    assert snap_trim_to_phrase(12.4, [11500, 16000], BPM) == 12.4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/render/test_phrase_align.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.render.phrase_align'`.

- [ ] **Step 3: Implement**

Create `app/domain/render/phrase_align.py`:

```python
"""Phrase-aligned track entry — snap an incoming trim to a phrase boundary.

Pure geometry: no I/O, no audio analysis. Keeps the kick grid intact by
only accepting near-whole-bar shifts (a bar is 4 beats; an integer number
of bars is a multiple of 4 beats, so every kick stays on the grid).
"""

from __future__ import annotations


def snap_trim_to_phrase(
    trim_s: float,
    phrase_boundaries_ms: list[int] | None,
    source_bpm: float,
    *,
    window_bars: int = 4,
) -> float:
    """Shift ``trim_s`` to the nearest phrase boundary when the move is safe.

    A shift is accepted only when it is (a) at most ``window_bars`` bars and
    (b) a near-whole number of bars (within 0.05 of an integer), which keeps
    the kick phase intact. Returns the adjusted trim (seconds), or the
    original when nothing qualifies.
    """
    if not phrase_boundaries_ms or source_bpm <= 0.0:
        return trim_s

    bar_s = 4.0 * (60.0 / source_bpm)
    trim_ms = trim_s * 1000.0

    best_ms = min(phrase_boundaries_ms, key=lambda b: abs(b - trim_ms))
    delta_ms = best_ms - trim_ms
    delta_bars = delta_ms / 1000.0 / bar_s
    if abs(delta_bars - round(delta_bars)) > 0.05:
        return trim_s
    if abs(delta_bars) > window_bars:
        return trim_s
    return trim_s + delta_ms / 1000.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/render/test_phrase_align.py -v`
Expected: PASS (all 9).

- [ ] **Step 5: Commit**

```bash
git add app/domain/render/phrase_align.py tests/domain/render/test_phrase_align.py
git commit -m "feat: snap_trim_to_phrase whole-bar phrase alignment helper"
```

---

### Task 3: Feature 1 — phrase snap in `place_segments` + plan flag

**Files:**
- Modify: `app/domain/render/timeline.py` (`place_segments`, lines 65-104)
- Modify: `app/domain/render/models.py` (`SegmentGeometry` lines 30-48, `RenderPlan` lines 104-203)
- Modify: `app/domain/render/plan_assembler.py` (`assemble`, lines 45-86)
- Test: `tests/domain/render/test_timeline.py`

**Interfaces:**
- Consumes: `TrackInput.phrase_boundaries_ms` / `.bpm` (Task 1); `snap_trim_to_phrase` (Task 2).
- Produces: `SegmentGeometry.phrase_aligned: bool`; `RenderPlan.phrase_align_count: int` — consumed by Task 4 (`_persist_plan`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/domain/render/test_timeline.py` (keep existing imports; add `from app.domain.render.timeline import place_segments`):

```python
def _phrase_input(trim_s, boundaries):
    return TrackInput(
        track_id=1,
        yandex_id=1,
        title="t",
        bpm=120.0,  # 1 bar = 2.0 s
        key_code=None,
        mix_in_ms=0,
        integrated_lufs=-12.0,
        file_path="/x.mp3",
        phrase_boundaries_ms=boundaries,
        dominant_phrase_bars=4,
    )


def _grid_with_trim(trim_s):
    return {1: BeatgridEntry(track_id=1, trim_start_s=trim_s, refined_trim_s=None, gain_db=0.0, phase_ms=0.0)}


def test_place_segments_snaps_whole_bar_to_phrase():
    inputs = [_phrase_input(10.0, [12000])]
    geoms = place_segments(
        inputs, _grid_with_trim(10.0), target_bpm=130.0, body_bars=24, transition_bars=32
    )
    assert geoms[0].trim_start_s == 12.0
    assert geoms[0].phrase_aligned is True


def test_place_segments_skips_non_whole_bar():
    inputs = [_phrase_input(9.0, [12000])]
    geoms = place_segments(
        inputs, _grid_with_trim(9.0), target_bpm=130.0, body_bars=24, transition_bars=32
    )
    assert geoms[0].trim_start_s == 9.0
    assert geoms[0].phrase_aligned is False


def test_place_segments_without_phrase_data_unchanged():
    inputs = [TrackInput(
        track_id=1, yandex_id=1, title="t", bpm=130.0, key_code=None,
        mix_in_ms=0, integrated_lufs=-12.0, file_path="/x.mp3",
    )]
    geoms = place_segments(
        inputs, _grid_with_trim(10.0), target_bpm=130.0, body_bars=24, transition_bars=32
    )
    assert geoms[0].trim_start_s == 10.0
    assert geoms[0].phrase_aligned is False


def test_assemble_reports_phrase_align_count():
    request = RenderRequest(
        version_id=1, workspace="/tmp/ws", timestamp="t", transition_bars=32, body_bars=24, stem=False
    )
    bar_plan = BarPlan(transition_bars=(), body_bars=[24])
    plan = RenderPlanner().assemble(
        RenderSettings(),
        request,
        [_phrase_input(10.0, [12000])],
        _grid_with_trim(10.0),
        bar_plan,
        stem_paths=None,
    )
    assert plan.phrase_align_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/render/test_timeline.py -v`
Expected: FAIL — `AttributeError: 'SegmentGeometry' object has no attribute 'phrase_aligned'` / `'RenderPlan' object has no attribute 'phrase_align_count'`.

- [ ] **Step 3: Implement**

`app/domain/render/models.py` — add to `SegmentGeometry` (after `start_s`):

```python
    start_s: float
    phrase_aligned: bool = False
```

Add to `RenderPlan` (after `segments: list[TrackSegment] = field(default_factory=list)`):

```python
    phrase_align_count: int = 0
```

And in `RenderPlan.from_settings`, add the kwarg + pass-through:

```python
    @classmethod
    def from_settings(
        cls,
        settings: RenderSettings,
        request: RenderRequest,
        *,
        segments: list[TrackSegment] | None = None,
        stem_segments: list[StemSegment] | None = None,
        stem_order: tuple[str, ...] = STEM_ORDER,
        phrase_align_count: int = 0,
    ) -> RenderPlan:
```

Add to the `return cls(...)`:

```python
            segments=segments if segments is not None else [],
            phrase_align_count=phrase_align_count,
```

`app/domain/render/timeline.py` — in `place_segments`, replace the `g = grid.get(ti.track_id)` / geometry construction block:

```python
        g = grid.get(ti.track_id)
        raw_trim = g.effective_trim if g is not None else 0.0
        phrase_aligned = False
        if g is not None and ti.phrase_boundaries_ms and ti.bpm:
            snapped = snap_trim_to_phrase(raw_trim, ti.phrase_boundaries_ms, ti.bpm)
            if snapped != raw_trim:
                phrase_aligned = True
            raw_trim = snapped
        geometries.append(
            SegmentGeometry(
                index=i,
                track_id=ti.track_id,
                tempo_ratio=ti.tempo_ratio(target_bpm),
                trim_start_s=raw_trim,
                gain_db=g.gain_db if g is not None else 0.0,
                body_bars=seg_body,
                d_in_s=d_in,
                d_out_s=d_out,
                length_s=length,
                start_s=running_t,
                phrase_aligned=phrase_aligned,
            )
        )
```

Add the import at the top of `timeline.py`:

```python
from app.domain.render.phrase_align import snap_trim_to_phrase
```

`app/domain/render/plan_assembler.py` — in `assemble`, after `geometries = place_segments(...)` and before building segments:

```python
        phrase_align_count = sum(1 for g in geometries if g.phrase_aligned)
```

Pass it to both `RenderPlan.from_settings(...)` calls (classic branch and stem branch):

```python
        if request.mode is RenderMode.CLASSIC:
            return RenderPlan.from_settings(
                settings,
                request,
                segments=cast(list[TrackSegment], segments),
                phrase_align_count=phrase_align_count,
            )
        return RenderPlan.from_settings(
            settings,
            request,
            segments=[],
            stem_segments=cast(list[StemSegment], segments),
            stem_order=_resolve_stem_order(stem_paths),
            phrase_align_count=phrase_align_count,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/render/test_timeline.py tests/domain/render/test_phrase_align.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/render/models.py app/domain/render/timeline.py app/domain/render/plan_assembler.py tests/domain/render/test_timeline.py
git commit -m "feat: place_segments snaps entry to phrase boundary, reports phrase_align_count"
```

---

### Task 4: Feature 1 — persist + diagnose report

**Files:**
- Modify: `app/handlers/_orchestrator/render_executor.py` (`_persist_plan`, lines 50-68)
- Modify: `app/tools/render/render_diagnose.py` (lines 57-83)
- Modify: `app/handlers/render_diagnose.py` (lines 55-67)
- Modify: `app/audio/render/diagnostics.py` (`analyze_set_flow`, signature ~line 189, summary ~line 465)
- Test: `tests/handlers/test_render_executor.py` (new), `tests/handlers/test_render_diagnose.py`

**Interfaces:**
- Consumes: `RenderPlan.phrase_align_count` (Task 3).
- Produces: `render_plan.json` keys `phrase_align: bool`, `phrase_align_count: int`; `analyze_set_flow(..., phrase_align_count=0)` adds `summary["phrase_aligned_tracks"]` + a warning.

- [ ] **Step 1: Write the failing tests**

Create `tests/handlers/test_render_executor.py`:

```python
import json

from app.domain.render.models import RenderMode, RenderPlan
from app.handlers._orchestrator.render_executor import RenderExecutor


def _plan(phrase_align_count: int) -> RenderPlan:
    return RenderPlan(
        target_bpm=130.0,
        xsplit_low_hz=260,
        xsplit_high_hz=4200,
        eq_phase_1_ratio=0.4,
        eq_phase_2_ratio=0.7,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=-1.0,
        mode=RenderMode.CLASSIC,
        phrase_align_count=phrase_align_count,
    )


def test_persist_plan_reports_phrase_align_true(tmp_path):
    executor = RenderExecutor()
    executor._persist_plan(_plan(2), object(), tmp_path)
    payload = json.loads((tmp_path / "render_plan.json").read_text())
    assert payload["phrase_align"] is True
    assert payload["phrase_align_count"] == 2


def test_persist_plan_reports_phrase_align_false(tmp_path):
    executor = RenderExecutor()
    executor._persist_plan(_plan(0), object(), tmp_path)
    payload = json.loads((tmp_path / "render_plan.json").read_text())
    assert payload["phrase_align"] is False
    assert payload["phrase_align_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/handlers/test_render_executor.py -v`
Expected: FAIL — `KeyError: 'phrase_align'` in the JSON payload.

- [ ] **Step 3: Implement**

`app/handlers/_orchestrator/render_executor.py` — extend the `payload` dict in `_persist_plan`:

```python
        payload = {
            "target_bpm": plan.target_bpm,
            "mode": plan.mode.value,
            "subgenre": getattr(request, "subgenre", None),
            "transition_bars": getattr(request, "transition_bars", None),
            "body_bars": getattr(request, "body_bars", None),
            "segments": timeline,
            "phrase_align": plan.phrase_align_count > 0,
            "phrase_align_count": plan.phrase_align_count,
        }
```

`app/tools/render/render_diagnose.py` — in the `if plan_path.exists():` branch, after `subgenre = plan.get("subgenre")`, add:

```python
        phrase_align_count = int(plan.get("phrase_align_count", 0))
```

In the `else:` branch add:

```python
        phrase_align_count = 0
```

And add to `version_context`:

```python
    version_context = {
        "segments": track_segments,
        "features": features,
        "titles": titles,
        "subgenre": subgenre,
        "phrase_align_count": phrase_align_count,
    }
```

`app/handlers/render_diagnose.py` — forward the count into `analyze_set_flow`:

```python
        flow = analyze_set_flow(
            name=rep.name,
            duration_s=rep.duration_s,
            windows=rep.windows,
            segments=version_context.get("segments", []),
            features=version_context.get("features", {}),
            titles=version_context.get("titles", {}),
            target_subgenre=version_context.get("subgenre"),
            lra=rep.loudness_range_lu,
            phrase_align_count=version_context.get("phrase_align_count", 0),
        )
```

`app/audio/render/diagnostics.py` — update `analyze_set_flow` signature:

```python
def analyze_set_flow(
    name: str,
    duration_s: float,
    windows: list[DiagWindow],
    segments: list[tuple[int, float, float]],
    features: dict[int, object],
    titles: dict[int, str],
    target_subgenre: str | None = None,
    lra: float | None = None,
    phrase_align_count: int = 0,
) -> dict[str, Any]:
```

Add to the `summary` dict (before `"quality_score"`):

```python
            "phrase_aligned_tracks": phrase_align_count,
```

And append a warning (before `return`):

```python
    if phrase_align_count > 0:
        warnings.append(
            f"{phrase_align_count} track(s) phrase-aligned on entry "
            "(trim snapped to a phrase boundary)"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/handlers/test_render_executor.py tests/handlers/test_render_diagnose.py tests/audio/render/test_diagnostics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/handlers/_orchestrator/render_executor.py app/tools/render/render_diagnose.py app/handlers/render_diagnose.py app/audio/render/diagnostics.py tests/handlers/test_render_executor.py
git commit -m "feat: persist + report phrase-aligned track count in diagnose flow"
```

---

### Task 5: Feature 2 — `peak_only_arc` preset + micro-arc curve

**Files:**
- Modify: `app/domain/performance/energy_arc.py` (`build_slots` PEAK_ONLY branch lines 77-79; add factory near line 256; `ARC_PRESETS` line 269)
- Test: `tests/domain/performance/test_energy_arc.py` (new)

**Interfaces:**
- Consumes: `ArcShape.PEAK_ONLY` (already exists), `EnergyArc`, `TrackCandidate`, `fit_tracks_to_arc`.
- Produces: `peak_only_arc(num_tracks=12) -> EnergyArc`, registered in `ARC_PRESETS` under `"peak_only"`; `build_slots()` on a PEAK_ONLY arc yields a rise→peak@~75%→ease energy curve. Consumed by Task 6.

- [ ] **Step 1: Write the failing tests**

Create `tests/domain/performance/test_energy_arc.py`:

```python
import numpy as np

from app.domain.performance.energy_arc import (
    ARC_PRESETS,
    ArcShape,
    TrackCandidate,
    fit_tracks_to_arc,
    peak_only_arc,
)


def test_peak_only_registered_in_presets():
    assert "peak_only" in ARC_PRESETS


def test_peak_only_arc_energy_peaks_near_75_percent():
    arc = peak_only_arc(num_tracks=8)
    slots = arc.build_slots()
    energies = [s.target_energy for s in slots]
    assert arc.shape is ArcShape.PEAK_ONLY
    peak_idx = int(np.argmax(energies))
    peak_pos = peak_idx / (len(energies) - 1)
    assert 0.6 <= peak_pos <= 0.9
    assert energies[0] < energies[peak_idx]
    assert energies[-1] < energies[peak_idx]
    assert all(0.45 <= e <= 0.80 for e in energies)
    assert all(a <= b for a, b in zip(energies[:peak_idx], energies[1:peak_idx + 1]))
    assert all(a >= b for a, b in zip(energies[peak_idx:-1], energies[peak_idx + 1:]))


def test_peak_only_flat_bpm():
    arc = peak_only_arc(num_tracks=6)
    slots = arc.build_slots()
    assert {s.target_bpm for s in slots} == {130.0}


def test_fit_tracks_to_arc_follows_peak_energy():
    energies = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    candidates = [
        TrackCandidate(
            track_id=100 + i,
            bpm=130.0,
            energy_mean=e,
            key_code=None,
            integrated_lufs=-12.0,
            spectral_centroid_hz=0.0,
        )
        for i, e in enumerate(energies)
    ]
    arc = peak_only_arc(num_tracks=6)
    order = fit_tracks_to_arc(candidates, arc)
    assert order is not None
    ordered_energy = [energies[tid - 100] for tid in order]
    peak_idx = int(np.argmax(ordered_energy))
    peak_pos = peak_idx / (len(ordered_energy) - 1)
    assert 0.6 <= peak_pos <= 0.9
    assert ordered_energy[-1] < ordered_energy[peak_idx]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/performance/test_energy_arc.py -v`
Expected: FAIL — `KeyError: 'peak_only'` (and the PEAK_ONLY curve is flat, not a peak).

- [ ] **Step 3: Implement**

In `app/domain/performance/energy_arc.py`, replace the `PEAK_ONLY` branch of `build_slots`:

```python
        elif self.shape == ArcShape.PEAK_ONLY:
            bpm_curve = np.full(n, self.target_bpm_peak)
            energy_curve = 0.50 + 0.25 * np.exp(-((x - 0.75) ** 2) / 0.05)
            energy_curve = np.clip(energy_curve, 0.45, 0.80)
```

Add the factory (after `festival_arc`, before `ARC_PRESETS`):

```python
def peak_only_arc(num_tracks: int = 12) -> EnergyArc:
    return EnergyArc(
        shape=ArcShape.PEAK_ONLY,
        num_tracks=num_tracks,
        target_bpm_start=130.0,
        target_bpm_peak=130.0,
        target_bpm_end=130.0,
        name=f"PeakOnly-{num_tracks}",
    )
```

Register it in `ARC_PRESETS`:

```python
ARC_PRESETS: dict[str, Callable[[int], EnergyArc]] = {
    "roller": roller_arc,
    "journey": journey_arc,
    "warehouse": warehouse_arc,
    "festival": festival_arc,
    "peak_only": peak_only_arc,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/performance/test_energy_arc.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/performance/energy_arc.py tests/domain/performance/test_energy_arc.py
git commit -m "feat: peak_only energy micro-arc preset for set ordering"
```

---

### Task 6: Feature 2 — `sequence_optimize(energy_arc="peak_time")`

**Files:**
- Modify: `app/tools/compute/sequence_optimize.py`
- Modify: `app/schemas/tool_responses.py` (`SequenceOptimizeResult.algorithm` Literal, line 99)
- Test: `tests/tools/compute/test_sequence_optimize_energy_arc.py` (new)

**Interfaces:**
- Consumes: `peak_only_arc`, `fit_tracks_to_arc`, `TrackCandidate` (Task 5); `features` from `get_scoring_features_batch` (already fetched).
- Produces: `sequence_optimize(..., energy_arc="peak_time")` returns a `SequenceOptimizeResult` whose `track_order` is the arc order and `algorithm == "peak_time"`. Consumed by nothing further (public tool surface).

- [ ] **Step 1: Write the failing tests**

Create `tests/tools/compute/test_sequence_optimize_energy_arc.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


def _peak_time_pool() -> dict[int, TrackFeatures]:
    energies = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    return {
        100 + i: TrackFeatures(bpm=130.0, energy_mean=e, key_code=None, integrated_lufs=-12.0)
        for i, e in enumerate(energies)
    }


@pytest.mark.asyncio
async def test_energy_arc_peak_time_returns_arc_order() -> None:
    out = await sequence_optimize(
        track_ids=[100, 101, 102, 103, 104, 105],
        energy_arc="peak_time",
        uow=_uow_with_features(_peak_time_pool()),
        scorer=MagicMock(),
        optimizer_builder=MagicMock(),
    )
    assert out.algorithm == "peak_time"
    energies = {tid: feats[tid].energy_mean for tid, feats in [(t, _peak_time_pool()[t]) for t in out.track_order]}
    ordered = [energies[tid] for tid in out.track_order]
    # peak (0.75) lands near the end but not last
    peak_idx = ordered.index(max(ordered))
    assert peak_idx >= len(ordered) - 2
    assert peak_idx < len(ordered) - 1
    assert ordered[-1] < max(ordered)


@pytest.mark.asyncio
async def test_energy_arc_peak_time_respects_excluded() -> None:
    out = await sequence_optimize(
        track_ids=[100, 101, 102, 103, 104, 105],
        energy_arc="peak_time",
        excluded=[104],
        uow=_uow_with_features(_peak_time_pool()),
        scorer=MagicMock(),
        optimizer_builder=MagicMock(),
    )
    assert 104 not in out.track_order
    assert len(out.track_order) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/compute/test_sequence_optimize_energy_arc.py -v`
Expected: FAIL — `unexpected keyword argument 'energy_arc'` (pydantic rejects unknown kwarg).

- [ ] **Step 3: Implement**

In `app/schemas/tool_responses.py`, extend the `algorithm` Literal:

```python
class SequenceOptimizeResult(BaseModel):
    track_order: list[int]
    quality_score: float
    algorithm: Literal["ga", "greedy", "constructive", "peak_time"]
    generations: int = 0
```

In `app/tools/compute/sequence_optimize.py`:

Add the parameter (after `excluded`):

```python
    energy_arc: Annotated[
        Literal["none", "peak_time"] | None,
        Field(
            description=(
                "``None``/``'none'`` uses the GA/greedy/constructive path. "
                "``'peak_time'`` orders the pool by a peak-time energy "
                "micro-arc (rise to ~75%, then ease) — the arc is "
                "authoritative for track order."
            )
        ),
    ] = None,
```

Add the module-level helper (after `_AUTO_GREEDY_THRESHOLD`):

```python
def _optimize_by_arc(
    track_ids: list[int],
    features: dict[int, TrackFeatures],
) -> SequenceOptimizeResult:
    """Order the pool by the peak-time energy micro-arc.

    The arc is authoritative: ``fit_tracks_to_arc`` greedily assigns each
    slot the remaining track whose BPM/energy/key deviates least from the
    slot's target. ``quality_score`` is 1 minus the mean absolute energy
    deviation of the assignment.
    """
    from app.domain.performance.energy_arc import (
        TrackCandidate,
        fit_tracks_to_arc,
        peak_only_arc,
    )

    candidates = [
        TrackCandidate(
            track_id=tid,
            bpm=features[tid].bpm if features[tid].bpm is not None else 130.0,
            energy_mean=features[tid].energy_mean if features[tid].energy_mean is not None else 0.5,
            key_code=features[tid].key_code,
            integrated_lufs=(
                features[tid].integrated_lufs if features[tid].integrated_lufs is not None else -12.0
            ),
            spectral_centroid_hz=features[tid].spectral_centroid_hz or 0.0,
        )
        for tid in track_ids
    ]
    arc = peak_only_arc(num_tracks=len(track_ids))
    order = fit_tracks_to_arc(candidates, arc)
    if order is None:
        order = list(track_ids)

    arc.build_slots()
    by_id = {c.track_id: c for c in candidates}
    slot_energy = {s.position: s.target_energy for s in arc.slots}
    deviations = [
        abs(by_id[tid].energy_mean - slot_energy[i + 1]) for i, tid in enumerate(order)
    ]
    quality = 1.0 - (sum(deviations) / len(deviations)) if deviations else 1.0
    return SequenceOptimizeResult(
        track_order=order,
        quality_score=round(max(0.0, min(1.0, quality)), 4),
        algorithm="peak_time",
        generations=0,
    )
```

Add the import at the top of the module:

```python
from app.shared.features import TrackFeatures
```

Insert the arc branch in the tool body after `features_list = [features[tid] for tid in track_ids]` (line ~186):

```python
    if energy_arc == "peak_time":
        active_ids = [tid for tid in track_ids if tid not in excluded_set]
        return _optimize_by_arc(track_ids=active_ids, features=features)
```

> `excluded_set` is already computed above; `track_ids` at this point is the validated pool (duplicates/pinned orphans/excluded-empty already rejected).

Also extend the tool `description=` string to mention `energy_arc`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools/compute/test_sequence_optimize_energy_arc.py tests/tools/compute/test_sequence_optimize.py tests/tools/compute/test_duplicate_track_ids.py -v`
Expected: PASS (arc tests + existing tool tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add app/tools/compute/sequence_optimize.py app/schemas/tool_responses.py tests/tools/compute/test_sequence_optimize_energy_arc.py
git commit -m "feat: sequence_optimize energy_arc=peak_time micro-arc ordering"
```

---

### Task 7: Feature 3 — `TransitionScore.warnings` + `CamelotDistanceSpec.check(soft)`

**Files:**
- Modify: `app/domain/transition/score.py` (`TransitionScore`, lines 47-61)
- Modify: `app/domain/transition/constraints/specs/camelot_distance.py`
- Modify: `app/domain/transition/constraints/specs/bpm_difference.py`
- Modify: `app/domain/transition/constraints/specs/energy_gap.py`
- Test: `tests/domain/transition/test_camelot_spec.py` (new)

**Interfaces:**
- Consumes: nothing new.
- Produces: `TransitionScore.warnings: tuple[str, ...] = ()`; every spec's `check(...)` gains a `soft: bool = False` kwarg; `CamelotDistanceSpec.check` returns `tuple[str | None, str | None]` = `(reason, warning)`; Bpm/Energy specs keep returning `str | None` but accept (and ignore) `soft`. Consumed by Task 8 (chain).

- [ ] **Step 1: Write the failing tests**

Create `tests/domain/transition/test_camelot_spec.py`:

```python
from __future__ import annotations

from app.domain.transition.constraints.specs.camelot_distance import CamelotDistanceSpec
from app.shared.features import TrackFeatures


def _t(key_code: int) -> TrackFeatures:
    return TrackFeatures(bpm=128.0, key_code=key_code, key_confidence=0.9, atonality=False)


def test_strict_returns_reason():
    a, b = _t(0), _t(12)  # distance >= 5 on the wheel
    reason, warning = CamelotDistanceSpec().check(a, b)
    assert reason is not None and "Camelot" in reason
    assert warning is None


def test_soft_returns_warning_not_reason():
    a, b = _t(0), _t(12)
    reason, warning = CamelotDistanceSpec().check(a, b, soft=True)
    assert reason is None
    assert warning is not None and "Camelot" in warning and "(soft)" in warning


def test_compatible_pair_returns_none_none():
    a, b = _t(8), _t(9)
    assert CamelotDistanceSpec().check(a, b) == (None, None)
    assert CamelotDistanceSpec().check(a, b, soft=True) == (None, None)


def test_unreliable_key_never_rejects():
    a = TrackFeatures(bpm=128.0, key_code=0, key_confidence=None)
    b = TrackFeatures(bpm=128.0, key_code=12, key_confidence=0.9)
    assert CamelotDistanceSpec().check(a, b) == (None, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/transition/test_camelot_spec.py -v`
Expected: FAIL — unpacking error (`cannot unpack non-iterable str` / `NoneType`).

- [ ] **Step 3: Implement**

`app/domain/transition/score.py` — add the field to `TransitionScore`:

```python
    best_transition: NeuralMixTransition | None = None
    section_pair_class: str | None = None
    warnings: tuple[str, ...] = ()
```

`app/domain/transition/constraints/specs/camelot_distance.py` — change the signature and body:

```python
    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
        soft: bool = False,
    ) -> tuple[str | None, str | None]:
        settings = get_settings().transition

        key_dist: int | None
        if pre_key_dist is not None:
            key_dist = pre_key_dist
        elif from_t.key_code is not None and to_t.key_code is not None:
            key_dist = camelot_distance(from_t.key_code, to_t.key_code)
        else:
            key_dist = None

        key_floor = settings.hard_reject_key_confidence_floor
        if (
            key_dist is not None
            and key_dist >= settings.hard_reject_camelot_dist
            and key_reliable(from_t, key_floor)
            and key_reliable(to_t, key_floor)
        ):
            if soft:
                return (
                    None,
                    f"Camelot distance {key_dist} >= {settings.hard_reject_camelot_dist} (soft)",
                )
            return f"Camelot distance {key_dist} >= {settings.hard_reject_camelot_dist}", None

        return None, None
```

`app/domain/transition/constraints/specs/bpm_difference.py` — add the ignored `soft` kwarg:

```python
    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
        soft: bool = False,
    ) -> str | None:
```

`app/domain/transition/constraints/specs/energy_gap.py` — same ignored `soft` kwarg added to its `check` signature.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/transition/test_camelot_spec.py tests/domain/transition/test_hard_constraints.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/transition/score.py app/domain/transition/constraints/specs/camelot_distance.py app/domain/transition/constraints/specs/bpm_difference.py app/domain/transition/constraints/specs/energy_gap.py tests/domain/transition/test_camelot_spec.py
git commit -m "feat: TransitionScore.warnings + soft mode on CamelotDistanceSpec"
```

---

### Task 8: Feature 3 — chain + `check_hard_constraints(soft_camelot)`

**Files:**
- Modify: `app/domain/transition/constraints/chain.py`
- Modify: `app/domain/transition/hard_constraints.py`
- Test: `tests/domain/transition/test_hard_constraints.py`

**Interfaces:**
- Consumes: spec `check` tuples (Task 7).
- Produces: `HardConstraintChain.check(..., soft_camelot=False) -> TransitionScore | None` — in soft mode a Camelot-only violation returns a **passing** `TransitionScore(hard_reject=False, warnings=...)`; `check_hard_constraints(..., soft_camelot=False) -> TransitionScore | None` forwards it. Consumed by Tasks 9-11.

- [ ] **Step 1: Write the failing tests**

Append to `tests/domain/transition/test_hard_constraints.py` (the module already has `check_hard_constraints` imported and a `_features(**overrides)` helper with `bpm=128, key_code=8, integrated_lufs=-10`):

```python
    def test_soft_camelot_becomes_warning_not_reject(self) -> None:
        a = _features(key_code=0, key_confidence=0.9)
        b = _features(key_code=12, key_confidence=0.9)
        strict = check_hard_constraints(a, b)
        assert strict is not None and strict.hard_reject is True
        soft = check_hard_constraints(a, b, soft_camelot=True)
        assert soft is not None
        assert soft.hard_reject is False
        assert any("Camelot" in w and "(soft)" in w for w in soft.warnings)

    def test_soft_mode_bpm_still_rejects(self) -> None:
        a = _features(bpm=120.0, key_code=0, key_confidence=0.9)
        b = _features(bpm=140.0, key_code=12, key_confidence=0.9)
        result = check_hard_constraints(a, b, soft_camelot=True)
        assert result is not None and result.hard_reject is True
        assert "BPM" in (result.reject_reason or "")

    def test_soft_mode_compatible_pair_returns_none(self) -> None:
        a = _features(key_code=8, key_confidence=0.9)
        b = _features(key_code=9, key_confidence=0.9)
        assert check_hard_constraints(a, b, soft_camelot=True) is None

    def test_strict_mode_unchanged_with_warnings_empty(self) -> None:
        a = _features(key_code=0, key_confidence=0.9)
        b = _features(key_code=12, key_confidence=0.9)
        strict = check_hard_constraints(a, b)
        assert strict is not None and strict.hard_reject is True
        assert strict.warnings == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/transition/test_hard_constraints.py -v`
Expected: FAIL — `check_hard_constraints() got an unexpected keyword argument 'soft_camelot'`.

- [ ] **Step 3: Implement**

`app/domain/transition/constraints/chain.py` — replace `check`:

```python
    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
        soft_camelot: bool = False,
    ) -> TransitionScore | None:
        warnings: list[str] = []
        for c in self._constraints:
            result = c.check(
                from_t,
                to_t,
                pre_bpm_dist=pre_bpm_dist,
                pre_key_dist=pre_key_dist,
                pre_energy_delta=pre_energy_delta,
                soft=soft_camelot,
            )
            if isinstance(result, tuple):
                reason, warning = result
            else:
                reason, warning = result, None
            if reason is not None:
                from app.domain.transition.score import TransitionScore

                return TransitionScore(
                    bpm=0.0,
                    energy=0.0,
                    drums=0.0,
                    bass=0.0,
                    harmonics=0.0,
                    vocals=0.0,
                    overall=0.0,
                    hard_reject=True,
                    reject_reason=reason,
                )
            if warning is not None:
                warnings.append(warning)
        if warnings:
            from app.domain.transition.score import TransitionScore

            return TransitionScore(hard_reject=False, warnings=tuple(warnings))
        return None
```

`app/domain/transition/hard_constraints.py` — forward the flag:

```python
def check_hard_constraints(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    pre_bpm_dist: float | None = None,
    pre_key_dist: int | None = None,
    pre_energy_delta: float | None = None,
    soft_camelot: bool = False,
) -> TransitionScore | None:
    """Return a rejection, a passing-with-warnings score, or ``None``."""
    return _chain.check(
        from_t,
        to_t,
        pre_bpm_dist=pre_bpm_dist,
        pre_key_dist=pre_key_dist,
        pre_energy_delta=pre_energy_delta,
        soft_camelot=soft_camelot,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/transition/test_hard_constraints.py tests/domain/transition/test_camelot_spec.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/transition/constraints/chain.py app/domain/transition/hard_constraints.py tests/domain/transition/test_hard_constraints.py
git commit -m "feat: soft_camelot flag on hard-constraint chain surfaces warnings"
```

---

### Task 9: Feature 3 — scorer merges warnings + NeuralMixScorer forwards flag

**Files:**
- Modify: `app/domain/transition/scorer.py`
- Modify: `app/domain/transition/neural_mix/scorer.py`
- Test: `tests/domain/transition/test_scorer.py`, `tests/domain/transition/test_neural_mix.py`

**Interfaces:**
- Consumes: `check_hard_constraints(..., soft_camelot=)` (Task 8).
- Produces: `TransitionScorer.score/score_all_intents/score_with_candidates(..., soft_camelot=False)`; `NeuralMixScorer.score/score_with_candidates(..., soft_camelot=False)`. A soft-mode Camelot-only pair scores normally and carries `warnings`. Consumed by Tasks 11-12.

- [ ] **Step 1: Write the failing tests**

Append to `tests/domain/transition/test_scorer.py` (the module has a `_bp(**overrides)` helper with `key_code=8, key_confidence=0.7, atonality=False`):

```python
def test_scorer_soft_camelot_scores_with_warning() -> None:
    scorer = TransitionScorer()
    a = _bp(key_code=0)
    b = _bp(key_code=12)  # Camelot distance >= 5, reliable keys

    strict = scorer.score(a, b)
    assert strict.hard_reject is True
    assert strict.warnings == ()

    soft = scorer.score(a, b, soft_camelot=True)
    assert soft.hard_reject is False
    assert soft.overall > 0.0
    assert any("Camelot" in w for w in soft.warnings)


def test_scorer_soft_camelot_score_all_intents() -> None:
    from app.domain.transition.intent import TransitionIntent

    scorer = TransitionScorer()
    a = _bp(key_code=0)
    b = _bp(key_code=12)

    results = scorer.score_all_intents(a, b, soft_camelot=True)
    for intent in (TransitionIntent.MAINTAIN, TransitionIntent.RAMP_UP):
        assert results[intent].hard_reject is False
        assert any("Camelot" in w for w in results[intent].warnings)


def test_scorer_soft_camelot_score_with_candidates() -> None:
    scorer = TransitionScorer()
    a = _bp(key_code=0)
    b = _bp(key_code=12)

    result = scorer.score_with_candidates(a, b, soft_camelot=True)
    assert result.hard_reject is False
    assert any("Camelot" in w for w in result.warnings)


def test_scorer_strict_camelot_still_rejects() -> None:
    scorer = TransitionScorer()
    a = _bp(key_code=0)
    b = _bp(key_code=12)
    strict = scorer.score(a, b)
    assert strict.hard_reject is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/transition/test_scorer.py::test_scorer_soft_camelot_scores_with_warning -v`
Expected: FAIL — `score() got an unexpected keyword argument 'soft_camelot'`.

- [ ] **Step 3: Implement**

`app/domain/transition/neural_mix/scorer.py` — add `soft_camelot: bool = False` to both methods and forward:

```python
    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        soft_camelot: bool = False,
    ) -> NeuralMixScore:
        rejection = check_hard_constraints(from_t, to_t, soft_camelot=soft_camelot)
        return (
            self._from_rejection(rejection)
            if rejection is not None and rejection.hard_reject
            else self._compute(from_t, to_t)
        )

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
        *,
        soft_camelot: bool = False,
    ) -> NeuralMixScore:
        rejection = check_hard_constraints(
            from_t,
            to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
            soft_camelot=soft_camelot,
        )
        return (
            self._from_rejection(rejection)
            if rejection is not None and rejection.hard_reject
            else self._compute(from_t, to_t)
        )
```

> In strict mode `rejection` is either `None` or a `hard_reject=True` score, so `rejection is not None and rejection.hard_reject` is behaviour-identical to the old `rejection is not None`.

`app/domain/transition/scorer.py`:

`score` — new signature + gate handling:

```python
    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
        soft_camelot: bool = False,
    ) -> TransitionScore:
        gate = check_hard_constraints(from_t, to_t, soft_camelot=soft_camelot)
        if gate is not None and gate.hard_reject:
            return gate

        base_weights = INTENT_WEIGHT_MODIFIERS[intent] if intent is not None else self.weights
        weights, pair_class_value = _apply_section_overlay(base_weights, section_context)
        score = self._compute_score(
            from_t,
            to_t,
            weights=weights,
            section_pair_class_value=pair_class_value,
            soft_camelot=soft_camelot,
        )
        if gate is not None and gate.warnings:
            score.warnings = gate.warnings
        return score
```

`score_all_intents` — new signature + gate:

```python
    def score_all_intents(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        intents: Iterable[TransitionIntent] | None = None,
        *,
        section_context: SectionContext | None = None,
        soft_camelot: bool = False,
    ) -> dict[TransitionIntent, TransitionScore]:
        targets = tuple(intents) if intents is not None else _ALL_INTENTS

        gate = check_hard_constraints(from_t, to_t, soft_camelot=soft_camelot)
        if gate is not None and gate.hard_reject:
            return {intent: gate for intent in targets}

        nm = self._neural.score(from_t, to_t, soft_camelot=soft_camelot)
        bpm = score_bpm(from_t, to_t)
        energy = score_energy(from_t, to_t)
        drums = nm.stem_scores.get(NeuralMixStem.DRUMS, 0.0)
        bass = nm.stem_scores.get(NeuralMixStem.BASS, 0.0)
        harmonics = nm.stem_scores.get(NeuralMixStem.HARMONICS, 0.0)
        vocals = nm.stem_scores.get(NeuralMixStem.VOCALS, 0.0)
        best: NeuralMixTransition | None = nm.best_transition

        warnings = gate.warnings if gate is not None else ()
        out: dict[TransitionIntent, TransitionScore] = {}
        for intent in targets:
            base_weights = INTENT_WEIGHT_MODIFIERS[intent]
            weights, pair_class_value = _apply_section_overlay(base_weights, section_context)
            overall = (
                weights.get("bpm", 0.0) * bpm
                + weights.get("energy", 0.0) * energy
                + weights.get("drums", 0.0) * drums
                + weights.get("bass", 0.0) * bass
                + weights.get("harmonics", 0.0) * harmonics
                + weights.get("vocals", 0.0) * vocals
            )
            out[intent] = TransitionScore(
                bpm=bpm,
                energy=energy,
                drums=drums,
                bass=bass,
                harmonics=harmonics,
                vocals=vocals,
                overall=overall,
                best_transition=best,
                section_pair_class=pair_class_value,
                warnings=warnings,
            )
        return out
```

`score_with_candidates` — new signature + gate:

```python
    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
        *,
        section_context: SectionContext | None = None,
        soft_camelot: bool = False,
    ) -> TransitionScore:
        gate = check_hard_constraints(
            from_t,
            to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
            soft_camelot=soft_camelot,
        )
        if gate is not None and gate.hard_reject:
            return gate

        weights, pair_class_value = _apply_section_overlay(self.weights, section_context)
        score = self._compute_score(
            from_t,
            to_t,
            weights=weights,
            section_pair_class_value=pair_class_value,
            soft_camelot=soft_camelot,
        )
        if gate is not None and gate.warnings:
            score.warnings = gate.warnings
        return score
```

`_compute_score` — new signature + forward:

```python
    def _compute_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        weights: dict[str, float],
        section_pair_class_value: str | None = None,
        soft_camelot: bool = False,
    ) -> TransitionScore:
        nm = self._neural.score(from_t, to_t, soft_camelot=soft_camelot)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/transition/test_scorer.py tests/domain/transition/test_neural_mix.py tests/domain/transition/test_hard_constraints.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/transition/scorer.py app/domain/transition/neural_mix/scorer.py tests/domain/transition/test_scorer.py
git commit -m "feat: scorer merges soft-camelot warnings into TransitionScore"
```

---

### Task 10: Feature 3 — bulk scorer soft mask

**Files:**
- Modify: `app/domain/transition/bulk_scorer.py` (`hard_reject_mask_bulk` line 64, `score_pairs_bulk` line 223)
- Test: `tests/domain/transition/test_bulk_scorer_soft.py` (new)

**Interfaces:**
- Consumes: nothing new.
- Produces: `hard_reject_mask_bulk(fa, ia, ib, *, soft_camelot=False)`; `score_pairs_bulk(fa, pairs, intents, *, soft_camelot=False)`. Consumed by Task 11 (GA `_eager_populate_cache`).

- [ ] **Step 1: Write the failing tests**

Create `tests/domain/transition/test_bulk_scorer_soft.py`:

```python
from __future__ import annotations

import numpy as np

from app.domain.transition.bulk_scorer import (
    extract_feature_arrays,
    hard_reject_mask_bulk,
    score_pairs_bulk,
)
from app.domain.transition.intent import TransitionIntent
from app.shared.features import TrackFeatures


def _tracks() -> list[TrackFeatures]:
    # (0, 12) is a reliable-key Camelot distance >= 5 pair
    return [
        TrackFeatures(bpm=130.0, key_code=0, key_confidence=0.9, integrated_lufs=-10.0),
        TrackFeatures(bpm=130.0, key_code=12, key_confidence=0.9, integrated_lufs=-10.0),
        TrackFeatures(bpm=130.0, key_code=12, key_confidence=0.9, integrated_lufs=-10.0),
    ]


def test_soft_mask_drops_camelot_keeps_compatible() -> None:
    fa = extract_feature_arrays(_tracks())
    ia = np.array([0], dtype=np.int64)
    ib = np.array([1], dtype=np.int64)

    assert hard_reject_mask_bulk(fa, ia, ib)[0] is True
    assert hard_reject_mask_bulk(fa, ia, ib, soft_camelot=True)[0] is False


def test_soft_mask_keeps_bpm_reject() -> None:
    fa = extract_feature_arrays(
        [
            TrackFeatures(bpm=120.0, key_code=8, key_confidence=0.9, integrated_lufs=-10.0),
            TrackFeatures(bpm=140.0, key_code=8, key_confidence=0.9, integrated_lufs=-10.0),
        ]
    )
    ia = np.array([0], dtype=np.int64)
    ib = np.array([1], dtype=np.int64)
    assert hard_reject_mask_bulk(fa, ia, ib, soft_camelot=True)[0] is True


def test_score_pairs_bulk_soft_scores_camelot_pair() -> None:
    fa = extract_feature_arrays(_tracks())
    pairs = [(0, 1)]
    strict = score_pairs_bulk(fa, pairs, [TransitionIntent.MAINTAIN])
    soft = score_pairs_bulk(
        fa, pairs, [TransitionIntent.MAINTAIN], soft_camelot=True
    )
    key = (0, 1, TransitionIntent.MAINTAIN.value)
    assert strict[key] == 0.0
    assert soft[key] > 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/transition/test_bulk_scorer_soft.py -v`
Expected: FAIL — `hard_reject_mask_bulk() got an unexpected keyword argument 'soft_camelot'`.

- [ ] **Step 3: Implement**

`app/domain/transition/bulk_scorer.py`:

```python
def hard_reject_mask_bulk(
    fa: FeatureArrays, ia: IntArr, ib: IntArr, *, soft_camelot: bool = False
) -> BoolArr:
    settings = get_settings().transition
    ...
    if soft_camelot:
        return bpm_violates | lufs_violates
    return bpm_violates | key_violates | lufs_violates
```

`score_pairs_bulk` — add the flag and forward:

```python
def score_pairs_bulk(
    fa: FeatureArrays,
    pairs: Sequence[tuple[int, int]],
    intents: Iterable[TransitionIntent],
    *,
    soft_camelot: bool = False,
) -> dict[tuple[int, int, str], float]:
    ...
    rejected = hard_reject_mask_bulk(fa, ia, ib, soft_camelot=soft_camelot)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/transition/test_bulk_scorer_soft.py tests/domain/transition/test_bulk_scorer_parity.py -v`
Expected: PASS (new tests + parity unchanged — parity uses strict defaults).

- [ ] **Step 5: Commit**

```bash
git add app/domain/transition/bulk_scorer.py tests/domain/transition/test_bulk_scorer_soft.py
git commit -m "feat: soft_camelot on vectorised hard-reject mask"
```

---

### Task 11: Feature 3 — optimizers + lifespan accept `soft_camelot`

**Files:**
- Modify: `app/domain/optimization/genetic.py`
- Modify: `app/domain/optimization/greedy.py`
- Modify: `app/domain/optimization/constructive.py`
- Modify: `app/domain/optimization/fitness.py`
- Modify: `app/server/lifespan.py` (`scoring_lifespan`, lines 240-252)
- Test: `tests/domain/optimization/test_genetic.py`, `tests/domain/optimization/test_greedy.py`, `tests/domain/optimization/test_constructive.py`

**Interfaces:**
- Consumes: `check_hard_constraints(..., soft_camelot=)` (Task 8), `score_pairs_bulk(..., soft_camelot=)` / `scorer.score_all_intents(..., soft_camelot=)` (Tasks 9-10).
- Produces: `GeneticAlgorithm(scorer, ..., soft_camelot=False)`, `GreedyChainBuilder(scorer, *, soft_camelot=False)`, `ConstructiveSlotBuilder(scorer, *, beam_width=..., slot_candidates=..., soft_camelot=False)`; `optimizer_builder(*, algorithm, scorer, soft_camelot=False)` in lifespan. Consumed by Task 12.

- [ ] **Step 1: Write the failing tests**

Append to `tests/domain/optimization/test_genetic.py` (read the file first to match its fixtures — the helper below builds a minimal soft-mode pair):

```python
def test_genetic_precompute_reject_mask_soft_omits_camelot() -> None:
    from app.domain.optimization.genetic import GeneticAlgorithm
    from app.shared.features import TrackFeatures

    tracks = [
        TrackFeatures(bpm=130.0, key_code=0, key_confidence=0.9, integrated_lufs=-10.0),
        TrackFeatures(bpm=130.0, key_code=12, key_confidence=0.9, integrated_lufs=-10.0),
    ]
    idx_map = {0: 0, 1: 1}
    strict = GeneticAlgorithm._precompute_reject_mask(tracks, [0, 1], idx_map)
    soft = GeneticAlgorithm._precompute_reject_mask(
        tracks, [0, 1], idx_map, soft_camelot=True
    )
    assert (0, 1) in strict
    assert (0, 1) not in soft
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/optimization/test_genetic.py -k soft -v`
Expected: FAIL — `_precompute_reject_mask() got an unexpected keyword argument 'soft_camelot'`.

- [ ] **Step 3: Implement**

`app/domain/optimization/genetic.py`:

- Constructor: add `soft_camelot: bool = False` param and `self.soft_camelot = soft_camelot`.
- `_precompute_reject_mask` — make it an instance-unaware static still, but add the kwarg and use `.hard_reject`:

```python
    @staticmethod
    def _precompute_reject_mask(
        tracks: list[TrackFeatures],
        active_ids: list[int],
        idx_map: dict[int, int],
        *,
        soft_camelot: bool = False,
    ) -> set[tuple[int, int]]:
        reject: set[tuple[int, int]] = set()
        indices = [idx_map[tid] for tid in active_ids]
        for i, idx_a in enumerate(indices):
            a = tracks[idx_a]
            for idx_b in indices[i + 1 :]:
                b = tracks[idx_b]
                gate_ab = check_hard_constraints(a, b, soft_camelot=soft_camelot)
                if gate_ab is not None and gate_ab.hard_reject:
                    reject.add((idx_a, idx_b))
                gate_ba = check_hard_constraints(b, a, soft_camelot=soft_camelot)
                if gate_ba is not None and gate_ba.hard_reject:
                    reject.add((idx_b, idx_a))
        return reject
```

- In `optimize`, the call site becomes:

```python
        reject_mask = self._precompute_reject_mask(
            tracks, active_ids, idx_map, soft_camelot=self.soft_camelot
        )
```

- In `_eager_populate_cache`, forward to the two bulk/scalar calls:

```python
            bulk = score_pairs_bulk(
                fa, generic_pairs, _PRECOMPUTE_INTENTS, soft_camelot=self.soft_camelot
            )
```

and

```python
            scores = self.scorer.score_all_intents(
                tracks[idx_a],
                tracks[idx_b],
                _PRECOMPUTE_INTENTS,
                section_context=section_context,
                soft_camelot=self.soft_camelot,
            )
```

- `_fitness` — forward into `compute_fitness`:

```python
        return compute_fitness(
            self.scorer,
            tracks,
            order,
            idx_map,
            template,
            moods,
            score_cache=score_cache,
            reject_mask=reject_mask,
            soft_camelot=self.soft_camelot,
        )
```

`app/domain/optimization/fitness.py`:

- `transition_quality` — add `soft_camelot: bool = False`, forward into both `scorer.score(...)` calls:

```python
                score = scorer.score(
                    a,
                    b,
                    intent=context.intent,
                    section_context=context.section_context,
                    soft_camelot=soft_camelot,
                )
```

and

```python
            score = scorer.score(
                a,
                b,
                intent=context.intent,
                section_context=context.section_context,
                soft_camelot=soft_camelot,
            )
```

- `compute_fitness` — add `soft_camelot: bool = False` and forward:

```python
    trans = transition_quality(
        scorer,
        tracks,
        order,
        idx_map,
        template=template,
        score_cache=score_cache,
        reject_mask=reject_mask,
        soft_camelot=soft_camelot,
    )
```

`app/domain/optimization/greedy.py`:

- Constructor: `def __init__(self, scorer: TransitionScorer, *, soft_camelot: bool = False) -> None:` + `self.soft_camelot = soft_camelot`.
- `optimize` — forward into the `self.scorer.score(...)` call (add `soft_camelot=self.soft_camelot`) and the final `compute_fitness(...)` call (add `soft_camelot=self.soft_camelot`).

`app/domain/optimization/constructive.py`:

- Constructor: `def __init__(self, scorer, *, beam_width=..., slot_candidates=..., soft_camelot: bool = False)` + `self.soft_camelot = soft_camelot`.
- `_transition_score` — add `soft_camelot=self.soft_camelot` to `self.scorer.score(...)`.
- `optimize` final `compute_fitness(...)` — add `soft_camelot=self.soft_camelot`.

`app/server/lifespan.py` — `scoring_lifespan`:

```python
    def optimizer_builder(
        *, algorithm: str, scorer: TransitionScorer, soft_camelot: bool = False
    ) -> Any:
        if algorithm == "constructive":
            return ConstructiveSlotBuilder(scorer=scorer, soft_camelot=soft_camelot)
        if algorithm == "greedy":
            return GreedyChainBuilder(scorer=scorer, soft_camelot=soft_camelot)
        return GeneticAlgorithm(scorer=scorer, soft_camelot=soft_camelot)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/optimization/ -v`
Expected: PASS (new test + existing GA/greedy/constructive tests — defaults keep strict behaviour).

- [ ] **Step 5: Commit**

```bash
git add app/domain/optimization/genetic.py app/domain/optimization/greedy.py app/domain/optimization/constructive.py app/domain/optimization/fitness.py app/server/lifespan.py tests/domain/optimization/test_genetic.py
git commit -m "feat: optimizers + lifespan forward soft_camelot"
```

---

### Task 12: Feature 3 — `sequence_optimize(camelot_mode)` + update test fakes

**Files:**
- Modify: `app/tools/compute/sequence_optimize.py`
- Modify (test fakes): `tests/tools/compute/test_sequence_optimize_constructive.py`, `tests/tools/compute/test_sequence_optimize_auto_algorithm.py`, `tests/tools/compute/test_sequence_optimize_missing_features.py`, `tests/tools/compute/test_template_validation.py`
- Test: `tests/tools/compute/test_sequence_optimize_camelot.py` (new)

**Interfaces:**
- Consumes: `optimizer_builder(*, algorithm, scorer, soft_camelot=)` (Task 11).
- Produces: `sequence_optimize(..., camelot_mode="strict"|"soft")` — default `"strict"` forwards `soft_camelot=False`; `"soft"` forwards `True`.

- [ ] **Step 1: Write the failing tests**

Create `tests/tools/compute/test_sequence_optimize_camelot.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


def _capturing_builder(captured: dict[str, object]) -> object:
    def fake_optimizer_builder(
        *, algorithm: str, scorer: object, soft_camelot: bool = False
    ) -> object:
        captured["soft_camelot"] = soft_camelot
        result = MagicMock()
        result.track_order = [1, 2]
        result.quality_score = 0.5
        result.generations = 0
        return MagicMock(optimize=lambda **kw: result)

    return fake_optimizer_builder


@pytest.mark.asyncio
async def test_camelot_mode_soft_forwards_true() -> None:
    captured: dict[str, object] = {}
    out = await sequence_optimize(
        track_ids=[1, 2],
        camelot_mode="soft",
        uow=_uow_with_features({1: TrackFeatures(bpm=130.0), 2: TrackFeatures(bpm=132.0)}),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["soft_camelot"] is True
    assert out.track_order == [1, 2]


@pytest.mark.asyncio
async def test_camelot_mode_default_strict() -> None:
    captured: dict[str, object] = {}
    await sequence_optimize(
        track_ids=[1, 2],
        uow=_uow_with_features({1: TrackFeatures(bpm=130.0), 2: TrackFeatures(bpm=132.0)}),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["soft_camelot"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/compute/test_sequence_optimize_camelot.py -v`
Expected: FAIL — `unexpected keyword argument 'camelot_mode'`.

- [ ] **Step 3: Implement**

In `app/tools/compute/sequence_optimize.py`, add the parameter (after `energy_arc`):

```python
    camelot_mode: Annotated[
        Literal["strict", "soft"],
        Field(
            description=(
                "``'strict'`` (default) hard-rejects a Camelot distance >= "
                "the threshold. ``'soft'`` downgrades it to a warning in "
                "TransitionScore.warnings — BPM/energy hard rejects stay active."
            )
        ),
    ] = "strict",
```

Forward it to the builder (replace line ~198):

```python
    optimizer = optimizer_builder(
        algorithm=resolved_algorithm,
        scorer=scorer,
        soft_camelot=camelot_mode == "soft",
    )
```

- [ ] **Step 4: Update existing test fakes to accept the new kwarg**

Every `def fake_optimizer_builder(*, algorithm: str, scorer: object)` definition across `tests/tools/compute/` must become `(*, algorithm: str, scorer: object, soft_camelot: bool = False)`. Find them all:

Run: `rg -l "def fake_optimizer_builder" tests/tools/compute/`

Edit each of the 4 files (`test_sequence_optimize_constructive.py`, `test_sequence_optimize_auto_algorithm.py`, `test_sequence_optimize_missing_features.py`, `test_template_validation.py`), plus `_capturing_builder` in `test_sequence_optimize_auto_algorithm.py`, to add the `soft_camelot: bool = False` keyword parameter.

- [ ] **Step 5: Run the full compute test suite**

Run: `uv run pytest tests/tools/compute/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/tools/compute/sequence_optimize.py tests/tools/compute/test_sequence_optimize_camelot.py tests/tools/compute/test_sequence_optimize_constructive.py tests/tools/compute/test_sequence_optimize_auto_algorithm.py tests/tools/compute/test_sequence_optimize_missing_features.py tests/tools/compute/test_template_validation.py
git commit -m "feat: sequence_optimize camelot_mode strict|soft"
```

---

### Task 13: Feature 2+3 — end-to-end + full gate

**Files:**
- Test: `tests/tools/compute/test_sequence_optimize_peak_time_soft.py` (new)

**Interfaces:**
- Consumes: everything from Tasks 5-12.

- [ ] **Step 1: Write the combined integration test**

Create `tests/tools/compute/test_sequence_optimize_peak_time_soft.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


def _pool() -> dict[int, TrackFeatures]:
    energies = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    return {
        100 + i: TrackFeatures(bpm=130.0, energy_mean=e, key_code=None, integrated_lufs=-12.0)
        for i, e in enumerate(energies)
    }


@pytest.mark.asyncio
async def test_peak_time_arc_with_soft_camelot() -> None:
    out = await sequence_optimize(
        track_ids=[100, 101, 102, 103, 104, 105],
        energy_arc="peak_time",
        camelot_mode="soft",
        uow=_uow_with_features(_pool()),
        scorer=MagicMock(),
        optimizer_builder=MagicMock(),
    )
    assert out.algorithm == "peak_time"
    assert len(out.track_order) == 6
    assert set(out.track_order) == {100, 101, 102, 103, 104, 105}
    assert 0.0 <= out.quality_score <= 1.0
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/tools/compute/test_sequence_optimize_peak_time_soft.py -v`
Expected: PASS.

- [ ] **Step 3: Full gate**

Run: `make check`
Expected: ruff + mypy strict + pytest + import-linter all PASS.

If mypy complains about the `object()` used for `request` in `test_persist_plan_reports_phrase_align_true` (`getattr(request, "subgenre", None)` is fine on `object`), switch the test to a `SimpleNamespace(subgenre=None, transition_bars=None, body_bars=None)` instead.

- [ ] **Step 4: Commit**

```bash
git add tests/tools/compute/test_sequence_optimize_peak_time_soft.py
git commit -m "test: sequence_optimize energy_arc + camelot_mode integration"
```

---

## Self-Review

**Spec coverage:**
- Feature 1 (phrase-align): data already stored ✓; TrackInput fields ✓ (Task 1); repo read ✓ (Task 1); `snap_trim_to_phrase` pure helper ✓ (Task 2); `place_segments` snap ✓ (Task 3); `_persist_plan` `phrase_align` ✓ (Task 4); diagnose structural report ✓ (Task 4). Acceptance: whole-bar ✓, non-whole-bar rejected ✓, no-boundaries no-op ✓, kick phase preserved (whole-bar rule) ✓.
- Feature 2 (micro-arc): `peak_only_arc` factory + ARC_PRESETS ✓ (Task 5); PEAK_ONLY energy curve rise-peak-ease ✓ (Task 5); `sequence_optimize(energy_arc="peak_time")` via `fit_tracks_to_arc` ✓ (Task 6); `TrackCandidate` built from `get_scoring_features_batch` features ✓ (Task 6); default path unchanged ✓ (guard: branch only fires on `"peak_time"`). Acceptance: energy peaks near 75% ✓ (test); order follows curve ✓ (tests); default unchanged ✓ (existing tests).
- Feature 3 (soft Camelot): `TransitionScore.warnings` ✓ (Task 7); spec `check(soft)` tuple ✓ (Task 7); chain collects warnings, no hard reject on soft ✓ (Task 8); `check_hard_constraints` forwards ✓ (Task 8); scorer `score/score_all_intents/score_with_candidates` forward + merge ✓ (Task 9); GA `_precompute_reject_mask` skips camelot on soft ✓ (Task 11); `bulk_scorer.hard_reject_mask_bulk` drops `key_violates` ✓ (Task 10); optimizers + lifespan accept flag ✓ (Task 11); `sequence_optimize(camelot_mode)` ✓ (Task 12). Acceptance: strict unchanged (byte-for-byte — all soft branches default-off; parity tests keep strict defaults) ✓; soft pair scores + carries warning + GA mask omits it ✓; BPM/energy rejects active in soft ✓ (tests).
- Testing section: all listed cases covered across tasks; full gate ✓ (Task 13).

**Placeholder scan:** No TBDs — every step has real code + exact commands.

**Type consistency:** `snap_trim_to_phrase` signature identical across Tasks 2-3; `phrase_aligned`/`phrase_align_count` consistent Tasks 3-4; `check_hard_constraints(..., soft_camelot=)` consistent Tasks 8-11; `score_pairs_bulk(..., soft_camelot=)` consistent Tasks 10-11; `optimizer_builder(*, algorithm, scorer, soft_camelot=False)` consistent Tasks 11-12; `energy_arc`/`camelot_mode` consistent Tasks 6/12-13. `SequenceOptimizeResult.algorithm` Literal extended once (Task 6) and used by arc path.

**Risk notes:** `NeuralMixScorer.score` needed the soft flag (unlisted in spec but required — otherwise `_compute_score` reads `stem_scores` from a rejection object in soft mode). Test fakes in `tests/tools/compute/` need the `soft_camelot` kwarg (Task 12). `make check` mypy note for `object()` request in Task 4 test handled in Task 13 step 3.
