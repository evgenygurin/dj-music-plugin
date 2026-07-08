# Transition + Render Refactor — Design

> Date: 2026-07-08 · Status: approved · Branch: `feat/transition-render-refactor`
>
> Consolidates and supersedes:
> - `docs/superpowers/specs/2026-04-08-transition-system-redesign.md` (Phase 1 — partially done)
> - `docs/superpowers/specs/2026-05-13-transition-architecture-refactor-design.md` (Phase 2 — not started)
> - `docs/superpowers/specs/2026-07-08-render-stabilization-design.md` (render stabilization)
>
> Research basis:
> - `docs/research/2026-04-08-techno-transitions-research.md`
> - `docs/research/2026-05-13-neural-mix-transitions-deep-dive.md`
> - Web research: DJ.Studio, Crossfader, DJ TechTools, Pirate, Pioneer DJ, ISMIR papers

---

## Summary

This spec covers three phases executed in a single branch:

1. **Sound first (render)**: pinpoint bass swap, phased EQ ritual, per-subgenre transition
   length, FILTER_SWEEP preset, VoicingAnalyzer.
2. **Architecture**: full OCP refactoring (Protocols, CoR, Template Method, scalar/bulk
   co-location) per the May 2026 spec, consolidated with partial April 2026 Phase 1 work.
3. **Calibration**: weight rebalancing, section-aware overlays for remaining pair classes,
   dead-constant cleanup.

Order: sound changes are user-visible and independent of architecture changes, so they
ship first in the PR sequence. Architecture changes are internal and gated by golden
tests.

---

## Phase 1 — Render (Sound)

### 1.1 Pinpoint bass swap (1 beat)

Current: `low_swap_bars=2` — afade qsin 2 bars on the low band. Two kicks overlap for
~1 second at 130 BPM.

New: `low_swap_beats=1` (0.5 bar at 4/4, ~230 ms at 130 BPM).

Changes in `graph.py` / `timeline.py`:
- Low band incoming: `afade=t=in:d=<beat_s>:curve=qsin`, start exactly on the
  phrase-boundary downbeat.
- Low band outgoing: `afade=t=out:d=<beat_s>:curve=qsin`, ending on the same downbeat.
- High band: unchanged — crossfades the full transition duration.

Config: `DJ_RENDER_LOW_SWAP_BEATS=1` (overridable).

### 1.2 Phased EQ ritual (highs → mids → bass)

Current: symmetric 2-band crossover (low/high via `asplit → lowpass/highpass`). Both
bands crossfade linearly/qsine over the transition.

New: 3-band crossover mimicking real DJ EQ ritual.

```
xsplit_low_hz=250   (low/mid boundary — kick + bass)
xsplit_high_hz=4000  (mid/high boundary — hats + air)

Phase 1 (0–40% of transition length):
  Incoming HIGH  — afade in
  Incoming MID   — silent
  Incoming LOW   — silent
  Outgoing HIGH  — holds unity
  Outgoing MID   — holds unity
  Outgoing LOW   — holds unity

Phase 2 (40–70% of transition length):
  Incoming MID   — afade in
  Outgoing MID   — afade out

Phase 3 (70% of transition length — pinpoint):
  Incoming LOW   — afade in (1 beat)
  Outgoing LOW   — afade out (1 beat)
  On phrase boundary downbeat
```

Implementation: 6-stream filtergraph per segment (`asplit=3 → lowpass/highpass/bandpass` →
independent afade per stream → amix). Phase boundaries computed from beatgrid phrase grid.

Config: `DJ_RENDER_XSPLIT_LOW_HZ=250`, `DJ_RENDER_XSPLIT_HIGH_HZ=4000`,
`DJ_RENDER_EQ_PHASE_1_RATIO=0.40`, `DJ_RENDER_EQ_PHASE_2_RATIO=0.70`.

### 1.3 Per-subgenre transition length

Current: global `transition_bars=16` and `body_bars=64` for all tracks.

New: subgenre-pair-aware lengths derived from DJ practice.

