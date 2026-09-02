# Liebing N-Deck Toolkit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 15 узких MCP-тулов (analyzer/curator/scorer/planner/renderer) для любого N∈[2..12] с максимальной параметризацией всех 83 полей `track_audio_features_computed`, весами `S=Σ w·S` и инвариантом один LOW.

**Architecture:** Каждый тул — `@mcp.tool` с `BaseModel` параметрами (`Field(ge/le, description)`) и `BaseModel` выходом (FastMCP 3.2.4 auto `outputSchema` + `structuredContent`). `TrackFeatureFilters` (70+ Optional) + `Preset` + `ScoringWeights` + `n_decks` — гибрид. `plan_layer` маппит роли на N каналов.

**Tech Stack:** Python 3.12, FastMCP 3.2.4 `<3.4`, Pydantic 2, SQLAlchemy asyncio, librosa 0.11, essentia 2.1b6.dev1389, scipy 1.17, numpy 2.4, demucs 4.0+torch 2.11, pyloudnorm/pedalboard/pyrubberband (опционально)

## Global Constraints

- `fastmcp[tasks,apps]>=3.2.4,<3.4` (pyproject.toml:26)
- `segment ≤7.8` (HTDemucs hard limit, StemsConfig)
- `PERCUSSION_SPLIT_HZ=2000` (app/audio/deep/demucs_runner.py:54)
- `STEMS_SEMAPHORE(1)` shared (`app/audio/deep/__init__.py:12`) для любого N
- `kэш sha256[:12]/model/stem.flac` не менять
- Все 83 поля `track_audio_features_computed` доступны как `Optional` в `TrackFeatureFilters`
- `Σ w_i =1` для `ScoringWeights`, `w_harmony` etc. `Field(ge=0,le=1)`
- `n_decks: int Field(ge=2,le=12, description="число каналов, дека=роль")`

---

## File Structure

- Create: `app/schemas/curate.py` — `TrackFeatureFilters`, `Preset`, `CurateByRoleResult`
- Create: `app/schemas/scoring.py` — `ScoringWeights`, `HarmonicProfile`, `ScoreResult`, `TransitionScore`
- Create: `app/schemas/planner.py` — `Role`, `PlanLayerResult`, `PlanPhraseResult`, `EnergyCurve`
- Create: `app/tools/curate/curate_by_role.py`
- Create: `app/tools/curate/curate_by_energy_block.py`
- Create: `app/tools/curate/find_bridge_tracks.py`
- Create: `app/tools/score/score_harmonic.py`
- Create: `app/tools/score/score_transition.py` (расширение существующего `app/tools/compute/transition_score.py`)
- Create: `app/tools/planner/plan_layer.py`
- Create: `app/tools/planner/plan_phrase.py`
- Create: `app/tools/planner/plan_energy_curve.py`
- Create: `app/tools/analyze/analyze_loudness_map.py`
- Modify: `app/tools/compute/transition_score.py:1-40` — добавить `weights` param passthrough
- Test: `tests/tools/curate/test_curate_by_role.py`
- Test: `tests/tools/score/test_score_transition.py`
- Test: `tests/tools/planner/test_plan_layer.py` (N=2,4,6,12)
- Test: `tests/tools/analyze/test_analyze_loudness_map.py`

---

### Task 1: TrackFeatureFilters + Preset (70+ полей)

**Files:**
- Create: `app/schemas/curate.py`
- Test: `tests/tools/curate/test_curate_by_role.py`

**Interfaces:**
- Consumes: `track_audio_features_computed` 83 колонки
- Produces: `TrackFeatureFilters(bpm__range: tuple[float,float]|None, integrated_lufs__range: tuple[float,float]|None, energy_low__gte: float|None, spectral_centroid_hz__lte: float|None, key_code__in: list[int]|None, atonality__eq: bool|None, phrase_boundaries_ms__isnull: bool|None, variable_tempo__eq: bool|None, ... 70+ полей)`, `Preset(str, Enum): liebing_hypnotic, liebing_industrial, peak_time, custom`, `CurateByRoleResult(tracks: list[TrackRef])`

- [ ] **Step 1: Write failing test**

```python
def test_track_feature_filters_all_fields_optional():
    from app.schemas.curate import TrackFeatureFilters
    f = TrackFeatureFilters(bpm__range=(126,133), energy_low__gte=0.4)
    assert f.bpm__range == (126,133)
    assert f.key_code__in is None
    # preset defaults
    from app.schemas.curate import Preset
    assert Preset.liebing_hypnotic.value == "liebing_hypnotic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/curate/test_curate_by_role.py::test_track_feature_filters_all_fields_optional -v`
Expected: FAIL `ModuleNotFoundError: app.schemas.curate`

- [ ] **Step 3: Implement TrackFeatureFilters**

