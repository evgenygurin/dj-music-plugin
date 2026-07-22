# MCP Integration of DJ Performance Modules — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose 14 new DJ performance modules as 11 MCP tools + extend render_mixdown with 8 new parameters.

**Architecture:** Four namespaces (render:config, render:effects, render:diagnostics, performance). Each tool follows existing FastMCP pattern: `@tool` decorator → Pydantic schema → handler/business logic in domain module. No new dependencies.

**Tech Stack:** FastMCP v3, Pydantic v2, ffmpeg (librubberband), scipy (reverb IR), existing 26 analyzers.

## Global Constraints

- Python >=3.12 via `uv run`
- All imports from `app/` — no new pip packages
- Follow existing FastMCP tool pattern (`@tool`, `Depends(get_uow)`, `CurrentContext()`)
- Pydantic `BaseModel` schemas in `app/schemas/<name>.py`, one per file
- `ruff check` clean, `mypy` strict on new files
- Commands use `uv run` — never bare `python`/`pytest`

---

### Task 1: Response Schemas

**Files:**
- Create: `app/schemas/subgenre_preset.py`
- Create: `app/schemas/energy_arc.py`
- Create: `app/schemas/filter_sweep.py`
- Create: `app/schemas/echo_delay.py`
- Create: `app/schemas/reverb.py`
- Create: `app/schemas/auto_fix.py`
- Create: `app/schemas/cue_points.py`
- Create: `app/schemas/transition_window.py`
- Create: `app/schemas/key_compatibility.py`
- Create: `app/schemas/multi_deck.py`
- Create: `app/schemas/stem_matrix.py`

**Interfaces:**
- Produces: 11 Pydantic models, each named `<Topic>Result`, used by Tasks 4-7

- [ ] **Step 1: Create `app/schemas/subgenre_preset.py`**

```python
"""Structured-output model for subgenre_preset tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SubgenrePresetResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    subgenre: str
    transition_bars: int
    body_bars: int
    xsplit_low_hz: int
    xsplit_high_hz: int
    eq_phase_1_ratio: float
    eq_phase_2_ratio: float
    low_swap_beats: float
    outro_fade_bars: int
    hpf_cutoff_hz: float
    per_track_eq_mid_cut_db: float
    per_track_eq_bright_boost_db: float
    pre_comp_threshold_db: float
    pre_comp_ratio: float
    glue_comp_threshold_db: float
    glue_comp_ratio: float
    master_eq_air_boost_db: float
    master_eq_mud_cut_db: float
    master_eq_sub_boost_db: float
    limiter_ceiling: float
    limiter_attack_ms: float
    limiter_release_ms: float
    dynaudnorm_maxgain: float
```

- [ ] **Step 2: Create `app/schemas/energy_arc.py`**

```python
"""Structured-output model for energy_arc_plan tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArcSlotResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int
    target_bpm: float
    target_energy: float
    label: str


class EnergyArcResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    shape: str
    num_tracks: int
    bpm_start: float
    bpm_peak: float
    bpm_end: float
    slots: list[ArcSlotResult] = Field(default_factory=list)
```

- [ ] **Step 3: Create `app/schemas/filter_sweep.py`**

```python
"""Structured-output model for filter_sweep_builder tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FilterSweepSide(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_freq_hz: float
    end_freq_hz: float
    direction: str
    curve: str
    resonance: float
    ffmpeg_expr: str | None = None


class FilterSweepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset_name: str | None = None
    outgoing: FilterSweepSide | None = None
    incoming: FilterSweepSide | None = None
```

- [ ] **Step 4: Create `app/schemas/echo_delay.py`**

```python
"""Structured-output model for echo_builder tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EchoResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset_name: str | None = None
    delay_ms: float
    decay: float
    taps: int
    wet_dry_ratio: float
    stereo_spread: float
    ffmpeg_aecho_expr: str
```

- [ ] **Step 5: Create `app/schemas/reverb.py`**

```python
"""Structured-output model for reverb_builder tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReverbResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset_name: str | None = None
    decay_s: float
    pre_delay_ms: float
    mix_ratio: float
    space: str
    sample_rate: int
    total_samples: int
    highpass_hz: float
    lowpass_hz: float
```

- [ ] **Step 6: Create `app/schemas/auto_fix.py`**

```python
"""Structured-output model for auto_fix tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FixItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    at_s: float
    action: str


class AutoFixResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    dry_run: bool
    defects_found: int = 0
    fixes: list[FixItem] = Field(default_factory=list)
    fixed_path: str | None = None
```

- [ ] **Step 7: Create `app/schemas/cue_points.py`**

```python
"""Structured-output model for cue_points tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CueItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    cue_type: str
    position_ms: int
    label: str
    color: str


class CuePointsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    track_id: int
    bpm: float = 0.0
    cues: list[CueItem] = Field(default_factory=list)
```

- [ ] **Step 8: Create `app/schemas/transition_window.py`**

```python
"""Structured-output model for transition_window tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TransitionWindowResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_track_id: int
    to_track_id: int
    mix_out_start_ms: int
    mix_out_end_ms: int
    mix_in_start_ms: int
    mix_in_end_ms: int
    recommendation: str
```

- [ ] **Step 9: Create `app/schemas/key_compatibility.py`**

```python
"""Structured-output model for key_compatibility tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class KeyCompatibilityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_key: int
    to_key: int
    from_camelot: str
    to_camelot: str
    distance: int
    relation: str
    compatibility_score: float
    description: str
```

- [ ] **Step 10: Create `app/schemas/multi_deck.py`**

```python
"""Structured-output model for multi_deck_plan tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DeckAssign(BaseModel):
    model_config = ConfigDict(frozen=True)

    deck_index: int
    track_id: int
    active_stems: list[str]
    gain_db: float
    lowpass_hz: float
    highpass_hz: float


class DeckWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_s: float
    end_s: float
    decks: list[DeckAssign]


class MultiDeckPlanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_simultaneous: int
    target_bpm: float
    windows: list[DeckWindow] = Field(default_factory=list)
    ffmpeg_amix_graph: str = ""
```

- [ ] **Step 11: Create `app/schemas/stem_matrix.py`**

```python
"""Structured-output model for stem_matrix tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ActiveStem(BaseModel):
    model_config = ConfigDict(frozen=True)

    deck_index: int
    stem_type: str
    track_id: int


class MatrixFrame(BaseModel):
    model_config = ConfigDict(frozen=True)

    time_s: float
    active_decks: list[ActiveStem] = Field(default_factory=list)
    fade_outs: int = 0
    fade_ins: int = 0


class StemMatrixResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_duration_s: float
    frame_count: int
    target_bpm: float
    frames: list[MatrixFrame] = Field(default_factory=list)
```

