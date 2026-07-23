# Render Config MCP Surface — Resource Provider + Override Layer

> **Date:** 2026-07-22
> **Status:** Draft for review
> **Problem:** `RenderSettings` (30+ DSP params) is invisible to AI clients. Changing defaults breaks every render. Per-render DSP overrides impossible without modifying Python code.

---

## Design Constraints

1. **Zero modifications to existing code.** Only add new files.
2. **OCP (Open-Closed).** Existing tool/handler/plan/executor work unchanged.
3. **AI-first.** Resources for reading config, tool params for overriding.
4. **FastMCP v3 patterns.** Custom Provider + Resource templates.

---

## Data Flow (unchanged, in grey)

```
Tool (existing) → Handler → RenderRequest → Orchestrator → Planner → RenderPlan → Executor → MP3
```

## Data Flow (new layer in blue)

```
New Tool (extended) ───────────────────────┐
                                           v
                      New Handler ──→ RenderRequest (same)
                      + overrides ──→ RenderRequestOverrides
                                           |
                      Orchestrator.run() ←──┘ (same, runs as before)
                           |
                      RenderPlan ←─── from_settings() (same)
                           |
                      apply_overrides(plan, overrides) ──→ RenderPlan (modified)
                           |
                      Executor.execute(modified_plan) (same executor)
```

---

## New Files

### 1. `app/providers/render_config.py` — FastMCP v3 Provider

Custom **FastMCP v3 Provider** exposing render settings as MCP resources.

**Resources:**

| URI | Returns | Description |
|-----|---------|-------------|
| `settings://render` | `RenderSettings` as JSON | All 30+ DSP defaults |
| `settings://render/{field}` | `{field: value}` | Single field |
| `schema://render/tool_extended` | `{params: [...]}` | Full param schema for `render_mixdown_extended` |

**Provider registration** (in `server.py`):

```python
from app.providers.render_config import RenderConfigProvider
server.add_provider(RenderConfigProvider())
```

**Implementation sketch:**

```python
from fastmcp.providers import Provider
from app.config import get_settings

class RenderConfigProvider(Provider):
    namespace = "settings"
    
    async def read(self, path: str) -> Any:
        settings = get_settings().render
        if not path or path == "/":
            return settings.model_dump(mode="json")
        parts = path.strip("/").split("/")
        if parts[0] == "render":
            if len(parts) == 1:
                return settings.model_dump(mode="json")
            field = parts[1]
            if hasattr(settings, field):
                return {field: getattr(settings, field)}
        return None

# Also expose schema:// via separate Provider or resource template
```

### 2. `app/domain/render/overrides.py` — Override Dataclass + Applicator

```python
from dataclasses import dataclass, replace
from typing import Optional
from app.domain.render.models import RenderPlan

@dataclass(frozen=True, slots=True)
class RenderRequestOverrides:
    # ── Per-track pre-processing ──
    hpf_cutoff_hz: float | None = None
    per_track_eq_mid_cut_db: float | None = None
    per_track_eq_bright_boost_db: float | None = None
    pre_comp_threshold_db: float | None = None
    pre_comp_ratio: float | None = None
    pre_comp_attack_ms: float | None = None
    pre_comp_release_ms: float | None = None
    # ── Master bus ──
    glue_comp_threshold_db: float | None = None
    glue_comp_ratio: float | None = None
    glue_comp_attack_ms: float | None = None
    glue_comp_release_ms: float | None = None
    master_eq_air_boost_db: float | None = None
    master_eq_mud_cut_db: float | None = None
    master_eq_sub_boost_db: float | None = None
    limiter_attack_ms: float | None = None
    limiter_release_ms: float | None = None
    limiter_ceiling: float | None = None
    dynaudnorm_maxgain: float | None = None
    # ── Crossfade geometry ──
    xsplit_low_hz: int | None = None
    xsplit_high_hz: int | None = None
    eq_phase_1_ratio: float | None = None
    eq_phase_2_ratio: float | None = None
    low_swap_beats: float | None = None
    outro_fade_bars: int | None = None


def apply_overrides(plan: RenderPlan, overrides: RenderRequestOverrides) -> RenderPlan:
    """Return a new RenderPlan with non-None overrides applied."""
    kwargs: dict[str, object] = {}
    for field_name in overrides.__dataclass_fields__:
        value = getattr(overrides, field_name)
        if value is not None:
            kwargs[field_name] = value
    if not kwargs:
        return plan
    return replace(plan, **kwargs)
```

### 3. `app/tools/render/render_mixdown_extended.py` — New Tool

Same signature as `render_mixdown` **plus** all DSP override params.

```
@tool(name="render_mixdown_extended", task=True, timeout=1800.0)
async def render_mixdown_extended(
    version_id: int,
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
    # ── DSP overrides (all optional) ──
    hpf_cutoff_hz: float | None = None,
    per_track_eq_mid_cut_db: float | None = None,
    # ... etc, one per RenderSettings field
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderMixdownResult: ...
```

### 4. `app/handlers/render_mixdown_extended.py` — New Handler

```python
async def render_mixdown_extended_handler(
    *, ctx, uow, version_id, workspace, timestamp,
    # ... same params as render_mixdown_handler ...
    # ... plus DSP overrides ...
) -> RenderMixdownResult:
    _validate_out_name(out_name)
    request = RenderRequest(version_id=version_id, ...)
    overrides = RenderRequestOverrides(hpf_cutoff_hz=hpf_cutoff_hz, ...)
    plan = await RenderOrchestrator(uow).run_raw(request)  # returns plan
    plan = apply_overrides(plan, overrides)
    return await RenderExecutor(uow).execute_raw(ctx, request, plan)
```

---

## Integration Points

| Location | What to add | Existing code changed? |
|----------|-------------|----------------------|
| `server.py` | `server.add_provider(RenderConfigProvider())` | **Yes** (one line) — unavoidable registration |
| `app/tools/__init__.py` | Export new tool | **Yes** (one import) — unavoidable registration |
| Everywhere else | New files only | **No** |

---

## Verification

1. `uv run pytest tests/` — all existing tests pass (no code changed)
2. `uv run ruff check` — no lint issues
3. Read resource `settings://render` → returns full JSON of all defaults
4. Call `render_mixdown_extended(version_id=N, limiter_ceiling=0.9)` → uses 0.9 instead of default 0.85

---

## Future

1. **Preset resources**: `settings://render/presets/{name}` — named override sets (hypnotic, industrial, etc.)
2. **RenderDiff resource**: `diff://render/plan/{version_id}` — what the actual plan will use
3. **Schema evolution**: FastMCP v3 namespace transforms for backward compat
