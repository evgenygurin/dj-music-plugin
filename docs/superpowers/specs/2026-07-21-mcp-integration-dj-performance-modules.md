# Spec: MCP Integration of DJ Performance Modules

**Date:** 2026-07-21
**Status:** draft
**Scope:** Connect 14 new audio/domain modules as MCP tools, extend render_mixdown

---

## 1. Summary

We built 14 new modules (`app/audio/effects/`, `app/domain/performance/`, additions to `app/domain/render/`) providing filter sweeps, echo, reverb, subgenre presets, energy arc planning, cue point detection, Camelot key analysis, multi-deck layering, stem matrices, automation curves, and auto-fix diagnostics. None are exposed as MCP tools yet.

This spec covers: (a) extending `render_mixdown` with 8 new parameters, (b) creating 11 new MCP tools across 4 namespaces, (c) extending `unlock_namespace` with 2 new namespaces, (d) writing Pydantic response schemas, (e) wiring handlers.

---

## 2. Namespaces & Registration

### 2.1 New namespaces in `unlock_namespace.py`

| Namespace | Tag | Locked by default? |
|-----------|-----|-------------------|
| `render:config` | `namespace:render:config` | **no** — read-only builders |
| `render:effects` | `namespace:render:effects` | **no** — read-only builders |
| `render:diagnostics` | `namespace:render:diagnostics` | **yes** — destructive (ffmpeg) |
| `performance` | `namespace:performance` | **yes** — future write ops |

Changes to `app/tools/admin/unlock_namespace.py`:
- Add `"render:diagnostics"`, `"performance"` to `NAMESPACES` frozenset
- Add corresponding entries in `NAMESPACE_TAGS` dict
- Update the `Literal[...]` type annotation on the `namespace` parameter

### 2.2 File layout

```
app/tools/render/
  render_mixdown.py          ← extended (new params)
  subgenre_preset.py         ← NEW
  energy_arc_plan.py         ← NEW
  filter_sweep_builder.py    ← NEW
  echo_builder.py            ← NEW
  reverb_builder.py          ← NEW
  auto_fix.py                ← NEW

app/tools/performance/
  __init__.py                ← NEW
  cue_points.py              ← NEW
  transition_window.py       ← NEW
  key_compatibility.py       ← NEW
  multi_deck_plan.py         ← NEW
  stem_matrix.py             ← NEW

app/schemas/
  subgenre_preset.py         ← NEW (SubgenrePresetResult)
  energy_arc.py              ← NEW (EnergyArcResult)
  filter_sweep.py            ← NEW (FilterSweepResult)
  echo_delay.py              ← NEW (EchoResult)
  reverb.py                  ← NEW (ReverbResult)
  auto_fix.py                ← NEW (AutoFixResult)
  cue_points.py              ← NEW (CuePointsResult)
  transition_window.py       ← NEW (TransitionWindowResult)
  key_compatibility.py       ← NEW (KeyCompatibilityResult)
  multi_deck.py              ← NEW (MultiDeckPlanResult)
  stem_matrix.py             ← NEW (StemMatrixResult)
```

Schema module naming: `<schema>.py` under `app/schemas/`. Each exports a Pydantic `BaseModel` named `<Whatever>Result`.

### 2.3 Tool registration pattern

All new tools follow the existing FastMCP pattern:

```python
@tool(
    name="tool_name",
    tags={"namespace:<ns>", ...},
    annotations={"readOnlyHint": bool, "idempotentHint": bool, "openWorldHint": bool},
    description="...",
    meta={"timeout_s": float},
    timeout=float,
    task=bool,  # True for heavy/ffmpeg tools
)
async def tool_name(
    ...params...,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> ResultSchema:
    ...
```

---

## 3. Extended `render_mixdown`

### 3.1 New parameters

