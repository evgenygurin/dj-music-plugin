# Multi-Genre Manual Set Building — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a multi-genre (techno + house + others) manual DJ set pipeline using FastMCP v3+ prompts/resources, centralized constants, polymorphic resource templates, parameterized prompts, and mathematical transition scoring.

**Architecture:** Constants file removes hardcoding from `subgenre_presets.py`. Resource template (`local://genres/{genre}/subgenres`) provides step-by-step genre info. Prompt (`manual_set_workflow`) takes many optional parameters and returns `render_plan.json`. Validation uses `audit_rules`, `camelot`, `render/validation`.

**Tech Stack:** Python 3.12, uv, FastMCP v3.2.4, SQLAlchemy 2 (DB), librosa (audio), Pydantic v2, GitNexus (impact), Context7 (docs).

## Global Constraints

- Always use `uv` (`uv sync`, `uv run pytest`, `uv run ruff check`).
- Before any edit: `gitnexus_impact({target: "symbol", direction: "upstream"})`.
- Before commit: `gitnexus_detect_changes()`.
- `stem=True` default; effects (`filter_sweep`, `echo`, `reverb`) always `None`.
- `transition_bars`: default 48 (`render/defaults`), override to 0/16 for dense mix.
- `body_bars`: default 40, override to 32/16.
- `target_bpm`: 130.0.
- Multi-genre: support `techno`, `house`, `industrial`, `acid`, `minimal`, `dub`, `melodic`, `peak_time`, `hard`, plus house subgenres (`deep_house`, `tech_house`, `progressive_house`, `classic_house`).
- Constants in `app/config/subgenre_constants.json` (or `.py`) — single source of truth.

---

### Task 1: Centralized Subgenre Constants

**Files:**
- Create: `app/config/subgenre_constants.json`
- Modify: `app/domain/performance/subgenre_presets.py` (reference constants instead of inline values)
- Test: `tests/config/test_subgenre_constants.py`

**Interfaces:**
- Consumes: `subgenre_presets.py`, `reference/subgenres.md`, `reference/subgenres` (JSON resource), `subgenre_presets.py` (`PRESET_MAP`).
- Produces: `subgenre_constants.json` with 18 preset entries (14 techno aliases + 4 house), BPM ranges per subgenre, transition/body bars per preset, EQ settings (`eq_phase_1_ratio`, `low_swap_beats`, etc.), audit thresholds (`BpmRangeRule`, `LufsRangeRule`).

- [ ] **Step 1: Read source evidence**

Read `subgenre_presets.py` (line 339: `PRESET_MAP`), `reference/subgenres.md` (table of presets with transition/body bars), `reference/subgenres` JSON (15 profiles). Confirm discrepancies (e.g., `reference/subgenres.md` mentions 11 distinct presets; actual code has 18 entries; resource shows 15 profiles).

- [ ] **Step 2: Write `subgenre_constants.json`**

Create JSON file with sections:
- `presets`: 18 entries (`industrial_techno`, `dub_techno`, `hard_techno`, `hypnotic_techno`, `peak_time_techno`, `driving_techno`, `acid_techno`, `raw_techno`, `tribal_techno`, `detroit_techno`, `deep_techno`, `minimal_techno`, `progressive_techno`, `melodic_techno`, `deep_house`, `tech_house`, `progressive_house`, `classic_house`). Each entry: `transition_bars`, `body_bars`, `xsplit_low_hz`, `xsplit_high_hz`, `eq_phase_1_ratio`, `eq_phase_2_ratio`, `low_swap_beats`, `outro_fade_bars`, `hpf_cutoff_hz`, `pre_comp_threshold_db`, `pre_comp_ratio`, `glue_comp_threshold_db`, `glue_comp_ratio`, `master_eq_air_boost_db`, `master_eq_mud_cut_db`, `master_eq_sub_boost_db`, `limiter_ceiling`, `limiter_attack_ms`, `limiter_release_ms`, `dynaudnorm_maxgain`.
- `subgenre_profiles`: 15 techno profiles + 4 house profiles (from `reference/subgenres` JSON) with feature weights and ideal values.
- `audit_rules`: 9 rules with thresholds (`techno_bpm_min`: 120, `techno_bpm_max`: 155, `techno_lufs_min`: -20, `techno_lufs_max`: -4, etc.).
- `templates`: 8 template names with durations (`roller_90`: 90 min, etc.).
- `defaults`: `target_bpm`: 130.0, etc.

- [ ] **Step 3: Modernize `subgenre_presets.py`**

Replace inline preset definitions with imports/references to `subgenre_constants.json`. Keep backward compatibility (`resolve_preset`, `resolve_preset_by_subgenre` functions unchanged). Remove duplicate values; keep only logic (mapping, lookup).

- [ ] **Step 4: Write failing test**

Test that `subgenre_constants.json` loads, contains 18 presets, and that `PRESET_MAP` from `subgenre_presets.py` references the same values.

- [ ] **Step 5: Commit**

`git commit -m "feat(config): add subgenre_constants.json, modernize subgenre_presets.py"`

---

### Task 2: Multi-Genre Resource Template (`local://genres/{genre}/subgenres`)

**Files:**
- Create/Modify: `app/handlers/resource_genre_subgenres.py` (or update `app/resources/` if exists)
- Modify: `app/registry/resource_registry.py` (register `local://genres/{genre}/subgenres`)
- Test: `tests/test_resource_genre_subgenres.py`

