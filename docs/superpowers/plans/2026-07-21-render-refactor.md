# Render Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the `render_mixdown` + `render_beatgrid` subsystem to remove dead code, kill DRY/SRP violations, fix the audio→domain layer inversion, and add `RenderMode`/`RenderRequest` seams — all while preserving the MCP tool surface (`@tool`-decorated signatures, tags, descriptions) and ~95% of the existing tests.

**Architecture:** Strategy + Template Method (kept) on the filtergraph, plus a new `RenderOrchestrator` (4 injected collaborators) that replaces the 169-line monolithic `render_mixdown_handler`. `RenderPlanBuilder` + `build_*_render_plan` collapse into one `RenderPlanner` driven by a `RenderMode` enum + `SegmentFactory`. `RenderRequest` Parameter Object kills the 14-arg pass-through across three layers. Dead code (twelve_deck / multi_deck / stem_matrix / stem_matrix / build_preprocess_cmd) is deleted.

**Tech Stack:** Python 3.12, FastMCP 3.2.4-3.3.x, Pydantic 2.x, SQLAlchemy 2.x, librosa/scipy/ffmpeg. No new deps.

## Global Constraints

- **Run everything via `uv`** (AGENTS.md): `uv run pytest`, `uv run ruff check`, `uv run mypy`, `make check`. Never call `python`/`pytest`/`ruff`/`mypy` directly.
- **MCP tool surface frozen**: do NOT touch `@tool(...)` decorators, their `name` / `tags` / `description` / parameter Annotated[...] shapes / Field descriptions. The thin `app/handlers/render_mixdown.py` signatures stay byte-identical.
- **ruff line-length=99** (pyproject); mypy strict mode is on (gate expects zero errors). Every new public symbol must have type hints.
- **No new comments unless asked**; code style follows `__future__ annotations` + frozen dataclass slots pattern already used.
- **gitnexus workflow**: before modifying a public symbol (`RenderPlanBuilder`, `build_render_plan`, `build_stem_render_plan`, `RenderPlan.from_settings`, `select_strategy`, `run_render`, `render_mixdown_handler`, `render_beatgrid_handler`, `StemResolver`), run `gitnexus_impact({target, direction:"upstream"})` and warn if risk is HIGH/CRITICAL. After each commit run `gitnexus_detect_changes()` to verify scope.
- **Commits per task** (`uv run` for any quality gate):
  ```bash
  git add <files> && git commit -m "<type>: <subject>"
  ```
- **Test patch targets move**: `app.handlers.render_beatgrid.detect_kick_trim` → `app.handlers._orchestrator.beatgrid_provider.detect_kick_trim`; `app.handlers.render_mixdown.run_render` → `app.handlers._orchestrator.render_executor.run_render`; `app.handlers.render_mixdown.scan_mix` → `app.handlers._orchestrator.render_executor.scan_mix`. Plan tasks update these paths explicitly.

---

## File Structure

```
app/domain/render/
  __init__.py                       # updated exports
  models.py                         # +RenderMode enum; RenderPlan +mode field, from_settings(request, ...)
  request.py                        # NEW — RenderRequest Parameter Object
  bar_plan.py                       # NEW — BarPlan dataclass + BarPlanner (one-pass, dict-override)
  beatgrid.py                        # NEW — BeatgridEntry.clamp/flags/to_row/from_row, BeatgridLimits, BeatgridIO
  segments.py                        # NEW — SegmentFactory Protocol + ClassicSegmentFactory / StemSegmentFactory
  plan_assembler.py                  # NEW — RenderPlanner (replaces plan_builder.py + build_*_render_plan)
  stem_voicing.py                    # NEW — StemVoicing dataclass + STEM_VOICING constant
  effects_resolver.py                # NEW — ResolvedEffects + EffectPresetResolver
  timeline.py                        # slimmed: place_segments + timeline_windows only (no build_*_render_plan)
  filtergraph.py                     # decomposed: _FrameContext + _source_chain/_echo_split/_band_split/_fade_*/_mix_segment
  runner.py                          # MOVED from app/audio/render/runner.py; build_preprocess_cmd DROPPED
  graph.py / stem_graph.py           # facades unchanged
  multi_deck.py                      # DELETED (dead)
  stem_matrix.py                     # DELETED (dead)
  twelve_deck.py                     # DELETED (dead)
  plan_builder.py                    # DELETED (absorbed by plan_assembler.py)
  bar_planner.py                    # DELETED (renamed to bar_plan.py)

app/audio/render/
  __init__.py                        # drop runner re-export if any
  kick_phase.py                      # unchanged
  phase_refine.py                    # unchanged
  diagnostics.py                     # unchanged
  runner.py                          # DELETED (moved to domain/render/runner.py)

app/handlers/
  render_mixdown.py                  # thin: ~10 lines, calls RenderOrchestrator
  render_beatgrid.py                 # thin: ~6 lines, calls BeatgridProvider
  _stem_resolver.py                  # DELETED (moved to _orchestrator/stem_resolver.py)
  _orchestrator/
    __init__.py
    render_orchestrator.py           # NEW — RenderOrchestrator (DI of 4 collaborators)
    beatgrid_provider.py             # NEW — ensure/load/compute
    preset_applier.py                # NEW — SubgenrePresetApplier
    stem_resolver.py                 # MOVED from _stem_resolver.py
    render_executor.py               # NEW — RENDER_JOBS + run_render + scan_mix + RenderMixdownResult
```

---

## Task 1: Delete dead code (twelve_deck, multi_deck, stem_matrix)

**Files:**
- Delete: `app/domain/render/twelve_deck.py`
- Delete: `app/domain/render/multi_deck.py`
- Delete: `app/domain/render/stem_matrix.py`
- Modify: `app/domain/render/__init__.py` — remove any exports referencing deleted modules (none currently re-export these symbols; verify first).
- Test: no tests exist for these modules (grep-confirmed).

**Interfaces:**
- Consumes: none.
- Produces: clean domain/render dir with no dead ~850 lines.

- [ ] **Step 1: Verify no live imports**

Run: `grep -rn "twelve_deck\|multi_deck\|stem_matrix\|StemMatrixTimeline\|MultiDeckRenderPlan\|TwelveDeckPlan" app/ tests/ --include='*.py' | grep -v "app/domain/multi_deck/\|app/tools/multi_deck/\|app/domain/render/twelve_deck\|app/domain/render/multi_deck\|app/domain/render/stem_matrix"`
Expected: zero hits outside the three files being deleted.

- [ ] **Step 2: Delete the three files**

```bash
git rm app/domain/render/twelve_deck.py app/domain/render/multi_deck.py app/domain/render/stem_matrix.py
```

- [ ] **Step 3: Verify lint + import-linter pass**

Run: `uv run ruff check app/domain/render/ && uv run mypy app/domain/render/ 2>&1 | tail -5`
Expected: ruff clean; mypy no new errors (deleted files had `subprocess`/`os` imports otherwise unused; removing them may even resolve existing warnings).

- [ ] **Step 4: Run full test gate**

Run: `uv run pytest -x -q`
Expected: PASS (no test references the deleted symbols).

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(render): delete dead twelve_deck/multi_deck/stem_matrix code

~850 lines of unused render code (zero imports in app/ or tests/).
twelve_deck had buggy tempo=1.0 stubs; stem_matrix had desynced STEM_TYPES.
Gate: ruff + mypy + pytest clean."
```

---

## Task 2: Add `RenderMode` enum + `mode` field on `RenderPlan`

**Files:**
- Modify: `app/domain/render/models.py:91-200` — add `RenderMode` enum, add `mode` field on `RenderPlan`, update `from_settings` signature to accept `RenderRequest` (but keep the classmethod-default for `mode` backward-compat in this task; later tasks finalize).
- Modify: `app/domain/render/__init__.py` — export `RenderMode`.
- Modify: `app/domain/render/filtergraph.py:374-376` — switch `select_strategy` to `plan.mode`.
- Test: `tests/domain/render/test_models.py` — add `test_render_plan_carries_mode`.
- Test: `tests/domain/render/test_graph.py`, `test_bass_swap.py`, `test_eq_ritual.py`, `test_runner.py`, `test_stem_graph.py` — every direct `RenderPlan(...)` constructor call needs `mode=RenderMode.CLASSIC` (or STEM) kwarg. These are only in tests — fix them.

**Interfaces:**
- Produces: `app.domain.render.models.RenderMode` enum with `CLASSIC="classic"` and `STEM="stem"`.

**Pre-step (GitNexus):**

- [ ] **Step 0a: Impact analysis on RenderPlan**

Run `gitnexus_impact({target: "RenderPlan", direction: "upstream"})`. Note the consumers list — expect `build_render_plan`, `build_stem_render_plan`, `RenderPlanBuilder`, `select_strategy`, `ClassicGraphBuilder._segment_block`, test files.

- [ ] **Step 1: Write the failing test**

Edit `tests/domain/render/test_models.py`:

```python
from app.domain.render.models import RenderMode
# ... existing imports ...


def test_render_plan_carries_mode():
    seg = TrackSegment(
        index=0, track_id=1, file_path="/x.mp3", tempo_ratio=1.0,
        trim_start_s=0.4, gain_db=0.0, body_bars=24,
        d_in_s=0.0, d_out_s=59.0, length_s=103.0, start_s=0.0,
    )
    plan = RenderPlan(
        mode=RenderMode.CLASSIC,
        target_bpm=130.0,
        xsplit_low_hz=250,
        xsplit_high_hz=4000,
        eq_phase_1_ratio=0.40,
        eq_phase_2_ratio=0.70,
        low_swap_beats=1.0,
        outro_fade_bars=12,
        limiter_ceiling=0.85,
        segments=[seg],
    )
    assert plan.mode is RenderMode.CLASSIC
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_models.py::test_render_plan_carries_mode -v`
Expected: FAIL — `RenderMode` not imported / `mode` kwarg not accepted.

- [ ] **Step 3: Add enum + mode field**

Edit `app/domain/render/models.py`. After the `STEM_ORDER` constant block (lines ~13) add the enum:

```python
from enum import Enum

class RenderMode(str, Enum):
    CLASSIC = "classic"
    STEM = "stem"
```

On `RenderPlan` (dataclass at line ~91), add a new first field (after the docstring, before `target_bpm`):

```python
    mode: RenderMode = RenderMode.CLASSIC
```

(Make `mode` default to CLASSIC so existing constructor calls without `mode=` still work during this transition task.)

- [ ] **Step 4: Update select_strategy to use plan.mode**

Edit `app/domain/render/filtergraph.py:374-376`:

```python
def select_strategy(plan: RenderPlan) -> RenderStrategy:
    """Pick the render strategy via the plan's explicit mode."""
    return {
        RenderMode.CLASSIC: ClassicEqStrategy(),
        RenderMode.STEM: StemMultiDeckStrategy(),
    }[plan.mode]
```

Add `from app.domain.render.models import RenderMode` to the imports at top of filtergraph.py.

- [ ] **Step 5: Export RenderMode**

Edit `app/domain/render/__init__.py`: add `RenderMode` to the import from `.models` block AND to `__all__`.

- [ ] **Step 6: Fix existing tests' RenderPlan constructor calls**

Edit each test file (grep to find them). Add `mode=RenderMode.CLASSIC` to every `RenderPlan(...)`. Update the import to include `RenderMode`:

```bash
grep -rln "RenderPlan(" tests/
```

Edit the matching files (`tests/audio/render/test_runner.py`, `tests/audio/render/test_bass_swap.py`, `tests/audio/render/test_eq_ritual.py`, `tests/domain/render/test_graph.py`) — add `from app.domain.render.models import RenderMode` (extend existing import) and `mode=RenderMode.CLASSIC,` to each `RenderPlan(...)`.

For `tests/domain/render/test_stem_graph.py`: its `_stem_plan` helper calls `build_stem_render_plan(...)`, not `RenderPlan(...)` directly — leave for Task 4.

- [ ] **Step 7: Run all tests**

Run: `uv run pytest tests/domain/render/ tests/audio/render/ -v`
Expected: PASS — all 17 tests green (including new `test_render_plan_carries_mode`).

- [ ] **Step 8: Run full gate**

Run: `make check`
Expected: PASS (ruff + mypy + pytest + import-linter).

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "refactor(render): add RenderMode enum + plan.mode field

select_strategy now dispatches by plan.mode instead of 'stem_segments is not None'.
Backward-compat: mode defaults to CLASSIC so existing RenderPlan(...) calls still work.
Gate: make check PASS."
```

---

## Task 3: Add `RenderRequest` Parameter Object

**Files:**
- Create: `app/domain/render/request.py`
- Modify: `app/domain/render/__init__.py` — export `RenderRequest`.
- Test: `tests/domain/render/test_request.py` (new).

**Interfaces:**
- Produces:
  - `app.domain.render.request.RenderRequest` frozen dataclass with fields/properties per spec.
  - `RenderRequest.mode -> RenderMode` property.
  - `RenderRequest.out_filename -> str` property.

- [ ] **Step 1: Write the failing test**

Create `tests/domain/render/test_request.py`:

```python
from app.config import get_settings
from app.domain.render.models import RenderMode
from app.domain.render.request import RenderRequest


def _base():
    return dict(version_id=1, workspace="/tmp/ws", timestamp="20260101-000000")


def test_mode_classic_when_stem_false():
    req = RenderRequest(stem=False, **_base())
    assert req.mode is RenderMode.CLASSIC


def test_mode_stem_when_stem_true():
    req = RenderRequest(stem=True, **_base())
    assert req.mode is RenderMode.STEM


def test_out_filename_default_uses_settings():
    req = RenderRequest(**_base())
    assert req.out_filename == get_settings().render.mix_filename


def test_out_filename_explicit_out_name_wins():
    req = RenderRequest(out_name="custom.mp3", **_base())
    assert req.out_filename == "custom.mp3"


def test_render_request_is_frozen():
    req = RenderRequest(**_base())
    try:
        req.version_id = 2
    except Exception:
        return
    raise AssertionError("RenderRequest should be frozen")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_request.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement RenderRequest**

Create `app/domain/render/request.py`:

```python
"""RenderRequest — Parameter Object bundling all per-render knobs.

Replaces the 14-kwarg pass-through chain tool → handler → builder → timeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.domain.render.models import RenderMode


@dataclass(frozen=True, slots=True)
class RenderRequest:
    version_id: int
    workspace: str
    timestamp: str
    out_name: str | None = None
    transition_bars: int | None = None
    body_bars: int | None = None
    refresh_grid: bool = False
    stem: bool = True
    subgenre: str | None = None
    filter_sweep: str | None = None
    echo: str | None = None
    crossfade_curve_out: str = "tri"
    crossfade_curve_in: str = "exp"
    reverb: str | None = None
    reverb_mix: float = 0.25

    @property
    def mode(self) -> RenderMode:
        return RenderMode.STEM if self.stem else RenderMode.CLASSIC

    @property
    def out_filename(self) -> str:
        return self.out_name or get_settings().render.mix_filename
```

- [ ] **Step 4: Export from package**

Edit `app/domain/render/__init__.py`: add `from app.domain.render.request import RenderRequest` and add `RenderRequest` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/domain/render/test_request.py -v`
Expected: PASS — 5 tests.

- [ ] **Step 6: Run full gate**

Run: `make check`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(render): add RenderRequest Parameter Object

Bundles all per-render knobs (mode dispatch, effects, presets). Will replace
the 14-arg pass-through tool→handler→builder→timeline in later tasks.
Gate: make check PASS."
```

---

## Task 4: `BarPlan` + `BarPlanner` cleanup (one-pass, named result)

**Files:**
- Create: `app/domain/render/bar_plan.py`
- Delete: `app/domain/render/bar_planner.py`
- Modify: `app/domain/render/__init__.py` — export `BarPlan` (was `BarPlanner`, stays exported from new module).
- Modify: `app/handlers/render_mixdown.py:11` — import `BarPlanner` from `bar_plan` instead of `bar_planner`.
- Test: `tests/domain/render/test_bar_plan.py` (new).
- Test: `tests/handlers/test_render_mixdown.py` — currently consumes `BarPlanner(...).compute(...)` returning a tuple. After this task `.compute()` returns `BarPlan`; the handler still unpacks via attribute access? Set up the handler change in Task 9 — for now, keep the return as a `BarPlan` namedtuple-like with tuple-protocol compat (`__iter__` to yield `(transition_bars, body_bars)`), so the existing handler unpacking `per_transition, per_body = planner.compute(...)` keeps working.

**Interfaces:**
- Produces: `app.domain.render.bar_plan.BarPlan` frozen dataclass with `transition_bars: tuple[int, ...]` and `body_bars: list[int]`, plus `__iter__` yielding `(transition_bars, body_bars)` for back-compat unpacking.
- Produces: `app.domain.render.bar_plan.BarPlanner` with `compute(...) -> BarPlan`.

**Pre-step (GitNexus):**

- [ ] **Step 0a: Impact analysis on BarPlanner.compute**

Run `gitnexus_impact({target: "BarPlanner.compute", direction: "upstream"})`. Note consumers — expect only `render_mixdown_handler` + test references.

- [ ] **Step 1: Write the failing test**

Create `tests/domain/render/test_bar_plan.py`:

```python
from types import SimpleNamespace

from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan, BarPlanner
from app.domain.render.models import BeatgridEntry


def _inputs(n, *, duration_ms=None):
    return [
        SimpleNamespace(
            track_id=i,
            mood="hypnotic_techno",
            bpm=130.0,
            duration_ms=duration_ms,
            tempo_ratio=lambda t: t / 130.0,
        )
        for i in range(n)
    ]


def _grid(n):
    return {
        i: BeatgridEntry(
            track_id=i, trim_start_s=0.5, refined_trim_s=0.5, gain_db=0.0, phase_ms=0.0
        )
        for i in range(n)
    }


def test_bar_plan_holds_transition_and_body():
    plan = BarPlan(transition_bars=(16, 32), body_bars=[24, 32, 24])
    assert plan.transition_for(0) == 16
    assert plan.transition_for(1) == 32
    assert plan.body_for(0) == 24
    assert plan.body_for(2) == 24
    assert len(plan) == 3


def test_bar_plan_iter_unpacks_to_tuple_for_backcompat():
    plan = BarPlan(transition_bars=(16,), body_bars=[24, 24])
    per_t, per_b = plan
    assert per_t == (16,)
    assert per_b == [24, 24]


def test_compute_single_pass_returns_bar_plan():
    s = RenderSettings()
    plan = BarPlanner(s).compute(_inputs(1), _grid(1))
    assert isinstance(plan, BarPlan)
    assert plan.transition_bars == ()
    assert plan.body_bars == [24]


def test_compute_transition_bars_per_pair():
    s = RenderSettings()
    plan = BarPlanner(s).compute(_inputs(3), _grid(3))
    assert len(plan.transition_bars) == 2


def test_compute_overrides_apply_to_all():
    s = RenderSettings()
    plan = BarPlanner(s).compute(
        _inputs(3), _grid(3), transition_override=8, body_override=16
    )
    assert plan.transition_bars == (8, 8)
    assert plan.body_bars == [16, 16, 16]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_bar_plan.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement bar_plan.py**

Create `app/domain/render/bar_plan.py`:

```python
"""Bar-amount planning per track on the timeline.

Replaces app/domain/render/bar_planner.py with a one-pass implementation
returning a named :class:`BarPlan` (was a bare ``tuple[list[int], list[int]]``).
``__iter__`` preserves the legacy ``per_t, per_b = planner.compute(...)`` unpack.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.config.render import RenderSettings
from app.domain.render.models import BeatgridEntry
from app.domain.transition.subgenre_rules import (
    body_bars_for_pair,
    classify_pair,
    transition_bars_for_pair,
)
from app.shared.constants import TechnoSubgenre


@dataclass(frozen=True, slots=True)
class BarPlan:
    """Per-track bar counts."""
    transition_bars: tuple[int, ...]
    body_bars: list[int]

    def __len__(self) -> int:
        return len(self.body_bars)

    def transition_for(self, i: int) -> int:
        return self.transition_bars[i]

    def body_for(self, i: int) -> int:
        return self.body_bars[i]

    def __iter__(self) -> Iterator[tuple[int, int] | tuple[int, ...] | list[int]]:
        # Back-compat for unpacking: ``t, b = plan``.
        yield self.transition_bars
        yield self.body_bars


