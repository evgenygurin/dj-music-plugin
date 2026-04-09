# Techno Transition Matrix (15 Subgenres × 8 Set Templates)

> Date: 2026-04-09  
> Scope: runtime-aligned transition policy for `dj-music-plugin`  
> Related: `docs/research/2026-04-08-techno-transitions-research.md`, `docs/transition-scoring.md`

## 1. Goal

This document converts deep transition research into an operational matrix for this codebase:

- 15 techno subgenres (`TechnoSubgenre`)
- 8 set templates (`SetTemplate`)
- phase-level transition rules for BPM / energy / harmonic strictness
- recommended transition styles (`TransitionStyle`)
- implementation mapping: implemented vs partial vs missing

## 2. Policy Notation

### 2.1 Phase Codes (used in the 15×8 matrix)

- `W`: warm-up
- `B`: build
- `P`: peak
- `R`: release
- `C`: contrast/bridge
- `A`: avoid except forced fallback

### 2.2 Runtime Transition Windows by Phase

| Phase | BPM Window | Energy Window (ΔLUFS) | Harmonic Policy | Preferred Styles |
|---|---|---|---|---|
| `W` | `±2` | `<= 1.5` | strict (`same/adjacent`) | `BASS_SWAP_LONG`, `LONG_BLEND` |
| `B` | `±3` | `<= 2.0` | strict-moderate | `BASS_SWAP_LONG`, `BASS_SWAP_SHORT` |
| `P` | `±4` | `<= 2.5` | moderate-relaxed | `BASS_SWAP_SHORT`, `CUT`, `FILTER_SWEEP` |
| `R` | `±3` | `<= 2.0` down-bias | strict | `LONG_BLEND`, `ECHO_OUT` |
| `C` | `±5` | `<= 3.0` | relaxed (drum-only aware) | `FILTER_SWEEP`, `ECHO_OUT`, `CUT` |
| `A` | n/a | n/a | n/a | only as emergency fallback |

Notes:
- Hard constraints remain runtime gatekeepers (`BPM>10`, `Camelot>=5`, `Energy gap>6`).
- Drum-only intro/outro pairs use section-aware harmonic relaxation from `SectionContext`.

## 3. Subgenre Baseline Profiles

| Subgenre | Typical BPM | Typical LUFS Band | Harmonic Strictness | Default Transition Styles |
|---|---:|---:|---|---|
| ambient_dub | 120-125 | -16..-12 | high | `LONG_BLEND`, `BASS_SWAP_LONG` |
| dub_techno | 122-128 | -14..-11 | high | `LONG_BLEND`, `BASS_SWAP_LONG` |
| minimal | 125-130 | -12..-9 | high | `BASS_SWAP_LONG`, `LONG_BLEND` |
| detroit | 125-132 | -11..-8 | medium-high | `BASS_SWAP_LONG`, `BASS_SWAP_SHORT` |
| melodic_deep | 122-128 | -12..-9 | high | `LONG_BLEND`, `BASS_SWAP_LONG` |
| progressive | 126-132 | -11..-8 | medium-high | `BASS_SWAP_LONG`, `BASS_SWAP_SHORT` |
| hypnotic | 128-134 | -10..-7 | medium | `BASS_SWAP_LONG`, `BASS_SWAP_SHORT` |
| driving | 128-135 | -9..-7 | medium | `BASS_SWAP_SHORT`, `BASS_SWAP_LONG` |
| tribal | 126-133 | -9..-7 | medium | `BASS_SWAP_SHORT`, `FILTER_SWEEP` |
| breakbeat | 130-140 | -9..-6 | medium-relaxed | `FILTER_SWEEP`, `CUT` |
| peak_time | 130-138 | -8..-6 | medium | `BASS_SWAP_SHORT`, `CUT` |
| acid | 132-140 | -8..-6 | medium-relaxed | `BASS_SWAP_SHORT`, `FILTER_SWEEP` |
| raw | 135-145 | -7..-5 | relaxed | `CUT`, `FILTER_SWEEP` |
| industrial | 138-150 | -7..-5 | relaxed | `FILTER_SWEEP`, `CUT` |
| hard_techno | 140-155 | -6..-4 | relaxed | `CUT`, `FILTER_SWEEP` |

## 4. 15×8 Template Matrix