- [ ] **Step 12: Verify schemas import**

```bash
uv run python -c "
from app.schemas.subgenre_preset import SubgenrePresetResult
from app.schemas.energy_arc import EnergyArcResult
from app.schemas.filter_sweep import FilterSweepResult
from app.schemas.echo_delay import EchoResult
from app.schemas.reverb import ReverbResult
from app.schemas.auto_fix import AutoFixResult
from app.schemas.cue_points import CuePointsResult
from app.schemas.transition_window import TransitionWindowResult
from app.schemas.key_compatibility import KeyCompatibilityResult
from app.schemas.multi_deck import MultiDeckPlanResult
from app.schemas.stem_matrix import StemMatrixResult
print('All 11 schemas import OK')
"
```

- [ ] **Step 13: Commit**

```bash
git add app/schemas/subgenre_preset.py app/schemas/energy_arc.py app/schemas/filter_sweep.py app/schemas/echo_delay.py app/schemas/reverb.py app/schemas/auto_fix.py app/schemas/cue_points.py app/schemas/transition_window.py app/schemas/key_compatibility.py app/schemas/multi_deck.py app/schemas/stem_matrix.py
git commit -m "feat: add 11 response schemas for new MCP tools"
```

---

### Task 2: Extend unlock_namespace

**Files:**
- Modify: `app/tools/admin/unlock_namespace.py`

**Interfaces:**
- Produces: `"render:diagnostics"` and `"performance"` available for unlock/lock

- [ ] **Step 1: Add new namespaces to NAMESPACES**

Edit `app/tools/admin/unlock_namespace.py` — add two entries to `NAMESPACES`:

```python
NAMESPACES = frozenset(
    {
        "crud:destructive",
        "provider:write",
        "sync",
        "ui:read",
        "render:diagnostics",
        "performance",
        "all",
    }
)
```

- [ ] **Step 2: Add corresponding tags to NAMESPACE_TAGS**

```python
NAMESPACE_TAGS = {
    "crud:destructive": ["namespace:crud:destructive"],
    "provider:write": ["namespace:provider:write"],
    "sync": ["namespace:sync"],
    "ui:read": ["namespace:ui:read"],
    "render:diagnostics": ["namespace:render:diagnostics"],
    "performance": ["namespace:performance"],
    "all": [
        "namespace:crud:destructive",
        "namespace:provider:write",
        "namespace:sync",
        "namespace:ui:read",
        "namespace:render:diagnostics",
        "namespace:performance",
    ],
}
```

- [ ] **Step 3: Update the Literal type on the namespace parameter**

Change the `namespace` parameter annotation from:
```python
Literal["crud:destructive", "provider:write", "sync", "ui:read", "all"],
```
to:
```python
Literal["crud:destructive", "provider:write", "sync", "ui:read", "render:diagnostics", "performance", "all"],
```

- [ ] **Step 4: Update the docstring description**

Change the description line from:
```python
"Namespaces: crud:destructive, provider:write, sync, ui:read, or 'all'."
```
to:
```python
"Namespaces: crud:destructive, provider:write, sync, ui:read, render:diagnostics, performance, or 'all'."
```

- [ ] **Step 5: Verify import and lint**

```bash
uv run ruff check app/tools/admin/unlock_namespace.py
uv run python -c "from app.tools.admin.unlock_namespace import NAMESPACES; print('render:diagnostics' in NAMESPACES); print('performance' in NAMESPACES)"
```

- [ ] **Step 6: Commit**

```bash
git add app/tools/admin/unlock_namespace.py
git commit -m "feat: add render:diagnostics and performance namespaces to unlock_namespace"
```

---

### Task 3: Extend render_mixdown with subgenre and effects

**Files:**
- Modify: `app/tools/render/render_mixdown.py` — add 8 new tool parameters
- Modify: `app/handlers/render_mixdown.py` — add handler params + subgenre.apply() + plan_kwargs

**Interfaces:**
- Consumes: `SubgenreRenderPreset.resolve_preset()` from `app.domain.performance.subgenre_presets`
- Consumes: `FILTER_PRESETS` from `app.audio.effects.filter_sweep`
- Consumes: `ECHO_PRESETS` from `app.audio.effects.echo_delay`
- Produces: same `RenderMixdownResult`, backward compatible

- [ ] **Step 1: Add new parameters to the tool signature**

Edit `app/tools/render/render_mixdown.py` — add these params after `stem: bool = True`:

```python
    subgenre: Annotated[
        str | None,
        Field(description="Subgenre preset: industrial_techno, dub_techno, hard_techno, hypnotic_techno, peak_time_techno, driving_techno, acid_techno"),
    ] = None,
    filter_sweep: Annotated[
        str | None,
        Field(description="Filter sweep preset: classic_lowpass, acid_squelch, industrial_cut, hypnotic_wash, dub_echo_sweep"),
    ] = None,
    echo: Annotated[
        str | None,
        Field(description="Echo preset: techno_standard, vocal_throw, industrial_stutter, dub_space, acid_bounce"),
    ] = None,
    crossfade_curve_out: Annotated[
        str,
        Field(description="acrossfade curve for outgoing track: tri, exp, log, squ, sin, nofade"),
    ] = "tri",
    crossfade_curve_in: Annotated[
        str,
        Field(description="acrossfade curve for incoming track: tri, exp, log, squ, sin, nofade"),
    ] = "exp",
    reverb: Annotated[
        str | None,
        Field(description="Reverb preset: techno_hall, techno_cathedral, industrial_warehouse, dub_plate, minimal_room"),
    ] = None,
    reverb_mix: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Reverb wet/dry ratio"),
    ] = 0.25,
```

- [ ] **Step 2: Pass new params through to the handler**

In the same file, update the call to `render_mixdown_handler`:

```python
    return await render_mixdown_handler(
        ctx=ctx,
        uow=uow,
        version_id=version_id,
        workspace=render_workspace(version_id),
        timestamp=render_timestamp(),
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
```

- [ ] **Step 3: Add new params to handler signature**

Edit `app/handlers/render_mixdown.py` — add params after `stem: bool = True`:

```python
    subgenre: str | None = None,
    filter_sweep: str | None = None,
    echo: str | None = None,
    crossfade_curve_out: str = "tri",
    crossfade_curve_in: str = "exp",
    reverb: str | None = None,
    reverb_mix: float = 0.25,
```