Add to the existing `render_mixdown` tool signature (keeping all existing params):

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `subgenre` | `str \| None` | `None` | Subgenre preset name: "industrial_techno", "dub_techno", etc. |
| `filter_sweep` | `str \| None` | `None` | Preset: "classic_lowpass", "acid_squelch", "industrial_cut", "hypnotic_wash", "dub_echo_sweep" |
| `echo` | `str \| None` | `None` | Preset: "techno_standard", "vocal_throw", "industrial_stutter", "dub_space", "acid_bounce" |
| `crossfade_curve_out` | `str` | `"tri"` | acrossfade curve for outgoing: "tri", "exp", "log", "squ", "sin", "nofade" |
| `crossfade_curve_in` | `str` | `"exp"` | acrossfade curve for incoming |
| `reverb` | `str \| None` | `None` | Preset: "techno_hall", "techno_cathedral", "industrial_warehouse", "dub_plate", "minimal_room" |
| `reverb_mix` | `float` | `0.25` | Wet/dry ratio 0.0–1.0 |

### 3.2 Handler integration points

**Subgenre preset** → `_config_bar_override()`:
Before `build_render_plan()`, if `subgenre` is set:
`SubgenreRenderPreset.resolve(subgenre).apply(settings)` — overrides EQ, compression, limiter.

**Filter sweep** → `_enrich_transitions()` → `SegmentGeometry`:
New field `filter_sweep: FilterSweepPlan | None` on `SegmentGeometry`.
Builder: `FILTER_PRESETS[filter_sweep]` → `FilterSweepPlan`.
ffmpeg: `lowpass=f=14000:enable='between(t,T_out,T_out+8)'` + `asendcmd` for frequency sweep.

**Echo** → same pattern:
New field `echo: EchoPlan | None` on `SegmentGeometry`.
ffmpeg: `asplit` → `atrim` → `aecho` → `amix` back into the outgoing track's tail.

**Crossfade curves** → `acrossfade`:
Replace manual volume automation between two tracks with native `acrossfade=d=D:c1=curve_out:c2=curve_in`.

**Reverb** → master chain:
Generate IR via `ReverbIR.generate_ir()`, save as temporary WAV.
ffmpeg: `[master]asplit[master_dry][master_wet]; [master_wet][ir]afftfilt=real=ir:win_size=4096[wet]; [master_dry][wet]amix=inputs=2:weights=1-M M[out]`.

### 3.3 Backward compatibility

All new parameters have defaults that preserve existing behavior:
- `subgenre=None` → no preset applied (existing defaults)
- `filter_sweep=None` → no filter sweep
- `echo=None` → no echo
- `crossfade_curve_out="tri"` → triangle curve (smooth, neutral)
- `reverb=None` → no reverb

---

## 4. New Tools — `render:config` Namespace

### 4.1 `subgenre_preset`

**File:** `app/tools/render/subgenre_preset.py`
**Schema:** `app/schemas/subgenre_preset.py::SubgenrePresetResult`

Returns all 22 render parameters for a given subgenre. Purely informational — the client can read values before deciding which subgenre to pass to `render_mixdown`.

```
Input:  subgenre (Literal[...]) 
Output: {subgenre, transition_bars, body_bars, xsplit_low_hz, xsplit_high_hz,
         eq_phase_1_ratio, eq_phase_2_ratio, low_swap_beats, outro_fade_bars,
         hpf_cutoff_hz, per_track_eq_mid_cut_db, per_track_eq_bright_boost_db,
         pre_comp_threshold_db, pre_comp_ratio, glue_comp_threshold_db, glue_comp_ratio,
         master_eq_air_boost_db, master_eq_mud_cut_db, master_eq_sub_boost_db,
         limiter_ceiling, limiter_attack_ms, limiter_release_ms, dynaudnorm_maxgain}
```

Tags: `namespace:render:config`. Always visible. Timeout: 5s.

### 4.2 `energy_arc_plan`

**File:** `app/tools/render/energy_arc_plan.py`
**Schema:** `app/schemas/energy_arc.py::EnergyArcResult`

Generates an energy arc as an array of target slots. Each slot describes the ideal BPM and energy for a position in the set.

```
Input:  shape (Literal["roller","journey","warehouse","festival"]), num_tracks (int),
        bpm_start (float), bpm_peak (float), bpm_end (float)
Output: {shape, num_tracks, slots: [{position, target_bpm, target_energy, label}]}
```

