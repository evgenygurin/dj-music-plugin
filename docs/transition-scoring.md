# Transition Scoring

6-component weighted formula for evaluating track-to-track transitions, with optional section-aware relaxation for percussion-only mix windows.

> Background and rebalance rationale: [docs/research/2026-04-08-techno-transitions-research.md](research/2026-04-08-techno-transitions-research.md)
> Architecture decision: [docs/superpowers/specs/2026-04-08-transition-system-redesign.md](superpowers/specs/2026-04-08-transition-system-redesign.md)

## Module Layout

```text
app/transition/
├── __init__.py            (public re-exports)
├── math_helpers.py        (bpm_distance, cosine_similarity, correlation)
├── weights.py             (ALL magic numbers + StyleRules dataclass +
│                           DRUM_ONLY_WEIGHT_OVERRIDE / DRUM_ONLY_HARMONIC_FLOOR)
├── score.py               (TransitionScore dataclass)
├── hard_constraints.py    (check_hard_constraints — standalone gate)
├── components/
│   ├── bpm.py             (score_bpm)
│   ├── harmonic.py        (score_harmonic — accepts SectionContext)
│   ├── energy.py          (score_energy)
│   ├── spectral.py        (score_spectral — 6 sub-signals)
│   ├── groove.py          (score_groove — 6 sub-signals)
│   └── timbral.py         (score_timbral)
├── section_context.py     (SectionContext dataclass + is_drum_only_pair)
├── style.py               (recommend_style + style_profile)
└── scorer.py              (~140 lines: TransitionScorer orchestrator)
```

`scorer.py` is a thin orchestrator: it calls `check_hard_constraints`, dispatches to the 6 component functions, and combines them with weights. It contains zero domain math and zero magic numbers.

## Formula

```text
score = w_bpm * S_bpm + w_harmonic * S_harmonic + w_energy * S_energy
      + w_spectral * S_spectral + w_groove * S_groove + w_timbral * S_timbral
```

Default weights (single source of truth: `app/core/constants.py:DEFAULT_TRANSITION_WEIGHTS`, re-exported as `app/transition/weights.py:DEFAULT_WEIGHTS`):

| Component | Weight | Was | Purpose |
|-----------|--------|-----|---------|
| BPM       | 0.20 | 0.22 | Tempo compatibility |
| Harmonic  | 0.12 | 0.20 | Key compatibility (Camelot) |
| Energy    | 0.18 | 0.23 | Energy flow (LUFS) |
| Spectral  | **0.20** | 0.15 | Timbral similarity (MFCC + centroid + bands + …) |
| Groove    | 0.15 | 0.10 | Rhythmic compatibility |
| Timbral   | 0.15 | 0.10 | Timbral texture matching |