**Interfaces:**
- Consumes: `subgenre_constants.json` (presets, profiles), `reference/subgenres` JSON.
- Produces: Resource that returns JSON: `{"genre": ..., "subgenres": [{"name": ..., "bpm_range": [min, max], "mood": ..., "preset": ..., "profile_features": {...}}]}`.

- [ ] **Step 1: Read resource patterns from docs**

Read official docs for resource templates (`resource://{param}`) and stacked decorators. Confirm pattern: function takes `genre: str`, returns dict.

- [ ] **Step 2: Implement resource**

```python
from fastmcp import FastMCP

@mcp.resource("local://genres/{genre}/subgenres")
def genre_subgenres(genre: str) -> dict:
    ...
```

Load `subgenre_constants.json`; filter presets/profiles by genre; return structured JSON.

- [ ] **Step 3: Register in registry**

Update `resource_registry` to include new URI template.

- [ ] **Step 4: Test resource response**

Call `dj_read_resource(uri="local://genres/techno/subgenres")` — expect JSON with `subgenres` array.

- [ ] **Step 5: Commit**

---

### Task 3: Polymorphic Prompt (`manual_set_workflow`)

**Files:**
- Create/Modify: `app/prompts/manual_set_workflow.py` (or add to existing prompts directory)
- Modify: `app/registry/prompt_registry.py`
- Test: `tests/test_prompt_manual_set_workflow.py`

**Interfaces:**
- Consumes: `subgenre_constants.json`, `reference/templates` JSON.
- Produces: Prompt function with parameters (`genre`, `subgenre`, `template`, `bpm_range`, `mood`, `transition_bars`, `body_bars`, `camelot_mode`, `stem`, `filter_sweep`, `echo`, `reverb`, `version_id`).

- [ ] **Step 1: Read prompt docs**

Confirm `@mcp.prompt` decorator supports optional/default parameters (`str = "summary"`, `bool = False`, `int = 48`, `str = None`). Confirm `list[int]` and `dict[str, str]` supported.

- [ ] **Step 2: Write prompt**

```python
@mcp.prompt(
    name="manual_set_workflow",
    description="Manual DJ set design workflow with multi-genre support",
    tags={"manual", "set", "multi-genre"},
    meta={"version": "v2", "author": "manual-set-design"}
)
def manual_set_workflow(
    genre: str = "techno",
    subgenre: str | None = None,
    template: str = "roller_90",
    bpm_range: list[int] | None = None,
    mood: str | None = None,
    transition_bars: int | None = 48,
    body_bars: int | None = 40,
    camelot_mode: str = "soft",
    stem: bool = True,
    filter_sweep: str | None = None,
    echo: str | None = None,
    reverb: str | None = None,
    version_id: int | None = None
) -> list[Message]:
    ...
```

Prompt returns messages: user message describing selected genre/template, assistant message with `render_plan.json` preview, user message asking for confirmation, assistant message with validation gate checklist.

- [ ] **Step 3: Register prompt**

- [ ] **Step 4: Write failing test**

Call prompt with `genre="techno"`, `template="roller_90"` — expect `render_plan.json` preview.

- [ ] **Step 5: Verify prompt schema**

Check that `fastmcp list <target>` shows prompt with all parameters and descriptions.

- [ ] **Step 6: Commit**

---

### Task 4: Multi-Genre Constants Integration

**Files:**
- Modify: `subgenre_presets.py` (use constants)
- Modify: `app/config/render.py` (reference constants file)
- Test: `tests/test_subgenre_constants_integration.py`

- [ ] **Step 1: Import constants**

In `subgenre_presets.py`: `from app.config.subgenre_constants import PRESET_MAP, SUBGENRE_PROFILES, AUDIT_RULES`.

- [ ] **Step 2: Replace hardcoded values**

Replace `INDUSTRIAL = SubgenreRenderPreset(...)` with lookup from constants.

- [ ] **Step 3: Verify integration**

Run `pytest tests/test_subgenre_constants_integration.py` — confirm that `resolve_preset("industrial_techno")` returns same preset as before.

- [ ] **Step 4: Commit**

---

### Task 5: Multi-Genre Design Spec Update

**Files:**
- Modify: `docs/superpowers/specs/2026-09-03-manual-set-building-design.md`
- Modify: `AGENTS.md` (shorten, reference rules)
- Modify: `reference/subgenres.md` (already updated)

- [ ] **Step 1: Update spec**

Add sections: Multi-Genre Constants (`subgenre_constants.json`), Polymorphic Resource Template (`local://genres/{genre}/subgenres`), Polymorphic Prompt (`manual_set_workflow`), Integration of DB parameters (`track_audio_features_computed`, `stem_features`, `transition` scores).

- [ ] **Step 2: Update AGENTS.md**

Shorten render lessons, reference `skills/validate-set/SKILL.md`, `rules/render.md`, `subgenre_constants.json`.

- [ ] **Step 3: Verify docs consistency**

Search for outdated references (`"11 distinct"`, `"deprecated"` without context). Fix any remaining.

- [ ] **Step 4: Commit**

---

### Task 6: Implementation Plan Execution (optional batch)

- [ ] **Step 1: Confirm user review of spec**

Ask user to review updated spec doc (`docs/superpowers/specs/2026-09-03-manual-set-building-design.md`).

- [ ] **Step 2: Execute Task 1 (constants)**

- [ ] **Step 3: Execute Task 2 (resource)**

- [ ] **Step 4: Execute Task 3 (prompt)**

- [ ] **Step 5: Execute Task 4 (integration)**

- [ ] **Step 6: Execute Task 5 (spec/docs)**

---

**Plan complete.** Ready for user approval before implementing.
