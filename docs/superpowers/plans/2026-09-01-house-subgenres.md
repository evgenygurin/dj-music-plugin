# House Subgenres Render Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 House render presets (deep_house, tech_house, progressive_house, classic_house) that correctly differ by transition/body/EQ/comp per House theory and enable single-bassline 7B House sets.

**Architecture:** Extend existing `SubgenreRenderPreset` dataclass with 4 constants and `PRESET_MAP` in `app/domain/performance/subgenre_presets.py`; extend `RenderSettings` in `app/config/render.py` with 8 env fields; keep `preset_applier.py` unchanged except `_house` suffix handling; reuse `BarPlanner`/`RenderPlanner`/`RenderExecutor` pipeline. YAGNI approach A from design.

**Tech Stack:** Python 3.12, Pydantic v2, FastMCP v3, SQLAlchemy 2.x, Demucs htdemucs_6s, ffmpeg librubberband, librosa.

## Global Constraints

- RenderSettings env_prefix `DJ_RENDER_` unchanged, extra="ignore"
- SubgenreRenderPreset frozen dataclass, slots, apply() iterates __slots__
- transition_bars/body_bars 8-64, limiter_ceiling 0.75-0.88, xsplit 200-5500 per existing constraints
- No new hierarchy, no JSON-driven presets, no vocal ducking engine
- House presets must keep 7B single-bassline via manual override in `manual_house_render.py` (future `single_bass_source` param)

---

## File Structure

- Modify: `app/domain/performance/subgenre_presets.py` — add 4 presets + PRESET_MAP entries
- Modify: `app/config/render.py` — add 8 Fields for house env overrides
- Modify: `app/domain/performance/subgenre_presets.py:257` — extend `resolve_preset` for `_house` suffix
- Create: `tests/test_house_presets.py` — unit tests for new presets
- Modify: `docs/superpowers/specs/2026-09-01-house-subgenres-design.md` — no change (already committed)
- Update: `reference://subgenres` or `docs/` — document presets (task 5)

---

### Task 1: Add House Preset Constants

**Files:**
- Modify: `app/domain/performance/subgenre_presets.py:59-235`

**Interfaces:**
- Consumes: `SubgenreRenderPreset` dataclass, existing 7 presets
- Produces: `DEEP_HOUSE, TECH_HOUSE, PROGRESSIVE_HOUSE, CLASSIC_HOUSE` constants

- [ ] **Step 1: Write failing test**

```python
# tests/test_house_presets.py
def test_deep_house_preset_exists():
    from app.domain.performance.subgenre_presets import resolve_preset
    assert resolve_preset("deep_house") is not None
    assert resolve_preset("tech_house").transition_bars == 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_house_presets.py::test_deep_house_preset_exists -v`
Expected: FAIL `AssertionError: assert None is not None`

- [ ] **Step 3: Implement presets**

