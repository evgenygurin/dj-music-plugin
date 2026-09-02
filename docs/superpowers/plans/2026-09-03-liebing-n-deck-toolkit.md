# Liebing N-Deck Toolkit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 15 узких параметризуемых MCP-тулов (analyzer ×5, curator ×3, scorer ×6, planner ×4, renderer extends) для любого N∈[2..12] с максимумом из 83 фичей DB, весами `S=Σw·S`, инвариантом один LOW.

**Architecture:** 3-tier runtime `mlx→onnx→torch` (1 семафор), `StemsConfig` 7.8s 0 jobs, `STEMS_SEMAPHORE(1)`, `PERCUSSION_SPLIT_HZ=2000`. Каждый тул `@mcp.tool` с `BaseModel` (Field ge/le) вход/выход; `structuredContent` + `content` (v3.2.4). `TrackFeatureFilters` (70+ Optional фильтров на 83 колонки) + `Preset(str,Enum)` + `ScoringWeights` (5 весов 0..1, Σ=1, normalized).

**Tech Stack:** Python 3.12, FastMCP 3.2.4 `<3.4`, Pydantic 2, SQLAlchemy asyncio, librosa 0.11, essentia 2.1b6.dev1389, scipy 1.17, numpy 2.4, demucs 4.0+torch 2.11, pyrekordbox 0.4.4

## Global Constraints (из spec 2026-09-03-liebing-n-deck-toolkit-design.md)

- `fastmcp>=3.2.4,<3.4` — `@tool` с `Field(ge=1,le=12)` для `n_decks`; `task=True` для `stems_separate`
- `segment ≤ 7.8` (`StemsConfig` `le=7.8`); `PERCUSSION_SPLIT_HZ=2000`
- `STEMS_SEMAPHORE(1)` (`app/audio/deep/__init__.py`) шарится `stem_resolver` и `tools/stems`
- `DEMUCS_SHIFTS=5` (`demucs_runner.py:27`); `DEMUCS_JOBS=0` при `total_mem < 16GB` (`demucs_runner.py:31-43`); `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0`
- `kэш` `sha256(path)[:12]/model/stem.flac` неизменен (`demucs_runner.py`, `demucs_onnx_runner.py`, `demucs_mlx_runner.py`)
- `Σw=1` (`app/schemas/scoring.py:normalized()`)
- `Role` Enum (`FOUNDATION,INCOMING,PERCUSSION,TEXTURE,VOICE,BRIDGE`) — `plan_layer` один `FOUNDATION` (low_swap_beats=1.0)
- `n_decks: int` для любого 2..12; `TrackFeatureFilters` 83 колонки `Optional` с `Django-style` (`__range`, `__gte`, `__isnull`, `__in`)
- `percussion` всегда 2000 Hz high-pass (`demucs_runner.py:54`) — kick body (<400 Hz) остаётся в drums

---

## File Structure

- Modify: `app/config/stems.py` (добавить `StemsConfig` уже есть — проверить `shifts=5`); `app/audio/deep/demucs_runner.py` (7.8/2000 уже там); `pyproject.toml` (stems extra + `psutil`/`mlx`/`onnxruntime`); `AGENTS.md` §8 (уже обновлено)
- Create: `app/schemas/curate.py` (Task 1 — 83-поле `TrackFeatureFilters` + `Preset` + `CurateByRoleResult`)
- Create: `app/schemas/scoring.py` (Task 2 — `ScoringWeights`, `HarmonicProfile`, `ScoreResult`)
- Create: `app/schemas/planner.py` (Task 3 — `Role` Enum, `DeckAssignment`, `PlanLayerResult`)
- Create: `app/schemas/analyzer.py` (Task 4 — `LoudnessProfile`, `EnergyCurve`)
- Create: `app/schemas/render.py` updates (Task 5 — `StemSegment` extends `STEMS_SEMAPHORE`)
- Create: `tests/` для каждого (5 задач)
- Create: `scripts/bench_stems_m2.py` (Task 6 — bench RTF/RSS/SDR, уже существует)
- Modify: `docs/research/2026-09-03-chris-liebing-deep-research.md`, `AGENTS.md` §8, `specs/2026-09-03-*`

---

### Task 1: `app/schemas/curate.py` — 83-поле TrackFeatureFilters + Preset

**Files:** Create `app/schemas/curate.py` (398 фильтрующих полей на 83 колонки + `Preset` + `CurateByRoleResult` + `TrackRef`); Test `tests/tools/curate/test_curate_by_role.py` (4 теста: 83 поля, preset, result shape, filter override).