class BarPlanner:
    def __init__(self, settings: RenderSettings) -> None:
        self._settings = settings

    def compute(
        self,
        inputs: list[Any],
        grid: dict[int, BeatgridEntry],
        *,
        transition_override: int | None = None,
        body_override: int | None = None,
    ) -> BarPlan:
        per_transition: list[int] = []
        per_body: list[int] = []
        for i, ti in enumerate(inputs):
            next_mood = getattr(inputs[i + 1], "mood", None) if i + 1 < len(inputs) else None
            if i < len(inputs) - 1:
                if transition_override is not None:
                    per_transition.append(transition_override)
                else:
                    pair = classify_pair(getattr(ti, "mood", None), next_mood)
                    per_transition.append(
                        self._config_or_default(
                            getattr(ti, "mood", None), next_mood, pair, "transition_bars",
                            transition_bars_for_pair(pair),
                        )
                    )
            if body_override is not None:
                per_body.append(body_override)
            else:
                per_body.append(
                    self._config_or_default(
                        getattr(ti, "mood", None),
                        None,
                        classify_pair(getattr(ti, "mood", None), None),
                        "body_bars",
                        body_bars_for_pair(classify_pair(getattr(ti, "mood", None), None)),
                    )
                )
        per_body = self._clamp_to_source_duration(inputs, grid, per_transition, per_body)
        return BarPlan(tuple(per_transition), per_body)

    def _config_or_default(
        self, mood_a: Any, mood_b: Any, _pair: Any, prefix: str, default: int
    ) -> int:
        tov = self._config_bar_override(mood_a, prefix)
        if tov is not None:
            return tov
        return default

    def _config_bar_override(
        self, subgenre: TechnoSubgenre | str | None, prefix: str
    ) -> int | None:
        if subgenre is None:
            return None
        if isinstance(subgenre, str):
            try:
                subgenre = TechnoSubgenre(subgenre)
            except ValueError:
                return None
        return getattr(self._settings, f"{prefix}_{subgenre.value}", None)

    def _clamp_to_source_duration(
        self,
        inputs: list[Any],
        grid: dict[int, BeatgridEntry],
        per_transition: list[int],
        per_body: list[int],
    ) -> list[int]:
        target_bpm = self._settings.target_bpm
        bar_s = 4.0 * (60.0 / target_bpm)
        clamped = list(per_body)
        for i, ti in enumerate(inputs):
            duration_ms = getattr(ti, "duration_ms", None)
            if not duration_ms:
                continue
            d_in = per_transition[i - 1] * bar_s if i > 0 else 0.0
            d_out = per_transition[i] * bar_s if i < len(inputs) - 1 else 0.0
            g = grid.get(ti.track_id)
            trim = g.effective_trim if g is not None else 0.0
            available_s = max(0.0, duration_ms / 1000.0 - trim - 1.0)
            ratio = ti.tempo_ratio(target_bpm)
            max_output_s = available_s / ratio if ratio > 0 else available_s
            budget = max_output_s - d_in - d_out
            if budget <= 0:
                clamped[i] = 1
                continue
            clamped[i] = min(clamped[i], max(1, int(budget // bar_s)))
        return clamped
```

- [ ] **Step 4: Delete the old file, update handler import**

```bash
git rm app/domain/render/bar_planner.py
```

Edit `app/handlers/render_mixdown.py:10` — change:
```python
from app.domain.render.bar_planner import BarPlanner
```
to:
```python
from app.domain.render.bar_plan import BarPlanner
```

- [ ] **Step 5: Export BarPlan from package**

Edit `app/domain/render/__init__.py`: replace `from app.domain.render.bar_planner import BarPlanner` (if present) with `from app.domain.render.bar_plan import BarPlan, BarPlanner`. Add `BarPlan`, `BarPlanner` to `__all__` (BarPlanner was already there).

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/domain/render/test_bar_plan.py tests/handlers/test_render_mixdown.py -v`
Expected: PASS — handler's existing `per_t, per_b = planner.compute(...)` unpacking still works via `BarPlan.__iter__`.

- [ ] **Step 7: Run full gate**

Run: `make check`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "refactor(render): BarPlanner returns named BarPlan (one-pass)

Removes the double-iterate over inputs + duplicate classify_pair call.
BarPlan.__iter__ keeps the legacy unpacking site working until the orchestrator
arrives in Task 11.
Gate: make check PASS."
```

---

## Task 5: `BeatgridEntry` methods + `BeatgridLimits` + `BeatgridIO`

**Files:**
- Create: `app/domain/render/beatgrid.py`
- Modify: `app/domain/render/models.py:35-48` — keep `BeatgridEntry` existing structure; the methods live on the dataclass in the new module via composition. Strategy: import `BeatgridEntry` into `beatgrid.py` and add free functions `BeatgridLimits` + `clamp_entry()` + `entry_flags()` + `entry_to_row()` + `entry_from_row()` operating on `BeatgridEntry`.

  Wait — `BeatgridEntry` is `@dataclass(frozen=True, slots=True)` in `models.py`. We cannot add methods in another module. Two options:
  (a) Move `BeatgridEntry` to `beatgrid.py` and re-export from `models.py`.
  (b) Add free-standing functions `clamp(entry, limits)`, `entry_flags(entry, limits)`, `entry_to_row(entry)`, `entry_from_row(row)` in `beatgrid.py` and a single `BeatgridIO`.
  
  Choose (b) — keeps `models.py` thin and avoids import cycles (models.py is the leaf).
- Test: `tests/domain/render/test_beatgrid.py` (new).

**Interfaces:**
- Produces:
  - `app.domain.render.beatgrid.BeatgridLimits` frozen dataclass.
  - `app.domain.render.beatgrid.BeatgridLimits.from_settings(s) -> BeatgridLimits`.
  - `app.domain.render.beatgrid.clamp_entry(entry, limits) -> BeatgridEntry`.
  - `app.domain.render.beatgrid.entry_flags(entry, limits) -> list[str]`.
  - `app.domain.render.beatgrid.entry_to_row(entry) -> dict[str, Any]`.
  - `app.domain.render.beatgrid.entry_from_row(row) -> BeatgridEntry`.
  - `app.domain.render.beatgrid.BeatgridIO` static-method class: `.read(workspace) -> list[BeatgridEntry]`, `.write(workspace, entries)`.

- [ ] **Step 1: Write the failing test**

Create `tests/domain/render/test_beatgrid.py`:

```python
import json
from pathlib import Path

from app.config.render import RenderSettings
from app.domain.render.beatgrid import (
    BeatgridIO,
    BeatgridLimits,
    clamp_entry,
    entry_flags,
    entry_from_row,
    entry_to_row,
)
from app.domain.render.models import BeatgridEntry


def _entry(*, trim=0.5, refined=None, phase=10.0, gain=0.0):
    return BeatgridEntry(
        track_id=1, trim_start_s=trim, refined_trim_s=refined,
        gain_db=gain, phase_ms=phase,
    )


def test_limits_defaults():
    l = BeatgridLimits()
    assert l.max_phase_ms == 120.0
    assert l.max_trim_start_s == 8.0
    assert l.fixed_flag_threshold_ms == 40.0
    assert l.fixed_flag_gain_db == 1.5


def test_clamp_entry_caps_phase_and_trim():
    l = BeatgridLimits(max_phase_ms=80.0, max_trim_start_s=8.0)
    e = _entry(trim=10.0, refined=10.5, phase=200.0)
    clamped = clamp_entry(e, l)
    assert clamped.trim_start_s == 8.0
    assert clamped.phase_ms == 80.0
    assert clamped.refined_trim_s == 8.08  # 8.0 + 80/1000


def test_clamp_entry_neg_phase_clamped_to_minus_limit():
    l = BeatgridLimits(max_phase_ms=120.0)
    e = _entry(phase=-300.0)
    assert clamp_entry(e, l).phase_ms == -120.0


def test_entry_flags_fixed_when_phase_exceeds_threshold():
    l = BeatgridLimits(fixed_flag_threshold_ms=40.0, fixed_flag_gain_db=1.5)
    e = _entry(phase=50.0)
    assert entry_flags(e, l) == ["fixed"]


def test_entry_flags_fixed_when_gain_exceeds_threshold():
    l = BeatgridLimits(fixed_flag_threshold_ms=40.0, fixed_flag_gain_db=1.5)
    e = _entry(phase=10.0, gain=2.0)
    assert entry_flags(e, l) == ["fixed"]


def test_entry_flags_empty_for_clean_entry():
    l = BeatgridLimits()
    e = _entry(phase=10.0, gain=0.5)
    assert entry_flags(e, l) == []


def test_entry_to_row_round_trips():
    e = _entry(trim=0.42, refined=0.43, phase=15.0, gain=1.0)
    row = entry_to_row(e)
    assert row["track_id"] == 1
    assert row["trim_start_s"] == 0.42
    assert row["refined_trim_s"] == 0.43
    assert row["gain_db"] == 1.0
    assert row["phase_ms"] == 15.0
    assert row["flags"] == []


def test_entry_from_row_inverts_to_row():
    e = _entry(trim=0.42, refined=0.43, phase=15.0, gain=1.0)
    assert entry_from_row(entry_to_row(e)) == e


def test_entry_from_row_handles_missing_refined_and_gain():
    row = {"track_id": 5, "trim_start_s": 0.4, "phase_ms": 0.0}
    e = entry_from_row(row)
    assert e.refined_trim_s is None
    assert e.gain_db == 0.0


def test_beatgrid_io_write_and_read(tmp_path):
    entries = [
        _entry(trim=0.4, refined=0.4, phase=0.0),
        _entry(trim=0.5, refined=0.51, phase=10.0, gain=1.5),
    ]
    BeatgridIO.write(str(tmp_path), entries)
    rows = json.loads((tmp_path / "beatgrid.json").read_text())
    assert len(rows) == 2
    assert rows[0]["track_id"] == 1
    loaded = BeatgridIO.read(str(tmp_path))
    assert loaded == entries


def test_beatgrid_limits_from_settings():
    s = RenderSettings()
    l = BeatgridLimits.from_settings(s)
    assert l.max_phase_ms == 120.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_beatgrid.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement beatgrid.py**

Create `app/domain/render/beatgrid.py`:

```python
"""Beatgrid domain behaviour + JSON IO — clamps, flags, row mapping.

Keeps ``BeatgridEntry`` (in app.domain.render.models) pure-data and
puts all derived behaviour + the JSON schema single-source-of-truth here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.render import RenderSettings
from app.domain.render.models import BeatgridEntry

_GRID_FILENAME = "beatgrid.json"


@dataclass(frozen=True, slots=True)
class BeatgridLimits:
    max_phase_ms: float = 120.0
    max_trim_start_s: float = 8.0
    fixed_flag_threshold_ms: float = 40.0
    fixed_flag_gain_db: float = 1.5

    @classmethod
    def from_settings(cls, _settings: RenderSettings) -> BeatgridLimits:
        return cls()


def clamp_entry(entry: BeatgridEntry, limits: BeatgridLimits) -> BeatgridEntry:
    trim = min(entry.trim_start_s, limits.max_trim_start_s)
    phase = max(-limits.max_phase_ms, min(limits.max_phase_ms, entry.phase_ms))
    refined = min(
        round(trim + phase / 1000.0, 4),
        round(trim + limits.max_phase_ms / 1000.0, 4),
    )
    return BeatgridEntry(
        track_id=entry.track_id,
        trim_start_s=trim,
        refined_trim_s=refined,
        gain_db=entry.gain_db,
        phase_ms=phase,
    )


def entry_flags(entry: BeatgridEntry, limits: BeatgridLimits) -> list[str]:
    if abs(entry.phase_ms) > limits.fixed_flag_threshold_ms or abs(entry.gain_db) > limits.fixed_flag_gain_db:
        return ["fixed"]
    return []


def entry_to_row(entry: BeatgridEntry) -> dict[str, Any]:
    return {
        "track_id": entry.track_id,
        "trim_start_s": entry.trim_start_s,
        "refined_trim_s": entry.refined_trim_s,
        "gain_db": entry.gain_db,
        "phase_ms": entry.phase_ms,
    }


def entry_from_row(row: Mapping[str, Any]) -> BeatgridEntry:
    return BeatgridEntry(
        track_id=row["track_id"],
        trim_start_s=row["trim_start_s"],
        refined_trim_s=row.get("refined_trim_s"),
        gain_db=row.get("gain_db", 0.0),
        phase_ms=row.get("phase_ms", 0.0),
    )


class BeatgridIO:
    """File-backed beatgrid.json read/write (single source of JSON schema)."""

    @staticmethod
    def read(workspace: str) -> list[BeatgridEntry]:
        rows = json.loads((Path(workspace) / _GRID_FILENAME).read_text())
        return [entry_from_row(r) for r in rows]

    @staticmethod
    def write(workspace: str, entries: list[BeatgridEntry]) -> None:
        Path(workspace).mkdir(parents=True, exist_ok=True)
        (Path(workspace) / _GRID_FILENAME).write_text(
            json.dumps([entry_to_row(e) for e in entries], indent=1)
        )
```

- [ ] **Step 4: Export from package**

Edit `app/domain/render/__init__.py`: add
```python
from app.domain.render.beatgrid import (
    BeatgridIO,
    BeatgridLimits,
    clamp_entry,
    entry_flags,
    entry_from_row,
    entry_to_row,
)
```
and add these names to `__all__`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/domain/render/test_beatgrid.py -v`
Expected: PASS — 12 tests.

- [ ] **Step 6: Run full gate**

Run: `make check`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(render): BeatgridLimits + entry clamp/flags/row + BeatgridIO

Centralises the beatgrid.json schema in one module (was duplicated between
render_beatgrid_handler writer and render_mixdown_handler._load_grid reader).
Gate: make check PASS."
```

---

## Task 6: `stem_voicing.py` single source for stem HPF + gain

**Files:**
- Create: `app/domain/render/stem_voicing.py`
- Modify: `app/domain/render/filtergraph.py:35-41,244,285-294` — replace `_STEM_HPF_HZ` constant and `_stem_trim_gain_db` static method with lookups in `STEM_VOICING`.
- Modify: `app/domain/render/__init__.py` — export `StemVoicing`, `STEM_VOICING`.
- Test: `tests/domain/render/test_stem_voicing.py` (new).
- Test: `tests/domain/render/test_stem_graph.py` — current assertions on `[lo0_bass]` and `highpass=f=120` etc. must still pass (voicing values unchanged — just refactored source).

**Interfaces:**
- Produces: `app.domain.render.stem_voicing.StemVoicing` frozen dataclass with `hpf_hz: int | None`, `gain_db: float`.
- Produces: `app.domain.render.stem_voicing.STEM_VOICING` dict[str, StemVoicing] keyed by stem name.

- [ ] **Step 1: Write the failing test**

Create `tests/domain/render/test_stem_voicing.py`:

```python
from app.domain.render.models import STEM_ORDER
from app.domain.render.stem_voicing import STEM_VOICING


def test_voicing_defined_for_every_stem_in_order():
    assert set(STEM_VOICING) == set(STEM_ORDER)


def test_drums_and_bass_have_no_hpf():
    assert STEM_VOICING["drums"].hpf_hz is None
    assert STEM_VOICING["bass"].hpf_hz is None


def test_harmonic_uses_80hz_hpf_at_minus_2db():
    assert STEM_VOICING["harmonic"].hpf_hz == 80
    assert STEM_VOICING["harmonic"].gain_db == -2.0


def test_instrumental_uses_120hz_hpf_at_minus_7db():
    assert STEM_VOICING["instrumental"].hpf_hz == 120
    assert STEM_VOICING["instrumental"].gain_db == -7.0


def test_acappella_uses_120hz_hpf_at_minus_3db():
    assert STEM_VOICING["acappella"].hpf_hz == 120
    assert STEM_VOICING["acappella"].gain_db == -3.0


def test_drums_and_bass_have_zero_gain():
    assert STEM_VOICING["drums"].gain_db == 0.0
    assert STEM_VOICING["bass"].gain_db == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_stem_voicing.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement stem_voicing.py**

Create `app/domain/render/stem_voicing.py`:

```python
"""Stem voicing — single source of bleed-masking HPF + headroom trim.

Used by ``StemGraphBuilder`` so the HPF and per-stem gain staging live
beside ``models.STEM_ORDER`` instead of being scattered across static
methods in the filtergraph module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StemVoicing:
    hpf_hz: int | None
    gain_db: float


STEM_VOICING: dict[str, StemVoicing] = {
    "drums":        StemVoicing(hpf_hz=None, gain_db=0.0),
    "bass":         StemVoicing(hpf_hz=None, gain_db=0.0),
    "harmonic":     StemVoicing(hpf_hz=80,   gain_db=-2.0),
    "instrumental": StemVoicing(hpf_hz=120,  gain_db=-7.0),
    "acappella":    StemVoicing(hpf_hz=120,  gain_db=-3.0),
}
```

- [ ] **Step 4: Export from package**

Edit `app/domain/render/__init__.py`: add
```python
from app.domain.render.stem_voicing import STEM_VOICING, StemVoicing
```
and add `StemVoicing`, `STEM_VOICING` to `__all__`.

- [ ] **Step 5: Refactor filtergraph.py to use STEM_VOICING**

Edit `app/domain/render/filtergraph.py`:

In imports block (around lines 22-31), after the `from app.domain.render.models` line, add:
```python
from app.domain.render.stem_voicing import STEM_VOICING
```

Delete the `_STEM_HPF_HZ` constant at lines 35-41:
```python
_STEM_HPF_HZ: dict[str, int | None] = {
    "drums": None,
    ...
}
```

In `StemGraphBuilder._segment_block` at line ~244:
```python
gain_db = seg.gain_db + self._stem_trim_gain_db(stem)
```
becomes:
```python
gain_db = seg.gain_db + STEM_VOICING[stem].gain_db
```

In `_stem_chain` (line ~266), the `_STEM_HPF_HZ[stem]` lookup becomes `STEM_VOICING[stem].hpf_hz`. Update the signature to use the voicing dict; the static method becomes:

```python
@staticmethod
def _stem_chain(input_idx, seg, label, hpf_hz, gain_db):
    hpf = f"highpass=f={hpf_hz}," if hpf_hz else ""
    ...
```
(this is already the current signature — just update the call site).

Delete the `_stem_trim_gain_db` static method (lines 285-294) entirely — replaced by `STEM_VOICING[stem].gain_db` inline.

Update the `_segment_block` call to `.apply_entry(...)` to pass `STEM_VOICING[stem].hpf_hz`:
```python
parts.append(self._stem_chain(input_idx, seg, label, STEM_VOICING[stem].hpf_hz, gain_db))
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/domain/render/test_stem_voicing.py tests/domain/render/test_stem_graph.py -v`
Expected: PASS — voicing tests pass; stem_graph tests pass (values unchanged).

- [ ] **Step 7: Run full gate**

Run: `make check`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "refactor(render): single source of stem HPF + gain staging

StemGraphBuilder now reads STEM_VOICING[stem] instead of two static methods +
a module-level dict. Same values, one place, named value object.
Gate: make check PASS."
```

---

## Task 7: `EffectPresetResolver` + `ResolvedEffects` value object

**Files:**
- Create: `app/domain/render/effects_resolver.py`
- Modify: `app/domain/render/filtergraph.py:99-133` — replace the inline late-imports with the resolver (resolver does the import upfront in module scope at construction — no late import inside hot path).
- Modify: `app/domain/render/__init__.py` — export `ResolvedEffects`, `EffectPresetResolver`.
- Test: `tests/domain/render/test_effects_resolver.py` (new).

**Interfaces:**
- Produces:
  - `app.domain.render.effects_resolver.ResolvedEffects` frozen dataclass with `echo: EchoPlan | None`, `sweep: FilterSweepPreset | None`.
  - `app.domain.render.effects_resolver.EffectPresetResolver` with `resolve(plan) -> ResolvedEffects`.

- [ ] **Step 1: Inspect existing preset modules for exact types**

Run: `cat app/audio/effects/echo_delay.py | head -50` and `cat app/audio/effects/filter_sweep.py | head -50`
Read: classes `EchoPlan` (method `ffmpeg_aecho_expr()`, fields `delay_ms`, `decay`, `taps`, `wet_dry_ratio`, `stereo_spread`, property `effective_delay_ms`) and `FilterSweepPreset` (field `outgoing` with `.end_freq_hz`; assume the existing `_segment_block` access pattern is the contract).

- [ ] **Step 2: Write the failing test**

Create `tests/domain/render/test_effects_resolver.py`:

```python
from types import SimpleNamespace

from app.domain.render.effects_resolver import EffectPresetResolver, ResolvedEffects
from app.domain.render.models import RenderMode


def _plan(*, echo=None, sweep=None):
    return SimpleNamespace(echo_preset=echo, filter_sweep_preset=sweep, mode=RenderMode.CLASSIC)


def test_resolver_returns_none_when_no_presets():
    fx = EffectPresetResolver().resolve(_plan())
    assert isinstance(fx, ResolvedEffects)
    assert fx.echo is None
    assert fx.sweep is None


def test_resolver_returns_known_echo_preset():
    fx = EffectPresetResolver().resolve(_plan(echo="techno_standard"))
    assert fx.echo is not None
    assert fx.echo.wet_dry_ratio > 0


def test_resolver_returns_none_for_unknown_echo_preset():
    fx = EffectPresetResolver().resolve(_plan(echo="not_a_preset"))
    assert fx.echo is None


def test_resolver_returns_known_sweep_preset():
    fx = EffectPresetResolver().resolve(_plan(sweep="classic_lowpass"))
    assert fx.sweep is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_effects_resolver.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement effects_resolver.py**

Create `app/domain/render/effects_resolver.py`:

```python
"""Resolve render-plan effect preset names into value objects.

The filtergraph builders used to ``from app.audio.effects... import`` inline,
deep inside ``_segment_block`` (late import each call). Centralising it here
makes the preset registry a single dependency of the render domain —
``ClassicGraphBuilder`` consumes plain value objects, never module paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.audio.effects.echo_delay import ECHO_PRESETS
from app.audio.effects.filter_sweep import FILTER_PRESETS


@dataclass(frozen=True, slots=True)
class ResolvedEffects:
    echo: Any | None = None
    sweep: Any | None = None


class EffectPresetResolver:
    def resolve(self, plan: Any) -> ResolvedEffects:
        return ResolvedEffects(
            echo=self._resolve_echo(plan.echo_preset),
            sweep=self._resolve_sweep(plan.filter_sweep_preset),
        )

    @staticmethod
    def _resolve_echo(name: str | None) -> Any | None:
        if name is None:
            return None
        return ECHO_PRESETS.get(name)

    @staticmethod
    def _resolve_sweep(name: str | None) -> Any | None:
        if name is None:
            return None
        return FILTER_PRESETS.get(name)
```

- [ ] **Step 5: Export from package**

Edit `app/domain/render/__init__.py`: add
```python
from app.domain.render.effects_resolver import EffectPresetResolver, ResolvedEffects
```
and add both names to `__all__`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/domain/render/test_effects_resolver.py -v`
Expected: PASS — 5 tests.

- [ ] **Step 7: Commit (filtergraph integration in Task 8)**

```bash
git add -A && git commit -m "feat(render): EffectPresetResolver resolves echo/sweep upfront

filtergraph will switch to ResolvedEffects value objects in the next task;
removes the late-import-during-_segment_block anti-pattern.
Gate: make check PASS."
```

---

## Task 8: Refactor `ClassicGraphBuilder._segment_block` into focused methods

**Files:**
- Modify: `app/domain/render/filtergraph.py:44-212` — extract `_FrameContext` dataclass + decompose `_segment_block` into `_source_chain`, `_echo_split`, `_band_split`, `_fade_high`, `_fade_mid`, `_fade_low`, `_mix_segment`. Use `EffectPresetResolver` instead of late imports. `StemGraphBuilder` keeps its existing structure (it's already small).
- Test: `tests/audio/render/test_eq_ritual.py`, `test_bass_swap.py`, `tests/domain/render/test_graph.py` — all must continue to pass unchanged. Add no new tests here, the existing ~30 tests cover the contract.

**Interfaces:**
- Consumes: `EffectPresetResolver` + `ResolvedEffects` (Task 7), `STEM_VOICING` (Task 6).
- Produces: same public `build_filtergraph(plan)` + `build_stem_filtergraph(plan)` outputs.

**Pre-step (GitNexus):**

- [ ] **Step 0a: Impact analysis on ClassicGraphBuilder._segment_block**

Run `gitnexus_impact({target: "ClassicGraphBuilder._segment_block", direction: "upstream"})` (or via owning class `ClassicGraphBuilder`). Expect test files only — confirm.

- [ ] **Step 1: Run baseline tests**

Run: `uv run pytest tests/audio/render/test_eq_ritual.py tests/audio/render/test_bass_swap.py tests/domain/render/test_graph.py -v 2>&1 | tail -10`
Expected: PASS — snapshot of current behavior (we'll keep these green).

- [ ] **Step 2: Add `_FrameContext` dataclass + decompose `_segment_block`**

Edit `app/domain/render/filtergraph.py`. After the imports and effect-late-imports cleanup, add at top of `filtergraph.py` (right after the `STEM_VOICING` import):

```python
from app.domain.render.effects_resolver import EffectPresetResolver, ResolvedEffects
```

Add the `_FrameContext` dataclass before the `FilterGraphBuilder` class:

```python
@dataclass(frozen=True, slots=True)
class _FrameContext:
    plan: "RenderPlan"
    i: int
    seg: "TrackSegment"
    length: float
    bar_s: float
    beat_s: float
    low_x: float
    p1: float
    p2: float
    has_prev: bool
    has_next: bool
    curve_out: str
    curve_in: str
    n: int
    outro_fade_s: float

    @classmethod
    def from_segment(cls, plan: "RenderPlan", i: int, seg: "TrackSegment") -> _FrameContext:
        bar_s = 4.0 * (60.0 / plan.target_bpm)
        beat_s = 60.0 / plan.target_bpm
        return cls(
            plan=plan,
            i=i,
            seg=seg,
            length=seg.length_s,
            bar_s=bar_s,
            beat_s=beat_s,
            low_x=plan.low_swap_beats * beat_s,
            p1=plan.eq_phase_1_ratio,
            p2=plan.eq_phase_2_ratio,
            has_prev=i > 0,
            has_next=i < plan.n - 1,
            curve_out=plan.crossfade_curve_out,
            curve_in=plan.crossfade_curve_in,
            n=plan.n,
            outro_fade_s=min(plan.outro_fade_bars * bar_s, seg.length_s),
        )
```

(Add `from dataclasses import dataclass` to imports if not already present.)

Replace `ClassicGraphBuilder._segment_block` (lines 87-212) entirely with:

```python
class ClassicGraphBuilder(FilterGraphBuilder):
    """Single-file-per-track 3-band EQ bass-swap (highs → mids → bass pinpoint)."""

    _effects: EffectPresetResolver = EffectPresetResolver()

    def _segments(self, plan: RenderPlan) -> Sequence[TrackSegment]:
        return plan.segments

    def _segment_block(self, plan: RenderPlan, i: int, seg: object) -> tuple[list[str], str]:
        assert isinstance(seg, TrackSegment)
        ctx = _FrameContext.from_segment(plan, i, seg)
        fx = self._effects.resolve(plan)
        parts: list[str] = [self._source_chain(ctx)]
        parts.extend(self._echo_split(ctx, fx))
        parts.extend(self._band_split(ctx, fx))
        parts.append(self._fade_band(ctx, ctx.has_next or ctx.outro_fade_s, "_high",
                                     self._high_fades(ctx)))
        parts.append(self._fade_band(ctx, ctx.has_next or ctx.outro_fade_s, "_mid",
                                     self._mid_fades(ctx)))
        parts.append(self._fade_band(ctx, ctx.has_next or ctx.outro_fade_s, "_low",
                                     self._low_fades(ctx)))
        parts.append(self._mix_segment(ctx, fx))
        return parts, f"[m{i}]"

    @staticmethod
    def _source_chain(ctx: _FrameContext) -> str:
        seg = ctx.seg
        return (
            f"[{ctx.i}:a]atrim=start={seg.trim_start_s:.4f}:"
            f"duration={ctx.length / seg.tempo_ratio + 1.0:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={seg.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={ctx.length:.3f},asetpts=PTS-STARTPTS,volume={seg.gain_db:.2f}dB,"
            f"aformat=sample_rates=44100:channel_layouts=stereo[s{ctx.i}]"
        )

    @staticmethod
    def _echo_split(ctx: _FrameContext, fx: ResolvedEffects) -> list[str]:
        if fx.echo is None:
            return []
        echo_aecho = fx.echo.ffmpeg_aecho_expr()
        parts = [f"[s{ctx.i}]asplit=2[sd{ctx.i}][se{ctx.i}]"]
        if ctx.has_next:
            tail_start = max(0.0, ctx.length - ctx.seg.d_out_s * 0.3)
            tail_dur = min(ctx.seg.d_out_s * 0.3, ctx.length - tail_start)
            parts.append(
                f"[se{ctx.i}]atrim=start={tail_start:.3f}:duration={tail_dur:.3f},"
                f"asetpts=PTS-STARTPTS,aecho={echo_aecho}[se{ctx.i}_out]"
            )
        else:
            parts.append(f"[se{ctx.i}]aecho={echo_aecho}[se{ctx.i}_out]")
        return parts

    @staticmethod
    def _band_split(ctx: _FrameContext, fx: ResolvedEffects) -> list[str]:
        # apply sweep on dry branch (post-echo split or directly) before 3-band split.
        sweep_expr = ""
        has_sweep = fx.sweep is not None and fx.sweep.outgoing is not None and ctx.has_next
        if has_sweep and fx.sweep is not None:
            end_f = int(fx.sweep.outgoing.end_freq_hz)
            t_start = ctx.length - ctx.seg.d_out_s
            sweep_expr = (
                f"lowpass=f={end_f}:enable='between(t,{t_start:.2f},{ctx.length:.2f})',"
            )
        dry_in = f"[sd{ctx.i}]" if fx.echo is not None else f"[s{ctx.i}]"
        return [
            f"{dry_in}{sweep_expr}asplit=3[s{ctx.i}a][s{ctx.i}b][s{ctx.i}c]",
            f"[s{ctx.i}a]lowpass=f={ctx.plan.xsplit_low_hz}[lo{ctx.i}]",
            f"[s{ctx.i}b]highpass=f={ctx.plan.xsplit_low_hz},"
            f"lowpass=f={ctx.plan.xsplit_high_hz}[mid{ctx.i}]",
            f"[s{ctx.i}c]highpass=f={ctx.plan.xsplit_high_hz}[hi{ctx.i}]",
        ]

    @staticmethod
    def _high_fades(ctx: _FrameContext) -> list[str]:
        d_in, d_out = ctx.seg.d_in_s, ctx.seg.d_out_s
        in_fade = (
            [f"afade=t=in:curve={ctx.curve_in}:st=0:d={d_in * ctx.p1:.3f}"]
            if ctx.has_prev else []
        )
        if ctx.has_next:
            out_fade = (
                [f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - d_out:.3f}:d={d_out * ctx.p1:.3f}"]
            )
        else:
            out_fade = [f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - ctx.outro_fade_s:.3f}:d={ctx.outro_fade_s:.3f}"]
        return in_fade + out_fade

    @staticmethod
    def _mid_fades(ctx: _FrameContext) -> list[str]:
        d_in, d_out = ctx.seg.d_in_s, ctx.seg.d_out_s
        in_fade = (
            [f"afade=t=in:curve={ctx.curve_in}:st={d_in * ctx.p1:.3f}:d={d_in * (ctx.p2 - ctx.p1):.3f}"]
            if ctx.has_prev else []
        )
        if ctx.has_next:
            out_fade = [
                f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - d_out * (1.0 - ctx.p1):.3f}:"
                f"d={d_out * (ctx.p2 - ctx.p1):.3f}"
            ]
        else:
            out_fade = [f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - ctx.outro_fade_s:.3f}:d={ctx.outro_fade_s:.3f}"]
        return in_fade + out_fade

    @staticmethod
    def _low_fades(ctx: _FrameContext) -> list[str]:
        d_in, d_out = ctx.seg.d_in_s, ctx.seg.d_out_s
        in_fade = (
            [f"afade=t=in:curve={ctx.curve_in}:st={d_in * ctx.p2 - ctx.low_x / 2:.3f}:d={ctx.low_x:.3f}"]
            if ctx.has_prev else []
        )
        if ctx.has_next:
            in_fade_out = (
                [f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - d_out * (1.0 - ctx.p2) - ctx.low_x / 2:.3f}:d={ctx.low_x:.3f}"]
            )
        else:
            in_fade_out = [f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - ctx.outro_fade_s:.3f}:d={ctx.outro_fade_s:.3f}"]
        return in_fade + in_fade_out

    @staticmethod
    def _fade_band(ctx: _FrameContext, _always: bool, _suffix: str, fades: list[str]) -> str:
        # Stitches one [band{i}] block with the named fades. Band name resolution is
        # implicit via the suffix on separate [H{i}], [MID{i}], [Lo{i}] labels.
        return ""  # placeholder — real per-band emission is the three helpers below

    @staticmethod
    def _mix_segment(ctx: _FrameContext, fx: ResolvedEffects) -> str:
        t_ms = int(ctx.seg.start_s * 1000)
        if fx.echo is None:
            return (
                f"[H{ctx.i}][MID{ctx.i}][Lo{ctx.i}]amix=inputs=3:normalize=0,"
                f"adelay={t_ms}|{t_ms}|{t_ms}[m{ctx.i}]"
            )
        echo_wet = max(0.1, min(0.5, min(0.25, fx.echo.wet_dry_ratio * 0.6)))
        return (
            f"[H{ctx.i}][MID{ctx.i}][Lo{ctx.i}]amix=inputs=3:normalize=0[sm{ctx.i}];"
            f"[sm{ctx.i}][se{ctx.i}_out]amix=inputs=2:normalize=0:weights=1 {echo_wet:.2f},"
            f"adelay={t_ms}|{t_ms}[m{ctx.i}]"
        )
```

**Important:** the above shows an inline approach; to match the existing test contracts (`[H0]`, `[MID0]`, `[Lo0]`, `[m0]` labels with afade lists merged by `,`), implement three explicit per-band appenders that mirror the original block:

```python
    def _emit_high_band(self, ctx: _FrameContext) -> str:
        return f"[hi{ctx.i}]{','.join(self._high_fades(ctx)) or 'acopy'}[H{ctx.i}]"

    def _emit_mid_band(self, ctx: _FrameContext) -> str:
        return f"[mid{ctx.i}]{','.join(self._mid_fades(ctx)) or 'acopy'}[MID{ctx.i}]"

    def _emit_low_band(self, ctx: _FrameContext) -> str:
        return f"[lo{ctx.i}]{','.join(self._low_fades(ctx)) or 'acopy'}[Lo{ctx.i}]"
```

Final `_segment_block`:

```python
    def _segment_block(self, plan, i, seg) -> tuple[list[str], str]:
        assert isinstance(seg, TrackSegment)
        ctx = _FrameContext.from_segment(plan, i, seg)
        fx = self._effects.resolve(plan)
        return [
            self._source_chain(ctx),
            *self._echo_split(ctx, fx),
            *self._band_split(ctx, fx),
            self._emit_high_band(ctx),
            self._emit_mid_band(ctx),
            self._emit_low_band(ctx),
            self._mix_segment(ctx, fx),
        ], f"[m{i}]"
```

Note: remove the placeholder `_fade_band` helper; the three explicit `_emit_*` methods replace it (Drop the placeholder + the `_always`, `_suffix` references in the plan above — keep only the explicit emitters.)

- [ ] **Step 3: Run filtergraph tests**

Run: `uv run pytest tests/audio/render/test_eq_ritual.py tests/audio/render/test_bass_swap.py tests/domain/render/test_graph.py -v`
Expected: PASS — every assertion on `asplit`, `lowpass`, `highpass`, `amix=inputs=3`, `afade` shapes preserved. If any test fails, check whether the original asserted on the per-band `acopy` fallback — read the failing assertion and adjust the `or 'acopy'` ternary.

- [ ] **Step 4: Run full gate**

Run: `make check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(render): decompose ClassicGraphBuilder._segment_block

125-line _segment_block split into _source_chain/_echo_split/_band_split/
_high/_mid/_low/_mix via a _FrameContext value object. Late imports removed
in favour of injected EffectPresetResolver. Same filtergraph output.
Gate: make check PASS."
```

---

## Task 9: `RenderPlanner` + `SegmentFactory` + `RenderPlan.from_settings(request, ...)` simplification

**Files:**
- Create: `app/domain/render/segments.py` — `SegmentFactory` Protocol + `ClassicSegmentFactory` + `StemSegmentFactory`.
- Create: `app/domain/render/plan_assembler.py` — `RenderPlanner` class.
- Modify: `app/domain/render/models.py:141-200` — change `from_settings` signature to accept `request: RenderRequest` instead of 14 effect kwargs.
- Modify: `app/domain/render/timeline.py:114-258` — drop `build_render_plan` and `build_stem_render_plan`; keep `place_segments` + `timeline_windows`.
- Delete: `app/domain/render/plan_builder.py`.
- Modify: `app/domain/render/__init__.py` — drop `RenderPlanBuilder`, `build_render_plan`, `build_stem_render_plan`; export `RenderPlanner`, `SegmentFactory`, `ClassicSegmentFactory`, `StemSegmentFactory`.
- Modify: `app/handlers/render_mixdown.py:12` — replace `RenderPlanBuilder` import with `RenderPlanner` (final handler rewrite in Task 11; this task just keeps the symbol resolvable).
- Test: `tests/domain/render/test_plan_assembler.py` (new).
- Test: `tests/domain/render/test_timeline.py` — rewrite the 3 `build_render_plan(...)` calls to `RenderPlanner().assemble(...)`.
- Test: `tests/domain/render/test_stem_graph.py` — `_stem_plan(n)` helper must use `RenderPlanner().assemble(...)` to build the test plan (was `build_stem_render_plan`).
- Test: `tests/domain/render/test_models.py` — update tests using `RenderPlan.from_settings` OR `RenderPlan(mode=...)` direct constructor. Existing `test_render_plan_holds_segments` does direct constructor — already updated in Task 2.

**Interfaces:**
- Consumes: `RenderRequest` (Task 3), `BarPlan` (Task 4), `place_segments` (timeline.py), `RenderPlan.from_settings(settings, request, *, segments, stem_segments=None)`.
- Produces:
  - `app.domain.render.segments.SegmentFactory` Protocol with `build_segments(geometries, inputs, stem_paths, settings, request)`.
  - `app.domain.render.plan_assembler.RenderPlanner.assemble(settings, request, inputs, grid, bar_plan, stem_paths) -> RenderPlan`.

**Pre-step (GitNexus):**

- [ ] **Step 0a: Impact analysis**

Run `gitnexus_impact({target: "build_render_plan", direction: "upstream"})` and `gitnexus_impact({target: "RenderPlanBuilder", direction: "upstream"})`. Expect: `render_mixdown_handler`, `tests/domain/render/test_timeline.py`, `tests/domain/render/test_stem_graph.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/domain/render/test_plan_assembler.py`:

```python
from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan
from app.domain.render.beatgrid import BeatgridLimits
from app.domain.render.models import (
    BeatgridEntry, RenderMode, RenderPlan, StemSegment, TrackInput, TrackSegment,
)
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.segments import ClassicSegmentFactory, StemSegmentFactory
from app.domain.render.request import RenderRequest


def _inputs(n, *, bpm=130.0):
    return [
        TrackInput(
            track_id=i, yandex_id=i, title=f"t{i}", bpm=bpm, key_code=1,
            mix_in_ms=0, integrated_lufs=-12.0, file_path=f"/x{i}.mp3",
            duration_ms=600_000,
        )
        for i in range(n)
    ]


def _grid(n):
    return {
        i: BeatgridEntry(track_id=i, trim_start_s=0.0, refined_trim_s=0.0,
                         gain_db=0.0, phase_ms=0.0)
        for i in range(n)
    }


def _req(*, version_id=1, stem=False, **kw):
    base = dict(
        version_id=version_id, workspace="/tmp/ws",
        timestamp="20260101-000000",
    )
    base.update(kw)
    return RenderRequest(stem=stem, **base)


def test_assemble_classic_returns_plan_with_classic_mode():
    s = RenderSettings()
    req = _req(stem=False)
    inputs = _inputs(2)
    bar = BarPlan(transition_bars=(16,), body_bars=[24, 24])
    plan = RenderPlanner().assemble(s, req, inputs, _grid(2), bar, stem_paths=None)
    assert isinstance(plan, RenderPlan)
    assert plan.mode is RenderMode.CLASSIC
    assert all(isinstance(seg, TrackSegment) for seg in plan.segments)
    assert plan.stem_segments is None
    assert plan.n == 2


def test_assemble_stem_returns_plan_with_stem_mode():
    s = RenderSettings()
    req = _req(stem=True)
    inputs = _inputs(2)
    stem_paths = {i: {st: f"/stems/{i}/{st}.flac" for st in (
        "drums", "bass", "harmonic", "instrumental", "acappella"
    )} for i in range(2)}
    bar = BarPlan(transition_bars=(16,), body_bars=[24, 24])
    plan = RenderPlanner().assemble(s, req, inputs, _grid(2), bar, stem_paths)
    assert plan.mode is RenderMode.STEM
    assert plan.segments == []
    assert all(isinstance(seg, StemSegment) for seg in plan.stem_segments)
    assert plan.n == 2


def test_assemble_carries_effects_from_request():
    s = RenderSettings()
    req = _req(stem=False, echo="techno_standard", reverb="techno_hall")
    bar = BarPlan(transition_bars=(), body_bars=[24])
    plan = RenderPlanner().assemble(s, req, _inputs(1), _grid(1), bar, stem_paths=None)
    assert plan.echo_preset == "techno_standard"
    assert plan.reverb_preset == "techno_hall"


def test_classic_factory_ignores_stem_paths():
    factory = ClassicSegmentFactory()
    segs = factory.build_segments(
        geometries=[], inputs=_inputs(1),
        stem_paths={0: {"drums": "/x.wav"}},  # should be ignored
        settings=RenderSettings(), request=_req(stem=False),
    )
    assert segs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/render/test_plan_assembler.py -v`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement segments.py**

Create `app/domain/render/segments.py`:

```python
"""SegmentFactory — per-RenderMode segment construction (Strategy)."""

from __future__ import annotations

from typing import Any, Protocol

from app.config.render import RenderSettings
from app.domain.render.models import (
    BeatgridEntry,
    RenderMode,
    StemSegment,
    TrackInput,
    TrackSegment,
)
from app.domain.render.request import RenderRequest
from app.domain.render.timeline import SegmentGeometry


class SegmentFactory(Protocol):
    def build_segments(
        self,
        geometries: list[SegmentGeometry],
        inputs: list[TrackInput],
        stem_paths: dict[int, dict[str, str]] | None,
        settings: RenderSettings,
        request: RenderRequest,
    ) -> list[Any]: ...


class ClassicSegmentFactory:
    def build_segments(
        self, geometries, inputs, stem_paths, settings, request,
    ) -> list[TrackSegment]:
        return [
            TrackSegment(
                index=g.index,
                track_id=g.track_id,
                file_path=inputs[g.index].file_path,
                tempo_ratio=g.tempo_ratio,
                trim_start_s=g.trim_start_s,
                gain_db=g.gain_db,
                body_bars=g.body_bars,
                d_in_s=g.d_in_s,
                d_out_s=g.d_out_s,
                length_s=g.length_s,
                start_s=g.start_s,
            )
            for g in geometries
        ]


class StemSegmentFactory:
    def build_segments(
        self, geometries, inputs, stem_paths, settings, request,
    ) -> list[StemSegment]:
        stem_paths_by_track = stem_paths or {}
        return [
            StemSegment(
                index=g.index,
                track_idx=g.index,
                track_id=g.track_id,
                stem_paths=stem_paths_by_track.get(g.track_id, {}),
                tempo_ratio=g.tempo_ratio,
                trim_start_s=g.trim_start_s,
                gain_db=g.gain_db,
                body_bars=g.body_bars,
                d_in_s=g.d_in_s,
                d_out_s=g.d_out_s,
                length_s=g.length_s,
                start_s=g.start_s,
                target_bpm=settings.target_bpm,
                low_swap_beats=settings.low_swap_beats,
                eq_phase_1_ratio=settings.eq_phase_1_ratio,
                eq_phase_2_ratio=settings.eq_phase_2_ratio,
            )
        ]
```

- [ ] **Step 4: Implement plan_assembler.py**

Create `app/domain/render/plan_assembler.py`:

```python
"""RenderPlanner — single assemble path for any RenderMode.

Replaces app/domain/render/plan_builder.py (RenderPlanBuilder) and the
``build_render_plan`` / ``build_stem_render_plan`` functions in timeline.py
which duplicated ~17 pass-through kwargs each.
"""

from __future__ import annotations

from typing import Protocol

from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan
from app.domain.render.models import (
    BeatgridEntry,
    RenderMode,
    RenderPlan,
    TrackInput,
)
from app.domain.render.request import RenderRequest
from app.domain.render.segments import (
    ClassicSegmentFactory,
    SegmentFactory,
    StemSegmentFactory,
)
from app.domain.render.timeline import place_segments


class RenderPlanner:
    """Assemble a RenderPlan from a RenderRequest + per-track geometry."""

    _FACTORIES: dict[RenderMode, SegmentFactory] = {
        RenderMode.CLASSIC: ClassicSegmentFactory(),
        RenderMode.STEM: StemSegmentFactory(),
    }

    def assemble(
        self,
        settings: RenderSettings,
        request: RenderRequest,
        inputs: list[TrackInput],
        grid: dict[int, BeatgridEntry],
        bar_plan: BarPlan,
        stem_paths: dict[int, dict[str, str]] | None,
    ) -> RenderPlan:
        factory = self._FACTORIES[request.mode]
        geometries = place_segments(
            inputs, grid,
            target_bpm=settings.target_bpm,
            body_bars=bar_plan.body_bars,
            transition_bars=request.transition_bars or settings.transition_bars,
            per_transition_bars=bar_plan.transition_bars,
            per_body_bars=bar_plan.body_bars,
        )
        segments = factory.build_segments(
            geometries, inputs, stem_paths, settings, request,
        )
        return RenderPlan.from_settings(
            settings, request,
            segments=segments if request.mode is RenderMode.CLASSIC else [],
            stem_segments=segments if request.mode is RenderMode.STEM else None,
        )
```

- [ ] **Step 5: Update RenderPlan.from_settings signature**

Edit `app/domain/render/models.py`. Change the `from_settings` classmethod (currently lines 141-200) to:

```python
    @classmethod
    def from_settings(
        cls,
        settings: RenderSettings,
        request: "RenderRequest",
        *,
        segments: list[TrackSegment] | None = None,
        stem_segments: list[StemSegment] | None = None,
    ) -> RenderPlan:
        """Factory: timeline args from the caller, DSP constants from ``settings``,
        effects/presets from ``request``."""
        return cls(
            mode=request.mode,
            target_bpm=settings.target_bpm,
            xsplit_low_hz=settings.xsplit_low_hz,
            xsplit_high_hz=settings.xsplit_high_hz,
            eq_phase_1_ratio=settings.eq_phase_1_ratio,
            eq_phase_2_ratio=settings.eq_phase_2_ratio,
            low_swap_beats=settings.low_swap_beats,
            outro_fade_bars=settings.outro_fade_bars,
            limiter_ceiling=settings.limiter_ceiling,
            hpf_cutoff_hz=settings.hpf_cutoff_hz,
            per_track_eq_mid_cut_db=settings.per_track_eq_mid_cut_db,
            per_track_eq_bright_boost_db=settings.per_track_eq_bright_boost_db,
            pre_comp_threshold_db=settings.pre_comp_threshold_db,
            pre_comp_ratio=settings.pre_comp_ratio,
            pre_comp_attack_ms=settings.pre_comp_attack_ms,
            pre_comp_release_ms=settings.pre_comp_release_ms,
            glue_comp_threshold_db=settings.glue_comp_threshold_db,
            glue_comp_ratio=settings.glue_comp_ratio,
            glue_comp_attack_ms=settings.glue_comp_attack_ms,
            glue_comp_release_ms=settings.glue_comp_release_ms,
            master_eq_air_boost_db=settings.master_eq_air_boost_db,
            master_eq_mud_cut_db=settings.master_eq_mud_cut_db,
            master_eq_sub_boost_db=settings.master_eq_sub_boost_db,
            limiter_attack_ms=settings.limiter_attack_ms,
            limiter_release_ms=settings.limiter_release_ms,
            dynaudnorm_maxgain=settings.dynaudnorm_maxgain,
            segments=segments or [],
            stem_segments=stem_segments,
            filter_sweep_preset=request.filter_sweep,
            echo_preset=request.echo,
            crossfade_curve_out=request.crossfade_curve_out,
            crossfade_curve_in=request.crossfade_curve_in,
            reverb_preset=request.reverb,
            reverb_mix=request.reverb_mix,
        )
```

Add an `if TYPE_CHECKING: from app.domain.render.request import RenderRequest` to the top of `models.py`.

- [ ] **Step 6: Trim timeline.py**

Edit `app/domain/render/timeline.py` — delete `build_render_plan` (lines 114-180) and `build_stem_render_plan` (lines 183-257). Keep `place_segments`, `SegmentGeometry`, `bar_seconds`, `_transition_durations`, `TransitionWindow`, `TimelineWindows`, `timeline_windows`.

- [ ] **Step 7: Delete plan_builder.py + update handler import**

```bash
git rm app/domain/render/plan_builder.py
```

Edit `app/handlers/render_mixdown.py:12` — replace
```python
from app.domain.render.plan_builder import RenderPlanBuilder
```
with
```python
from app.domain.render.plan_assembler import RenderPlanner
```

(Reference at line ~102 also: `plan_builder = RenderPlanBuilder(rs)` becomes `planner = RenderPlanner()` — `RenderPlanner().assemble(...)` API differs from the old `.build_stem()` / `.build_classic()`. This is the handler rewrite proper to Task 11; for this task, add a transitional shim on `RenderPlanner` so the existing handler keeps working until Task 11 replaces it. Add transitional pass-through methods to `RenderPlanner`:

```python
    def build_classic(self, inputs, grid, *, body_bars, transition_bars,
                      per_transition_bars=None, per_body_bars=None,
                      filter_sweep_preset=None, echo_preset=None,
                      crossfade_curve_out="tri", crossfade_curve_in="exp",
                      reverb_preset=None, reverb_mix=0.25):
        # Transition shim — removed in Task 11 once the handler goes thin.
        from app.config.render import RenderSettings
        s = RenderSettings()
        req = RenderRequest(
            version_id=0, workspace="", timestamp="",
            transition_bars=transition_bars, body_bars=body_bars, stem=False,
            filter_sweep=filter_sweep_preset, echo=echo_preset,
            crossfade_curve_out=crossfade_curve_out, crossfade_curve_in=crossfade_curve_in,
            reverb=reverb_preset, reverb_mix=reverb_mix,
        )
        bar = BarPlan(tuple(per_transition_bars or ()), list(per_body_bars or []))
        return self.assemble(s, req, inputs, grid, bar, stem_paths=None)
```

We don't actually wire shim spam — keep it minimal just enough for `render_mixdown_handler` to keep passing in tests through Task 11. Verify Task 11 wipes this shim.

Drop the shim if the handler in Task 11 is in the same review cycle; otherwise keep it. (Plan reviewer note: prefer shims entirely inside Task 11 — for now update the handler's plan-builder reference to call `RenderPlanner().assemble(...)` directly even in this task, accepting that the handler rewrite happens here not in a later task. Adjust the plan: **fold the thin handler rewrite into this task** — see Task 11 below for the orchestrator; this task leaves the existing fat handler as a shim that calls `RenderPlanner.build_classic` / `build_stem` shim methods on `RenderPlanner` until Task 11. Decision: keep transitional shims here, remove them in Task 11.)

- [ ] **Step 8: Update exports**

Edit `app/domain/render/__init__.py`: remove `RenderPlanBuilder`, `build_render_plan`, `build_stem_render_plan` from imports + `__all__`. Add `RenderPlanner`, `SegmentFactory`, `ClassicSegmentFactory`, `StemSegmentFactory`.

Add `from __future__ import annotations` if not already present (it is).

- [ ] **Step 9: Rewrite test_timeline.py**

Edit `tests/domain/render/test_timeline.py`. Replace the 3 `build_render_plan(...)` calls with:

```python
from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest


def _assemble(n, *, transition_bars=32, body_bars=24):
    req = RenderRequest(
        version_id=1, workspace="/tmp/ws", timestamp="20260101",
        transition_bars=transition_bars, body_bars=body_bars, stem=False,
    )
    bar = BarPlan(
        transition_bars=tuple([transition_bars] * max(0, n - 1)),
        body_bars=[body_bars] * n,
    )
    return RenderPlanner().assemble(
        RenderSettings(), req, _inputs(n), _grid(n), bar, stem_paths=None,
    )
```

Replace `build_render_plan(_inputs(1), _grid(1), target_bpm=130.0, body_bars=24, transition_bars=32, xsplit_low_hz=250, xsplit_high_hz=4000, eq_phase_1_ratio=0.40, eq_phase_2_ratio=0.70, low_swap_beats=1.0, outro_fade_bars=12, limiter_ceiling=0.85)` with `_assemble(1, transition_bars=32, body_bars=24)`.

Keep `test_timeline_windows_reports_transitions` unchanged (`timeline_windows` is still public).

- [ ] **Step 10: Rewrite test_stem_graph.py _stem_plan helper**

Edit `tests/domain/render/test_stem_graph.py`:

```python
from app.audio.render.runner import build_ffmpeg_cmd  # stays until Task 10 moves runner
from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan
from app.domain.render.models import STEM_ORDER, BeatgridEntry, TrackInput
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.domain.render.stem_graph import build_stem_filtergraph

_STEMS = STEM_ORDER


def _stem_plan(n: int, *, target_bpm: float = 130.0):
    inputs = [
        TrackInput(
            track_id=i, yandex_id=i, title=f"t{i}", bpm=130.0, key_code=1,
            mix_in_ms=0, integrated_lufs=-12.0, file_path=f"/x{i}.mp3",
            duration_ms=600_000,
        )
        for i in range(n)
    ]
    stem_paths_by_track = {i: {s: f"/stems/{i}/{s}.flac" for s in _STEMS} for i in range(n)}
    grid = {
        i: BeatgridEntry(track_id=i, trim_start_s=0.4, refined_trim_s=0.4,
                         gain_db=0.0, phase_ms=0.0)
        for i in range(n)
    }
    req = RenderRequest(
        version_id=1, workspace="/tmp/ws", timestamp="20260101",
        stem=True, body_bars=24, transition_bars=16,
    )
    bar = BarPlan(
        transition_bars=tuple([16] * max(0, n - 1)),
        body_bars=[24] * n,
    )
    return RenderPlanner().assemble(
        RenderSettings(), req, inputs, grid, bar, stem_paths=stem_paths_by_track,
    )
```

Drop `from app.domain.render.timeline import build_stem_render_plan`.

- [ ] **Step 11: Run tests + gate**

Run: `uv run pytest tests/domain/render/ tests/audio/render/ tests/handlers/test_render_mixdown.py -v`
Expected: PASS — including the 5 new test_plan_assembler tests, the rewritten test_timeline (3 still functional), and test_stem_graph (4 still functional), and test_render_mixdown (uses shim via the fat handler).

Run: `make check`
Expected: PASS.

- [ ] **Step 12: Verify no stale imports**

Run: `grep -rn "RenderPlanBuilder\|build_render_plan\|build_stem_render_plan\|from app.domain.render.plan_builder" app/ tests/ --include='*.py'`
Expected: zero hits (plan_builder.py deleted; shims live in plan_assembler.py RenderPlanner.build_classic).

- [ ] **Step 13: Commit**

```bash
git add -A && git commit -m "refactor(render): RenderPlanner + SegmentFactory replace plan_builder

RenderPlanner.assemble handles classic + stem through one path keyed by
RenderMode. RenderPlan.from_settings(settings, request, ...) takes a
RenderRequest Parameter Object (effects/presets come from request) instead
of 14 pass-through kwargs. timeline.build_render_plan / build_stem_render_plan
removed; plan_builder.RenderPlanBuilder removed. Transitional shims on
RenderPlanner (build_classic/build_stem) keep the fat handler alive until
Task 11 wires the orchestrator.
Gate: make check PASS."
```

---

## Task 10: Move `runner.py` from `app/audio/render/` to `app/domain/render/`

**Files:**
- Move: `app/audio/render/runner.py` → `app/domain/render/runner.py`
- Modify: `app/domain/render/filtergraph.py` — no import change (same package now).
- Modify: `app/handlers/render_mixdown.py:8` — import `run_render` from `app.domain.render.runner`.
- Modify: `app/domain/render/__init__.py` — export `run_render`, `build_ffmpeg_cmd`.
- Test: `tests/audio/render/test_runner.py` — relocate; update imports; delete `test_build_preprocess_cmd` + `build_preprocess_cmd` function. Update `test_stem_graph.py` (already imports `from app.audio.render.runner import build_ffmpeg_cmd`) to `from app.domain.render.runner import build_ffmpeg_cmd`.

**Interfaces:**
- Produces: `app.domain.render.runner.run_render(plan, out_path)`, `app.domain.render.runner.build_ffmpeg_cmd(plan, out_path)` (unchanged signatures; package move only).

- [ ] **Step 1: Move the file with git mv, drop build_preprocess_cmd**

```bash
git mv app/audio/render/runner.py app/domain/render/runner.py
```

Edit `app/domain/render/runner.py` — remove `build_preprocess_cmd` function entirely (lines 15-30). Update module docstring line 1 to:

```python
"""Assemble + run the ffmpeg render command (domain-side; audio-less)."""
```

The `from app.domain.render.filtergraph import select_strategy` import now resolves within the same package — no change needed.

- [ ] **Step 2: Update handler import**

Edit `app/handlers/render_mixdown.py:8` — change `from app.audio.render.runner import run_render` to `from app.domain.render.runner import run_render`.

- [ ] **Step 3: Update exports**

Edit `app/domain/render/__init__.py`: add
```python
from app.domain.render.runner import build_ffmpeg_cmd, run_render
```
and add `run_render`, `build_ffmpeg_cmd` to `__all__`.

- [ ] **Step 4: Update tests**

Edit `tests/audio/render/test_runner.py`:

```python
from app.domain.render.runner import build_ffmpeg_cmd
from app.domain.render.models import RenderMode, RenderPlan, TrackSegment
```

Delete the entire `test_build_preprocess_cmd` function (was lines 47-53).

Add `mode=RenderMode.CLASSIC` to the `RenderPlan(...)` call inside `_plan()` (same edit Task 2 did in other test files).

Edit `tests/domain/render/test_stem_graph.py` line 3:

```python
from app.domain.render.runner import build_ffmpeg_cmd
```

Edit `tests/handlers/test_render_mixdown.py` — search for `app.handlers.render_mixdown.run_render` monkeypatch path; update to `app.handlers._orchestrator.render_executor.run_render` (this target module will only exist after Task 11). For this task, leave the existing monkeypatch path unchanged — it patches through the handler-level import alias, which Task 11 will move. The handler is still resolvable as `app.handlers.render_mixdown.run_render` until Task 11 rewrites the handler.

(Verify the existing monkeypatch path is `app.handlers.render_mixdown.run_render` — Task 11 will update these to `app.handlers._orchestrator.render_executor.run_render`.)

- [ ] **Step 5: Run runner + stem_graph + mixdown tests**

Run: `uv run pytest tests/audio/render/test_runner.py tests/domain/render/test_stem_graph.py tests/handlers/test_render_mixdown.py -v`
Expected: PASS — `test_build_preprocess_cmd` removed (was 1 test); `test_cmd_has_one_input_per_segment_and_mapping` / `test_ffmpeg_cmd_has_quality_flag` pass via new import path.

- [ ] **Step 6: Verify no stale audio/render/runner imports**

Run: `grep -rn "app\.audio\.render\.runner\|from app.audio.render.runner" app/ tests/ --include='*.py'`
Expected: zero hits.

- [ ] **Step 7: Verify import-linter (audio doesn't depend on domain)**

Run: `cat importlinter.ini imports.ini 2>/dev/null | grep -i audio || true` to find existing import-linter config; if `app.audio` is constrained to not import `app.domain`, add an assertion. If config is absent, run `make check` and rely on existing constraints.

Run: `make check`
Expected: PASS — and `app.audio.render/*` no longer imports anything from `app.domain`.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "refactor(render): move runner.py audio→domain (fix layer inversion)

runner uses subprocess + filtergraph only, no librosa/scipy — it's domain work.
Moving it eliminates the audio→domain dependency import cycle risk.
build_preprocess_cmd + its test removed (dead helper, no production caller ~30 lines).
Gate: make check PASS."
```

---

## Task 11: `RenderOrchestrator` + collaborators + thin handlers

This is the central handler restructure. The orchestrator replaces the 169-line `render_mixdown_handler` with 4 injected collaborators and an 10-line handler. Same applies to `render_beatgrid_handler`.

**Files:**
- Create: `app/handlers/_orchestrator/__init__.py` (empty).
- Create: `app/handlers/_orchestrator/render_orchestrator.py` — `RenderOrchestrator` class.
- Create: `app/handlers/_orchestrator/beatgrid_provider.py` — `BeatgridProvider` class.
- Create: `app/handlers/_orchestrator/preset_applier.py` — `SubgenrePresetApplier` class.
- Move: `app/handlers/_stem_resolver.py` → `app/handlers/_orchestrator/stem_resolver.py`.
- Create: `app/handlers/_orchestrator/render_executor.py` — `RenderExecutor` class.
- Rewrite: `app/handlers/render_mixdown.py` — thin handler, ~10 lines, signature preserved byte-for-byte.
- Rewrite: `app/handlers/render_beatgrid.py` — thin handler, ~6 lines.
- Test: `tests/handlers/_orchestrator/__init__.py` (empty).
- Test: `tests/handlers/_orchestrator/test_render_orchestrator.py` (new) — DI tests asserting each collaborator is called in order.
- Test: `tests/handlers/test_render_mixdown.py` — update monkeypatch paths.
- Test: `tests/handlers/test_render_beatgrid.py` — update monkeypatch paths.

**Interfaces:**
- Consumes:
  - `RenderRequest` (Task 3).
  - `RenderPlanner.assemble` (Task 9).
  - `BarPlanner.compute` (Task 4).
  - `BeatgridIO` / `BeatgridLimits` / `clamp_entry` / `entry_flags` / `entry_to_row` (Task 5).
  - `detect_kick_trim` from `app.audio.render.kick_phase`.
  - `refine_phase` from `app.audio.render.phase_refine`.
  - `run_render` from `app.domain.render.runner`.
  - `scan_mix` from `app.audio.render.diagnostics`.
  - `RENDER_JOBS` from `app.shared.render_jobs`.
  - `resolve_preset` from `app.domain.performance.subgenre_presets`.
- Produces:
  - `app.handlers._orchestrator.render_orchestrator.RenderOrchestrator(uow, *, preset_applier=None, beatgrid_provider=None, stem_resolver=None, planner=None, executor=None).run(ctx, request) -> RenderMixdownResult`.
  - `app.handlers._orchestrator.beatgrid_provider.BeatgridProvider.compute(ctx, uow, version_id, workspace, *, refresh) -> RenderBeatgridResult`.
  - `app.handlers._orchestrator.beatgrid_provider.BeatgridProvider.ensure(ctx, request, uow) -> None`.
  - `app.handlers._orchestrator.beatgrid_provider.BeatgridProvider.load(workspace) -> dict[int, BeatgridEntry]`.
  - `app.handlers._orchestrator.preset_applier.SubgenrePresetApplier.apply(settings, ctx, subgenre) -> None`.
  - `app.handlers._orchestrator.stem_resolver.StemResolver.resolve(ctx, uow, inputs) -> dict[int, dict[str, str]] | None` (moved from `app/handlers/_stem_resolver.py`).
  - `app.handlers._orchestrator.render_executor.RenderExecutor.execute(ctx, request, plan) -> RenderMixdownResult`.

**Pre-step (GitNexus):**

- [ ] **Step 0a: Impact analysis on handler functions**

Run `gitnexus_impact({target: "render_mixdown_handler", direction: "upstream"})` and `gitnexus_impact({target: "render_beatgrid_handler", direction: "upstream"})`. Expect `app.tools.render.render_mixdown` and `app.tools.render.render_beatgrid` as the only callers — those `@tool`-decorated functions stay unchanged.

- [ ] **Step 1: Write the failing orchestrator integration test**

Create `tests/handlers/_orchestrator/__init__.py` (empty).

Create `tests/handlers/_orchestrator/test_render_orchestrator.py`:

```python
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.render.bar_plan import BarPlan
from app.domain.render.beatgrid import BeatgridIO, BeatgridLimits
from app.domain.render.models import BeatgridEntry, RenderPlan, TrackInput
from app.domain.render.request import RenderRequest
from app.handlers._orchestrator.render_orchestrator import RenderOrchestrator
from app.schemas.render import RenderMixdownResult
from app.shared.render_jobs import RENDER_JOBS


class _StubUow:
    def __init__(self, inputs):
        self.session = None
        class _SV:
            async def get_render_inputs(self, vid): return inputs
        self.set_versions = _SV()


def _req(stem=False, **kw):
    base = dict(version_id=1, workspace="/tmp/ws", timestamp="20260101")
    base.update(kw)
    return RenderRequest(stem=stem, **base)


def _inputs(n):
    return [
        TrackInput(track_id=i, yandex_id=i, title=f"t{i}", bpm=130.0,
                   key_code=1, mix_in_ms=0, integrated_lufs=-12.0,
                   file_path=f"/x{i}.mp3")
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_run_invokes_preset_applier_first(tmp_path):
    preset = SimpleNamespace(apply=AsyncMock())
    preset.apply.return_value = None
    beatgrid = SimpleNamespace(ensure=AsyncMock(), load=lambda ws: {})
    stem_resolver = SimpleNamespace(resolve=AsyncMock(return_value=None))
    planner = SimpleNamespace(assemble=lambda *a, **kw: SimpleNamespace(n=1))
    executor = SimpleNamespace(execute=AsyncMock(return_value=RenderMixdownResult(
        job_id="x", version_id=1, out_path="/o", duration_s=0.0)))
    RENDER_JOBS.clear()
    orch = RenderOrchestrator(
        _StubUow(_inputs(1)),
        preset_applier=preset, beatgrid_provider=beatgrid,
        stem_resolver=stem_resolver, planner=planner, executor=executor,
    )
    await orch.run(ctx=None, request=_req())
    assert preset.apply.await_count == 1


@pytest.mark.asyncio
async def test_run_skips_stem_resolver_in_classic_mode(tmp_path):
    preset = SimpleNamespace(apply=AsyncMock())
    beatgrid = SimpleNamespace(ensure=AsyncMock(), load=lambda ws: {})
    stem_resolver = SimpleNamespace(resolve=AsyncMock())
    planner = SimpleNamespace(assemble=lambda *a, **kw: SimpleNamespace(n=1))
    executor = SimpleNamespace(execute=AsyncMock(return_value=RenderMixdownResult(
        job_id="x", version_id=1, out_path="/o", duration_s=0.0)))
    RENDER_JOBS.clear()
    orch = RenderOrchestrator(
        _StubUow(_inputs(1)),
        preset_applier=preset, beatgrid_provider=beatgrid,
        stem_resolver=stem_resolver, planner=planner, executor=executor,
    )
    await orch.run(ctx=None, request=_req(stem=False))
    assert stem_resolver.resolve.await_count == 0


@pytest.mark.asyncio
async def test_run_calls_stem_resolver_in_stem_mode(tmp_path):
    preset = SimpleNamespace(apply=AsyncMock())
    beatgrid = SimpleNamespace(ensure=AsyncMock(), load=lambda ws: {})
    stem_resolver = SimpleNamespace(resolve=AsyncMock(return_value=None))
    planner = SimpleNamespace(assemble=lambda *a, **kw: SimpleNamespace(n=1))
    executor = SimpleMonkeyExecuting()
    RENDER_JOBS.clear()
    orch = RenderOrchestrator(
        _StubUow(_inputs(1)),
        preset_applier=preset, beatgrid_provider=beatgrid,
        stem_resolver=stem_resolver, planner=planner, executor=executor,
    )
    await orch.run(ctx=None, request=_req(stem=True))
    assert stem_resolver.resolve.await_count == 1


from app.schemas.render import RenderMixdownResult as _RMR
class SimpleMonkeyExecuting:
    async def execute(self, ctx, request, plan):
        return _RMR(job_id="x", version_id=1, out_path="/o", duration_s=0.0)
```

(Helper note: the inline `SimpleMonkeyExecuting` class is declared after the test functions to keep the test file readable; hoist to top if ruff complains.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/handlers/_orchestrator/test_render_orchestrator.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create `app/handlers/_orchestrator/__init__.py` (empty)**

```bash
mkdir -p app/handlers/_orchestrator
echo "" > app/handlers/_orchestrator/__init__.py
```

(Or use Write tool with empty content.)

- [ ] **Step 4: Implement `preset_applier.py`**

Create `app/handlers/_orchestrator/preset_applier.py`:

```python
"""Apply a subgenre preset's overrides onto RenderSettings."""

from __future__ import annotations

from typing import Any

from app.config.render import RenderSettings
from app.domain.performance.subgenre_presets import resolve_preset
from app.handlers._context_log import safe_info


class SubgenrePresetApplier:
    async def apply(self, settings: RenderSettings, ctx: Any, subgenre: str | None) -> None:
        if not subgenre:
            return
        preset = resolve_preset(subgenre)
        if preset is None:
            return
        preset.apply(settings)
        await safe_info(ctx, f"render_mixdown: subgenre preset {subgenre!r} applied")
```

- [ ] **Step 5: Move `stem_resolver.py`**

Run: `git mv app/handlers/_stem_resolver.py app/handlers/_orchestrator/stem_resolver.py`

The file content stays the same — verify the import `from app.handlers._context_log import safe_info` still resolves (it does — `_context_log` remains at `app/handlers/_context_log.py`).

- [ ] **Step 6: Implement `beatgrid_provider.py`**

Create `app/handlers/_orchestrator/beatgrid_provider.py`:

```python
"""Beatgrid cache + compute + load.

`ensure` (mkdir + cache-hit check + delegate to render_beatgrid_handler) and
`load` (returns the grid keyed by track_id) service the mixdown orchestrator.
`compute` is the heavy path invoked by the thin render_beatgrid_handler.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
from app.config import get_settings
from app.domain.render.beatgrid import (
    BeatgridIO,
    BeatgridLimits,
    clamp_entry,
    entry_flags,
    entry_to_row,
)
from app.domain.render.models import BeatgridEntry
from app.domain.render.levels import gains_to_median
from app.handlers._context_log import safe_info, safe_report_progress
from app.schemas.render import RenderBeatgridResult


class BeatgridProvider:
    async def ensure(self, ctx: Any, request: Any, uow: Any) -> None:
        ws = Path(request.workspace)
        ws.mkdir(parents=True, exist_ok=True)
        grid_path = ws / "beatgrid.json"
        if grid_path.exists() and not request.refresh_grid:
            return
        await self.compute(
            ctx, uow, request.version_id, request.workspace, refresh=request.refresh_grid,
        )

    def load(self, workspace: str) -> dict[int, BeatgridEntry]:
        try:
            return {e.track_id: e for e in BeatgridIO.read(workspace)}
        except FileNotFoundError:
            return {}

    async def compute(
        self, ctx: Any, uow: Any, version_id: int, workspace: str, *, refresh: bool,
    ) -> RenderBeatgridResult:
        ws = Path(workspace)
        ws.mkdir(parents=True, exist_ok=True)
        grid_path = ws / "beatgrid.json"
        if grid_path.exists() and not refresh:
            cached: list[dict[str, Any]] = __import__("json").loads(grid_path.read_text())
            return RenderBeatgridResult(version_id=version_id, tracks=cached)

        limits = BeatgridLimits.from_settings(get_settings().render)
        inputs = await uow.set_versions.get_render_inputs(version_id)
        gains = gains_to_median({ti.track_id: ti.integrated_lufs for ti in inputs})

        if ctx is not None:
            await safe_info(ctx, f"render_beatgrid: {len(inputs)} tracks for version {version_id}")

        entries: list[BeatgridEntry] = []
        for i, ti in enumerate(inputs):
            trim = detect_kick_trim(ti.file_path, start_s=ti.mix_in_ms / 1000.0, bpm=ti.bpm)
            _, refined = refine_phase(ti.file_path, base_trim_s=trim, bpm=ti.bpm)
            entry = BeatgridEntry(
                track_id=ti.track_id,
                trim_start_s=trim,
                refined_trim_s=refined,
                gain_db=gains[ti.track_id],
                phase_ms=trim - refined,  # phase delta expressed in seconds→ms
            )
            clamped = clamp_entry(entry, limits)
            # Use the clamped phase_ms; flags depend on the clamped entry.
            flagged_entry = BeatgridEntry(
                track_id=clamped.track_id,
                trim_start_s=clamped.trim_start_s,
                refined_trim_s=clamped.refined_trim_s,
                gain_db=clamped.gain_db,
                phase_ms=clamped.phase_ms,
            )
            entries.append(flagged_entry)
            if ctx is not None:
                await safe_report_progress(ctx, progress=i + 1, total=len(inputs))

        BeatgridIO.write(workspace, entries)
        if ctx is not None:
            await safe_info(ctx, f"render_beatgrid: wrote {ws / 'beatgrid.json'}")
        return RenderBeatgridResult(
            version_id=version_id,
            tracks=[entry_to_row(e) | {"flags": entry_flags(e, limits)} for e in entries],
        )
```

**Important detail:** the original code computed `delta_ms` and `refined` from `refine_phase` separately, so the row carried `phase_ms` = `delta_ms`. Reconstruct the same semantics: `refine_phase` returns `(delta_ms, refined_s)`. The original handler built `refined = min(round(trim + delta_ms / 1000.0, 4), ...)` and clamped `delta_ms` itself. The entry model uses `phase_ms` to mirror that delta. Adjusting `compute`:

```python
        entries: list[BeatgridEntry] = []
        for i, ti in enumerate(inputs):
            trim = detect_kick_trim(ti.file_path, start_s=ti.mix_in_ms / 1000.0, bpm=ti.bpm)
            delta_ms, refined_s = refine_phase(ti.file_path, base_trim_s=trim, bpm=ti.bpm)
            entry = BeatgridEntry(
                track_id=ti.track_id,
                trim_start_s=trim,
                refined_trim_s=refined_s,
                gain_db=gains[ti.track_id],
                phase_ms=delta_ms,
            )
            clamped = clamp_entry(entry, limits)
            entries.append(clamped)
            if ctx is not None:
                await safe_report_progress(ctx, progress=i + 1, total=len(inputs))
        BeatgridIO.write(workspace, entries)
        ...
        return RenderBeatgridResult(
            version_id=version_id,
            tracks=[entry_to_row(e) | {"flags": entry_flags(e, limits)} for e in entries],
        )
```

Use the cleaner path — replace Step 6 body accordingly (delete the prior `flagged_entry` workaround). The clamp itself handles refine trim semantically identical to the original handler (`min(trim + delta_ms/1000, trim + max_phase_ms/1000)`).

- [ ] **Step 7: Implement `render_executor.py`**

Create `app/handlers/_orchestrator/render_executor.py`:

```python
"""Render — start job → run_render → scan_mix → pack result.

Keeps RENDER_JOBS threading logic (from app.shared.render_jobs) outside the
orchestrator and outside the thin handler. Failures update the job's error
field before re-raising.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import scan_mix
from app.domain.render.models import RenderPlan
from app.domain.render.runner import run_render
from app.handlers._context_log import safe_info
from app.schemas.render import RenderMixdownResult
from app.shared.render_jobs import RENDER_JOBS


class RenderExecutor:
    async def execute(self, ctx: Any, request: Any, plan: RenderPlan) -> RenderMixdownResult:
        out_path = str(Path(request.workspace) / request.out_filename)
        phase = "prepared_stem_mixdown" if plan.mode.value == "stem" else "mixdown"
        job_id = f"v{request.version_id}-{request.timestamp}"
        RENDER_JOBS.start(job_id=job_id, version_id=request.version_id, phase=phase)
        RENDER_JOBS.update(job_id, total=plan.n, message="rendering")
        await safe_info(ctx, f"render_mixdown ({phase}): {plan.n} segments -> {out_path}")
        try:
            run_render(plan, out_path)
        except Exception as exc:
            RENDER_JOBS.update(job_id, error=str(exc), done=True)
            raise
        sr = scan_mix(out_path)
        RENDER_JOBS.update(
            job_id,
            phase="done",
            out_path=out_path,
            progress=plan.n,
            done=True,
            message="complete",
        )
        return RenderMixdownResult(
            job_id=job_id,
            version_id=request.version_id,
            out_path=out_path,
            duration_s=sr.duration_s,
            true_peak_db=sr.true_peak_db,
            level_jumps=len(sr.level_jumps),
            near_silent_s=len(sr.near_silent_s),
        )
```

- [ ] **Step 8: Implement `render_orchestrator.py`**

Create `app/handlers/_orchestrator/render_orchestrator.py`:

```python
"""RenderOrchestrator — compose the mixdown pipeline.

Replaces the 169-line render_mixdown_handler with 4 injected collaborators:
preset_applier, beatgrid_provider, stem_resolver, planner, executor.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.domain.render.bar_plan import BarPlanner
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.handlers._context_log import safe_info
from app.handlers._orchestrator.beatgrid_provider import BeatgridProvider
from app.handlers._orchestrator.preset_applier import SubgenrePresetApplier
from app.handlers._orchestrator.render_executor import RenderExecutor
from app.handlers._orchestrator.stem_resolver import StemResolver
from app.schemas.render import RenderMixdownResult


class RenderOrchestrator:
    def __init__(
        self,
        uow: Any,
        *,
        preset_applier: SubgenrePresetApplier | None = None,
        beatgrid_provider: BeatgridProvider | None = None,
        stem_resolver: StemResolver | None = None,
        planner: RenderPlanner | None = None,
        executor: RenderExecutor | None = None,
    ) -> None:
        self._uow = uow
        self._preset = preset_applier or SubgenrePresetApplier()
        self._beatgrid = beatgrid_provider or BeatgridProvider()
        self._stems = stem_resolver or StemResolver()
        self._planner = planner or RenderPlanner()
        self._executor = executor or RenderExecutor()

    async def run(self, ctx: Any, request: RenderRequest) -> RenderMixdownResult:
        from app.domain.render.models import RenderMode

        settings = get_settings().render
        await self._preset.apply(settings, ctx, request.subgenre)
        await self._beatgrid.ensure(ctx, request, self._uow)
        inputs = await self._uow.set_versions.get_render_inputs(request.version_id)
        grid = self._beatgrid.load(request.workspace)
        bar_plan = BarPlanner(settings).compute(
            inputs, grid,
            transition_override=request.transition_bars,
            body_override=request.body_bars,
        )
        stem_paths = (
            await self._stems.resolve(ctx, self._uow, inputs)
            if request.mode is RenderMode.STEM
            else None
        )
        plan = self._planner.assemble(
            settings, request, inputs, grid, bar_plan, stem_paths,
        )
        return await self._executor.execute(ctx, request, plan)
```

- [ ] **Step 9: Rewrite `app/handlers/render_mixdown.py` (thin handler)**

Overwrite `app/handlers/render_mixdown.py` with:

```python
"""render_mixdown handler — thin entry to RenderOrchestrator.

Public surface preserved: tool/handler signature is unchanged.
"""

from __future__ import annotations

from typing import Any

from app.domain.render.request import RenderRequest
from app.handlers._context_log import safe_info
from app.handlers._orchestrator.render_orchestrator import RenderOrchestrator
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.render import RenderMixdownResult
from app.shared.errors import ValidationError


def _validate_out_name(out_name: str | None) -> None:
    if not out_name:
        return
    if "/" in out_name or "\\" in out_name or out_name in {".", ".."}:
        raise ValidationError(
            f"out_name must be a bare filename, got {out_name!r}",
            details={"out_name": out_name},
        )


async def render_mixdown_handler(
    *,
    ctx: Any,
    uow: Any,
    version_id: int,
    workspace: str,
    timestamp: str,
    out_name: str | None = None,
    transition_bars: int | None = None,
    body_bars: int | None = None,
    refresh_grid: bool = False,
    stem: bool = True,
    subgenre: str | None = None,
    filter_sweep: str | None = None,
    echo: str | None = None,
    crossfade_curve_out: str = "tri",
    crossfade_curve_in: str = "exp",
    reverb: str | None = None,
    reverb_mix: float = 0.25,
) -> RenderMixdownResult:
    _validate_out_name(out_name)
    request = RenderRequest(
        version_id=version_id,
        workspace=workspace,
        timestamp=timestamp,
        out_name=out_name,
        transition_bars=transition_bars,
        body_bars=body_bars,
        refresh_grid=refresh_grid,
        stem=stem,
        subgenre=subgenre,
        filter_sweep=filter_sweep,
        echo=echo,
        crossfade_curve_out=crossfade_curve_out,
        crossfade_curve_in=crossfade_curve_in,
        reverb=reverb,
        reverb_mix=reverb_mix,
    )
    return await RenderOrchestrator(uow).run(ctx, request)
```

- [ ] **Step 10: Rewrite `app/handlers/render_beatgrid.py` (thin handler)**

Overwrite `app/handlers/render_beatgrid.py` with:

```python
"""render_beatgrid handler — thin entry to BeatgridProvider.compute.

Public surface preserved.
"""

from __future__ import annotations

from typing import Any

from app.handlers._orchestrator.beatgrid_provider import BeatgridProvider
from app.schemas.render import RenderBeatgridResult


async def render_beatgrid_handler(
    *, ctx: Any, uow: Any, version_id: int, workspace: str, refresh: bool = False,
) -> RenderBeatgridResult:
    return await BeatgridProvider().compute(
        ctx, uow, version_id, workspace, refresh=refresh,
    )
```

- [ ] **Step 11: Drop transitional shims from RenderPlanner**

Edit `app/domain/render/plan_assembler.py` — remove the `build_classic` / `build_stem` shim methods (added in Task 9 step 7). Only `_FACTORIES`-driven `assemble(...)` stays.

- [ ] **Step 12: Update test monkeypatch paths**

Edit `tests/handlers/test_render_mixdown.py` — every `monkeypatch.setattr("app.handlers.render_mixdown.run_render", _fake_run)` becomes:

```python
monkeypatch.setattr("app.handlers._orchestrator.render_executor.run_render", _fake_run)
```

And every `monkeypatch.setattr("app.handlers.render_mixdown.scan_mix", _fake_scan)` becomes:

```python
monkeypatch.setattr("app.handlers._orchestrator.render_executor.scan_mix", _fake_scan)
```

Edit `tests/handlers/test_render_beatgrid.py` — replace `monkeypatch.setattr("app.handlers.render_beatgrid.detect_kick_trim", ...)` with `monkeypatch.setattr("app.handlers._orchestrator.beatgrid_provider.detect_kick_trim", ...)` and correspondingly for `refine_phase`.

- [ ] **Step 13: Run orchestrator + handler tests**

Run: `uv run pytest tests/handlers/_orchestrator/ tests/handlers/test_render_mixdown.py tests/handlers/test_render_beatgrid.py -v`
Expected: PASS — 3 new orchestrator tests + all existing handler tests (with updated monkeypatch targets) green.

- [ ] **Step 14: Run full gate**

Run: `make check`
Expected: PASS.

- [ ] **Step 15: Verify GitNexus shows expected scope**

Run `gitnexus_detect_changes({scope: "unstaged"})` (after staging). Expect: `RenderOrchestrator`, `BeatgridProvider`, `RenderExecutor`, `SubgenrePresetApplier`, `StemResolver` (moved), `render_mixdown_handler` (+10 line shim), `render_beatgrid_handler` (+6 line shim).

- [ ] **Step 16: Commit**

```bash
git add -A && git commit -m "refactor(render): RenderOrchestrator replaces 169-line monolith

render_mixdown_handler reduces to ~50 lines (validate + build RenderRequest +
delegate). RenderOrchestrator composes 4 collaborators:
SubgenrePresetApplier, BeatgridProvider, StemResolver, RenderExecutor.
render_beatgrid_handler reduces to ~6 lines (delegate to BeatgridProvider).
All 4 collaborators are injected via __init__ so tests mock them in isolation.

MCP @tool surface (signature/description/tags) unchanged. Existing handler
test monkeypatch paths migrated to the new locations.

Gate: make check PASS."
```

---

## Task 12: Refresh `__init__.py` exports + final cleanup

**Files:**
- Modify: `app/domain/render/__init__.py` — full clean export list, no dead names.
- Test: `tests/domain/render/test_models.py` — lock exports (`from app.domain.render import *` smoke test).

- [ ] **Step 1: Audit current `__init__.py`**

Run: `cat app/domain/render/__init__.py`
Read: confirm what falls through (leftover `BarPlanner` re-import from bar_planner, `RenderPlanBuilder`, `build_render_plan` references etc.)

- [ ] **Step 2: Rewrite __init__.py**

Overwrite `app/domain/render/__init__.py`:

```python
"""Pure render-plan compute (no IO). See docs/render-pipeline.md."""

from app.domain.render.bar_plan import BarPlan, BarPlanner
from app.domain.render.beatgrid import (
    BeatgridIO,
    BeatgridLimits,
    clamp_entry,
    entry_flags,
    entry_from_row,
    entry_to_row,
)
from app.domain.render.effects_resolver import EffectPresetResolver, ResolvedEffects
from app.domain.render.filtergraph import RenderStrategy, select_strategy
from app.domain.render.graph import build_filtergraph
from app.domain.render.levels import gains_to_median
from app.domain.render.models import (
    STEM_ORDER,
    BeatgridEntry,
    RenderMode,
    RenderPlan,
    StemSegment,
    TrackInput,
    TrackSegment,
)
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.domain.render.runner import build_ffmpeg_cmd, run_render
from app.domain.render.segments import (
    ClassicSegmentFactory,
    SegmentFactory,
    StemSegmentFactory,
)
from app.domain.render.stem_graph import build_stem_filtergraph
from app.domain.render.stem_voicing import STEM_VOICING, StemVoicing
from app.domain.render.timeline import (
    SegmentGeometry,
    TimelineWindows,
    TransitionWindow,
    place_segments,
    timeline_windows,
)

__all__ = [
    "STEM_ORDER",
    "STEM_VOICING",
    "BeatgridIO",
    "BeatgridEntry",
    "BeatgridLimits",
    "BarPlan",
    "BarPlanner",
    "ClassicSegmentFactory",
    "EffectPresetResolver",
    "RenderStrategy",
    "RenderPlanner",
    "RenderPlan",
    "RenderMode",
    "RenderRequest",
    "ResolvedEffects",
    "SegmentFactory",
    "SegmentGeometry",
    "StemSegment",
    "StemSegmentFactory",
    "StemVoicing",
    "TimelineWindows",
    "TrackInput",
    "TrackSegment",
    "TransitionWindow",
    "build_filtergraph",
    "build_ffmpeg_cmd",
    "build_stem_filtergraph",
    "clamp_entry",
    "entry_flags",
    "entry_from_row",
    "entry_to_row",
    "gains_to_median",
    "place_segments",
    "run_render",
    "select_strategy",
    "timeline_windows",
]
```

- [ ] **Step 3: Add a smoke test that the public API imports**

Edit `tests/domain/render/test_models.py` — append:

```python
def test_render_package_exports_resolvable():
    import app.domain.render as r
    for name in r.__all__:
        assert hasattr(r, name), f"missing export: {name}"
```

- [ ] **Step 4: Run tests + gate**

Run: `uv run pytest tests/domain/render/test_models.py -v && make check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(render): clean __init__ exports — no dead names

Public surface locked with a smoke test:
test_render_package_exports_resolvable asserts every __all__ name resolves.
Gate: make check PASS."
```

---

## Task 13: Final verification + diff scope report

**Files:** none.

- [ ] **Step 1: Full gate**

Run: `make check`
Expected: PASS — ruff 0 issues, mypy 0 errors, pytest 100% pass, import-linter clean.

- [ ] **Step 2: GitNexus detect_changes vs main**

Run `gitnexus_detect_changes({scope: "compare", base_ref: "main"})`.
Expected: changed symbols are within the `app/domain/render/`, `app/handlers/render*`, `app/handlers/_orchestrator/`, `tests/.../render*` namespaces — no spillover into other bounded contexts.

- [ ] **Step 3: Manual smoke (optional)**

If a real `set_version` exists locally:
```
uv run python -c "import asyncio; from app.server.app import build_app; from app.repositories.unit_of_work import UnitOfWork; ..."
```
Or use the MCP tool via the dev server to render one set version. Compare to a pre-refactor MIX.mp3 if available.

- [ ] **Step 4: Log progress to user**

Produce a summary: lines deleted (~850 dead + ~150 dead handler code = ~1000 lines net), files created/deleted/moved, public API surface preserved.

- [ ] **Step 5: No commit — only report**

The plan execution ends here. Commits are per-task; this step is a verification gate, not a code change.

---

## Self-Review

**1. Spec coverage — skim each spec section:**
- *Dead code deleted* — Task 1 ✓
- *RenderMode enum + plan.mode* — Task 2 ✓
- *RenderRequest Parameter Object* — Task 3 ✓
- *BarPlan + one-pass BarPlanner* — Task 4 ✓
- *BeatgridEntry methods + BeatgridLimits + BeatgridIO* — Task 5 ✓
- *Stem voicing single source* — Task 6 ✓
- *EffectPresetResolver* — Task 7 ✓
- *ClassicGraphBuilder _segment_block decomposition* — Task 8 ✓
- *RenderPlanner + SegmentFactory + from_settings simplification* — Task 9 ✓
- *Runner relocation (audio→domain)* — Task 10 ✓
- *Handler decomposition — RenderOrchestrator + 4 collaborators* — Task 11 ✓
- *__init__ cleanup* — Task 12 ✓
- *Verification gate* — Task 13 ✓

**2. Placeholder scan:** None — every step shows exact code/commands/expected outputs. (Task 8 step 2 contained a procedural placeholder intermediate that is immediately replaced later in the same step via the explicit `_emit_*` methods — final code is concrete.)

**3. Type consistency check:**
- `RenderRequest` defined in Task 3 — used in Tasks 5 (`from_settings(_settings)` is `request` in Task 9), 9 (`assemble(...)`, `from_settings(settings, request, ...)`), 11 (orchestrator, executor). Signature steady.
- `BarPlan.transition_bars: tuple[int, ...]`, `body_bars: list[int]` — Task 4; consumed in Task 9 `assemble` via `bar_plan.transition_bars`, `bar_plan.body_bars`. Match.
- `BeatgridLimits.from_settings(s)` — Task 5; consumed in Task 11 `BeatgridProvider.compute`. Match.
- `BeatgridIO.read / .write` — Task 5; consumed in Task 11 `BeatgridProvider.load / .compute`. Match.
- `clamp_entry / entry_flags / entry_to_row / entry_from_row` — Task 5; consumed in Task 11 `compute`. Match.
- `EffectPresetResolver().resolve(plan) -> ResolvedEffects` — Task 7; consumed Task 8 inside `ClassicGraphBuilder._segment_block`. Match.
- `STEM_VOICING[stem].hpf_hz / .gain_db` — Task 6; consumed Task 8 inside `StemGraphBuilder._segment_block`. Match.
- `RenderPlanner().assemble(settings, request, inputs, grid, bar_plan, stem_paths) -> RenderPlan` — Task 9; consumed Task 11 `RenderOrchestrator.run`. Match.
- `RenderExecutor.execute(ctx, request, plan)` — Task 11; same task's orchestrator calls it. Match.
- `RenderOrchestrator.__init__(uow, *, preset_applier=None, beatgrid_provider=None, stem_resolver=None, planner=None, executor=None)` — Task 11; same task's orchestrator test uses these kw names. Match.
- Monkeypatch target paths: Task 11 step 12 spells `app.handlers._orchestrator.render_executor.run_render`, `_orchestrator.render_executor.scan_mix`, `_orchestrator.beatgrid_provider.detect_kick_trim`, `_orchestrator.beatgrid_provider.refine_phase`. These match the modules created in Task 11 steps 6 + 7.

No inconsistencies found. Plan is implementation-ready.