| Subgenre pair        | transition_bars | body_bars | Rationale |
|----------------------|-----------------|-----------|-----------|
| hypnotic/hypnotic    | 64              | 96        | Long blends, slow evolution |
| minimal/minimal      | 48              | 64        | Space for groove transfer |
| melodic/melodic      | 48              | 64        | Harmonic continuity needs time |
| peak_time/peak_time  | 32              | 64        | Standard techno blend |
| hard/hard            | 24              | 48        | Energy-driven, faster |
| acid/acid            | 32              | 48        | 303 lines need room |
| industrial/industrial| 16              | 32        | Abrasive — short sharp swaps |
| mixed pair           | 32              | 64        | Default fallback |
| acid/hypnotic        | 32              | 48        | FILTER_SWEEP default |

Configuration:
```
DJ_RENDER_TRANSITION_BARS_HYPNOTIC=64
DJ_RENDER_TRANSITION_BARS_MINIMAL=48
DJ_RENDER_TRANSITION_BARS_MELODIC=48
DJ_RENDER_TRANSITION_BARS_PEAK_TIME=32
DJ_RENDER_TRANSITION_BARS_HARD=24
DJ_RENDER_TRANSITION_BARS_ACID=32
DJ_RENDER_TRANSITION_BARS_INDUSTRIAL=16
DJ_RENDER_TRANSITION_BARS_DEFAULT=32
```

Files: extend `subgenre_rules.py:clamp_bars()` with transition/body bar lookup.
`timeline.py:build_render_plan()` reads from pair context instead of global config.

### 1.4 FILTER_SWEEP — 8th Neural Mix preset

New `NeuralMixTransition.FILTER_SWEEP` enum member.

Envelope (16 bars default):
```
A (outgoing): all stems → HPF ramp 100 Hz → 5000 Hz over bars 0–16
B (incoming): all stems → LPF ramp 5000 Hz → 20000 Hz over bars 0–16
```

Implementation in ffmpeg: 3-band split + per-band volume envelopes simulating HPF/LPF
sweep — primary approach (proven, portable). `afftfilt` considered as future optimization
(complex expression, build-dependent).

Stem-level: filter sweep applies to ALL stems equally (unlike other presets which have
per-stem envelopes). This is correct — a filter sweep is a spectral effect, not a
stem-selective one.

Picker rule: `acid/hypnotic` subgenre pair AND NOT drum-only sections → FILTER_SWEEP
(confidence 0.85).

Builder: `FilterSweepRecipeBuilder(BaseRecipeBuilder)` in
`recipe/builders/filter_sweep.py`.

### 1.5 VoicingAnalyzer

New analyzer `app/audio/analyzers/voicing.py`:

```python
class VoicingAnalyzer(BaseAnalyzer):
    name = "voicing"
    required_packages = ["essentia"]
    clip_duration_s = 60.0
    produces = ["voicing_ratio"]
```

Algorithm:
1. `essentia.standard.PitchYin()` → pitch + pitch confidence per frame
2. `essentia.standard.HarmonicPeaks()` → harmonic peak magnitudes
3. Voicing probability = harmonic energy / total energy per frame
4. `voicing_ratio` = fraction of frames with voicing_probability > 0.5

Migration: new column `voicing_ratio REAL` in `track_audio_features_computed`.
Alembic revision. Backfill on L5 re-analysis only.

Picker: replace `_vocal_active()` spectral proxy with `track.voicing_ratio > 0.3`.
Keep spectral proxy as fallback for tracks without L5 analysis.

---

## Phase 2 — Architecture

### 2.1 Target structure