Tags: `namespace:render:config`. Always visible. Timeout: 5s.

---

## 5. New Tools — `render:effects` Namespace

Three constructors. Each accepts EITHER a preset name OR custom parameters (mutually exclusive via `preset=None`). Returns both human-readable parameters and ffmpeg-ready expression.

### 5.1 `filter_sweep_builder`

**File:** `app/tools/render/filter_sweep_builder.py`
**Schema:** `app/schemas/filter_sweep.py::FilterSweepResult`

```
Input:  preset (Literal[...] | None), OR custom: start_freq_hz, end_freq_hz,
        direction, curve, resonance
Output: {preset_name, outgoing: {start_freq_hz, end_freq_hz, curve, resonance, ffmpeg_expr},
         incoming: {...}}
```

Tags: `namespace:render:effects`. Always visible. Timeout: 5s.

### 5.2 `echo_builder`

**File:** `app/tools/render/echo_builder.py`
**Schema:** `app/schemas/echo_delay.py::EchoResult`

```
Input:  preset (Literal[...] | None), OR custom: delay_ms, decay, taps, wet_dry, stereo_spread
Output: {preset_name, delay_ms, decay, taps, wet_dry_ratio, stereo_spread,
         ffmpeg_aecho_expr, ffmpeg_filter_chain}
```

Tags: `namespace:render:effects`. Always visible. Timeout: 5s.

### 5.3 `reverb_builder`

**File:** `app/tools/render/reverb_builder.py`
**Schema:** `app/schemas/reverb.py::ReverbResult`

```
Input:  preset (Literal[...] | None), OR custom: decay_s, pre_delay_ms, mix_ratio, space
Output: {preset_name, decay_s, pre_delay_ms, mix_ratio, space,
         sample_rate, total_samples, highpass_hz, lowpass_hz}
```

Tags: `namespace:render:effects`. Always visible. Timeout: 10s. Calls `ReverbIR.generate_ir()` to compute total_samples.

---

## 6. New Tools — `render:diagnostics` Namespace

### 6.1 `auto_fix`

**File:** `app/tools/render/auto_fix.py`
**Schema:** `app/schemas/auto_fix.py::AutoFixResult`

Analyzes render diagnostics defects and proposes/generates ffmpeg fix chain.

```
Input:  version_id (int), mix_path (str|None), dry_run (bool=True)
Output (dry_run): {dry_run: true, defects_found: N,
                    fixes: [{type, at_s, action}], fixed_path: null}
Output (apply):   {dry_run: false, fixed_path: "generated-sets/render/vXX/MIX_fixed.mp3"}
```

If `dry_run=False`: saves IR WAV to workspace, runs ffmpeg, writes output.

Tags: `namespace:render:diagnostics`, `write`. Hidden (requires unlock). Timeout: 600s. Task: true.

---

## 7. New Tools — `performance` Namespace

### 7.1 `cue_points`

**File:** `app/tools/performance/cue_points.py`
**Schema:** `app/schemas/cue_points.py::CuePointsResult`

Auto-detects 8 hot cues (A–H) from track section data.

```
Input:  track_id (int)
Output: {track_id, bpm, cues: [{index, cue_type, position_ms, label, color}]}
```

Logic: reads `track_sections` via `uow.track_sections.list_by_track(track_id)` → `detect_cues(sections, bpm, first_downbeat_ms, duration_ms)`.

Tags: `namespace:performance`. Hidden. Timeout: 5s.

### 7.2 `transition_window`

**File:** `app/tools/performance/transition_window.py`
**Schema:** `app/schemas/transition_window.py::TransitionWindowResult`

Finds optimal mix-out/mix-in windows between two tracks based on their detected structure.

```
Input:  from_track_id (int), to_track_id (int), bpm (float|None), preferred_bars (int=32)
Output: {from_track_id, to_track_id,
         mix_out_start_ms, mix_out_end_ms, mix_in_start_ms, mix_in_end_ms,
         recommendation (str)}
```

Tags: `namespace:performance`. Hidden. Timeout: 5s.