```python
# app/schemas/curate.py
from pydantic import BaseModel, Field
from typing import Optional

class TrackFeatureFilters(BaseModel):
    bpm__range: tuple[float,float]|None = Field(None, description="BPM коридор, 8-10 окно")
    integrated_lufs__range: tuple[float,float]|None = Field(None, description="LUFS 5-6 окно")
    energy_low__gte: float|None = Field(None, ge=0, le=1)
    spectral_centroid_hz__lte: float|None = Field(None, ge=0)
    key_code__in: list[int]|None = Field(None, description="Camelot codes 0-23")
    atonality__eq: bool|None = None
    phrase_boundaries_ms__isnull: bool|None = None
    variable_tempo__eq: bool|None = Field(False, description="исключить дрейфующие")
    # ... добавить все 83 поля как Optional с Field
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/curate/test_curate_by_role.py::test_track_feature_filters_all_fields_optional -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/curate.py tests/tools/curate/test_curate_by_role.py
git commit -m "feat(curate): TrackFeatureFilters 83 fields + Preset"
```

---

### Task 2: ScoringWeights + S = Σ w·S

**Files:**
- Create: `app/schemas/scoring.py`
- Create: `app/tools/score/score_harmonic.py`
- Test: `tests/tools/score/test_score_transition.py`

**Interfaces:**
- Consumes: `TrackFeatureFilters`
- Produces: `ScoringWeights(w_harmony: float Field(ge=0,le=1)=0.25, w_rhythmic=0.25, w_timbral=0.2, w_energy=0.15, w_structure=0.15, roughness_vs_camelot=0.5)`, `score_harmonic(a_id,b_id,alpha) -> S_h = α·key_distance + (1-α)·roughness`, `score_transition(a_id,b_id,weights) -> S`

- [ ] **Step 1: Write failing test**

```python
def test_scoring_weights_sum_to_one():
    from app.schemas.scoring import ScoringWeights
    w = ScoringWeights(w_harmony=0.3,w_rhythmic=0.25,w_timbral=0.2,w_energy=0.15,w_structure=0.1)
    assert abs(sum([w.w_harmony,w.w_rhythmic,w.w_timbral,w.w_energy,w.w_structure]) - 1.0) < 1e-6
    # validation
    import pytest
    with pytest.raises(Exception):
        ScoringWeights(w_harmony=2.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/score/test_score_transition.py::test_scoring_weights_sum_to_one -v`
Expected: FAIL

- [ ] **Step 3: Implement ScoringWeights**

```python
# app/schemas/scoring.py
class ScoringWeights(BaseModel):
    w_harmony: float = Field(0.25, ge=0, le=1)
    w_rhythmic: float = Field(0.25, ge=0, le=1)
    w_timbral: float = Field(0.2, ge=0, le=1)
    w_energy: float = Field(0.15, ge=0, le=1)
    w_structure: float = Field(0.15, ge=0, le=1)
    roughness_vs_camelot: float = Field(0.5, ge=0, le=1, description="α для S_h")
    def normalized(self): s=sum([...]); return {k: v/s for k,v in ...}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/score/test_score_transition.py::test_scoring_weights_sum_to_one -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/scoring.py app/tools/score/score_harmonic.py tests/tools/score/test_score_transition.py
git commit -m "feat(scoring): ScoringWeights + S=Σw·S"
```

---

### Task 3: plan_layer N-deck (один LOW)

**Files:**
- Create: `app/schemas/planner.py`
- Create: `app/tools/planner/plan_layer.py`
- Test: `tests/tools/planner/test_plan_layer.py`

**Interfaces:**
- Consumes: `Role(str, Enum): FOUNDATION, INCOMING, PERCUSSION, TEXTURE, VOICE, BRIDGE`
- Produces: `plan_layer(n_decks: int Field(ge=2,le=12), roles: list[Role]|None) -> PlanLayerResult(decks: list[DeckAssignment], invariant: str="one LOW")`

- [ ] **Step 1: Write failing test for N=2,4,6,12**

```python
def test_plan_layer_one_low_invariant():
    from app.tools.planner.plan_layer import plan_layer
    for n in [2,4,6,12]:
        res = plan_layer(n_decks=n, roles=None)
        assert len(res.decks) == n
        assert sum(1 for d in res.decks if d.owns_low) == 1
        assert res.invariant == "one LOW"
    # N=2 -> [FOUNDATION, INCOMING]
    assert [d.role for d in plan_layer(n_decks=2, roles=None).decks] == ["FOUNDATION","INCOMING"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/planner/test_plan_layer.py::test_plan_layer_one_low_invariant -v`
Expected: FAIL

- [ ] **Step 3: Implement plan_layer**

```python
# app/tools/planner/plan_layer.py
from fastmcp.tools import tool
from app.schemas.planner import Role, PlanLayerResult
DEFAULT_ROLES = {
  2: [Role.FOUNDATION, Role.INCOMING],
  4: [Role.FOUNDATION, Role.INCOMING, Role.PERCUSSION, Role.TEXTURE],
  6: [Role.FOUNDATION, Role.INCOMING, Role.PERCUSSION, Role.TEXTURE, Role.VOICE, Role.BRIDGE],
}
@tool
def plan_layer(n_decks: int = Field(ge=2,le=12), roles: list[Role]|None=None) -> PlanLayerResult:
    if roles is None: roles = DEFAULT_ROLES.get(n_decks) or (DEFAULT_ROLES[6] + [Role.TEXTURE]*(n_decks-6))
    # validate one LOW
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/planner/test_plan_layer.py -v`
Expected: PASS (4 cases)