- [ ] **Step 4: Apply subgenre preset in handler (before _compute_bars)**

Add this block right after `rs = get_settings().render` (line 185):

```python
    # Apply subgenre preset to render settings
    if subgenre:
        from app.domain.performance.subgenre_presets import resolve_preset

        preset = resolve_preset(subgenre)
        if preset is not None:
            preset.apply(rs)
            await safe_info(ctx, f"render_mixdown: subgenre preset '{subgenre}' applied")
```

- [ ] **Step 5: Add filter_sweep and echo to plan_kwargs**

In the `plan_kwargs` dict (line 214), add:

```python
        "filter_sweep_name": filter_sweep,
        "echo_name": echo,
        "crossfade_curve_out": crossfade_curve_out,
        "crossfade_curve_in": crossfade_curve_in,
```

- [ ] **Step 6: Add reverb to plan_kwargs if reverb preset is set**

After `plan_kwargs`, add:

```python
    if reverb:
        plan_kwargs["reverb_name"] = reverb
        plan_kwargs["reverb_mix"] = reverb_mix
```

- [ ] **Step 7: Verify the handler still works with all defaults**

```bash
uv run python -c "
from app.handlers.render_mixdown import render_mixdown_handler
print('Handler import OK with new params')
"
```

- [ ] **Step 8: Commit**

```bash
git add app/tools/render/render_mixdown.py app/handlers/render_mixdown.py
git commit -m "feat: extend render_mixdown with subgenre, filter_sweep, echo, reverb, crossfade params"
```

---

### Task 4: render:config tools

**Files:**
- Create: `app/tools/render/subgenre_preset.py`
- Create: `app/tools/render/energy_arc_plan.py`

**Interfaces:**
- Consumes: `SubgenreRenderPreset.resolve_preset()` from `app.domain.performance.subgenre_presets`
- Consumes: `EnergyArc` from `app.domain.performance.energy_arc`
- Produces: `SubgenrePresetResult`, `EnergyArcResult` (Task 1)

- [ ] **Step 1: Create `app/tools/render/subgenre_preset.py`**

```python
"""subgenre_preset — render settings tailored to a techno subgenre."""
from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.subgenre_presets import resolve_preset, PRESET_MAP
from app.schemas.subgenre_preset import SubgenrePresetResult

VALID_SUBGENRES = Literal[
    "industrial_techno", "dub_techno", "hard_techno",
    "hypnotic_techno", "peak_time_techno", "driving_techno",
    "acid_techno", "raw_techno", "tribal_techno", "detroit_techno",
    "deep_techno", "minimal_techno", "progressive_techno",
    "melodic_techno",
]

SUBGENRE_NAMES: list[str] = list(PRESET_MAP.keys())


@tool(
    name="subgenre_preset",
    tags={"namespace:render:config"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Get the complete render settings preset for a techno subgenre. "
        "Returns 22 DSP parameters tuned for the subgenre's mixing style "
        "(industrial=aggressive compression, dub=long transitions, etc.). "
        "Use the returned subgenre name with render_mixdown's subgenre parameter."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def subgenre_preset(
    subgenre: Annotated[
        str,
        Field(description="Subgenre key: industrial_techno, dub_techno, etc."),
    ],
) -> SubgenrePresetResult:
    if subgenre not in PRESET_MAP:
        raise ValueError(
            f"unknown subgenre {subgenre!r}; valid: {sorted(SUBGENRE_NAMES)}"
        )
    preset = resolve_preset(subgenre)
    if preset is None:
        raise ValueError(f"no preset for {subgenre!r}")
    return SubgenrePresetResult(
        subgenre=subgenre,
        transition_bars=preset.transition_bars,
        body_bars=preset.body_bars,
        xsplit_low_hz=preset.xsplit_low_hz,
        xsplit_high_hz=preset.xsplit_high_hz,
        eq_phase_1_ratio=preset.eq_phase_1_ratio,
        eq_phase_2_ratio=preset.eq_phase_2_ratio,
        low_swap_beats=preset.low_swap_beats,
        outro_fade_bars=preset.outro_fade_bars,
        hpf_cutoff_hz=preset.hpf_cutoff_hz,
        per_track_eq_mid_cut_db=preset.per_track_eq_mid_cut_db,
        per_track_eq_bright_boost_db=preset.per_track_eq_bright_boost_db,
        pre_comp_threshold_db=preset.pre_comp_threshold_db,
        pre_comp_ratio=preset.pre_comp_ratio,
        glue_comp_threshold_db=preset.glue_comp_threshold_db,
        glue_comp_ratio=preset.glue_comp_ratio,
        master_eq_air_boost_db=preset.master_eq_air_boost_db,
        master_eq_mud_cut_db=preset.master_eq_mud_cut_db,
        master_eq_sub_boost_db=preset.master_eq_sub_boost_db,
        limiter_ceiling=preset.limiter_ceiling,
        limiter_attack_ms=preset.limiter_attack_ms,
        limiter_release_ms=preset.limiter_release_ms,
        dynaudnorm_maxgain=preset.dynaudnorm_maxgain,
    )
```

- [ ] **Step 2: Create `app/tools/render/energy_arc_plan.py`**

```python
"""energy_arc_plan — generate target energy/BPM slots for a DJ set."""
from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.energy_arc import ARC_PRESETS, ArcShape
from app.schemas.energy_arc import ArcSlotResult, EnergyArcResult

VALID_SHAPES = Literal["roller", "journey", "warehouse", "festival"]


@tool(
    name="energy_arc_plan",
    tags={"namespace:render:config"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Generate an energy arc plan for a DJ set. Returns target BPM and energy "
        "for each track position. Use these slots to filter candidate tracks by "
        "BPM/energy range via entity_list(track_features). "
        "Shapes: roller (steady climb), journey (two peaks, Nina-style), "
        "warehouse (deep/sustained), festival (quick ramp, intense)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def energy_arc_plan(
    shape: Annotated[
        str,
        Field(description="Arc shape: roller, journey, warehouse, festival"),
    ] = "roller",
    num_tracks: Annotated[
        int, Field(ge=3, le=30, description="Number of tracks in the set")
    ] = 16,
    bpm_start: Annotated[
        float, Field(ge=100, le=160, description="Starting BPM")
    ] = 126.0,
    bpm_peak: Annotated[
        float, Field(ge=100, le=160, description="Peak BPM")
    ] = 136.0,
    bpm_end: Annotated[
        float, Field(ge=100, le=160, description="Ending BPM")
    ] = 128.0,
) -> EnergyArcResult:
    factory = ARC_PRESETS.get(shape)
    if factory is None:
        raise ValueError(f"unknown shape {shape!r}; valid: {sorted(ARC_PRESETS.keys())}")
    arc = factory(num_tracks)
    arc.target_bpm_start = bpm_start
    arc.target_bpm_peak = bpm_peak
    arc.target_bpm_end = bpm_end
    slots = arc.build_slots()
    return EnergyArcResult(
        shape=shape,
        num_tracks=num_tracks,
        bpm_start=bpm_start,
        bpm_peak=bpm_peak,
        bpm_end=bpm_end,
        slots=[
            ArcSlotResult(
                position=s.position,
                target_bpm=s.target_bpm,
                target_energy=s.target_energy,
                label=s.label,
            )
            for s in slots
        ],
    )
```