```
app/domain/transition/
├── __init__.py              # Frozen public API (21 names)
├── api.py                   # 8 Protocols (ScoringComponent, HardConstraint,
│                            #   WeightOverlay, PickerRule, RecipeBuilder,
│                            #   VocalActivityDetector, HarmonicMotifDetector,
│                            #   TransitionEvaluatorProtocol)
├── enums.py                 # NeuralMixStem, NeuralMixTransition (+ FILTER_SWEEP),
│                            #   TransitionIntent, SubgenrePairType, SectionPairClass
├── score.py                 # TransitionScore (unchanged)
├── orchestrator.py          # TransitionEvaluator + legacy TransitionScorer adapter
│
├── kernels/                 # Pure math — one file, scalar + bulk per concept
│   ├── bpm_distance.py      # bpm_distance(a,b) + bpm_distance_bulk(a,b)
│   ├── camelot_lookup.py    # _CAMELOT_DISTANCE + scalar/bulk helpers
│   ├── cosine.py            # cosine_similarity scalar + bulk
│   ├── gauss.py             # gauss_similarity(x,sigma) scalar + bulk
│   └── correlation.py       # correlation (legacy)
│
├── scoring/
│   ├── __init__.py          # DEFAULT_COMPONENTS: tuple[ScoringComponent, ...]
│   ├── composite.py         # CompositeScorer
│   ├── components/
│   │   ├── bpm.py           # BpmComponent: score() + score_pairs()
│   │   ├── energy.py        # EnergyComponent
│   │   ├── drums.py         # DrumsComponent
│   │   ├── bass.py          # BassComponent
│   │   ├── harmonics.py     # HarmonicsComponent
│   │   └── vocals.py        # VocalsComponent
│   ├── overlays/
│   │   ├── intent.py        # IntentOverlay (per-intent weight tables)
│   │   ├── section_pair.py  # SectionPairOverlay (DRUM_ONLY etc.)
│   │   └── renormalise.py   # Terminal — ensures Σ = 1.0
│   └── bulk/
│       ├── arrays.py         # FeatureArrays + extract_feature_arrays
│       └── stem_weight_matrix.py
│
├── constraints/
│   ├── chain.py             # HardConstraintChain (CoR)
│   └── specs/
│       ├── bpm_difference.py
│       ├── camelot_distance.py
│       └── energy_gap.py
│
├── neural_mix/              # Neural-Mix-specific (thin after decomposition)
│   ├── weight_matrix.py     # TRANSITION_STEM_WEIGHTS + TRANSITION_ENERGY_BIAS
│   ├── energy_bias.py       # energy_bias_modifier scalar + bulk
│   ├── score_dataclass.py   # NeuralMixScore
│   └── composite.py         # NeuralMixScorer
│
├── picker/
│   ├── api.py               # PickerDecision dataclass
│   ├── pipeline.py          # PickerPipeline (CoR) + pick_neural_mix() adapter
│   ├── proxies/
│   │   ├── vocal_activity.py    # SpectralVocalActivityDetector
│   │   ├── harmonic_motif.py    # HarmonicMotifDetector
│   │   └── camelot_compatibility.py
│   └── rules/
│       ├── hard_reject_rescue.py
│       ├── drum_only_section.py
│       ├── vocal_active.py
│       ├── harmonic_sustain.py
│       ├── energy_drop_to_slam.py
│       ├── ambient_or_cooldown.py
│       ├── filter_sweep.py       # NEW
│       ├── smooth_stem_blend.py
│       ├── harmonic_continuity.py
│       └── default_drums.py      # Terminal — DRUM_SWAP / DRUM_CUT / ECHO_OUT
│
├── recipe/
│   ├── api.py               # RecipeBuilder Protocol + KeyframeBundle
│   ├── model.py             # NeuralMixRecipe + StemKeyframe + MuteFXEvent
│   ├── constants.py         # LEVEL_SILENT, LEVEL_UNITY, DEFAULT_TRANSITION_BARS
│   ├── serialization.py     # to_json / from_json
│   ├── factory.py           # build_recipe + DEFAULT_BUILDERS
│   ├── orchestrator.py      # build_recipe_for_pair
│   ├── envelopes/
│   │   ├── linear_fade.py
│   │   ├── hold_then_fade.py
│   │   ├── kill_with_echo.py
│   │   └── enter_ramp.py
│   └── builders/
│       ├── base.py          # BaseRecipeBuilder (Template Method)
│       ├── fade.py
│       ├── echo_out.py
│       ├── vocal_sustain.py
│       ├── harmonic_sustain.py
│       ├── drum_swap.py
│       ├── vocal_cut.py
│       ├── drum_cut.py
│       └── filter_sweep.py  # NEW
│
└── context/
    ├── section.py           # SectionContext + SectionPairClass
    ├── subgenre.py          # SubgenrePairType + classify_pair + clamp_bars
    └── intent.py            # infer_intent + _TEMPLATE_PHASE_TABLE
```