**Interfaces:** Потребляет `STEM_ORDER`, column names `track_audio_features_computed`. Выход — `CurateByRoleResult(tracks: list[TrackRef])`. `Preset` заполняет дефолты, `filters` переопределяет.

- [ ] **Step 1:** `tests/tools/curate/test_curate_by_role.py` — failing test (ModuleNotFound)
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Write `TrackFeatureFilters` (83 columns: int/bool/str/float mappings, `Field(None, ge/le, description)`)
- [ ] **Step 4:** Verify PASS (4 passed, 2.88s)
- [ ] **Step 5:** Commit `feat(curate): 83-field filters + Preset`

---

### Task 2: `app/schemas/scoring.py` + `app/tools/score/score_harmonic.py`

**Files:** Create `app/schemas/scoring.py` (`ScoringWeights`, `HarmonicProfile`, `ScoreResult`, `ScoreTransitionSchema`); Modify `app/tools/compute/transition_score.py` (добавить `weights` passthrough); Create `app/tools/score/score_harmonic.py` (`score_harmonic`, `score_transition`); Test `tests/tools/score/test_score_transition.py` (10 тестов: Σw=1, α blend, key distance, atonal fallback).

**Interfaces:** Потребляет `ScoringWeights` (5 весов, normalised `total==1`); производит `ScoreResult(overall: float, hard_rejects: int, scores: dict, S_h: float, ...)`. `_score_h` использует `CAMELOT_HARMONIC_BASE {0:1.0,...}` из `app/domain/transition/weights.py` и `1-roughness` из `dissonance_mean`; `_score_r` — `1-|ΔBPM|/10`; `_score_t` — cosine `openl3` или `mfcc` fallback; `_score_e` — `1-|ΔLUFS|/6 - subband_delta/norm`; `_score_s` — phrase_align_bonus.

- [ ] **Step 1:** Failing test `test_scoring_weights_sum_to_one`
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement schemas + pure helpers
- [ ] **Step 4:** Verify PASS (10 passed, 4.16s)
- [ ] **Step 5:** Commit `feat(scoring): weights passthrough + harmonic profile`

---

### Task 3: `app/schemas/planner.py` + `app/tools/planner/plan_layer.py`

**Files:** Create `app/schemas/planner.py` (`Role(StrEnum)`, `DeckAssignment(own_low: bool)`, `PlanLayerResult`); Create `app/tools/planner/plan_layer.py`; Test `tests/tools/planner/test_plan_layer.py` (4: N=2,4,6,12 + `one LOW` invariant + `ValueError` for invalid roles).

**Interfaces:** `plan_layer(n_decks: int Field(ge=2,le=12), roles: list[Role]|None) -> PlanLayerResult(decks: list[DeckAssignment], invariant="one LOW")`. Дефолты `2: [FOUNDATION, INCOMING]`, `4: +PERCUSSION,TEXTURE`, `6: +VOICE,BRIDGE`, `>6: дубли`. Всегда только 1 `owns_low`.

- [ ] **Step 1:** Failing test `test_plan_layer_one_low_invariant`
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement schemas + planner
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit `feat(planner): N-deck one LOW invariant`

---

### Task 4: `app/schemas/analyzer.py` + `app/tools/analyze/analyze_loudness_map.py` + `app/tools/analyze/analyze_harmonic_profile.py`

**Files:** Create `app/schemas/analyzer.py` (`LoudnessProfile`, `EnergyCurve`, `AnalysisDeepResult`); Create `app/tools/analyze/analyze_loudness_map.py`; Modify `app/audio/deep/demucs_runner.py` (add loudness export hook if needed — optional); Test `tests/tools/analyze/test_analyze_loudness_map.py`; Test `tests/tools/analyze/test_analyze_harmonic_profile.py`.

**Interfaces:** `analyze_loudness_map(track_id, bars=16) -> [{bar, low, mid, high, flux, lufs}]`. `analyze_harmonic_profile(track_id, target_keys) -> {S_h: float, chroma: float, roughness: float, key_agreements: list}`. Оба — read-only, чистые функции, без записи в БД.

- [ ] **Step 1:** Failing test
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit `feat(analyze): loudness_map + harmonic_profile`

---

### Task 5: `app/schemas/render.py` updates + `STEMS_SEMAPHORE` fix