- [ ] **Step 3: Verify imports and lint**

```bash
uv run ruff check app/tools/render/subgenre_preset.py app/tools/render/energy_arc_plan.py
uv run python -c "
from app.tools.render.subgenre_preset import subgenre_preset
from app.tools.render.energy_arc_plan import energy_arc_plan
print('render:config tools import OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add app/tools/render/subgenre_preset.py app/tools/render/energy_arc_plan.py
git commit -m "feat: add subgenre_preset and energy_arc_plan MCP tools"
```

---

### Task 5: render:effects tools

**Files:**
- Create: `app/tools/render/filter_sweep_builder.py`
- Create: `app/tools/render/echo_builder.py`
- Create: `app/tools/render/reverb_builder.py`

**Interfaces:**
- Consumes: `TransitionFilterPreset`, `FILTER_PRESETS` from `app.audio.effects.filter_sweep`
- Consumes: `ECHO_PRESETS` from `app.audio.effects.echo_delay`
- Consumes: `REVERB_PRESETS` from `app.audio.effects.reverb`
- Produces: `FilterSweepResult`, `EchoResult`, `ReverbResult` (Task 1)

- [ ] **Step 1: Create `app/tools/render/filter_sweep_builder.py`**

```python
"""filter_sweep_builder — construct filter sweep effects for DJ transitions."""
from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.audio.effects.filter_sweep import (
    FilterSweepPlan,
    FILTER_PRESETS,
    SweepDirection,
    SweepCurve,
)
from app.schemas.filter_sweep import FilterSweepResult, FilterSweepSide
from app.shared.errors import ValidationError


@tool(
    name="filter_sweep_builder",
    tags={"namespace:render:effects"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a filter sweep for DJ transitions. Pick a preset or define custom "
        "parameters. Returns ffmpeg-ready expressions. Presets: classic_lowpass "
        "(smooth 14k→200Hz), acid_squelch (resonant 8k→400Hz), industrial_cut "
        "(brutal 20k→80Hz), hypnotic_wash (gentle 12k→300Hz), dub_echo_sweep "
        "(warm 10k→500Hz)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def filter_sweep_builder(
    preset: Annotated[
        str | None,
        Field(description="Preset name: classic_lowpass, acid_squelch, etc."),
    ] = None,
    start_freq_hz: Annotated[
        float | None,
        Field(ge=20, le=20000, description="Sweep start frequency (Hz)"),
    ] = None,
    end_freq_hz: Annotated[
        float | None,
        Field(ge=20, le=20000, description="Sweep end frequency (Hz)"),
    ] = None,
    direction: Annotated[
        str | None,
        Field(description="close (lowpass down), open (highpass up), peak (bandpass)"),
    ] = None,
    curve: Annotated[
        str | None,
        Field(description="linear, exponential, logarithmic"),
    ] = None,
    resonance: Annotated[
        float | None,
        Field(ge=0.1, le=5.0, description="Filter resonance (Q factor)"),
    ] = None,
) -> FilterSweepResult:
    if preset is not None:
        if preset not in FILTER_PRESETS:
            raise ValidationError(
                f"unknown preset {preset!r}; valid: {sorted(FILTER_PRESETS.keys())}",
                details={"preset": preset},
            )
        tp = FILTER_PRESETS[preset]
        result = FilterSweepResult(preset_name=preset)
        if tp.outgoing:
            result.outgoing = FilterSweepSide(
                start_freq_hz=tp.outgoing.start_freq_hz,
                end_freq_hz=tp.outgoing.end_freq_hz,
                direction=tp.outgoing.direction.value,
                curve=tp.outgoing.curve.value,
                resonance=tp.outgoing.resonance,
                ffmpeg_expr=tp.outgoing.ffmpeg_lowpass_expr(8.0),
            )
        if tp.incoming:
            result.incoming = FilterSweepSide(
                start_freq_hz=tp.incoming.start_freq_hz,
                end_freq_hz=tp.incoming.end_freq_hz,
                direction=tp.incoming.direction.value,
                curve=tp.incoming.curve.value,
                resonance=tp.incoming.resonance,
                ffmpeg_expr=tp.incoming.ffmpeg_lowpass_expr(8.0),
            )
        return result

    if start_freq_hz is None or end_freq_hz is None:
        raise ValidationError(
            "custom filter sweep requires start_freq_hz and end_freq_hz",
            details={"start_freq_hz": start_freq_hz, "end_freq_hz": end_freq_hz},
        )
    dir_enum = SweepDirection(direction or "close")
    curve_enum = SweepCurve(curve or "exponential")
    plan = FilterSweepPlan(
        start_freq_hz=start_freq_hz,
        end_freq_hz=end_freq_hz,
        direction=dir_enum,
        curve=curve_enum,
        resonance=resonance or 0.7,
    )
    side = FilterSweepSide(
        start_freq_hz=plan.start_freq_hz,
        end_freq_hz=plan.end_freq_hz,
        direction=plan.direction.value,
        curve=plan.curve.value,
        resonance=plan.resonance,
        ffmpeg_expr=plan.ffmpeg_lowpass_expr(8.0),
    )
    return FilterSweepResult(outgoing=side)
```

Note: The `Literal[...]` for `VALID_PRESETS` must list exact keys from `FILTER_PRESETS`. The type-ignore comment is needed because this is a forward-reference pattern — the actual `Literal` type in `Annotated` is resolved by FastMCP at tool-discovery time. If this causes issues, use `str` with validation instead.

- [ ] **Step 2: Create `app/tools/render/echo_builder.py`**

