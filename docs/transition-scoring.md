# Transition Scoring

Stem-aware 6-component weighted formula for evaluating track-to-track transitions, paired with the seven djay Pro 5 Neural Mix presets and a context-aware picker that selects the right preset for each pair.

> Background: [docs/research/2026-04-08-techno-transitions-research.md](research/2026-04-08-techno-transitions-research.md)
> Architecture decision: [docs/superpowers/specs/2026-04-08-transition-system-redesign.md](superpowers/specs/2026-04-08-transition-system-redesign.md)
> Neural Mix paradigm (v1.3.0): [Algoriddim Neural Mix overview](https://help.algoriddim.com/user-manual/djay-pro-mac/neural-mix/overview)

## Module Layout

```text
app/domain/transition/
├── __init__.py            (public re-exports)
├── math_helpers.py        (bpm_distance, cosine_similarity, correlation)
├── weights.py             (DEFAULT_WEIGHTS + BPM/energy/Camelot constants)
├── score.py               (TransitionScore dataclass + best_transition)
├── hard_constraints.py    (check_hard_constraints — standalone gate)
├── components/
│   ├── bpm.py             (score_bpm — pure-numpy)
│   └── energy.py          (score_energy — pure-numpy)
├── neural_mix.py          (NeuralMixTransition × 7 + NeuralMixStem × 4
│                           + NeuralMixScorer + 4 stem-compat functions
│                           + TRANSITION_STEM_WEIGHTS / ENERGY_BIAS)
├── recipe.py              (NeuralMixRecipe + StemKeyframe + MuteFXEvent
│                           + MuteFXTrigger + JSON serialisation)
├── builders.py            (7 pure 32-bar builders, build_recipe dispatcher)
├── picker.py              (pick_neural_mix decision tree
│                           + build_recipe_for_pair convenience wrapper)
├── section_context.py     (SectionContext dataclass + is_drum_only_pair)
├── subgenre_rules.py      (classify_pair + clamp_bars)
├── intent.py              (TransitionIntent + per-template phase table)
└── scorer.py              (TransitionScorer orchestrator — ~120 lines)
```

`scorer.py` is a thin orchestrator: it calls `check_hard_constraints`, dispatches to `score_bpm` + `score_energy` + the four `NeuralMixScorer` stem compats, and combines them with weights. It contains zero domain math and zero magic numbers.

## Formula

```text
score = w_bpm * S_bpm + w_harmonic * S_harmonic + w_energy * S_energy
      + w_spectral * S_spectral + w_groove * S_groove + w_timbral * S_timbral
```

Public field names on `TransitionScore` map to the four Neural Mix stems internally:

| Public field | Conceptual stem | Source function |
|---|---|---|
| `bpm` | — | `components.bpm.score_bpm` |
| `harmonic` | HARMONICS | `neural_mix.score_harmonic_compat` |
| `energy` | — | `components.energy.score_energy` |
| `spectral` | BASS | `neural_mix.score_bass_compat` |
| `groove` | DRUMS | `neural_mix.score_drums_compat` |
| `timbral` | VOCALS | `neural_mix.score_vocal_compat` |

Default weights (`app/domain/transition/weights.py:DEFAULT_WEIGHTS`):

| Component | Weight | Stem | Purpose |
|-----------|--------|------|---------|
| BPM       | 0.20 | — | Tempo compatibility |
| Harmonic  | 0.15 | HARMONICS | Pads / leads / chord-progression compat |
| Energy    | 0.15 | — | LUFS energy-flow compatibility |
| Spectral  | 0.15 | BASS | Bass-stem compat (Camelot + bass band + BPM) |
| Groove    | 0.20 | DRUMS | Drum-stem compat (BPM + kick + onset + beat-loudness) |
| Timbral   | 0.15 | VOCALS | Vocal-stem compat (centroid + chroma + pitch-salience) |

Total = 1.00. Rebalance rationale: Kim et al. ISMIR 2020 found stem-level features to be the strongest empirical predictors of real DJ-set transitions; Algoriddim's djay Pro 5 reorganised its Automix UI around four-stem routing (Drums / Bass / Harmonic / Vocals). The slight uplift on `groove` reflects techno DJ practice — kick / onset alignment is the load-bearing scoring axis at peak time.

### Effective runtime weights (READ THIS) — intent overrides DEFAULT_WEIGHTS

`DEFAULT_WEIGHTS` above is the **no-intent** path only. **The set-build path
always sets an intent** (via `infer_intent`), so the live score uses
`app/domain/transition/intent.py:INTENT_WEIGHT_MODIFIERS`, which differ
sharply — during a build the kick lock is nearly zeroed and loudness-flow +
harmonics dominate:

| Intent | bpm | energy | drums | bass | harmonics | vocals |
|---|---|---|---|---|---|---|
| MAINTAIN | 0.28 | 0.15 | 0.14 | 0.15 | 0.18 | 0.10 |
| RAMP_UP | 0.20 | 0.30 | **0.05** | 0.10 | 0.25 | 0.10 |
| COOL_DOWN | 0.20 | 0.25 | 0.05 | 0.15 | 0.20 | 0.15 |
| CONTRAST | 0.15 | 0.18 | 0.15 | 0.20 | 0.12 | 0.20 |

Implication for set-building: order **build-phase** pairs for clean LUFS rises
and harmonic continuity — groove-tightness will NOT carry a RAMP_UP pair.

⚠️ **Two stale weight sources** (do not tune them — they change nothing):
`config/transition.py` `weight_bpm/harmonic/energy/spectral/groove/timbral`
are **not consumed** by any scorer and diverge from the live values; the
`CAMELOT_BASE_SCORES` / `CREST_DIFF_PENALTY_THRESHOLD=4.0` /
`LRA_DIFF_PENALTY_THRESHOLD=5.0` constants in `weights.py` are **reference-only**
— the live scorer hard-codes its own Camelot tables in `neural_mix.py` and
reads `settings.transition.scoring_{crest,lra}_diff_penalty_threshold`
(10.0 / 8.0) for the energy penalties. Full audit:
[docs/research/2026-06-23-track-feature-reference-and-set-construction.md](research/2026-06-23-track-feature-reference-and-set-construction.md).

## Hard Constraints

If ANY violated → `TransitionScore(hard_reject=True, overall=0.0, reject_reason=...)`. The gate is `app/domain/transition/hard_constraints.py:check_hard_constraints` (standalone function).

| Constraint | Threshold | Config |
|-----------|-----------|--------|
| BPM difference > N (with double/half-time awareness) | 10 BPM | `settings.transition_hard_reject_bpm_diff` |
| Camelot distance ≥ N | 5 | `settings.transition_hard_reject_camelot_dist` |
| Energy gap > N LUFS | 6.0 LUFS | `settings.transition_hard_reject_energy_gap` |

## Component Details

### S_bpm — Tempo Compatibility

Gaussian similarity with double/half-time awareness, plus penalties for unstable / variable tempo and low BPM detection confidence.

```text
delta = bpm_distance(bpm_a, bpm_b)         # min over direct, double, half
S_bpm = exp(-delta² / (2 * BPM_GAUSS_SIGMA²))
S_bpm *= max(BPM_STABILITY_FLOOR, min(stability_a, stability_b))
S_bpm *= confidence_factor                  # below scoring_bpm_confidence_floor
S_bpm -= scoring_variable_tempo_penalty     # if either side variable
```

`BPM_GAUSS_SIGMA = 10.0` (2026-04-20 calibration). Values:

| Δ BPM | S_bpm (pre stability/confidence) | Real-world meaning |
|---|---|---|
| 0 | 1.00 | Identical tempo |
| 2 | 0.98 | 32-bar blend safe |
| 3 | 0.96 | Sync-safe |
| 5 | 0.88 | Pioneer DJ default pitch-adjust |
| 8 | 0.73 | Forced but mixable |
| 10 | 0.61 | Hard-reject boundary (`settings.transition_hard_reject_bpm_diff`) |

Prior σ=3.0 produced 0.25 for Δ=5 BPM, punishing the normal sync workflow. All thresholds in `weights.py` and `settings`.

### S_harmonic — HARMONICS Stem Compatibility

Camelot wheel distance lookup (40 % weight), weighted by HNR quality, blended with Tonnetz cosine similarity (20 %), MFCC cosine (20 %), and spectral-contrast similarity (10 %). Dissonance penalty when both sides have `dissonance_mean > 0.4`. The drum-only relaxation floor was retired with the v1.3.0 picker — drum-only sections now route through DRUM_SWAP / DRUM_CUT / FADE directly instead of compensating in the score.

```text
base = CAMELOT_BASE_SCORES[dist]            # {0:1.0, 1:0.9, 2:0.6, 3:0.3, 4:0.1}
hnr_factor = normalize(avg_hnr, -30..0 → 0.5..1.0)
S_h = 0.40 * base * hnr_factor + 0.20 * tonnetz_cos + 0.20 * mfcc_cos
    + 0.10 * spectral_contrast_proximity
S_h -= DISSONANCE_PENALTY                   # if both sides dissonant
```

### S_energy — Energy Flow

Gauss around a preferred +0.5 LUFS rise (professional mastering practice: incoming track ~0.5 LUFS hotter than outgoing), with optional penalties for inconsistent loudness range or crest factor and a small bonus for matching energy slope direction.

```text
delta = lufs_b - lufs_a
S_energy = exp(-(delta - ENERGY_PREFERRED_RISE_LUFS)² / (2 * ENERGY_SIGMOID_DIVISOR²))
         # ENERGY_PREFERRED_RISE_LUFS = 0.5, σ = 3.0
S_energy -= LRA_DIFF_PENALTY     # if |lra_a - lra_b| > threshold
S_energy -= CREST_DIFF_PENALTY   # if |crest_a - crest_b| > threshold
S_energy += ENERGY_SLOPE_BONUS   # if both slopes share sign
```

Values:

| Δ LUFS | S_energy (pre-penalty) | Meaning |
|---|---|---|
| +0.5 | 1.00 | Peak (preferred slight rise) |
| 0.0 | 0.99 | Identical loudness (essentially perfect) |
| +2.0 | 0.88 | 2 LUFS JND, noticeable rise |
| -2.0 | 0.71 | 2 LUFS drop, acceptable |
| +4.0 | 0.51 | Obvious rise |
| -4.0 | 0.33 | Obvious drop (asymmetric — drops cost more) |
| ±6.0 | hard reject |

Prior sigmoid centred at Δ=0 returned 0.5 for identical loudness — a bug that punished stable-energy peak-time sets (2026-04-20 fix).

### S_spectral — BASS Stem Compatibility

Camelot wheel distance (65 % weight) + bass-band energy proximity (20 %, via `energy_bands[0]+energy_bands[1]`) + BPM Gauss (15 %). Bass clash is the #1 reason Neural Mix transitions sound muddy — key compat dominates because the bass stem sits on the fundamental.

```text
base = CAMELOT_BASE_SCORES_BASS[dist]       # {0:1.0, 1:0.85, 2:0.55, 3:0.25, 4:0.05}
bass_band_proximity = 1 - |bass_a - bass_b| / max_bass
bpm_gauss = exp(-Δbpm² / 18)
S_s = 0.65 * base + 0.20 * bass_band_proximity + 0.15 * bpm_gauss
```

### S_groove — DRUMS Stem Compatibility

BPM lock (50 %, σ=3 with stability ceiling) + kick prominence proximity (25 %) + onset rate proximity (15 %) + beat-loudness band cosine (10 %).

```text
S_g = 0.50 * (exp(-Δbpm² / 18) * stability) + 0.25 * (1 - |kickP_a - kickP_b|)
    + 0.15 * (1 - |onset_a - onset_b| / max_onset)
    + 0.10 * cos(beat_loudness_band_ratio_a, beat_loudness_band_ratio_b)
```

### S_timbral — VOCALS Stem Compatibility

Spectral centroid proximity (40 %) + chroma entropy proximity (30 %) + pitch salience proximity (30 %). All proxies for vocal presence — the project has no real-time stem separation, so vocal compat is approximated from features that change when vocals enter.

```text
S_t = 0.40 * (1 - |centroid_a - centroid_b| / max_centroid)
    + 0.30 * (1 - |chromaH_a - chromaH_b| / 3)
    + 0.30 * (1 - |pitchS_a - pitchS_b| / 0.5)
```

## Context-Aware Intent (`infer_intent` v2)

`app/domain/transition/intent.py:infer_intent(set_position, energy_delta_lufs, template=None)`:

Phase boundaries are now per-template (`_TEMPLATE_PHASE_TABLE`, 3-tuple `(warmup_end, peak_start, peak_end)`):

| Template | warmup_end | peak_start | peak_end |
|---|---|---|---|
| WARM_UP_30 | 0.50 | 0.70 | 0.85 |
| CLASSIC_60 | 0.20 | 0.50 | 0.80 |
| PEAK_HOUR_60 | 0.10 | 0.30 | 0.90 |
| ROLLER_90 | 0.15 | 0.40 | 0.85 |
| PROGRESSIVE_120 | 0.30 | 0.60 | 0.85 |
| WAVE_120 | 0.20 | 0.50 | 0.80 |
| CLOSING_60 | 0.05 | 0.15 | 0.50 |
| FULL_LIBRARY | 0.20 | 0.50 | 0.85 |
| (no template) | 0.20 | 0.50 | 0.85 |

`infer_intent` currently reads `warmup_end` and `peak_end` for RAMP_UP/COOL_DOWN classification; `peak_start` is reserved for future use. When `template=None`, the historical 0.20 / 0.50 / 0.85 fallback is used — backward compatible.

## Runtime Wiring (Template + Mood + Section Context)

Transition math is only useful if it is wired into set runtime paths. Current runtime flow:

1. `app/handlers/set_version_build.py` now resolves `template_name` into a real template definition and passes both:
   - `template=<SetTemplateDefinition>` and
   - `moods=<track_id -> mood>`
   into GA/greedy optimizers.
2. `app/domain/optimization/fitness.py:transition_quality` now calls
   `infer_intent(..., template=<SetTemplate|None>)`, so transition intent follows the selected set template phase table.
3. `app/handlers/transition_persist.py:score_set_transitions` now resolves optional `SectionContext` per pair:
   - first from explicit set item section ids (`out_section_id` / `in_section_id`),
   - fallback via `mix_in_point_ms` / `mix_out_point_ms` + `track_sections` through `build_section_context`,
   - fallback to no-context scoring when neither path has enough data.

This keeps MCP response shapes backward compatible while enabling section-aware scoring whenever context exists.

## Known Limitations

### Vocal detection without stem separation

Real-time stem separation (`StemSeparator` via demucs/htdemucs) is marked
NOT YET IMPLEMENTED in [`audio-pipeline.md`](audio-pipeline.md). Until it
ships, `_vocal_active(track)` in [`picker.py`](../app/domain/transition/picker.py)
relies on **three spectral proxies** rather than direct voice detection:

1. `pitch_salience_mean > 0.55` — sustained pitched content
2. `spectral_centroid_hz > 2200 Hz` — content in/above the vocal range
3. `(energy_bands[lowmid] + energy_bands[mid]) / sum(energy_bands) > 0.40` —
   energy concentrated in the 250-2000 Hz band (overlaps most vocal
   formant range F1≈300-800 Hz + F2≈1000-2500 Hz; when band data is
   available, otherwise falls back to signals 1+2 only)

**Signal #3 is essential.** Without it, acid/melodic techno with TB-303-style
resonant leads (pitch_salience ≈ 0.7-0.9, centroid ≈ 2500-4000 Hz, but
energy concentrated in highmid 2-4 kHz, not lowmid+mid 250-2000 Hz) was
mis-classified
as vocal-active, routing the entire picker into rule 3 (VOCAL_CUT /
VOCAL_SUSTAIN) for sets without any actual vocals.

**Even with signal #3 the heuristic is a proxy, not real voice detection.** It
cannot distinguish:

- Lead vocals from sustained synth pads in the same band
- Vocal samples / one-shots from looped synth motifs
- Formant-shifted vocoded synth from clean vocals

When real stem separation lands (Phase 3, see
[`research/2026-05-13-neural-mix-transitions-deep-dive.md`](research/2026-05-13-neural-mix-transitions-deep-dive.md)
§ 7.3.F), the picker will read `vocal_stem_energy` directly instead of these
proxies, and rules 3+4 will become reliable on any genre.

### Other limitations

- **`FILTER_SWEEP` IS implemented** (correction — earlier docs said it wasn't).
  `NeuralMixTransition.FILTER_SWEEP` exists and `picker.py` rule 5b selects it
  for `HYPNOTIC_PAIR` when `enable_filter_sweep_style` (default `True`). NOTE:
  it is a **plugin-only** preset, NOT a djay Pro 5 built-in — cheatsheets must
  remap it to `DRUM_SWAP` + an optional manual filter-knob move (see user memory).
- **No `LOOP_ROLL` / `STUTTER_FX` / explicit `HARD_CUT`.** All three are
  approximated by `DRUM_CUT` with `bars=1`-like envelopes. Not a fidelity
  issue today, but a taxonomy gap — see Phase 3 plan.
- **Camelot weights are static + the hard reject is unconditional.**
  `S_harmonic` weights Camelot at 40% regardless of subgenre, and the
  **Camelot distance ≥5 hard reject fires blind to `key_confidence`,
  `atonality`, and `hnr_db`**. Measured: **98.7% of the library is `atonality=True`**
  and `key_confidence` is mostly low/NULL — so the hard reject can FALSE-reject
  two percussive/atonal tracks whose key "clash" is inaudible. `key_confidence`
  and `atonality` are loaded into `TrackFeatures` but **referenced by zero
  scoring functions**; only `hnr_db` relaxes the *soft* harmonic score (never
  the hard reject). Phase 2: skip/relax the Camelot hard reject when both
  tracks are atonal or low-confidence, and per-subgenre Camelot downweight.
- **`chroma_entropy` proximity scale (fixed 2026-06-23).** `chroma_entropy` is
  normalized to [0,1] but `score_vocal_compat` divided `|Δ|/3.0` (the old
  raw-bits scale) → the term could never drop below 0.667. Corrected to `/1.0`
  (golden snapshots regenerated). Near-zero practical effect on this library
  (`chroma_entropy` is near-constant 0.96–0.99) but correct in general.
- **`dissonance_mean` penalty rarely discriminates here.** The `−0.15` when
  both sides `>0.4` fires near-uniformly because the library sits at ≈0.50 —
  effectively a constant offset, not a discriminator (low practical impact).

## Camelot Wheel

24 keys arranged in a circle. Adjacent keys are harmonically compatible.

```text
        12B(E)
    11B(A)   1B(B)
  10B(D)       2B(F#)
 9B(G)           3B(Db)
  8B(C)        4B(Ab)
    7B(F)    5B(Eb)
        6B(Bb)

        12A(Dbm)
    11A(F#m)   1A(Abm)
  10A(Bm)        2A(Ebm)
 9A(Em)            3A(Bbm)
  8A(Am)         4A(Fm)
    7A(Dm)     5A(Cm)
        6A(Gm)
```

Compatible transitions (distance ≤ 1):

- Same position: 8A → 8A (same key)
- ±1 on wheel: 8A → 7A, 8A → 9A (adjacent keys)
- A↔B same number: 8A → 8B (relative major/minor)

## Neural Mix Picker (v1.3.0)

`app/domain/transition/picker.py:pick_neural_mix(score, fa, fb, *, section_context=None, subgenre_pair=None, intent=None)` returns a `PickerDecision` carrying the chosen `NeuralMixTransition`, picker confidence, a reason string, and any warnings. Pure function on `TransitionScore` + `TrackFeatures` + optional context — works on synthetic scores reconstructed from persisted DB rows.

Decision tree (first match wins):

1. `score.hard_reject` → **ECHO_OUT** (echo-tail rescue, masks the failure).
2. Drum-only mix windows (`SectionContext.is_drum_only_pair`):
   - `score.groove > 0.85` → **DRUM_SWAP** (groove transfer, harmonic continuity)
   - `score.groove > 0.65` → **DRUM_CUT** (drumless reset)
   - else → **FADE** (linear stem crossfade)
3. Vocal-active outro on A (`pitch_salience_mean > 0.4` AND `spectral_centroid_hz > 2200 Hz`):
   - Low-vocal B intro (`pitch_salience_mean < 0.3`) → **VOCAL_SUSTAIN**
   - High-vocal B intro → **VOCAL_CUT**
   - Missing B vocal data → **ECHO_OUT** (safe default)
4. Harmonic motif on A (low pitch salience, mid centroid, tonnetz present) + Camelot distance ≤ 1 + low-vocal B → **HARMONIC_SUSTAIN**.
5. High B-over-A energy delta (>2 LUFS) AND (`intent=RAMP_UP` OR `subgenre_pair=HARD_PAIR`) → **DRUM_CUT** (drop-style breakdown into slam).
6. `subgenre_pair=AMBIENT_PAIR` OR `intent=COOL_DOWN` → **FADE**.
7. Default → **ECHO_OUT** (universally safe).

## Neural Mix Recipe (v1.3.0)

`app/domain/transition/recipe.py:NeuralMixRecipe` is the persisted artefact a DJ tool replays against the two tracks to reproduce the chosen transition. Shape:

```python
@dataclass(frozen=True)
class NeuralMixRecipe:
    transition: NeuralMixTransition
    bars: int                        # default 32, scaled by template
    keyframes: tuple[StemKeyframe, ...]
    fx_events: tuple[MuteFXEvent, ...]
    mix_in_section: str | None
    mix_out_section: str | None
    confidence: float
    rescue: NeuralMixTransition       # fallback if recipe fails at runtime
    explanation: str
    warnings: tuple[str, ...]
```

Each `StemKeyframe` declares the level (in dB, `LEVEL_SILENT = -120 dB` floor) of one of eight (deck × stem) channels at one bar position. Linear interpolation between consecutive keyframes for the same channel. `MuteFXEvent` carries echo-tail trigger spacing — `echo_1`, `echo_3_4` (default), or `echo_1_2` (stutter).

JSON serialisation is symmetric (`to_json` / `from_json`); the `transitions.transition_recipe_json` column stores the round-tripped form. `transitions.fx_type` carries the `NeuralMixTransition` string value; `transitions.transition_bars` carries the bar count.

### Per-preset 32-bar stem matrices

The seven builders in `app/domain/transition/builders.py` materialise the following envelopes (default bars=32, all positions are bars; `0 dB` = unity, `−∞` = silent):

| Preset | A behaviour | B behaviour | Mute FX |
|---|---|---|---|
| **FADE** | All four stems linear ↘ from 0 dB at bar 0 to silent at bar 32 | Mirror ↗ | — |
| **ECHO_OUT** | Sequential kill: vocals at bar 8 → harmonic at 16 → drums+bass at 24 (each with echo_3_4 tail) | drums+bass enter at bar 16 ↗ 0 dB by 24; harmonic enters at 20 ↗ 0 dB by 28; vocals enter at 28 ↗ 0 dB by 32 | echo_3_4 ×4 |
| **VOCAL_SUSTAIN** | Vocals hold 0 dB through bar 24, fade to silent by 32. Other stems hold through bar 8, fade to silent by 24 | Drums/bass/harmonic enter at bar 8 ↗ 0 dB by 24. Vocals stay silent through bar 28, ↗ 0 dB by 32 | — |
| **HARMONIC_SUSTAIN** | Mirror of VOCAL_SUSTAIN with harmonic ↔ vocals roles swapped | Mirror | — |
| **DRUM_SWAP** | Phase 1 (0–16): drums ↘ silent; bass/harmonic/vocals hold. Phase 2 (16–32): bass/harmonic/vocals ↘ silent | Phase 1: drums ↗ 0 dB; rest silent. Phase 2: bass/harmonic/vocals ↗ 0 dB | — |
| **VOCAL_CUT** | Vocals killed at bar 4 with echo_1_2. Other stems hold through bar 4, fade to silent by 28 | Drums/bass/harmonic enter at 4 ↗ 0 dB by 28. Vocals stay silent through bar 28, ↗ 0 dB by 32 | echo_1_2 ×1 |
| **DRUM_CUT** | Drums killed at bar 4 with echo_1_2. Bass/harmonic/vocals hold through bar 4, fade to silent by 28 | Bass/harmonic/vocals enter at 4 ↗ 0 dB by 28. Drums stay silent through bar 31.5, then ramp to 0 dB by 32 (slam) | echo_1_2 ×1 |

`build_recipe_for_pair(score, fa, fb, *, section_context, subgenre_pair, intent, bars=32)` is the convenience wrapper — runs the picker, scales `bars` via `clamp_bars` when a subgenre pair is supplied, and dispatches into the appropriate builder. Used by `transition_persist_handler` and `set_version_build_handler` so every persisted transition row carries a fully-materialised recipe.

## Feature Loading

`TrackFeatures.from_db(row)` classmethod constructs the dataclass from a `TrackAudioFeaturesComputed` DB row — single source of truth for field mapping.

```python
# Single track
feat = await feat_repo.get_scoring_features(track_id)   # TrackFeatures | None

# Batch (N SQL → 1 SQL) — use in scoring loops
features_map = await feat_repo.get_scoring_features_batch(track_ids)
feat = features_map.get(tid, TrackFeatures())
```

Both methods live in `app/repositories/track_features.py`.

## Transition Cache

LRU cache for computed scores:

```text
Key: (track_id_a, track_id_b)   # ordered tuple
Value: TransitionScore
TTL: settings.transition_cache_ttl (default 3600s)
Max size: settings.transition_cache_max_size (default 10,000)
Invalidation: when audio features of either track change
```

## Optimization: Pruning Candidate Pairs

For 3000 tracks, naive O(n²) = 9M pairs. Pruning strategy:

1. **BPM index**: only consider tracks within ±10 BPM → ~30% of library
2. **Key index**: only compatible Camelot keys → ~40%
3. **Energy filter**: only within ±6 LUFS → ~50%
4. Combined: 9M × 0.3 × 0.4 × 0.5 ≈ **540K pairs**
