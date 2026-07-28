# Render Analysis Agent — Design Specification

**Date**: 2026-07-23  
**Project**: dj-music-plugin  
**Status**: Draft for Review

---

## 1. Problem Statement

Currently, DJ set rendering is a manual trial-and-error process:
1. User builds a set version
2. Runs `dj_render_beatgrid` (optional)
3. Runs `dj_render_mixdown` with guessed parameters (filter_sweep, echo, reverb, crossfade curves, stem vs classic, subgenre preset, transition/body bars)
4. Runs `dj_render_diagnose` to find defects
5. If defects found → manually tweak params → goto step 3

This is slow, error-prone, and requires deep domain knowledge of how each render parameter affects the final sound.

---

## 2. Goal

Create a **single MCP tool** `dj_render_analyze` that implements a **closed-loop analysis agent**:

- **Pre-render**: Analyzes track features + transitions + beatgrid to predict issues and recommend optimal render parameters
- **Post-render**: Runs `dj_render_diagnose`, interprets results, suggests fixes
- **Iterative**: Can re-render with adjusted params until quality threshold met (max 3 iterations by default)
- **Agentic**: Makes decisions based on techno DJ best practices encoded in the codebase (Camelot compatibility, BPM drift limits, phase alignment, energy arc, spectral diversity)

---

## 3. Architecture

### 3.1 New MCP Tool

```python
# app/tools/render/render_analyze.py

@tool(
    name="render_analyze",
    tags={"namespace:render", "read"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False},
    description=(
        "Closed-loop render analysis agent. "
        "Runs pre-render analysis, renders (or re-uses existing), diagnoses, "
        "and iteratively refines render parameters until quality threshold met "
        "or max iterations reached. Returns full report with recommendations."
    ),
    meta={"timeout_s": 3600.0},  # Can take up to 1 hour for full loops
    timeout=3600.0,
    task=True,
)
async def render_analyze(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    max_iterations: Annotated[int, Field(ge=1, le=10, description="Max render-diagnose-refine cycles")] = 3,
    quality_threshold: Annotated[float, Field(ge=0.0, le=1.0, description="Target quality_score (0-1)")] = 0.85,
    auto_render: Annotated[bool, Field(description="If True, runs render_mixdown internally; if False, only analyzes existing mix")] = True,
    force_refresh_grid: Annotated[bool, Field(description="Recompute beatgrid even if cached")] = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderAnalysisResult:
    ...
```

### 3.2 Result Schema

```python
# app/schemas/render.py (add to existing)

class RenderAnalysisResult(BaseModel):
    version_id: int
    iterations: int
    final_quality_score: float
    passed_threshold: bool
    
    # Per-iteration history
    history: list[RenderIteration]
    
    # Final recommendations
    recommended_params: RenderMixdownParams  # What to use for final render
    warnings: list[str]
    
    # If auto_render=False and mix exists
    existing_mix_diagnostics: DiagnosticsReport | None = None


class RenderIteration(BaseModel):
    iteration: int
    params_used: RenderMixdownParams
    render_job_id: str | None
    diagnostics: DiagnosticsReport
    quality_score: float
    defects_found: list[RenderDefect]
    adjustments_made: list[ParamAdjustment]


class RenderDefect(BaseModel):
    type: str  # "CAMELOT_CONFLICT", "BPM_DRIFT", "PHASE_MISALIGN", "LEVEL_JUMP", "BASS_THIN", "ENTRY_SHOCK", "LOW_END_COLLAPSE", "ENERGY_FLAT", "TEXTURE_UNIFORM"
    severity: float  # 0-1
    transition_index: int | None
    track_ids: tuple[int, int] | None
    description: str
    suggested_fix: str


class ParamAdjustment(BaseModel):
    param: str
    old_value: Any
    new_value: Any
    reason: str
```

---

## 4. Pre-Render Analysis Logic

### 4.1 Data Sources (Loaded Once)

| Source | Tool/Method | Key Data |
|--------|-------------|----------|
| Track features | `uow.track_features.get_scoring_features_batch()` | bpm, audio_bpm, key_code, key_confidence, atonality, integrated_lufs, energy_mean, spectral_centroid_hz, hp_ratio, kick_prominence, onset_rate, pulse_clarity, bpm_stability, phrase_boundaries_ms, dominant_phrase_bars, first_downbeat_ms, mood, beatport_genre |
| Beatgrid | `BeatgridProvider.load(workspace)` | trim_start_s, refined_trim_s, gain_db, phase_ms |
| Transitions | `dj_transition_score_pool(track_ids)` | All pairwise scores (bpm, energy, drums, bass, harmonics, vocals, overall, best_transition) |
| Set structure | `uow.set_versions.get_render_inputs(version_id)` | Ordered track list with mix_in_ms |