Template columns:

- `W30` = `warm_up_30`
- `C60` = `classic_60`
- `P60` = `peak_hour_60`
- `R90` = `roller_90`
- `P120` = `progressive_120`
- `W120` = `wave_120`
- `CL60` = `closing_60`
- `FL` = `full_library`

| Subgenre | W30 | C60 | P60 | R90 | P120 | W120 | CL60 | FL |
|---|---|---|---|---|---|---|---|---|
| ambient_dub | W | A | A | A | W | C | R | C |
| dub_techno | W | W | A | A | W | R | R | C |
| minimal | B | W | A | B | W | W | R | C |
| detroit | C | B | A | C | B | B | C | C |
| melodic_deep | B | B | A | C | B | R | R | C |
| progressive | C | B | A | C | B | B | R | C |
| hypnotic | A | R | B | R | C | B | B | C |
| driving | A | P | W | P | P | P | W | C |
| tribal | A | P | B | P | P | P | C | C |
| breakbeat | A | C | P | C | C | C | A | C |
| peak_time | A | P | P | P | P | P | A | C |
| acid | A | C | P | P | C | P | A | C |
| raw | A | A | P | C | C | C | A | C |
| industrial | A | A | P | C | C | C | A | C |
| hard_techno | A | A | P | C | C | C | A | C |

### 4.1 How to read matrix cells

Example:

- `industrial` × `P60` = `P`  
  Use peak-phase policy (`±4 BPM`, `ΔLUFS<=2.5`, relaxed harmonic, styles: `BASS_SWAP_SHORT`/`CUT`/`FILTER_SWEEP`).
- `ambient_dub` × `CL60` = `R`  
  Use release policy (`±3 BPM`, down-energy preference, strict harmonic, styles: `LONG_BLEND`/`ECHO_OUT`).

## 5. Mapping to Current Code

| Area | Modules | Status | Notes |
|---|---|---|---|
| Core 6-component scoring | `app/transition/scorer.py`, `components/*`, `weights.py` | Implemented | production path |
| Section-aware harmonic relax | `app/transition/section_context.py`, `score_harmonic`, `DRUM_ONLY_WEIGHT_OVERRIDE` | Implemented | scorer supports `SectionContext` |
| Template-aware intent model | `app/transition/intent.py` | Implemented | per-template phase boundaries already present |
| Mood/subgenre classification | `app/audio/classification/*`, `app/services/curation/mood.py` | Implemented | 15 profiles in code |
| Template catalog | `app/templates/registry.py` | Implemented | 8 templates |
| Template/mood into optimization runtime | `app/services/set/builder.py` + optimizer wiring | Partial -> targeted by current implementation cycle | existed conceptually, now wired end-to-end |
| Section/mix-point into set transition scoring | `app/services/set/scoring.py`, `app/services/mix_point_service.py` | Partial -> targeted by current implementation cycle | fallback path required when context absent |
| Persisted transition candidates API | `app/services/set/scoring.py:get_transition_candidates` | Missing | still stub |

## 6. Runtime Gaps This Matrix Exposes

1. Template intent and mood policies must influence ordering path, not only docs/spec.
2. Section context must be consumed in set scoring loop when data exists.
3. Validation must compare baseline vs aligned behavior on key templates:
   - `peak_hour_60`
   - `roller_90`
   - `progressive_120`
   - `closing_60`

## 7. Fresh Sources Added in This Iteration

- Sowula et al., **Mosaikbox: Improving Fully Automatic DJ Mixing Through Rule-Based Stem Modification and Precise Beat-Grid Estimation** (ISMIR 2024): https://repositum.tuwien.at/handle/20.500.12708/212628
- Argüello et al., **Cue Point Estimation using Object Detection** (arXiv 2407.06823, 2024): https://arxiv.org/abs/2407.06823
- Zehren et al., **Automatic Detection of Cue Points for DJ Mixing** (CMJ 2022 / arXiv 2007.08411): https://arxiv.org/abs/2007.08411
- Bernardes et al., **A Hierarchical Harmonic Mixing Method** (2017): https://nyuscholars.nyu.edu/en/publications/a-hierarchical-harmonic-mixing-method

These are additive to the source base already captured in `2026-04-08-techno-transitions-research.md`.