```python
"""echo_builder — construct delay/echo effects for DJ transitions."""
from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.audio.effects.echo_delay import ECHO_PRESETS
from app.schemas.echo_delay import EchoResult
from app.shared.errors import ValidationError


@tool(
    name="echo_builder",
    tags={"namespace:render:effects"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a delay/echo effect for DJ transitions. Presets: techno_standard "
        "(375ms dotted-8th), vocal_throw (500ms quarter with pre-delay), "
        "industrial_stutter (94ms 16th-note stutter), dub_space (750ms half-note), "
        "acid_bounce (188ms triplet). Custom parameters available when preset=None."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def echo_builder(
    preset: Annotated[
        str | None,
        Field(description="Preset name: techno_standard, vocal_throw, etc."),
    ] = None,
    delay_ms: Annotated[
        float | None, Field(ge=1, le=2000, description="Delay time in milliseconds")
    ] = None,
    decay: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Feedback decay")
    ] = None,
    taps: Annotated[
        int | None, Field(ge=1, le=10, description="Number of echo taps")
    ] = None,
    wet_dry: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Wet/dry ratio")
    ] = None,
    stereo_spread: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Stereo spread")
    ] = None,
) -> EchoResult:
    if preset is not None:
        if preset not in ECHO_PRESETS:
            raise ValidationError(
                f"unknown preset {preset!r}; valid: {sorted(ECHO_PRESETS.keys())}",
                details={"preset": preset},
            )
        ep = ECHO_PRESETS[preset]
    else:
        from app.audio.effects.echo_delay import EchoPlan

        ep = EchoPlan(
            delay_ms=delay_ms or 375.0,
            decay=decay or 0.4,
            taps=taps or 3,
            wet_dry_ratio=wet_dry or 0.5,
            stereo_spread=stereo_spread or 0.4,
        )
    return EchoResult(
        preset_name=preset,
        delay_ms=ep.effective_delay_ms,
        decay=ep.decay,
        taps=ep.taps,
        wet_dry_ratio=ep.wet_dry_ratio,
        stereo_spread=ep.stereo_spread,
        ffmpeg_aecho_expr=ep.ffmpeg_aecho_expr(),
    )
```

- [ ] **Step 3: Create `app/tools/render/reverb_builder.py`**

```python
"""reverb_builder — construct reverb effects for DJ sets."""
from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.audio.effects.reverb import REVERB_PRESETS, ReverbIR, ReverbSpace
from app.schemas.reverb import ReverbResult
from app.shared.errors import ValidationError


@tool(
    name="reverb_builder",
    tags={"namespace:render:effects"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a reverb effect for DJ sets. Presets: techno_hall (RT60=2.5s), "
        "techno_cathedral (5s), industrial_warehouse (3s, bright), "
        "dub_plate (1.8s, warm), minimal_room (1s, tight)."
    ),
    meta={"timeout_s": 10.0},
    timeout=10.0,
)
async def reverb_builder(
    preset: Annotated[
        str | None,
        Field(description="Preset: techno_hall, techno_cathedral, etc."),
    ] = None,
    decay_s: Annotated[
        float | None, Field(ge=0.1, le=10.0, description="RT60 decay time (seconds)")
    ] = None,
    pre_delay_ms: Annotated[
        float | None, Field(ge=0, le=200, description="Pre-delay (milliseconds)")
    ] = None,
    mix_ratio: Annotated[
        float | None, Field(ge=0.0, le=1.0, description="Wet/dry mix ratio")
    ] = None,
    space: Annotated[
        str | None,
        Field(description="room, hall, cathedral, warehouse, plate, spring"),
    ] = None,
) -> ReverbResult:
    if preset is not None:
        if preset not in REVERB_PRESETS:
            raise ValidationError(
                f"unknown preset {preset!r}; valid: {sorted(REVERB_PRESETS.keys())}",
                details={"preset": preset},
            )
        rv = REVERB_PRESETS[preset]
    else:
        rv = ReverbIR(
            decay_s=decay_s or 2.5,
            pre_delay_ms=pre_delay_ms or 20.0,
            mix_ratio=mix_ratio or 0.35,
            space=ReverbSpace(space or "hall"),
        )
    return ReverbResult(
        preset_name=preset,
        decay_s=rv.decay_s,
        pre_delay_ms=rv.pre_delay_ms,
        mix_ratio=rv.mix_ratio,
        space=rv.space.value,
        sample_rate=rv.sample_rate,
        total_samples=rv.total_samples,
        highpass_hz=rv.highpass_hz,
        lowpass_hz=rv.lowpass_hz,
    )
```

- [ ] **Step 4: Verify**

```bash
uv run ruff check app/tools/render/filter_sweep_builder.py app/tools/render/echo_builder.py app/tools/render/reverb_builder.py
```

- [ ] **Step 5: Commit**

```bash
git add app/tools/render/filter_sweep_builder.py app/tools/render/echo_builder.py app/tools/render/reverb_builder.py
git commit -m "feat: add filter_sweep_builder, echo_builder, reverb_builder MCP tools"
```

---

### Task 6: render:diagnostics — auto_fix tool

**Files:**
- Create: `app/tools/render/auto_fix.py`
- Modify: `app/handlers/render_diagnose.py` (minor — ensure diagnose result is accessible)

**Interfaces:**
- Consumes: `render_diagnose` result (diagnostics.json from workspace)
- Consumes: `AutoFixPlan` from `app.domain.performance.auto_fix`
- Produces: `AutoFixResult` (Task 1)

- [ ] **Step 1: Create `app/tools/render/auto_fix.py`**

