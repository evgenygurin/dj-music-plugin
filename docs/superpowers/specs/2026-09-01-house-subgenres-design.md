# House Subgenres Render Presets — Design

**Date:** 2026-09-01  
**Status:** Draft → Approved (approach A)  
**Related:** `app/domain/performance/subgenre_presets.py`, `app/config/render.py`, `app/handlers/_orchestrator/preset_applier.py`, `reference://subgenres`

## 1. Context

Current project has 7 techno presets (industrial, dub, hard, hypnotic, peak, driving, acid) with `transition_bars/body_bars` 8-64 and aggressive DSP (`pre_comp -22dB`, `xsplit 350Hz`). House `129-132 BPM` sessions (e.g., `House last summer set` 10 tracks, LUFS max) rendered with `hypnotic_techno` produce `MUFFLED`, `PHASE-UNSTABLE`, `DROPOUT -39dB` (v236 diagnose 44/204). User requires proper House construction: 4 subgenres (Deep, Tech, Progressive, Classic Vocal), single bassline continuity, correct phrasing.

## 2. Goals / Non-Goals

- **Goals:** Add 4 House presets that correctly differ by BPM/energy/transition/body/EQ/comp as per House theory (deep 118-124 warm, tech 122-128 stripped, progressive 122-128 cinematic, classic 120-126 vocal). Reuse existing `SubgenreRenderPreset` + `RenderSettings` pipeline (approach A, YAGNI). Ensure `v236` 7B-only single-bassline House set validates 6/7 ok.
- **Non-Goals:** New HouseRenderPreset hierarchy (B), config-driven JSON (C), stem-level vocal ducking engine, key-lock pitch beyond `target_bpm` stretch.

## 3. Architecture

```
MoodClassifier(Suno/Yandex mood) → SubgenreRenderPreset → RenderSettings (mutate) → BarPlanner (transition/body) → RenderPlanner (EQ/Xsplit) → RenderExecutor (ffmpeg)
         │
         └─ resolve_preset("deep_house") → DEEP_HOUSE
```

- Extend `app/domain/performance/subgenre_presets.py:239 PRESET_MAP` with 4 entries.
- Extend `app/config/render.py:40-53` with 8 new `Field` pairs (`transition_bars_deep_house`, etc.) for env override, but presets hard-code defaults; env is optional.
- `preset_applier.py:13` unchanged — `resolve_preset` already lowercases & normalizes `_techno` suffix; add handling for `_house` suffix.
- `reference://subgenres` updated to document House presets alongside techno.

## 4. Components

### 4.1 Preset Values (from S1/S2/S3 synthesis)

| Preset | transition | body | xsplit_low/high | eq_phase_1/2 | low_swap | hpf | pre_comp thr/ratio | glue thr/ratio | air/mud/sub | limiter ceil/atk/rel | Outro | Rationale |
|--------|------------|------|-----------------|--------------|----------|-----|--------------------|----------------|-------------|----------------------|-------|-----------|
| DEEP_HOUSE | 32 | 48 | 200/3500 | 0.50/0.80 | 2.0 | 25 | -14/2.0 | -12/2.0 | 0.5/0.0/1.5 | 0.88/15/50 | 16 | Long blend 32 bars (59s@122), warm sub boost, gentle comp, preserve 140-250Hz Rhodes |
| TECH_HOUSE | 16 | 32 | 280/4500 | 0.30/0.60 | 0.5 | 35 | -18/3.5 | -15/3.5 | 2.0/-1.5/0.75 | 0.82/8/25 | 8 | Short 16-bar punch, tight low_swap 0.5b, aggressive comp for stripped riff |
| PROGRESSIVE_HOUSE | 32 | 56 | 250/4000 | 0.40/0.70 | 1.5 | 28 | -16/2.5 | -13/2.5 | 1.0/-0.5/1.0 | 0.85/12/40 | 16 | Long body 56 (103s) for cinematic arcs, hypnotic-like but less mud |
| CLASSIC_HOUSE | 16 | 32 | 250/3800 | 0.35/0.65 | 1.0 | 30 | -16/2.5 | -13/2.5 | 1.0/0.0/1.0 | 0.85/12/35 | 12 | Vocal-centric, mid_cut 0 to keep 140-250Hz, key-lock aware |

All values within `RenderSettings` field constraints; `apply()` in `subgenre_presets.py:51` iterates `__slots__`.

### 4.2 Single-Bassline Mode

For user request "one bassline whole set": `manual_house_render.py` will override `stem_paths[tid][bass] = honey_bass.flac` for all `tid` after `StemResolver.resolve`. This reuses Demucs `bass.flac` from loudest track (Honey 29940 LUFS -10.78). No code change in resolver, just orchestration wrapper. Documented as `single_bass_source` param in future `RenderRequest`.

### 4.3 House Phrasing

- Bar planning: `BarPlanner.compute` with `transition_override/body_override` from preset (16/32 beats = 8/16 bars). House requires `phrase_align` on `16 beats` boundaries (kick-to-kick). Existing `phrase_align_count` used, no change.
- Harmonic: Camelot `8A→8A / ±1 / A↔B` per S2; validation via `dj_transition_score_pool` already checks `harmonics` 0.58→0.84. Keep `camelot_mode soft` for House (vocal tolerance).

## 5. Data Flow

1. User calls `dj_render_mixdown(version_id=236, subgenre="deep_house")`
2. `preset_applier.apply` → `resolve_preset("deep_house")` → `DEEP_HOUSE.apply(settings)` → `transition_bars=32 body_bars=48`
3. `BarPlanner` → `bar_plan` → `RenderPlanner` → `plan` with `xsplit 200Hz`, `eq_phase 0.5`
4. `StemResolver` → `stem_paths` → (optional) `single_bass` override → `RenderExecutor.execute` → `ffmpeg`
5. `diagnose` scans `MIX.mp3` for `DROPOUT/LEVEL-JUMP/PHASE` as in v236 37/172.

Error handling: `resolve_preset` returns `None` → `preset_applier` returns `False` → fallback to `RenderSettings` defaults (48/40). No exception. Invalid `subgenre` string → same fallback.

## 6. Testing

- Unit: `test_subgenre_presets.py` — verify 4 new presets resolve, `apply` mutates `RenderSettings` correctly, `transition/body` within 8-64, `limiter_ceiling` 0.75-0.88.
- Integration: render `v236` 7B-only with each preset, `validate_grid` 6/7 ok, `diagnose` flagged <35/172, `quality_score >0.84`.
- Manual: House set `v237` (Cigarette→Nerepla) with `tech_house 16/32` should show `Rave` clean (2 flags), `Players→Nerepla` no `DROPOUT -39dB`.

## 7. Rollout

- No migration; add fields to `RenderSettings` with defaults `None` so env not required.
- Update `CHANGELOG.md` + `reference://subgenres`.
- Keep `HYPNOTIC` for techno, deprecate using it for House in docs.

## 8. Risks

- Disk 98% + `asyncio.to_thread` fix (`stem_resolver.py:78`) needed for 7-track Demucs; without, 280s block hangs MCP (as in v235). Mitigated by `to_thread` patch already applied.
- All-7B mono-key risks `flatness_std 0.006` → add `mfcc_diversity` check in `curate-library`.

## 9. Alternatives Considered

- B: Separate `HouseRenderPreset` — rejected YAGNI, duplicates 80%.
- C: JSON-driven — rejected overhead, preset count small.
