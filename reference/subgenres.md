# Subgenre Render Presets

> 11 distinct presets (7 techno + 4 house; 18 entries in `PRESET_MAP` with aliases: 14 techno incl. aliases +4 house). House presets use single-bassline 7B phrasing (16-beat boundaries) via `SubgenreRenderPreset` → `RenderSettings` → `BarPlanner`/`RenderPlanner`.

## Preset Table (transition_bars / body_bars)

| Preset | transition | body | xsplit_low/high | eq_phase_1/2 | low_swap | hpf | pre_comp thr/ratio | glue thr/ratio | air/mud/sub | limiter ceil/atk/rel | Outro | Rationale |
|--------|------------|------|-----------------|--------------|----------|-----|--------------------|----------------|-------------|----------------------|-------|-----------|
| industrial_techno | 16 | 48 | 300/5000 | 0.25/0.50 | 0.5 | 35 | -15/3.0 | -12/2.5 | 1.5/-1.5/0.75 | 0.85/8/25 | 8 | Aggressive 16-bar swap, tight bass |
| dub_techno | 64 | 32 | 200/3500 | 0.60/0.85 | 2.0 | 25 | -14/2.0 | -12/2.0 | 0.5/0.0/1.5 | 0.88/15/50 | 24 | Hypnotic 64-bar fade, warm sub |
| hard_techno | 8 | 64 | 350/5500 | 0.20/0.40 | 0.25 | 40 | -22/5.0 | -18/5.0 | 2.5/-2.5/1.5 | 0.75/4/15 | 4 | Punishing 8-bar cut, max body |
| hypnotic_techno | 48 | 40 | 220/3800 | 0.55/0.80 | 2.0 | 28 | -16/2.5 | -13/2.5 | 1.0/-0.5/1.0 | 0.85/12/40 | 16 | Rolling 48-bar blend *(deprecated for House — use house presets below)* |
| peak_time_techno | 32 | 32 | 260/4200 | 0.40/0.70 | 1.0 | 30 | -18/3.0 | -14/3.0 | 1.5/-1.0/0.5 | 0.85/10/30 | 12 | Balanced peak |
| driving_techno | 24 | 40 | 280/4500 | 0.35/0.65 | 0.75 | 32 | -19/3.5 | -15/3.5 | 2.0/-1.5/0.75 | 0.82/8/25 | 10 | Rolling drive |
| acid_techno | 16 | 56 | 270/5000 | 0.30/0.55 | 0.5 | 35 | -20/4.0 | -16/4.0 | 2.5/-2.0/1.0 | 0.80/5/20 | 8 | 303 mid-forward |
| deep_house | 32 | 48 | 200/3500 | 0.50/0.80 | 2.0 | 25 | -14/2.0 | -12/2.0 | 0.5/0.0/1.5 | 0.88/15/50 | 16 | Long blend 32 bars (59s@122), warm sub, gentle comp |
| tech_house | 16 | 32 | 280/4500 | 0.30/0.60 | 0.5 | 35 | -18/3.5 | -15/3.5 | 2.0/-1.5/0.75 | 0.82/8/25 | 8 | Short 16-bar punch, tight 0.5b swap |
| progressive_house | 32 | 56 | 250/4000 | 0.40/0.70 | 1.5 | 28 | -16/2.5 | -13/2.5 | 1.0/-0.5/1.0 | 0.85/12/40 | 16 | Long body 56 (103s) cinematic arcs |
| classic_house | 16 | 32 | 250/3800 | 0.35/0.65 | 1.0 | 30 | -16/2.5 | -13/2.5 | 1.0/0.0/1.0 | 0.85/12/35 | 12 | Vocal-centric, mid_cut 0 |

All values within `RenderSettings` constraints: transition/body 8-64, limiter 0.75-0.88, xsplit 200-5500. Env overrides `DJ_RENDER_TRANSITION_BARS_<SUBGENRE>` / `DJ_RENDER_BODY_BARS_<SUBGENRE>` (8 fields for house).

## House Phrasing

- `BarPlanner.compute` with 16-beat phrase_align (kick-to-kick), `BarPlanner` clamped bodies for short sources (e.g. deep_house v237: 48,27,48,48,28,48,48 avg 42.1 → 899s).
- Harmonic: `camelot_mode soft` for vocal tolerance, single-bassline via `manual_house_render.py` override (future `single_bass_source`).

## Deprecation

`hypnotic_techno` is deprecated for House — use `deep_house`/`tech_house`/`progressive_house`/`classic_house` instead. Kept for techno only.

Source: `app/domain/performance/subgenre_presets.py` (`SubgenreRenderPreset`, `PRESET_MAP` 18 entries with aliases / 11 distinct, `resolve_preset` with `_house` suffix, `BarPlanner` house env fallback `DJ_RENDER_*_DEEP_HOUSE` etc.).