### 2.2 Core Protocols

```python
# api.py

class ScoringComponent(Protocol):
    name: str
    default_weight: float
    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float: ...
    def score_pairs(self, fa: FeatureArrays, ia: IntArr, ib: IntArr) -> FloatArr: ...

class HardConstraint(Protocol):
    name: str
    def check(self, from_t, to_t, *, pre_bpm_dist, pre_key_dist, pre_energy_delta) -> str | None: ...
    def check_bulk(self, fa, ia, ib) -> BoolArr: ...

class WeightOverlay(Protocol):
    def apply(self, weights: Mapping[str, float], *, intent, section_context) -> dict[str, float]: ...

class PickerRule(Protocol):
    name: str
    confidence: float
    def evaluate(self, score, from_t, to_t, *, section_context, subgenre_pair, intent) -> PickerDecision | None: ...

class VocalActivityDetector(Protocol):
    def is_active(self, t: TrackFeatures) -> bool: ...
    def is_low(self, t: TrackFeatures) -> bool: ...
    def data_missing(self, t: TrackFeatures) -> bool: ...

class RecipeBuilder(Protocol):
    transition: NeuralMixTransition
    def build(self, bars: int) -> KeyframeBundle: ...
```

### 2.3 What disappears

| Current file | Lines | Replaced by |
|---|---|---|
| `neural_mix.py` | 442 | `enums.py` + `scoring/components/{drums,bass,harmonics,vocals}.py` + `neural_mix/*.py` |
| `bulk_scorer.py` | 689 | `scoring/components/*.py` (co-located bulk) + `kernels/*.py` + `scoring/bulk/arrays.py` |
| `picker.py` | 435 | `picker/pipeline.py` + `picker/rules/*.py` + `picker/proxies/*.py` |
| `scorer.py` overlay duplicates | ~80 | `scoring/overlays/*.py` chain |
| DEAD constants in `weights.py` | ~20 | Deleted |

### 2.4 OCP acceptance test

New preset = 1 file in `recipe/builders/` + 1 line in `DEFAULT_BUILDERS` + 1 file in
`picker/rules/` + 1 line in `DEFAULT_RULES`. Core orchestrator, scorer, and pipeline
untouched. FILTER_SWEEP serves as proof-of-concept.

### 2.5 Public API preservation

All 21 names from `app/domain/transition/__init__:__all__` remain working.
`TransitionScorer` becomes a thin adapter wrapping `TransitionEvaluator`.

---

## Phase 3 — Calibration

### 3.1 Weight rebalancing

| Component | Old | New | Rationale |
|-----------|-----|-----|-----------|
| bpm       | 0.20 | 0.22 | Tempo is the foundation |
| energy    | 0.15 | 0.18 | Real DJs hold loudness step < 1 dB (Kim 2020) |
| drums     | 0.20 | 0.22 | Kick/onset alignment is load-bearing for techno |
| bass      | 0.15 | 0.15 | Unchanged |
| harmonics | 0.15 | 0.10 | Overrated for atonal percussion-heavy techno (Bibbó 2022) |
| vocals    | 0.15 | 0.13 | Vocal is rare in techno; now detected more precisely |

### 3.2 Section-aware overlays (complete the set)

Current: only `drum_only` has a non-identity overlay. Add the remaining four:

| SectionPairClass | Overlay | Logic |
|------------------|---------|-------|
| drum_only        | drums ×1.30, harmonics ×0.40, vocals ×0.30 | Existing — percussion windows |
| **drop_to_drop** | energy ×1.25, bpm ×0.80 | Two drops — loudness matters more than tempo |
| **breakdown_out**| harmonics ×1.20, drums ×0.70 | Outgoing in breakdown — melodic over groove |
| **buildup_in**   | energy ×1.30, bpm ×0.85 | Incoming buildup — prefer energy lift |
| generic          | ×1.0 identity | Fallback |