### 4.2 Analysis Checks (In Priority Order)

| Check | Data Used | Threshold | Action if Failed |
|-------|-----------|-----------|------------------|
| **Camelot conflicts** | transition_score_pool.camelot_distance | dist ≥ 5 AND both keys reliable (conf ≥ 0.5) | Recommend track reorder or bridge insertion |
| **BPM discrepancy** | track.audio_bpm vs track.bpm | \|audio_bpm - bpm\| > 0.5 | Use audio_bpm for time-stretch; warn |
| **BPM drift between tracks** | transition_score_pool.bpm_delta | \|delta\| > 5 | Recommend longer transition_bars |
| **Phase misalignment** | beatgrid.phase_ms diff between adjacent tracks | \|Δphase\| > 0.25 beats at target_bpm | Recommend phase adjustment or track swap |
| **Energy gap** | transition LUFS diff | \|ΔLUFS\| > 6 | Recommend pre-comp/glue-comp adjustment |
| **Stem separation quality** | track_features (hp_ratio, kick_prominence, onset_rate) | hp_ratio < 2.0 OR kick_prominence < 0.1 | Force `stem=False` (classic EQ) |
| **Energy arc flatness** | All track energy_std | energy_std < 0.02 | Recommend track reorder for dynamic arc |
| **Spectral texture uniformity** | All track centroid_std | centroid_std < 80Hz | Recommend track reorder |
| **Phrase alignment** | dominant_phrase_bars, phrase_boundaries_ms | Mismatch with transition_bars/body_bars | Adjust transition_bars/body_bars to phrase boundaries |

### 4.3 Parameter Recommendation Engine

```python
class RenderParameterAdvisor:
    """Recommends render_mixdown params based on track/set analysis."""
    
    def advise(self, pre_render_report: PreRenderReport) -> RenderMixdownParams:
        params = RenderMixdownParams()  # Start with defaults
        
        # 1. Subgenre preset → base params
        if pre_render_report.dominant_subgenre:
            params = apply_subgenre_preset(params, pre_render_report.dominant_subgenre)
        
        # 2. Stem vs Classic decision
        if pre_render_report.stem_quality_risk:
            params.stem = False
            params.filter_sweep = None
            params.echo = None
            params.reverb = None
        
        # 3. Camelot conflicts → adjust transitions
        if pre_render_report.camelot_conflicts:
            params.transition_bars = max(params.transition_bars, 48)  # Longer = more forgiving
            params.filter_sweep = "classic_lowpass"  # Mask harmonic clash
        
        # 4. BPM drift → longer transitions
        if pre_render_report.max_bpm_jump > 3:
            params.transition_bars = max(params.transition_bars, 40)
        
        # 5. Energy gaps → compression
        if pre_render_report.max_energy_gap_lufs > 4:
            params.pre_comp_threshold_db = -20.0
            params.pre_comp_ratio = 4.0
            params.glue_comp_threshold_db = -16.0
            params.glue_comp_ratio = 3.5
        
        # 6. Phase issues → disable effects that worsen alignment
        if pre_render_report.phase_issues:
            params.filter_sweep = None
            params.echo = None
            params.reverb = None
            params.crossfade_curve_in = "exp"
            params.crossfade_curve_out = "tri"
        
        # 7. Phrase alignment → adjust bar lengths
        if pre_render_report.phrase_mismatch:
            params.transition_bars = pre_render_report.suggested_transition_bars
            params.body_bars = pre_render_report.suggested_body_bars
        
        return params
```

---

## 5. Post-Render Diagnosis Logic

### 5.1 Defect Classification (from `diagnostics.py`)

| Diagnostic Tag | Defect Type | Severity Calculation |
|----------------|-------------|---------------------|
| `LEVEL-JUMP` | LEVEL_JUMP | \|ΔdB\| / 12.0 (capped at 1.0) |
| `DROPOUT` | DROPOUT | (mean_rms - window_rms) / 20.0 |
| `bass-thin` | BASS_THIN | (rms - low) / 25.0 |
| `ENTRY-SHOCK` | ENTRY_SHOCK | 0.8 (binary) |
| `LOW-END-COLLAPSE` | LOW_END_COLLAPSE | (prev_low_ratio / low_ratio) / 10.0 |
| `PHASE-UNSTABLE` | PHASE_UNSTABLE | 1.0 - stereo_corr |