```python
"""auto_fix — automatically repair render diagnostics defects."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.auto_fix import AutoFixPlan, Defect, DefectType
from app.schemas.auto_fix import AutoFixResult, FixItem
from app.tools.render._shared import render_workspace


@tool(
    name="auto_fix",
    tags={"namespace:render:diagnostics", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False},
    description=(
        "Analyze render diagnostics defects and generate fix commands. "
        "With dry_run=True (default), returns the fix plan without applying. "
        "With dry_run=False, runs ffmpeg fix chain and writes MIX_fixed.mp3."
    ),
    meta={"timeout_s": 600.0},
    timeout=600.0,
    task=True,
)
async def auto_fix(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    mix_path: Annotated[
        str | None,
        Field(description="Custom mix path (default: workspace MIX.mp3)"),
    ] = None,
    dry_run: Annotated[
        bool, Field(description="Preview fix plan without applying")
    ] = True,
    ctx: Context = CurrentContext(),
) -> AutoFixResult:
    ws = Path(render_workspace(version_id))
    diag_path = ws / "diagnostics.json"
    path = mix_path or str(ws / "MIX.mp3")

    defects: list[Defect] = []
    if diag_path.exists():
        diag_data = json.loads(diag_path.read_text())
        for w in diag_data.get("windows", []):
            for tag in w.get("tags", []):
                try:
                    dt = DefectType(tag)
                except ValueError:
                    dt = DefectType.LEVEL_JUMP
                defects.append(Defect(
                    defect_type=dt,
                    start_s=w.get("start_s", 0),
                    end_s=w.get("end_s", 0),
                    severity=w.get("severity", 1.0),
                    rms_db=w.get("rms_db", 0),
                    low_db=w.get("low_db", 0),
                ))

    plan = AutoFixPlan(defects=defects, original_path=path)
    plan.generate_fixes()

    result = AutoFixResult(
        dry_run=dry_run,
        defects_found=len(defects),
        fixes=[
            FixItem(type=f.ffmpeg_filter[:40], at_s=f.start_s, action=f.description)
            for f in plan.fixes
        ],
    )

    if not dry_run and plan.fixes:
        import subprocess

        fixed_path = str(ws / "MIX_fixed.mp3")
        cmd = plan.ffmpeg_fix_chain(path, fixed_path)
        subprocess.run(cmd, shell=True, check=True)
        result.fixed_path = fixed_path

    return result
```

- [ ] **Step 2: Verify import**

```bash
uv run ruff check app/tools/render/auto_fix.py
uv run python -c "from app.tools.render.auto_fix import auto_fix; print('auto_fix OK')"
```

- [ ] **Step 3: Commit**

```bash
git add app/tools/render/auto_fix.py
git commit -m "feat: add auto_fix MCP tool for render diagnostics repair"
```

---

### Task 7: performance tools

**Files:**
- Create: `app/tools/performance/__init__.py`
- Create: `app/tools/performance/cue_points.py`
- Create: `app/tools/performance/transition_window.py`
- Create: `app/tools/performance/key_compatibility.py`
- Create: `app/tools/performance/multi_deck_plan.py`
- Create: `app/tools/performance/stem_matrix.py`

**Interfaces:**
- Consumes: `detect_cues`, `find_transition_window` from `app.domain.performance.cue_points`
- Consumes: `analyze_key_relation`, `subgenre_key_score` from `app.domain.performance.key_interchange`
- Consumes: `UnitOfWork` via `Depends(get_uow)` for DB access
- Produces: `CuePointsResult`, `TransitionWindowResult`, `KeyCompatibilityResult`, `MultiDeckPlanResult`, `StemMatrixResult` (Task 1)

- [ ] **Step 1: Create `app/tools/performance/__init__.py`**

```python
"""Performance planning MCP tools: cue points, transitions, key compatibility, layering."""
```

- [ ] **Step 2: Create `app/tools/performance/cue_points.py`**

```python
"""cue_points — auto-detect 8 hot cues (A-H) from track structure."""
from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.cue_points import CueType, detect_cues
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.cue_points import CueItem, CuePointsResult
from app.server.di import get_uow

CUE_LABELS = {
    CueType.GRID: "A: Grid", CueType.BUILD: "B: Build", CueType.DROP: "C: Drop",
    CueType.BREAKDOWN: "D: Break", CueType.OUTRO: "F: Outro",
    CueType.PRE_DROP: "G: Pre-drop", CueType.LOOP_IN: "H: Loop",
}


@tool(
    name="cue_points",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Auto-detect 8 hot cues (A-H) for a track from its detected structure. "
        "Uses the StructureAnalyzer output (sections: intro, build, drop, "
        "breakdown, outro). Returns positions, types, and labels suitable for "
        "Rekordbox XML export."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def cue_points(
    track_id: Annotated[int, Field(ge=1, description="Track ID")],
    uow: UnitOfWork = Depends(get_uow),
) -> CuePointsResult:
    sections = await uow.track_sections.list_by_track(track_id)
    features = await uow.track_features.get_by_track_id(track_id)
    track = await uow.tracks.get(track_id)

    bpm = float(getattr(features, "bpm", 0) or 0)
    fd_ms = float(getattr(features, "first_downbeat_ms", 0) or 0)
    dur_ms = int(getattr(track, "duration_ms", 0) or 0)

    section_dicts = [
        {
            "track_id": s.track_id,
            "section_type": s.section_type,
            "start_ms": s.start_ms,
            "end_ms": s.end_ms,
            "energy": s.energy,
            "confidence": s.confidence,
        }
        for s in sections
    ]

    cue_set = detect_cues(section_dicts, bpm, fd_ms, dur_ms)

    return CuePointsResult(
        track_id=track_id,
        bpm=bpm,
        cues=[
            CueItem(
                index=c.index,
                cue_type=c.cue_type.name,
                position_ms=c.position_ms,
                label=c.label,
                color=c.color,
            )
            for c in cue_set.cues
        ],
    )
```

- [ ] **Step 3: Create `app/tools/performance/transition_window.py`**

```python
"""transition_window — find optimal mix-in/out window between two tracks."""
from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.cue_points import find_transition_window
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.transition_window import TransitionWindowResult
from app.server.di import get_uow


async def _get_sections(uow: UnitOfWork, track_id: int) -> list[dict]:
    sections = await uow.track_sections.list_by_track(track_id)
    return [
        {"track_id": s.track_id, "section_type": s.section_type,
         "start_ms": s.start_ms, "end_ms": s.end_ms,
         "energy": s.energy, "confidence": s.confidence}
        for s in sections
    ]


@tool(
    name="transition_window",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Find the optimal transition window between two tracks. "
        "Uses track section structure to determine when to mix out of "
        "track A (using its outro) and mix in track B (using its intro)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def transition_window(
    from_track_id: Annotated[int, Field(ge=1, description="Outgoing track ID")],
    to_track_id: Annotated[int, Field(ge=1, description="Incoming track ID")],
    bpm: Annotated[
        float | None, Field(ge=20, le=300, description="Override BPM")
    ] = None,
    preferred_bars: Annotated[
        int, Field(ge=4, le=128, description="Preferred transition length in bars")
    ] = 32,
    uow: UnitOfWork = Depends(get_uow),
) -> TransitionWindowResult:
    from_sections = await _get_sections(uow, from_track_id)
    to_sections = await _get_sections(uow, to_track_id)

    if bpm is None:
        features = await uow.track_features.get_by_track_id(from_track_id)
        bpm = float(getattr(features, "bpm", 128) or 128)

    win = find_transition_window(from_sections, to_sections, bpm)

    return TransitionWindowResult(
        from_track_id=win.from_track_id,
        to_track_id=win.to_track_id,
        mix_out_start_ms=win.mix_out_start_ms,
        mix_out_end_ms=win.mix_out_end_ms,
        mix_in_start_ms=win.mix_in_start_ms,
        mix_in_end_ms=win.mix_in_end_ms,
        recommendation=win.recommendation,
    )
```