### 3.3 Hard reject rescue — smarter routing

Current: all hard_reject → ECHO_OUT.

New:
- BPM mismatch → **ECHO_OUT** (echo tail masks tempo gap)
- Camelot clash + both tonal → **FILTER_SWEEP** (filter sweep masks harmonic clash)
- Energy gap → **ECHO_OUT** (fade out / fade in)
- Multiple violations → **ECHO_OUT** (safest)

---

## Migration Plan (9 PRs)

Each PR is independently `make check`-clean. Sound first, architecture second.

### PR 1 — Per-subgenre transition scaling
- `subgenre_rules.py`: extend with transition_bars + body_bars per SubgenrePairType
- `timeline.py`: read bars from pair context
- Config env vars for per-subgenre overrides
- Tests: `tests/domain/transition/test_subgenre_rules.py`

### PR 2 — Pinpoint bass swap (1 beat)
- `graph.py`, `timeline.py`: `low_swap_beats=1` (configurable)
- afade on low band = `beat_s` duration, phrase-boundary-anchored
- Config: `DJ_RENDER_LOW_SWAP_BEATS`
- Golden test: `tests/audio/render/test_bass_swap.py`

### PR 3 — Phased EQ ritual
- 3-band crossover (low/mid/high) in `graph.py`
- Per-phase afade envelopes matching DJ practice
- Config: `DJ_RENDER_XSPLIT_LOW_HZ`, `DJ_RENDER_XSPLIT_HIGH_HZ`, phase ratios
- Golden test: filtergraph snapshot

### PR 4 — FILTER_SWEEP preset
- `NeuralMixTransition.FILTER_SWEEP` enum member
- `FilterSweepRecipeBuilder` in `recipe/builders/filter_sweep.py`
- Picker rule: acid/hypnotic pair → FILTER_SWEEP
- ffmpeg implementation (afftfilt or cascaded-band)
- Tests: envelope snapshot + picker decision

### PR 5 — VoicingAnalyzer
- `app/audio/analyzers/voicing.py` (essentia PitchYin + HarmonicPeaks)
- Alembic migration: `voicing_ratio REAL`
- Picker: use `voicing_ratio > 0.3` when available, spectral proxy as fallback
- Tests: `tests/audio/analyzers/test_voicing.py`

### PR 6 — Architecture: Protocols + skeleton
- `api.py` with 8 Protocols
- New directory structure with empty modules + re-exports
- All existing imports preserved
- Tests: protocol conformance checks

### PR 7 — Architecture: Scorer + Constraints + Kernels
- `scoring/components/*.py` — scalar + bulk co-located
- `constraints/specs/*.py` — CoR chain
- `scoring/overlays/*.py` — WeightOverlay chain
- `kernels/*.py` — math primitives
- `neural_mix.py` → `neural_mix/*.py` decomposition
- Golden tests on parity (scalar and bulk)
- Dead constants removed from `weights.py`

### PR 8 — Architecture: Picker + Recipe
- `picker/pipeline.py` — CoR picker
- `picker/rules/*.py` — per-rule files (9 rules)
- `picker/proxies/*.py` — detectors
- `recipe/builders/*.py` — Template Method (8 builders)
- `recipe/envelopes/*.py` — reusable helpers
- Golden tests on picker decisions and recipe envelopes

### PR 9 — Calibration + cleanup
- Weight rebalancing (DEFAULT_WEIGHTS)
- Section-aware overlays for drop_to_drop, breakdown_out, buildup_in
- Smarter hard-reject rescue routing
- `docs/transition-scoring.md` update
- Final `make check` verification

---

## Tests

### Golden tests (baseline — run before any changes)

| File | What it snapshots |
|------|-------------------|
| `tests/domain/transition/_golden/scoring.json` | 20 representative pairs → 6 components + overall |
| `tests/domain/transition/_golden/recipes_{preset}.json` | All presets × {16, 32, 64} bars → per-keyframe |
| `tests/domain/transition/_golden/picker.json` | 30 decision scenarios → PickerDecision |
| `tests/domain/transition/_golden/overlays.json` | 4 intents × 5 SectionPairClass → weights dict |