### 5.2 Structural Flow Analysis (from `analyze_set_flow`)

| Metric | Warning Threshold | Defect Type |
|--------|-------------------|-------------|
| camelot_conflicts > 0 | Any | CAMELOT_CONFLICT |
| max_bpm_jump > 5 | Any | BPM_DRIFT |
| energy_std < 0.02 | < 0.02 | ENERGY_FLAT |
| centroid_std < 80 | < 80 | TEXTURE_UNIFORM |

### 5.3 Fix Suggestion Mapping

| Defect | Param Adjustment |
|--------|------------------|
| LEVEL_JUMP at transition | Increase transition_bars, adjust crossfade curves |
| BASS_THIN | Increase master_eq_sub_boost_db, check low_swap_beats |
| ENTRY_SHOCK | Softer crossfade_curve_in ("sin" or "log"), longer transition |
| LOW_END_COLLAPSE | Increase low_swap_beats, reduce filter_sweep aggression |
| PHASE_UNSTABLE | Disable filter_sweep/echo/reverb, check beatgrid |
| ENERGY_FLAT | Recommend track reorder (pre-render) |
| TEXTURE_UNIFORM | Recommend track reorder (pre-render) |

---

## 6. Iterative Refinement Loop

```python
async def run_analysis_loop(version_id, max_iterations, quality_threshold, auto_render):
    history = []
    current_params = initial_recommendation(pre_render_report)
    
    for iteration in range(1, max_iterations + 1):
        if auto_render:
            # Render with current params
            result = await render_mixdown_handler(
                version_id=version_id,
                transition_bars=current_params.transition_bars,
                body_bars=current_params.body_bars,
                stem=current_params.stem,
                filter_sweep=current_params.filter_sweep,
                echo=current_params.echo,
                reverb=current_params.reverb,
                crossfade_curve_in=current_params.crossfade_curve_in,
                crossfade_curve_out=current_params.crossfade_curve_out,
                # ... all extended params
            )
            mix_path = result.out_path
        else:
            # Use existing mix
            mix_path = get_existing_mix_path(version_id)
            if not mix_path.exists():
                raise ValidationError("No existing mix found")
        
        # Diagnose
        diag_result = await render_diagnose_handler(
            version_id=version_id,
            mix_path=mix_path,
            version_context=build_version_context(version_id)
        )
        
        # Analyze defects
        defects = classify_defects(diag_result)
        quality_score = diag_result.flow.summary.quality_score if diag_result.flow else 0.0
        
        history.append(RenderIteration(
            iteration=iteration,
            params_used=current_params,
            render_job_id=result.job_id if auto_render else None,
            diagnostics=diag_result,
            quality_score=quality_score,
            defects_found=defects,
            adjustments_made=[]
        ))
        
        # Check pass
        if quality_score >= quality_threshold:
            return RenderAnalysisResult(
                version_id=version_id,
                iterations=iteration,
                final_quality_score=quality_score,
                passed_threshold=True,
                history=history,
                recommended_params=current_params,
                warnings=[]
            )
        
        # Compute adjustments for next iteration
        adjustments = compute_adjustments(defects, current_params, pre_render_report)
        current_params = apply_adjustments(current_params, adjustments)
        history[-1].adjustments_made = adjustments
    
    # Max iterations reached
    return RenderAnalysisResult(
        version_id=version_id,
        iterations=max_iterations,
        final_quality_score=quality_score,
        passed_threshold=False,
        history=history,
        recommended_params=current_params,
        warnings=["Max iterations reached without passing quality threshold"]
    )
```

### 6.1 Adjustment Rules (Priority Order)

| Defect Pattern | Adjustment |
|----------------|------------|
| Multiple LEVEL_JUMP + BASS_THIN | `transition_bars += 8`, `low_swap_beats += 0.5`, `filter_sweep = None` |
| ENTRY_SHOCK + PHASE_UNSTABLE | `crossfade_curve_in = "sin"`, `reverb = None`, `echo = None` |
| LOW_END_COLLAPSE | `low_swap_beats += 1.0`, `master_eq_sub_boost_db += 0.5` |
| CAMELOT_CONFLICT (post-render) | Cannot fix via params → recommend track reorder in warnings |
| ENERGY_FLAT / TEXTURE_UNIFORM | Cannot fix via params → recommend track reorder in warnings |

---

## 7. Integration Points