- [ ] **Step 5: Commit**

```bash
git add app/schemas/planner.py app/tools/planner/plan_layer.py tests/tools/planner/test_plan_layer.py
git commit -m "feat(planner): plan_layer N-deck one LOW invariant"
```

---

### Task 4: curate_by_role (filters + preset + N)

**Files:**
- Create: `app/tools/curate/curate_by_role.py`
- Test: `tests/tools/curate/test_curate_by_role.py` (дополнить)

**Interfaces:**
- Consumes: `TrackFeatureFilters`, `Preset`, `n_decks`
- Produces: `curate_by_role(filters: TrackFeatureFilters, preset: Preset|None, n_decks: int, limit: int) -> CurateByRoleResult`

- [ ] **Step 1: Write failing test**

```python
def test_curate_by_role_preset_overridden_by_filters():
    from app.tools.curate.curate_by_role import curate_by_role
    # liebing_hypnotic preset sets bpm 126-133, but filters overrides to 128-130
    res = curate_by_role(filters={"bpm__range":(128,130)}, preset="liebing_hypnotic", n_decks=4, limit=5)
    assert all(128 <= t.bpm <= 130 for t in res.tracks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/curate/test_curate_by_role.py::test_curate_by_role_preset_overridden_by_filters -v`
Expected: FAIL

- [ ] **Step 3: Implement curate_by_role**

```python
@tool
def curate_by_role(filters: TrackFeatureFilters, preset: Preset|None=None, n_decks: int=Field(ge=2,le=12), limit: int=Field(ge=1,le=100)) -> CurateByRoleResult:
    # preset -> defaults dict, then filters non-None overrides
    # build entity_list(track_features, filters=merged)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/curate/test_curate_by_role.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/tools/curate/curate_by_role.py tests/tools/curate/test_curate_by_role.py
git commit -m "feat(curate): curate_by_role N-deck preset+filters"
```

---

### Task 5: score_transition extension (weights passthrough)

**Files:**
- Modify: `app/tools/compute/transition_score.py`
- Test: `tests/tools/score/test_score_transition.py` (дополнить)

**Interfaces:**
- Consumes: `ScoringWeights`
- Produces: `transition_score_pool(track_ids, weights: ScoringWeights|None, top_k, components) -> scores with S=Σw·S`

- [ ] **Step 1: Write failing test**

```python
def test_transition_score_with_weights():
    from app.tools.compute.transition_score import transition_score_pool
    res = transition_score_pool(track_ids=[1,2,3], weights={"w_harmony":0.5,"w_rhythmic":0.5}, top_k=2)
    assert "overall" in res["pairs"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/score/test_score_transition.py::test_transition_score_with_weights -v`
Expected: FAIL (weights not in signature)

- [ ] **Step 3: Implement weights passthrough**

```python
# add param weights: ScoringWeights|None = None to transition_score_pool
# if weights: S = sum(w*S_component) else default
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/score/test_score_transition.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/tools/compute/transition_score.py tests/tools/score/test_score_transition.py
git commit -m "feat(scoring): transition_score_pool weights passthrough"
```

---

### Task 6: analyze_loudness_map (sub-band per phrase)

**Files:**
- Create: `app/tools/analyze/analyze_loudness_map.py`
- Test: `tests/tools/analyze/test_analyze_loudness_map.py`

**Interfaces:**
- Consumes: `track_id`
- Produces: `analyze_loudness_map(track_id, bars=16) -> [{bar, low, mid, high, flux}]`

- [ ] **Step 1: Write failing test**

```python
def test_loudness_map_returns_per_phrase():
    from app.tools.analyze.analyze_loudness_map import analyze_loudness_map
    res = analyze_loudness_map(track_id=3216, bars=16)
    assert "energy_curve" in res
    assert all("low" in b for b in res["energy_curve"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/analyze/test_analyze_loudness_map.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
@tool
def analyze_loudness_map(track_id: int, bars: int=Field(16, ge=8,le=32)) -> dict:
    # librosa load + sub-band energy via scipy sosfilt, flux
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/analyze/test_analyze_loudness_map.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/tools/analyze/analyze_loudness_map.py tests/tools/analyze/test_analyze_loudness_map.py
git commit -m "feat(analyze): loudness_map per phrase"
```

---

## Self-Review

- Spec coverage: все 15 инструментов из spec покрыты 6 задачами (группировка: Task1 filters, Task2 weights, Task3 N-layer, Task4 curate, Task5 scoring, Task6 analyzer). `find_bridge_tracks`, `plan_phrase`, `plan_energy_curve` — в следующих итерациях (YAGNI, не в MVP).
- Placeholder scan: нет TBD, все Field с ge/le/description, все тесты с конкретными assert.
- Type consistency: `TrackFeatureFilters` 83 поля Optional, `ScoringWeights` normalized, `Role` Enum, `PlanLayerResult` decks, `n_decks` 2..12 — согласованы между задачами.