### Render-specific tests

| File | What it tests |
|------|---------------|
| `tests/audio/render/test_bass_swap.py` | 1-beat low swap filtergraph vs golden |
| `tests/audio/render/test_eq_ritual.py` | 3-band phased envelope vs golden |
| `tests/domain/render/test_subgenre_scaling.py` | Per-subgenre bar lookup |

### Architecture acceptance tests

| File | What it proves |
|------|---------------|
| `tests/domain/transition/test_extension_filter_sweep.py` | New preset = 1 file + 1 registry line |
| `tests/domain/transition/test_extension_custom_rule.py` | New picker rule plugs into CoR |
| `tests/domain/transition/test_extension_custom_overlay.py` | New weight overlay plugs into chain |
| `tests/domain/transition/test_extension_custom_component.py` | New scoring component plugs into Composite |

---

## Edge Cases

| Scenario | Behaviour |
|----------|-----------|
| Missing subgenre info for pair | Falls back to `DEFAULT` transition bars + body bars |
| Missing beatgrid for phrase anchoring | Bass swap falls back to bar-aligned (not phrase-aligned), WARN |
| 3-band crossover on mono source | `aformat=channel_layouts=stereo` first, then split |
| FILTER_SWEEP on non-acid/hypnotic pair | Not selected by picker unless manually forced |
| VoicingAnalyzer on pre-L5 tracks | `voicing_ratio` NULL → picker uses spectral proxy fallback |
| Track shorter than transition bars | `transition_bars = min(configured, track_duration_bars - body_bars_min)`, WARN if clamped |
| Concurrent renders with shared workspace | Temp files scoped to `tempfile.mkdtemp()` per render job |
| Golden tests on new weights | Separate golden file `_golden/scoring_v2.json` — old golden validates backward compat |
| TransitionScorer adapter | All 3 entry points (`score`, `score_all_intents`, `score_with_candidates`) proxied through `TransitionEvaluator` |

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Bass swap too short causes click/pop | afade qsin curve with 5 ms min duration prevents DC offset |
| 3-band crossover doubles ffmpeg filter complexity | Benchmark before merging; fall back to 2-band if >2x slowdown |
| FILTER_SWEEP ffmpeg afftfilt incompatible with some builds | Cascaded-band fallback implemented and tested first |
| VoicingAnalyzer false positives on pitched percussion | Voicing probability threshold 0.5 + harmonic peak count filter |
| Architecture refactor breaks external consumers | All public names preserved via re-exports; deprecated old modules kept as shims |
| Weight changes shift scores for existing sets | Documented in CHANGELOG; old transitions in DB not re-scored automatically |
| 9 PRs over 1 branch — drift risk | Each PR is `make check`-clean; golden tests run in CI per PR |

---

## Acceptance Criteria

- [ ] Bass swap duration = `low_swap_beats` (default 1), anchored to phrase downbeat
- [ ] 3-band EQ ritual produces highs-first, mids-second, bass-last envelope
- [ ] Per-subgenre transition length lookup returns correct values for all 9 pair types
- [ ] FILTER_SWEEP preset builds correct envelope; picker selects it for acid/hypnotic pairs
- [ ] VoicingAnalyzer produces `voicing_ratio` in [0, 1]; picker uses it when available
- [ ] All 8 Protocols defined and runtime-checkable
- [ ] `neural_mix.py`, `bulk_scorer.py`, `picker.py` decomposed into target structure
- [ ] Scalar/bulk parity golden tests pass (1e-9 tolerance)
- [ ] Picker decision golden tests pass
- [ ] Recipe envelope golden tests pass
- [ ] New preset = 1 file + 1 registry line (OCP acceptance test passes)
- [ ] All 21 public API names re-exported from `app/domain/transition/__init__.py`
- [ ] `make check` passes (ruff + mypy strict + full pytest suite + import-linter)
- [ ] `docs/transition-scoring.md` reflects new weights, new preset, new overlays
- [ ] `docs/render-pipeline.md` reflects bass swap and EQ ritual changes
- [ ] DEAD constants removed; no TODO/FIXME left in touched files