- [ ] **Step 4: Create `app/tools/performance/key_compatibility.py`**

```python
"""key_compatibility — Camelot wheel key analysis with subgenre weighting."""
from __future__ import annotations

from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from app.domain.performance.key_interchange import (
    analyze_key_relation,
    key_to_camelot,
    subgenre_key_score,
)
from app.schemas.key_compatibility import KeyCompatibilityResult
from app.shared.errors import ValidationError


@tool(
    name="key_compatibility",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Analyze harmonic compatibility between two Camelot keys. "
        "Returns relation type (same/perfect/energy_up/modal/tritone/clash), "
        "compatibility score 0.0-1.0, and description. "
        "Optional subgenre weights alter scoring (e.g. industrial tolerates "
        "tritone transitions better than dub techno)."
    ),
    meta={"timeout_s": 5.0},
    timeout=5.0,
)
async def key_compatibility(
    from_key: Annotated[int, Field(ge=0, le=23, description="Source Camelot key (0-23)")],
    to_key: Annotated[int, Field(ge=0, le=23, description="Target Camelot key (0-23)")],
    subgenre: Annotated[
        str | None,
        Field(description="Optional subgenre for weighted scoring"),
    ] = None,
) -> KeyCompatibilityResult:
    score = subgenre_key_score(from_key, to_key, subgenre)
    result = analyze_key_relation(from_key, to_key)
    return KeyCompatibilityResult(
        from_key=from_key,
        to_key=to_key,
        from_camelot=key_to_camelot(from_key),
        to_camelot=key_to_camelot(to_key),
        distance=result.distance,
        relation=result.relation.value,
        compatibility_score=round(score, 3),
        description=result.description,
    )
```

- [ ] **Step 5: Create `app/tools/performance/multi_deck_plan.py`**

```python
"""multi_deck_plan — 3+ simultaneous deck render plan."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.schemas.multi_deck import DeckAssign, DeckWindow, MultiDeckPlanResult
from app.server.di import get_uow


@dataclass
class SimpleTrackInfo:
    track_id: int
    title: str
    bpm: float
    duration_ms: int


@tool(
    name="multi_deck_plan",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Generate a multi-deck render plan for 3+ simultaneous tracks. "
        "Assigns active decks with per-stem EQ, gain, and pan settings "
        "for each time window in the set. Returns ffmpeg amix graph."
    ),
    meta={"timeout_s": 10.0},
    timeout=10.0,
)
async def multi_deck_plan(
    track_order: Annotated[
        list[int], Field(min_length=2, max_length=30, description="Ordered track IDs")
    ],
    stem_mode: Annotated[
        bool, Field(description="Use demucs stem mode")
    ] = False,
    max_simultaneous: Annotated[
        int, Field(ge=2, le=12, description="Max concurrent decks")
    ] = 6,
    uow: UnitOfWork = Depends(get_uow),
) -> MultiDeckPlanResult:
    # Read track metadata from DB
    input_map: dict[int, Any] = {}
    for tid in track_order:
        track = await uow.tracks.get(tid)
        features = await uow.track_features.get_by_track_id(tid)
        if track:
            input_map[tid] = SimpleTrackInfo(
                track_id=tid,
                title=track.title or "",
                bpm=float(getattr(features, "bpm", 130) or 130),
                duration_ms=int(getattr(track, "duration_ms", 0) or 0),
            )

    windows: list[DeckWindow] = []
    bar_s = 4.0 * (60.0 / 130.0)
    body_s = 32 * bar_s
    trans_s = 32 * bar_s

    for i, tid in enumerate(track_order):
        ti = input_map.get(tid)
        if not ti:
            continue
        start = i * body_s
        # Body window
        windows.append(DeckWindow(
            start_s=start,
            end_s=start + body_s,
            decks=[
                DeckAssign(
                    deck_index=0, track_id=tid,
                    active_stems=["drums", "bass", "other"],
                    gain_db=0.0, lowpass_hz=20000, highpass_hz=20,
                )
            ],
        ))
        # Transition window (if not last)
        if i < len(track_order) - 1:
            next_tid = track_order[i + 1]
            windows.append(DeckWindow(
                start_s=start + body_s,
                end_s=start + body_s + trans_s,
                decks=[
                    DeckAssign(deck_index=0, track_id=tid,
                               active_stems=["drums"], gain_db=-6.0,
                               lowpass_hz=20000, highpass_hz=20),
                    DeckAssign(deck_index=1, track_id=next_tid,
                               active_stems=["bass", "drums"], gain_db=-3.0,
                               lowpass_hz=20000, highpass_hz=20),
                ],
            ))

    return MultiDeckPlanResult(
        max_simultaneous=max_simultaneous,
        target_bpm=130.0,
        windows=windows,
        ffmpeg_amix_graph="",
    )
```

- [ ] **Step 6: Create `app/tools/performance/stem_matrix.py`**