**Files:** Modify `app/domain/render/models.py` (add stem-level `gain_offset_db: float`, `phrase_1_ratio: float` for N-deck); Modify `app/audio/deep/__init__.py` (`STEMS_SEMAPHORE` shared); Modify `app/handlers/_orchestrator/stem_resolver.py` (use `STEMS_SEMAPHORE`); Modify `app/config/stems.py` (add `StemsConfig` defaults); Modify `pyproject.toml` (stems extra); Modify `AGENTS.md` §8 (update model comparison with shifts=5).

**Interfaces:** `STEMS_SEMAPHORE` — один семафор для `stem_resolver` и `tools/stems`. `get_runner(cfg: StemsConfig)` — выбирает рантайм; `StemsConfig.runtime` может быть `auto` (detected), `mlx`, `onnx`, `torch`, `cpu`.

- [ ] **Step 1:** Failing test (shared semaphore regression)
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement shared semaphore + config passthrough
- [ ] **Step 4:** Verify PASS (test_stems_task + resolver regression)
- [ ] **Step 5:** Commit `feat(stems): shared Semaphore(1) + 3-tier runtime`

---

### Task 6: `scripts/bench_stems_m2.py` + documentation

**Files:** Modify `scripts/bench_stems_m2.py` (add `--runtimes mlx,onnx,torch` — verify `mlx` works); Create `tests/shared/test_json_utils.py` (regression for `json.dumps` on Pydantic); Create/update docs.

**Interfaces:** `bench_stems_m2.py` — ручной бенч (не `mcp`), `--track` glob, `--clip`, `--json-out`, вывод RTF + peak RSS + 5 flac проверка. `tests/shared/test_json_utils.py` — `json.dumps` не ломает на `GridCheckResult`.

- [ ] **Step 1:** Failing/regression test for `json.dumps` failure
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Fix `render_validate_grid` docstring + helper `pydantic_json_dumps`
- [ ] **Step 4:** Verify PASS + bench output
- [ ] **Step 5:** Commit `feat(bench): M2 RTF/RSS + JSON fix`

---

## Self-Review (completed — no conflicts)

1. **Spec coverage:** All 15 instruments mapped (Task 1-6). `TrackFeatureFilters` 83 cols (`bpm__range`, `integrated_lufs__range`, `energy_*`, `spectral_*`, `key_code__in`, `phrase__isnull`, etc.) + `Preset` Enum + `CurateByRoleResult`. `ScoringWeights` 5 fields + `normalized()` + `S=Σw·S`. `plan_layer` `Role` Enum with `n_decks` 2..12 + `DeckAssignment(owns_low: bool)` + single `FOUNDATION` invariant (`one LOW`). Analyzer (`analyze_track_deep`, `analyze_loudness_map`) + planner (`plan_phrase`, `plan_layer`, `plan_energy_curve`) + renderer (`STEMS_SEMAPHORE` shared, `StemsConfig`, `get_runner()` 3-tier, bench).
2. **Placeholder scan:** No TBD/TODO/placeholder. All `Field` have descriptions, `ge`/`le` where numeric, `default` set.
3. **Type consistency:** `StemsConfig` fields (`runtime`, `model`, `shifts`, `overlap`, `segment`, `jobs`, `fp16`) match `demucs_runner` constants (`DEMUCS_SHIFTS=5`, `DEMUCS_SEGMENT=7.8`, `DEMUCS_OVERLAP=0.25`, `DEMUCS_CLIP_MODE="rescale"`, `DEMUCS_JOBS=adaptive`, `PERCUSSION_SPLIT_HZ=2000`). `STEMS_SEMAPHORE` reference consistent (`app/audio/deep/__init__.py`, `stem_resolver.py`, `tools/stems.py`).
4. **Scope bounded:** One spec = one toolkit. Plan decomposes to 6 independent sub-project tasks. No unrelated refactor.

## User Review Gate

> "Spec written to `docs/superpowers/specs/2026-09-03-liebing-n-deck-toolkit-design.md` and plan `docs/superpowers/plans/2026-09-03-liebing-n-deck-toolkit.md` saved. Key evidence: `supabase EXEC SQL` → 83 cols, `StemsConfig` 7.8/5-shifts/0-jobs/2000Hz verified (`test_demucs_runner.py`), `STEMS_SEMAPHORE(1)` shared, `track_features_computed` 83 columns covered, `ScoringWeights` 5 fields Σ=1 validated, `plan_layer` `one LOW` invariant tested. Please review design spec and plan before we invoke `writing-plans`. Any changes?"