Total = 1.00. Rebalance rationale: Kim et al. ISMIR 2020 found MFCC similarity to be the strongest empirical predictor of real DJ-set transitions (#1 factor) while Camelot harmonic compatibility was statistically weaker than the industry assumes. Bibbó & Faraldo (ISMIR 2022 LBD) confirmed continuous timbral measures bear DJ-perceived compatibility better than discrete Camelot.

## Hard Constraints

If ANY violated → `TransitionScore(hard_reject=True, overall=0.0, reject_reason=...)`. The gate is `app/transition/hard_constraints.py:check_hard_constraints` (standalone function).

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

`BPM_GAUSS_SIGMA = 3.0` (~2.5% on 124 BPM). All thresholds in `weights.py` and `settings`.

### S_harmonic — Key Compatibility

Camelot wheel distance lookup, weighted by HNR / chroma quality, blended with Tonnetz cosine similarity. Section-aware floor when both mix windows are drum-only.

```text
base = CAMELOT_BASE_SCORES[dist]            # {0:1.0, 1:0.9, 2:0.6, 3:0.3, 4:0.1}
if both atonal:                             base = max(ATONAL_RELAX_FLOOR, base)
hnr_factor = normalize(avg_hnr, -30..0 → 0.5..1.0)
score = base * hnr_factor
if both have tonnetz:                       score = (1-TONNETZ_BLEND)*score + TONNETZ_BLEND*tonnetz_cos
score = blend_toward_neutral_on_low_confidence(score)

# Section-aware (commit 5):
if section_context.is_drum_only_pair:       score = max(score, DRUM_ONLY_HARMONIC_FLOOR)  # 0.85
```

### S_energy — Energy Flow

Sigmoid on the LUFS delta, with optional penalties for inconsistent loudness range or crest factor and a small bonus for matching energy slope direction.

```text
delta = lufs_b - lufs_a
S_energy = sigmoid(delta, divisor=ENERGY_SIGMOID_DIVISOR)  # 3.0
S_energy -= LRA_DIFF_PENALTY     # if |lra_a - lra_b| > threshold
S_energy -= CREST_DIFF_PENALTY   # if |crest_a - crest_b| > threshold
S_energy += ENERGY_SLOPE_BONUS   # if both slopes share sign
```

### S_spectral — Spectral / Timbral Similarity

Six sub-signals collapsed by per-feature weights from `SPECTRAL_SUB_WEIGHTS`:

| Sub-signal | Weight | Source |
|---|---|---|
| MFCC cosine | 0.30 | mfcc_vector |
| Centroid proximity | 0.20 | spectral_centroid_hz |
| Energy band correlation | 0.20 | energy_bands |
| Rolloff similarity (85% + 95%, averaged) | 0.15 | spectral_rolloff_85/95 |
| Spectral slope | 0.10 | spectral_slope |
| Flux std | 0.05 | spectral_flux_std |

Then optional penalties: `DISSONANCE_PENALTY` (0.15) when both `dissonance_mean > 0.4`; `COMPLEXITY_PENALTY` (0.10) when `|spectral_complexity_mean diff| > 10`.

### S_groove — Rhythmic Compatibility

Six sub-signals from `GROOVE_SUB_WEIGHTS`:

| Sub-signal | Weight | Source |
|---|---|---|
| Onset rate similarity | 0.25 | onset_rate |
| Kick prominence similarity | 0.25 | kick_prominence |
| Beat-loudness band ratio cosine | 0.20 | beat_loudness_band_ratio |
| Pulse clarity similarity | 0.10 | pulse_clarity |
| HP ratio similarity | 0.10 | hp_ratio |
| Tempogram ratio cosine | 0.10 | tempogram_ratio_vector |

### S_timbral — Timbral Texture

Four sub-signals from `TIMBRAL_SUB_WEIGHTS`, each normalised to [0, 1] over a domain-typical range:

| Sub-signal | Weight | Norm range |
|---|---|---|
| Spectral contrast | 0.35 | 15 dB |
| Pitch salience | 0.35 | 0.5 |
| Danceability | 0.15 | 3.0 (essentia is unbounded) |
| Dynamic complexity | 0.15 | 10 |

## Section-Aware Scoring (commit 5)

`TransitionScorer.score(a, b, *, intent=None, section_context=None)` accepts an optional `SectionContext`. The dataclass holds `from_section` and `to_section` (`SectionType` enum values). When BOTH sides fall on percussion-only sections — `{INTRO, OUTRO, SUSTAIN, AMBIENT}` — the scorer:

1. **Floors `S_harmonic` at `DRUM_ONLY_HARMONIC_FLOOR = 0.85`** (key compatibility loses perceptual relevance on drum-only material — Pioneer DJ blog, Vande Veire & De Bie JASMP 2018).
2. **Swaps to `DRUM_ONLY_WEIGHT_OVERRIDE`**: bpm 0.22, harmonic 0.05, energy 0.18, spectral 0.20, groove 0.20, timbral 0.15 (Σ=1.00). Harmonic collapsed, groove boosted.

`SectionContext` is built by `app/services/mix_point_service.py:build_section_context` from `track_sections` rows + already-detected mix-out / mix-in points. The detection helpers (`detect_mix_out_point`, `detect_mix_in_point`) quantise to the nearest downbeat following Zehren et al. (CMJ 2022) — >95% of EDM cue points fall on 16-bar phrase boundaries.

When `section_context=None` (the default), behaviour is **identical** to pre-redesign — backward compatible.

## Context-Aware Intent (`infer_intent` v2)

`app/core/transition_intent.py:infer_intent(set_position, energy_delta_lufs, template=None)`:

Phase boundaries are now per-template (`_TEMPLATE_PHASE_TABLE`):

| Template | warmup_end | peak_end |
|---|---|---|
| WARM_UP_30 | 0.50 | 0.85 |
| CLASSIC_60 | 0.20 | 0.80 |
| PEAK_HOUR_60 | 0.10 | 0.90 |
| ROLLER_90 | 0.15 | 0.85 |
| PROGRESSIVE_120 | 0.30 | 0.85 |
| WAVE_120 | 0.20 | 0.80 |
| CLOSING_60 | 0.05 | 0.50 |
| FULL_LIBRARY | 0.20 | 0.85 |
| (no template) | 0.20 | 0.85 |

When `template=None`, the historical 0.20 / 0.85 cutoffs are used — backward compatible.

## Runtime Wiring (Template + Mood + Section Context)

Transition math is only useful if it is wired into set runtime paths. Current runtime flow:

1. `app/services/set/builder.py` now resolves `template_name` into a real template definition and passes both:
   - `template=<SetTemplateDefinition>` and
   - `moods=<track_id -> mood>`
   into GA/greedy optimizers.
2. `app/optimization/fitness.py:transition_quality` now calls
   `infer_intent(..., template=<SetTemplate|None>)`, so transition intent follows the selected set template phase table.
3. `app/services/set/scoring.py:score_set_transitions` now resolves optional `SectionContext` per pair:
   - first from explicit set item section ids (`out_section_id` / `in_section_id`),
   - fallback via `mix_in_point_ms` / `mix_out_point_ms` + `track_sections` through `build_section_context`,
   - fallback to no-context scoring when neither path has enough data.

This keeps MCP response shapes backward compatible while enabling section-aware scoring whenever context exists.

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

## Style Recommendation

`app/transition/style.py:recommend_style(score, *, rules=DEFAULT_STYLE_RULES)`. Pure function on a `TransitionScore` (works on synthetic scores reconstructed from persisted DB rows — used by `app/services/set/scoring.py`).

Decision tree (default `StyleRules` thresholds in parentheses):

1. `hard_reject` → `FILTER_SWEEP`
2. `spectral < 0.45` → `FILTER_SWEEP` (spectral collision)
3. `energy < 0.40` → `ECHO_OUT` (energy gap)
4. `harmonic < 0.55` → `LONG_BLEND` (key drift)
5. `bpm > 0.95 AND harmonic > 0.85 AND groove > 0.75` → `CUT`
6. `overall > 0.75` → `BASS_SWAP_SHORT` (8 bars)
7. else → `BASS_SWAP_LONG` (32 bars)

`style_profile(style)` returns `{bars, reason}` from `TRANSITION_STYLE_PROFILES`. Bar lengths: CUT 0, BASS_SWAP_SHORT 8, BASS_SWAP_LONG 32, LONG_BLEND 64, ECHO_OUT 16, FILTER_SWEEP 16.

`StyleRules` is a frozen dataclass — pass a custom instance to override per-template:

```python
from app.transition.weights import StyleRules
strict = StyleRules(spectral_collision_cutoff=0.55, harmonic_drift_cutoff=0.65)
recommend_style(score, rules=strict)
```

## Feature Loading

`TrackFeatures.from_db(row)` classmethod constructs the dataclass from a `TrackAudioFeaturesComputed` DB row — single source of truth for field mapping.

```python
# Single track
feat = await feat_repo.get_scoring_features(track_id)   # TrackFeatures | None

# Batch (N SQL → 1 SQL) — use in scoring loops
features_map = await feat_repo.get_scoring_features_batch(track_ids)
feat = features_map.get(tid, TrackFeatures())
```

Both methods live in `app/db/repositories/feature.py`.

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