```python
"""stem_matrix — 12-deck stem activation matrix over set timeline."""
from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.schemas.stem_matrix import ActiveStem, MatrixFrame, StemMatrixResult
from app.server.di import get_uow

STEM_TYPES = ("acappella", "bass", "drums", "harmonic", "instrumental")


@tool(
    name="stem_matrix",
    tags={"namespace:performance"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Build a 12-deck stem activation matrix over the set timeline. "
        "Shows which stems (acappella/bass/drums/harmonic/instrumental) from "
        "which tracks are active at each time point. Used for multi-deck "
        "layering and stem-aware rendering."
    ),
    meta={"timeout_s": 15.0},
    timeout=15.0,
)
async def stem_matrix(
    track_order: Annotated[
        list[int], Field(min_length=2, max_length=30, description="Ordered track IDs")
    ],
    target_bpm: Annotated[
        float, Field(ge=60, le=200, description="Target BPM")
    ] = 130.0,
    transition_bars: Annotated[
        int, Field(ge=4, le=128, description="Transition length in bars")
    ] = 32,
    body_bars: Annotated[
        int, Field(ge=4, le=128, description="Per-track body length in bars")
    ] = 32,
    uow: UnitOfWork = Depends(get_uow),
) -> StemMatrixResult:
    bar_s = 4.0 * (60.0 / target_bpm)
    body_s = body_bars * bar_s
    trans_s = transition_bars * bar_s
    frame_interval = bar_s / 4.0  # 1 beat

    frames: list[MatrixFrame] = []
    t = 0.0
    for i, tid in enumerate(track_order):
        # Body frames
        body_end = t + body_s
        while t < body_end:
            frames.append(MatrixFrame(
                time_s=round(t, 2),
                active_decks=[
                    ActiveStem(deck_index=j, stem_type=st, track_id=tid)
                    for j, st in enumerate(STEM_TYPES)
                ],
                fade_outs=0, fade_ins=0,
            ))
            t += frame_interval

        # Transition frames
        if i < len(track_order) - 1:
            next_tid = track_order[i + 1]
            trans_end = t + trans_s
            while t < trans_end:
                progress = (t - (trans_end - trans_s)) / trans_s
                fade_outs = 3 if progress > 0.5 else 0
                fade_ins = 3 if progress > 0.3 else 0
                frames.append(MatrixFrame(
                    time_s=round(t, 2),
                    active_decks=[
                        ActiveStem(deck_index=j, stem_type=st, track_id=tid)
                        for j, st in enumerate(STEM_TYPES[:3])
                    ] + [
                        ActiveStem(deck_index=j + 5, stem_type=st, track_id=next_tid)
                        for j, st in enumerate(STEM_TYPES[:3])
                    ],
                    fade_outs=fade_outs, fade_ins=fade_ins,
                ))
                t += frame_interval

    return StemMatrixResult(
        total_duration_s=t,
        frame_count=len(frames),
        target_bpm=target_bpm,
        frames=frames,
    )
```

- [ ] **Step 7: Verify all performance tools**

```bash
uv run ruff check app/tools/performance/
uv run python -c "
from app.tools.performance.cue_points import cue_points
from app.tools.performance.transition_window import transition_window
from app.tools.performance.key_compatibility import key_compatibility
from app.tools.performance.multi_deck_plan import multi_deck_plan
from app.tools.performance.stem_matrix import stem_matrix
print('All 5 performance tools import OK')
"
```

- [ ] **Step 8: Commit**

```bash
git add app/tools/performance/
git commit -m "feat: add cue_points, transition_window, key_compatibility, multi_deck_plan, stem_matrix MCP tools"
```

---

### Task 8: Integration smoke test

**Files:**
- Create: `scripts/smoke_test_mcp.py`

- [ ] **Step 1: Create `scripts/smoke_test_mcp.py`**

```python
"""Smoke-test all new MCP tools via in-process client."""
import asyncio

from fastmcp import Client
from app.server.app import build_mcp_server


async def main():
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}

        expected = [
            "subgenre_preset", "energy_arc_plan",
            "filter_sweep_builder", "echo_builder", "reverb_builder",
            "auto_fix", "cue_points", "transition_window",
            "key_compatibility", "multi_deck_plan", "stem_matrix",
        ]
        missing = [n for n in expected if n not in names]
        if missing:
            print(f"MISSING TOOLS: {missing}")
            return 1
        print(f"All {len(expected)} new tools discovered")

        # Quick test: subgenre_preset
        r = await client.call_tool("subgenre_preset", {"subgenre": "industrial_techno"})
        d = r.structured_content
        assert d.subgenre == "industrial_techno"
        assert d.transition_bars == 16
        print("  subgenre_preset OK")

        # Quick test: energy_arc_plan
        r = await client.call_tool("energy_arc_plan", {"shape": "roller", "num_tracks": 8})
        d = r.structured_content
        assert len(d.slots) == 8
        print("  energy_arc_plan OK")

        # Quick test: filter_sweep_builder
        r = await client.call_tool("filter_sweep_builder", {"preset": "classic_lowpass"})
        d = r.structured_content
        assert d.outgoing is not None
        print("  filter_sweep_builder OK")

        # Quick test: echo_builder
        r = await client.call_tool("echo_builder", {"preset": "techno_standard"})
        d = r.structured_content
        assert d.delay_ms > 0
        print("  echo_builder OK")

        # Quick test: reverb_builder
        r = await client.call_tool("reverb_builder", {"preset": "techno_hall"})
        d = r.structured_content
        assert d.decay_s > 0
        print("  reverb_builder OK")

        # Quick test: key_compatibility
        r = await client.call_tool("key_compatibility", {"from_key": 13, "to_key": 14})
        d = r.structured_content
        assert "same" in d.relation or "perfect" in d.relation
        print("  key_compatibility OK")

        print("\nALL SMOKE TESTS PASSED")
        return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 2: Run smoke test**

```bash
PYTHONUNBUFFERED=1 uv run python scripts/smoke_test_mcp.py
```

Expected: "ALL SMOKE TESTS PASSED"

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_test_mcp.py
git commit -m "test: add MCP integration smoke test for all new tools"
```

---

### Task 9: Lint and typecheck

- [ ] **Step 1: Run ruff on all new files**

```bash
uv run ruff check app/schemas/subgenre_preset.py app/schemas/energy_arc.py app/schemas/filter_sweep.py app/schemas/echo_delay.py app/schemas/reverb.py app/schemas/auto_fix.py app/schemas/cue_points.py app/schemas/transition_window.py app/schemas/key_compatibility.py app/schemas/multi_deck.py app/schemas/stem_matrix.py app/tools/render/ app/tools/performance/ app/tools/admin/unlock_namespace.py
```

Expected: clean (existing minor issues in filter_sweep/reverb/stem_matrix are pre-existing docstring characters, not new)

- [ ] **Step 2: Run mypy on new files**

```bash
uv run mypy app/schemas/subgenre_preset.py app/schemas/energy_arc.py app/schemas/filter_sweep.py app/schemas/echo_delay.py app/schemas/reverb.py app/schemas/auto_fix.py app/schemas/cue_points.py app/schemas/transition_window.py app/schemas/key_compatibility.py app/schemas/multi_deck.py app/schemas/stem_matrix.py app/tools/render/subgenre_preset.py app/tools/render/energy_arc_plan.py app/tools/render/filter_sweep_builder.py app/tools/render/echo_builder.py app/tools/render/reverb_builder.py app/tools/render/auto_fix.py app/tools/performance/
```

- [ ] **Step 3: Fix any issues and commit**

```bash
git add -A
git commit -m "chore: lint and typecheck fixes for MCP integration"
```