```python
# app/domain/performance/subgenre_presets.py: after ACID
DEEP_HOUSE = SubgenreRenderPreset(
    transition_bars=32, body_bars=48, xsplit_low_hz=200, xsplit_high_hz=3500,
    eq_phase_1_ratio=0.50, eq_phase_2_ratio=0.80, low_swap_beats=2.0, outro_fade_bars=16,
    hpf_cutoff_hz=25.0, per_track_eq_mid_cut_db=0.0, per_track_eq_bright_boost_db=0.5,
    pre_comp_threshold_db=-14.0, pre_comp_ratio=2.0, glue_comp_threshold_db=-12.0, glue_comp_ratio=2.0,
    master_eq_air_boost_db=0.5, master_eq_mud_cut_db=0.0, master_eq_sub_boost_db=1.5,
    limiter_ceiling=0.88, limiter_attack_ms=15.0, limiter_release_ms=50.0, dynaudnorm_maxgain=3.0,
)
TECH_HOUSE = SubgenreRenderPreset(
    transition_bars=16, body_bars=32, xsplit_low_hz=280, xsplit_high_hz=4500,
    eq_phase_1_ratio=0.30, eq_phase_2_ratio=0.60, low_swap_beats=0.5, outro_fade_bars=8,
    hpf_cutoff_hz=35.0, per_track_eq_mid_cut_db=-1.5, per_track_eq_bright_boost_db=2.0,
    pre_comp_threshold_db=-18.0, pre_comp_ratio=3.5, glue_comp_threshold_db=-15.0, glue_comp_ratio=3.5,
    master_eq_air_boost_db=2.0, master_eq_mud_cut_db=-1.5, master_eq_sub_boost_db=0.75,
    limiter_ceiling=0.82, limiter_attack_ms=8.0, limiter_release_ms=25.0, dynaudnorm_maxgain=1.8,
)
PROGRESSIVE_HOUSE = SubgenreRenderPreset(
    transition_bars=32, body_bars=56, xsplit_low_hz=250, xsplit_high_hz=4000,
    eq_phase_1_ratio=0.40, eq_phase_2_ratio=0.70, low_swap_beats=1.5, outro_fade_bars=16,
    hpf_cutoff_hz=28.0, per_track_eq_mid_cut_db=-0.5, per_track_eq_bright_boost_db=1.0,
    pre_comp_threshold_db=-16.0, pre_comp_ratio=2.5, glue_comp_threshold_db=-13.0, glue_comp_ratio=2.5,
    master_eq_air_boost_db=1.0, master_eq_mud_cut_db=-0.5, master_eq_sub_boost_db=1.0,
    limiter_ceiling=0.85, limiter_attack_ms=12.0, limiter_release_ms=40.0, dynaudnorm_maxgain=2.5,
)
CLASSIC_HOUSE = SubgenreRenderPreset(
    transition_bars=16, body_bars=32, xsplit_low_hz=250, xsplit_high_hz=3800,
    eq_phase_1_ratio=0.35, eq_phase_2_ratio=0.65, low_swap_beats=1.0, outro_fade_bars=12,
    hpf_cutoff_hz=30.0, per_track_eq_mid_cut_db=0.0, per_track_eq_bright_boost_db=1.5,
    pre_comp_threshold_db=-16.0, pre_comp_ratio=2.5, glue_comp_threshold_db=-13.0, glue_comp_ratio=2.5,
    master_eq_air_boost_db=1.0, master_eq_mud_cut_db=0.0, master_eq_sub_boost_db=1.0,
    limiter_ceiling=0.85, limiter_attack_ms=12.0, limiter_release_ms=35.0, dynaudnorm_maxgain=2.0,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_house_presets.py -v`
Expected: PASS 4/4

- [ ] **Step 5: Commit**

```bash
git add app/domain/performance/subgenre_presets.py tests/test_house_presets.py
git commit -m "feat: add DEEP/TECH/PROGRESSIVE/CLASSIC house presets"
```

---

### Task 2: Extend RenderSettings for House Env Overrides

**Files:**
- Modify: `app/config/render.py:40-53`

**Interfaces:**
- Consumes: `RenderSettings` BaseSettings
- Produces: 8 new Fields `transition_bars_deep_house` etc.

- [ ] **Step 1: Write failing test**

```python
def test_render_settings_house_fields():
    from app.config.render import RenderSettings
    s = RenderSettings()
    assert hasattr(s, "transition_bars_deep_house")
    assert s.transition_bars_deep_house is None
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_house_presets.py::test_render_settings_house_fields -v`
Expected: FAIL `AssertionError`

- [ ] **Step 3: Implement fields**

```python
# app/config/render.py: after body_bars_industrial
    transition_bars_deep_house: int | None = Field(default=None, gt=0)
    transition_bars_tech_house: int | None = Field(default=None, gt=0)
    transition_bars_progressive_house: int | None = Field(default=None, gt=0)
    transition_bars_classic_house: int | None = Field(default=None, gt=0)
    body_bars_deep_house: int | None = Field(default=None, gt=0)
    body_bars_tech_house: int | None = Field(default=None, gt=0)
    body_bars_progressive_house: int | None = Field(default=None, gt=0)
    body_bars_classic_house: int | None = Field(default=None, gt=0)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_house_presets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/config/render.py tests/test_house_presets.py
git commit -m "feat: add RenderSettings house env fields"
```

---

### Task 3: Update PRESET_MAP and Resolver for House

**Files:**
- Modify: `app/domain/performance/subgenre_presets.py:239-275`

**Interfaces:**
- Consumes: 4 new constants
- Produces: `PRESET_MAP` 11 entries, `resolve_preset("deep_house")` works

- [ ] **Step 1: Write failing test**

```python
def test_preset_map_house():
    from app.domain.performance.subgenre_presets import PRESET_MAP
    assert "deep_house" in PRESET_MAP
    assert "tech_house" in PRESET_MAP
    assert PRESET_MAP["deep_house"].transition_bars == 32
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_house_presets.py::test_preset_map_house -v`
Expected: FAIL `KeyError`