### 7.3 `key_compatibility`

**File:** `app/tools/performance/key_compatibility.py`
**Schema:** `app/schemas/key_compatibility.py::KeyCompatibilityResult`

Camelot wheel compatibility with subgenre-aware weighting.

```
Input:  from_key (int 0–23), to_key (int 0–23), subgenre (str|None)
Output: {from_key, to_key, from_camelot, to_camelot,
         distance, relation, compatibility_score, description}
```

Tags: `namespace:performance`. Hidden. Timeout: 5s.

### 7.4 `multi_deck_plan`

**File:** `app/tools/performance/multi_deck_plan.py`
**Schema:** `app/schemas/multi_deck.py::MultiDeckPlanResult`

Generates a multi-deck render plan with deck assignments and time windows.

```
Input:  track_order (list[int]), stem_mode (bool=False), max_simultaneous (int=6)
Output: {max_simultaneous, target_bpm, windows: [{start_s, end_s, decks: [
           {deck_index, track_id, active_stems, gain_db, lowpass_hz, highpass_hz}
         ]}], ffmpeg_amix_graph (str)}
```

Tags: `namespace:performance`. Hidden. Timeout: 10s.

### 7.5 `stem_matrix`

**File:** `app/tools/performance/stem_matrix.py`
**Schema:** `app/schemas/stem_matrix.py::StemMatrixResult`

Generates 12-deck stem activation matrix over the set timeline.

```
Input:  track_order (list[int]), target_bpm (float=130),
        transition_bars (int=32), body_bars (int=32)
Output: {total_duration_s, frame_count, target_bpm,
         frames: [{time_s, active_decks: [{deck_index, stem_type, track_id}],
                   fade_outs: N, fade_ins: N}]}
```

Requires stem files on disk (reads `DjLibraryItem.file_path` for each track). Falls back to `["instrumental"]` if demucs stems not available.

Tags: `namespace:performance`. Hidden. Timeout: 15s.

---

## 8. Response Schemas

All use Pydantic `BaseModel` with `model_config = ConfigDict(frozen=True)`. Naming: `XxxResult` pattern matching existing `RenderMixdownResult`, `EntityCreateResult`, etc.

Location: `app/schemas/<module_name>.py`. Each schema file is self-contained (single schema per file, matching existing convention).

---

## 9. Error Handling

- **Invalid preset name:** `ValidationError` with list of valid presets
- **Missing audio files:** `ValidationError("no audio file registered for track X")`
- **Missing track sections:** return empty/default result, no error (graceful degradation)
- **ffmpeg failure (auto_fix):** propagate the `RuntimeError` with ffmpeg stderr
- **Custom params without preset:** validate all required custom params are set

---

## 10. Testing

- **Unit:** each domain/audio module already has pure-function logic — test via existing test patterns in `tests/domain/` and `tests/audio/`
- **Integration:** invoke new tools via `build_mcp_server() + Client()` pattern (same as `tests/tools/conftest.py`)
- **Smoke:** `scripts/smoke_test_all_tools.py` — extend to cover new tool names
- **No new test dependencies:** reuse existing test fixtures (mock_uow, etc.)

---

## 11. Dependencies

- All 14 modules already exist and import correctly
- No new pip packages needed
- Requires `app/audio/core/loader.py` M4A fix (already applied in this session)
- ffmpeg with `--enable-librubberband` (already used by existing render pipeline)

---

## 12. Non-Goals (out of scope)

- Real-time MIDI/OSC control
- GUI preview
- Ableton Live Set export
- Stems.mp4 container format
- Variable tempo render
- Migration of existing `transition_scorer` to use `key_compatibility`
- **Echo/reverb tail blending** — the `echo` and `reverb` presets apply their effects during the transition window only (the tail overlaps naturally within the existing crossfade). Extending transition overlap to accommodate a full decay tail requires re-architecting `_segment_sequence` and is deferred.
- **`automation_curve` tool** — the `AutomationCurve` module remains internal-only, used by the render engine to generate filter-sweep frequency curves. A standalone MCP tool for arbitrary automation curve design is deferred.