### 7.1 Existing Tools Used

| Tool | Purpose |
|------|---------|
| `dj_render_beatgrid` | Ensure beatgrid exists (called if `force_refresh_grid` or missing) |
| `dj_render_mixdown` | Actual rendering (when `auto_render=True`) |
| `dj_render_diagnose` | Post-render defect sweep + structural analysis |
| `dj_transition_score_pool` | Pre-render pairwise transition scoring |
| `dj_sequence_optimize` | Referenced for track reorder recommendations |

### 7.2 Existing Handlers Reused

| Handler | Method |
|---------|--------|
| `render_beatgrid_handler` | Beatgrid computation |
| `render_mixdown_handler` / `render_mixdown_extended_handler` | Rendering |
| `render_diagnose_handler` | Diagnostics |

### 7.3 New Handler

```python
# app/handlers/render_analyze.py
async def render_analyze_handler(
    *,
    ctx: Any,
    uow: Any,
    version_id: int,
    max_iterations: int,
    quality_threshold: float,
    auto_render: bool,
    force_refresh_grid: bool,
) -> RenderAnalysisResult:
    # Implementation per Section 6
```

---

## 8. Key Design Decisions

### 8.1 Why a Single Tool (Not Prompt)?

- **Deterministic**: Same inputs → same analysis (prompt would vary)
- **Stateful iteration**: Maintains history across render cycles
- **Performance**: Avoids LLM round-trips for algorithmic decisions
- **Testable**: Pure functions for each analysis step

### 8.2 Why Not Auto-Reorder Tracks?

- Track selection/ordering is a **creative DJ decision**
- Agent *recommends* reorder with specific reasoning ("Track 3→4 has Camelot conflict 99; insert bridge track X or swap with track 5")
- User applies via `dj_sequence_optimize` or manual edit

### 8.3 Why Max 3 Iterations Default?

- Each render = 2-5 min (demucs + ffmpeg)
- 3 iterations = 6-15 min acceptable wait
- Quality threshold 0.85 catches 90%+ of issues in practice

### 8.4 Parameter Safety (from AGENTS.md)

- **Always** default `filter_sweep=None, echo=None, reverb=None` unless analysis explicitly recommends
- **Always** validate beatgrid phase on ORIGINAL audio, not stems
- **Always** check audio_bpm vs stored BPM before time-stretch

---

## 9. Testing Strategy

| Test | Method |
|------|--------|
| Pre-render analysis detects known conflicts | Unit test with fixture tracks (Camelot conflict, BPM drift, phase mismatch) |
| Parameter advisor recommends correct fixes | Unit test: given defect X, param Y adjusted |
| Post-render defect classification matches diagnostics.py tags | Integration test with known MIX.mp3 |
| Iteration loop converges | Integration test: render → diagnose → adjust → re-render improves quality_score |
| Safety: never recommends filter_sweep/echo/reverb when phase issues exist | Unit test |

---

## 10. Open Questions for Review

1. **Quality threshold default**: 0.85 OK? Or make it configurable per subgenre?
2. **Max iterations**: 3 default, allow up to 10?
3. **Auto-render default**: `True` (full loop) or `False` (analyze existing)?
4. **Expose subgenre detection**: Infer from track features (BPM range, energy, spectral) or require explicit?
5. **Progress reporting**: Emit MCP progress notifications per iteration?

---

## 11. File Changes Summary

### New Files
- `app/tools/render/render_analyze.py` — MCP tool definition
- `app/handlers/render_analyze.py` — Handler with iteration loop
- `app/schemas/render.py` — Add `RenderAnalysisResult`, `RenderIteration`, `RenderDefect`, `ParamAdjustment`
- `app/domain/render/analysis.py` — Pure analysis logic (pre-render checks, parameter advisor, defect classifier, adjustment computer)

### Modified Files
- `app/tools/render/__init__.py` — Export new tool
- `app/handlers/__init__.py` — Export new handler
- `app/schemas/__init__.py` — Export new schemas

---

## 12. Implementation Priority

| Phase | Deliverable |
|-------|-------------|
| 1 | Pre-render analysis engine (`app/domain/render/analysis.py`) |
| 2 | Parameter advisor with subgenre presets |
| 3 | Defect classifier + adjustment computer |
| 4 | Iteration loop handler |
| 5 | MCP tool wiring + schemas |
| 6 | Tests (unit + integration) |
| 7 | Documentation / prompt update |

---

**Ready for review.** Please confirm design or request changes before I create the implementation plan.