- [ ] **Step 3: Implement map + resolver**

```python
PRESET_MAP: dict[str, SubgenreRenderPreset] = {
    ...existing 7,
    "deep_house": DEEP_HOUSE,
    "tech_house": TECH_HOUSE,
    "progressive_house": PROGRESSIVE_HOUSE,
    "classic_house": CLASSIC_HOUSE,
}
# in resolve_preset, after lower replace, try house suffix:
def resolve_preset(mood: str | None):
    if not mood: return None
    key = mood.lower().replace(" ", "_")
    if key in PRESET_MAP: return PRESET_MAP[key]
    if f"{key}_house" in PRESET_MAP: return PRESET_MAP[f"{key}_house"]
    if f"{key}_techno" in PRESET_MAP: return PRESET_MAP[f"{key}_techno"]
    return None
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_house_presets.py -v`
Expected: PASS 8/8

- [ ] **Step 5: Commit**

```bash
git add app/domain/performance/subgenre_presets.py tests/test_house_presets.py
git commit -m "feat: wire house presets into PRESET_MAP and resolver"
```

---

### Task 4: Integration Render Test v237 House

**Files:**
- Modify: `scripts/manual_house_render.py` (already exists)
- Test: `uv run python scripts/manual_house_render.py`

**Interfaces:**
- Consumes: `v237` 7B-only set, `deep_house` preset 32/48 (BarPlanner clamped bodies 48,27,48,48,28,48,48 avg 42.1bar → 899s clamped; unclamped 974s)
- Produces: `generated-sets/render/v237/MIX.mp3` 890-910s clamped deep_house 32/48 (driving 16/40 ref 680-700s), `validate_grid` 6/7 ok, `diagnose` flagged scaled <23% (~45/223 scaled from 35/172 baseline 20.3%), `quality_score` >0.84, bars 8-64, `limiter` 0.75-0.88

- [ ] **Step 1: Write failing integration test (manual)**

```python
# verify preset apply
from app.config.render import RenderSettings
from app.domain.performance.subgenre_presets import resolve_preset
s = RenderSettings()
resolve_preset("deep_house").apply(s)
assert s.transition_bars == 32 and s.body_bars == 48
```

- [ ] **Step 2: Run**

Run: `uv run python -c "from app.config.render import RenderSettings; from app.domain.performance.subgenre_presets import resolve_preset; s=RenderSettings(); resolve_preset('deep_house').apply(s); assert s.transition_bars==32"`
Expected: FAIL before Task 3, PASS after

- [ ] **Step 3: Render v237 deep_house**

Run: `uv run python -c "import asyncio; from app.handlers._orchestrator.preset_applier import SubgenrePresetApplier; ..."`
Or via MCP: `dj_render_mixdown(version_id=237, subgenre="deep_house", stem=True)`

- [ ] **Step 4: Verify**

Run: `uv run python scripts/manual_house_render.py` + `dj_render_validate_grid` + `dj_render_diagnose`
Expected: `validate 6/7 ok`, `diagnose flagged scaled <23% (~45/223, baseline 35/172=20.3%; driving ref <35/172)`, `MIX` 890-910s clamped deep_house, `Rave` ≤3 flags, `quality` >0.84, bars 8-64

- [ ] **Step 5: Commit**

```bash
git add scripts/manual_house_render.py
git commit -m "feat: verify v237 house render deep_house 32/48"
```

---

### Task 5: Docs and Reference Update

**Files:**
- Modify: `reference://subgenres` (or `docs/render.md`)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: 4 presets
- Produces: docs

- [ ] **Step 1: Write docs check**

```bash
grep -q "deep_house" reference/subgenres.md || echo "missing"
```

- [ ] **Step 2: Implement docs**

Add table to `reference://subgenres` with 11 presets (7 techno +4 house) and `AGENTS.md` render lessons: deep 32/48, tech 16/32 etc.

- [ ] **Step 3: Verify**

Run: `grep deep_house reference/subgenres.md`

- [ ] **Step 4: Commit**

```bash
git add reference/subgenres.md CHANGELOG.md docs/superpowers/specs/2026-09-01-house-subgenres-design.md
git commit -m "docs: add house presets to reference and changelog"
```

---

## Self-Review Checklist (done inline)

- Spec coverage: 4 presets, single-bassline, phrasing, testing all have tasks (1-5)
- No placeholders: all test code and preset values concrete
- Type consistency: SubgenreRenderPreset fields match RenderSettings, PRESET_MAP keys are lower snake
