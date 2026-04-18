# P2: Analyzers + Scoring/Classification Integration

## Goal

Add 4 new audio analyzers (SpectralComplexity, PitchSalience, BpmHistogram, Phrase) and integrate all P1, P2, and unused existing features into TransitionScorer and MoodClassifier. Add context-aware transition weights based on set position.

## Architecture

Builds on P1 layered architecture: `core/` -> `analyzers/` -> `classification/` -> `pipeline.py`. New analyzers follow identical pattern: `@register_analyzer` + `_extract(ctx)` + optional `depends_on`. Integration touches `TransitionScorer`, `MoodClassifier` profiles, `TrackFeatures`, and GA optimizer.

## Research Findings (informing design decisions)

| Finding | Source | Impact |
|---------|--------|--------|
| SpectralBandwidth marginal over MFCC | API research | Dropped from scope |
| Vocal ML models 100MB+ deps | essentia docs | Replaced with PitchSalience as lightweight proxy |
| "Intent-aware" not an established term | Academic survey | Renamed to "context-aware" (Len de Vries 2018) |
| Transition lengths peak at 32-beat (8 bar) | DTW analysis, 1557 mixes | Confirms phrase quantization value |
| 73.6% DJs use phrase-aligned transitions | CUE-DETR dataset | Motivates PhraseAnalyzer |
| BpmHistogramDescriptors nearly free from existing beats_intervals | essentia API | Phase 2 analyzer, depends on beat |
| PitchSalience 0-1 correlates with melodic/vocal content | essentia docs | Doubles as vocal presence proxy |

---

## Part A: New Analyzers (4)

### A1. SpectralComplexityAnalyzer

- **File**: `app/audio/analyzers/spectral_complexity.py`
- **Library**: essentia (`essentia.standard.SpectralComplexity`)
- **Cost**: +20ms per track
- **depends_on**: `frozenset()` (Phase 1, independent)
- **required_packages**: `["essentia"]`

**Algorithm**: Counts spectral peaks above magnitude threshold per frame, returns mean across all frames.

```python
sc = essentia.standard.SpectralComplexity(magnitudeThreshold=0.005, sampleRate=sr)
spectrum = essentia.standard.Spectrum()
windowing = essentia.standard.Windowing(type="blackmanharris62")

complexities = []
for frame in FrameGenerator(samples, frameSize=2048, hopSize=1024):
    spec = spectrum(windowing(frame))
    complexities.append(sc(spec))
return {"spectral_complexity_mean": float(np.mean(complexities))}
```

**Output**: `spectral_complexity_mean: float` (0-30+, unbounded). Typical: minimal 5, industrial 20+, white noise 30+.

**Use in**: MoodClassifier (industrial/acid = high, minimal/dub = low), TransitionScorer (two complex tracks = penalty).

### A2. PitchSalienceAnalyzer

- **File**: `app/audio/analyzers/pitch_salience.py`
- **Library**: essentia (`essentia.standard.PitchSalience`)
- **Cost**: +20ms per track
- **depends_on**: `frozenset()` (Phase 1, independent)
- **required_packages**: `["essentia"]`

**Algorithm**: Ratio of max autocorrelation to zero-lag autocorrelation of spectrum. Measures tonality/harmonicity.

```python
ps = essentia.standard.PitchSalience(lowBoundary=100, highBoundary=5000, sampleRate=sr)

saliences = []
for frame in FrameGenerator(samples, frameSize=2048, hopSize=1024):
    spec = spectrum(windowing(frame))
    saliences.append(ps(spec))
return {"pitch_salience_mean": float(np.mean(saliences))}
```

**Output**: `pitch_salience_mean: float` (0.0-1.0). Percussive-only ~0.1, melodic 0.4-0.7, vocal 0.5+.

**Difference from HNR**: HNR = harmonic-to-noise ratio in dB (unbounded, -30..+30). PitchSalience = normalized 0-1, autocorrelation-based, better for binary melodic/percussive classification.

**Use in**: MoodClassifier (melodic_deep vs driving), TransitionScorer (timbral component), transition type recommender (high salience = prefer NM_VOCAL_CUT/SUSTAIN).

### A3. BpmHistogramAnalyzer

- **File**: `app/audio/analyzers/bpm_histogram.py`
- **Library**: essentia (`essentia.standard.BpmHistogramDescriptors`)
- **Cost**: ~0ms (reuses beats_intervals from BeatDetector)
- **depends_on**: `frozenset({"beat"})` (Phase 2, dependent)
- **required_packages**: `["essentia"]`

**Algorithm**: Builds BPM histogram from beat intervals, extracts first/second peak descriptors.

```python
def _extract(self, ctx, *, prior_results=None):
    beats_intervals = (prior_results or {}).get("beats_intervals")
    if not beats_intervals or len(beats_intervals) < 4:
        return {"bpm_histogram_first_peak_weight": None, ...}

    bhd = essentia.standard.BpmHistogramDescriptors()
    intervals = np.array(beats_intervals, dtype=np.float32)
    p1_bpm, p1_weight, p1_spread, p2_bpm, p2_weight, p2_spread, hist = bhd(intervals)

    return {
        "bpm_histogram_first_peak_weight": float(p1_weight),
        "bpm_histogram_second_peak_bpm": float(p2_bpm),
        "bpm_histogram_second_peak_weight": float(p2_weight),
    }
```

**Output**: 3 floats. `first_peak_weight` 0-1 (techno: 0.8-0.95 = stable rhythm). `second_peak_bpm` in BPM (often half/double-time). `second_peak_weight` 0-1 (polyrhythm indicator).

**Prerequisite**: BeatDetector must export `beats_intervals` in its output dict. Currently exports `beat_times` — need to add `beats_intervals` (diff of beat_times).

**Use in**: MoodClassifier (stability discriminator: driving 0.9 vs breakbeat 0.6).

### A4. PhraseAnalyzer

- **File**: `app/audio/analyzers/phrase.py`
- **Library**: librosa (`librosa.segment.agglomerative`, `librosa.feature.chroma_cqt`)
- **Cost**: +300ms per track
- **depends_on**: `frozenset({"beat"})` (Phase 2, dependent)
- **required_packages**: `["librosa"]`

**Algorithm**:

1. Get `beat_times` from `prior_results`
2. Group beats into bars (4 beats each) -> bar boundaries
3. Compute mean chroma per bar (`librosa.feature.chroma_cqt`)
4. `librosa.segment.agglomerative(chroma_bars, k=k)` -> phrase boundary indices
5. Convert bar indices to milliseconds
6. Determine `dominant_phrase_bars` — mode of segment lengths, quantized to {8, 16, 32}

```python
def _extract(self, ctx, *, prior_results=None):
    beat_times = (prior_results or {}).get("beat_times", [])
    if len(beat_times) < 16:  # need at least 4 bars
        return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

    # Group beats into bars (4 beats per bar for 4/4)
    bar_times = beat_times[::4]
    n_bars = len(bar_times)

    # Compute chroma at bar resolution
    chroma = librosa.feature.chroma_cqt(y=ctx.samples, sr=ctx.sr)
    bar_frames = librosa.time_to_frames(bar_times, sr=ctx.sr)
    chroma_bars = np.array([
        chroma[:, max(0, f):f+hop].mean(axis=1)
        for f, hop in zip(bar_frames[:-1], np.diff(bar_frames))
    ]).T  # shape: (12, n_bars-1)

    # Determine k
    k = max(4, min(n_bars // 4, 64))
    boundaries = librosa.segment.agglomerative(chroma_bars, k=k)

    # Convert to ms
    phrase_boundaries_ms = [int(bar_times[min(b, len(bar_times)-1)] * 1000) for b in boundaries]

    # Dominant phrase length
    segment_lengths = np.diff(boundaries)  # in bars
    if len(segment_lengths) > 0:
        quantized = [min([8, 16, 32], key=lambda x: abs(x - sl)) for sl in segment_lengths]
        dominant = max(set(quantized), key=quantized.count)
    else:
        dominant = 16

    return {
        "phrase_boundaries_ms": phrase_boundaries_ms,
        "dominant_phrase_bars": int(dominant),
    }
```

**Output**: `phrase_boundaries_ms: list[int]` (timestamps), `dominant_phrase_bars: int` (8, 16, or 32).

**Use in**: Set generation (mix point quantization), transition type recommender (djay_bars alignment), score_groove bonus for phrase-aligned transitions.

---

## Part B: MoodClassifier Integration

### B1. New FeatureTargets in SubgenreProfiles

Add targets to existing `SubgenreProfile` dataclasses in `profiles.py`. No changes to `MoodClassifier` scoring engine — Strategy pattern auto-picks up new features.

**New features per profile** (weight, ideal, tolerance):

| Profile | danceability | dissonance_mean | dynamic_complexity | pitch_salience | spectral_complexity | bpm_stability | hp_ratio | pulse_clarity |
|---------|-------------|-----------------|-------------------|---------------|--------------------|--------------|---------|----|
| AMBIENT_DUB | (1.5, 0.8, 0.3) | (1.0, 0.15, 0.1) | (1.0, 0.15, 0.1) | (1.5, 0.45, 0.15) | (1.0, 8, 4) | — | (1.5, 4.0, 1.5) | (1.0, 0.15, 0.1) |
| DUB_TECHNO | (1.5, 1.2, 0.3) | (1.0, 0.2, 0.1) | (1.0, 0.2, 0.1) | (1.5, 0.4, 0.15) | (1.0, 8, 3) | — | (1.5, 3.5, 1.0) | (1.0, 0.3, 0.15) |
| MINIMAL | (1.5, 1.5, 0.3) | (1.0, 0.2, 0.1) | (1.0, 0.2, 0.1) | (1.0, 0.2, 0.15) | (1.5, 5, 2) | (1.0, 0.9, 0.1) | — | (1.0, 0.5, 0.2) |
| MELODIC_DEEP | (1.5, 1.8, 0.4) | (1.0, 0.15, 0.08) | (1.0, 0.3, 0.15) | (2.0, 0.55, 0.15) | (1.0, 10, 4) | — | (1.5, 2.5, 0.8) | (1.0, 0.5, 0.2) |
| DRIVING | (2.0, 2.5, 0.3) | (1.0, 0.3, 0.1) | (1.0, 0.2, 0.1) | (1.0, 0.15, 0.1) | (1.0, 12, 5) | (1.5, 0.95, 0.05) | (1.0, 1.3, 0.3) | (1.5, 0.7, 0.15) |
| PEAK_TIME | (2.0, 2.8, 0.3) | (1.0, 0.35, 0.15) | (1.0, 0.35, 0.15) | (1.0, 0.12, 0.08) | (1.0, 15, 5) | (1.5, 0.9, 0.05) | (1.0, 1.2, 0.3) | (1.5, 0.7, 0.15) |
| ACID | (1.5, 2.2, 0.4) | (2.0, 0.6, 0.15) | (1.0, 0.4, 0.2) | (1.5, 0.35, 0.15) | (1.5, 18, 5) | — | — | — |
| INDUSTRIAL | (1.0, 2.0, 0.5) | (2.0, 0.55, 0.15) | (1.5, 0.5, 0.2) | (1.0, 0.1, 0.08) | (2.0, 22, 5) | — | (1.0, 1.0, 0.3) | — |
| HARD_TECHNO | (1.5, 2.6, 0.3) | (1.5, 0.45, 0.15) | (1.0, 0.3, 0.15) | (1.0, 0.1, 0.08) | (1.5, 18, 5) | (1.0, 0.9, 0.05) | (1.0, 1.1, 0.3) | (1.5, 0.7, 0.15) |
| BREAKBEAT | (1.5, 2.0, 0.4) | (1.0, 0.3, 0.15) | (2.0, 0.7, 0.15) | (1.0, 0.2, 0.15) | (1.0, 12, 5) | (2.0, 0.7, 0.1) | — | (1.0, 0.5, 0.2) |
| TRIBAL | (1.5, 2.2, 0.3) | (1.0, 0.25, 0.1) | (1.0, 0.3, 0.15) | (1.0, 0.15, 0.1) | (1.0, 10, 4) | (1.5, 0.8, 0.1) | — | (1.5, 0.6, 0.15) |
| HYPNOTIC | (1.5, 2.0, 0.3) | (1.0, 0.25, 0.1) | (1.0, 0.15, 0.08) | (1.5, 0.3, 0.15) | (1.0, 8, 3) | (1.5, 0.95, 0.03) | — | (1.0, 0.6, 0.15) |
| PROGRESSIVE | (1.5, 2.0, 0.4) | (1.0, 0.2, 0.1) | (1.5, 0.45, 0.15) | (1.5, 0.4, 0.15) | (1.0, 12, 5) | — | (1.0, 2.0, 0.7) | — |
| DETROIT | (1.5, 2.0, 0.4) | (1.0, 0.25, 0.1) | (1.0, 0.3, 0.15) | (1.5, 0.45, 0.15) | (1.0, 12, 5) | — | (1.0, 2.0, 0.7) | — |
| RAW | (1.0, 2.3, 0.4) | (1.5, 0.5, 0.15) | (1.5, 0.45, 0.2) | (1.0, 0.12, 0.08) | (1.5, 18, 5) | — | (1.0, 1.1, 0.3) | — |

Empty cells (—) mean no target for that feature in that profile — feature is skipped in Gaussian scoring.

### B2. _CLASSIFIER_FIELDS Update

Add to `_CLASSIFIER_FIELDS` set in `app/models/audio.py`:

```python
"danceability", "dissonance_mean", "dynamic_complexity",
"pitch_salience_mean", "spectral_complexity_mean",
"bpm_histogram_first_peak_weight",
"hp_ratio", "pulse_clarity", "bpm_stability",
"spectral_slope",
```

### B3. Calibration Note

All ideal/tolerance values above are initial estimates based on:
- Techno audio criteria from `mood_classifier.py` reference values
- essentia algorithm output ranges from documentation
- Research findings on subgenre characteristics

Precise calibration requires running P2 features on real tracks (2800+ in DB) and analyzing distributions. This is a post-P2 task, not part of this spec.

---

## Part C: TransitionScorer Integration

### C1. Extended TrackFeatures

Add 8 fields to `TrackFeatures` dataclass in `app/core/track_features.py`:

```python
@dataclass
class TrackFeatures:
    # ... existing 12 fields ...

    # P1 features
    dissonance_mean: float | None = None
    danceability: float | None = None
    tonnetz_vector: list[float] | None = None       # 6D
    beat_loudness_band_ratio: list[float] | None = None  # 6D

    # P2 features
    spectral_complexity_mean: float | None = None
    pitch_salience_mean: float | None = None

    # Existing but previously unused
    bpm_stability: float | None = None
    spectral_contrast: float | None = None          # DB: spectral_contrast
```

Update `from_db()` classmethod to populate new fields from ORM row.

### C2. Enriched Scoring Components

**score_harmonic** (weight 0.20, unchanged):
```text
Current: camelot_score * hnr_factor
New:     0.70 * camelot_score * hnr_factor + 0.30 * tonnetz_cosine
```

Where `tonnetz_cosine = cosine_similarity(from.tonnetz_vector, to.tonnetz_vector)`. Falls back to current formula if tonnetz unavailable.

**score_spectral** (weight 0.15, unchanged):
```bash
Current: 0.40 * mfcc_cosine + 0.30 * centroid_proximity + 0.30 * band_balance
New:     same + dissonance_penalty + complexity_penalty
  dissonance_penalty: if both tracks dissonance > 0.4, subtract 0.15
  complexity_penalty: if abs(complexity_diff) > 10, subtract 0.10
```

Penalties are capped — score_spectral cannot go below 0.0.

**score_groove** (weight reduced from 0.15 to 0.10):
```text
Current: 0.50 * onset_match + 0.50 * kick_match
New:     0.35 * onset_match + 0.35 * kick_match + 0.30 * beat_loudness_cosine
```

Where `beat_loudness_cosine = cosine_similarity(from.beat_loudness_band_ratio, to.beat_loudness_band_ratio)`. Falls back to current 50/50 if unavailable.

**score_bpm** (weight reduced from 0.25 to 0.22):
```bash
Current: gaussian(bpm_diff, sigma=3) with half/double consideration
New:     same * bpm_stability_factor
  bpm_stability_factor: min(from.bpm_stability, to.bpm_stability) or 1.0 if unavailable
  Effect: unstable BPM (< 0.7) penalizes the score by up to 30%
```

### C3. New Timbral Component

**score_timbral** (new, weight 0.10):
```python
def _score_timbral(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    signals = []
    weights = []

    if from_t.spectral_contrast is not None and to_t.spectral_contrast is not None:
        # Spectral contrast proximity (0-1)
        diff = abs(from_t.spectral_contrast - to_t.spectral_contrast)
        signals.append(max(0.0, 1.0 - diff / 15.0))  # 15 dB = full penalty
        weights.append(0.5)

    if from_t.pitch_salience_mean is not None and to_t.pitch_salience_mean is not None:
        # Pitch salience proximity (0-1)
        diff = abs(from_t.pitch_salience_mean - to_t.pitch_salience_mean)
        signals.append(max(0.0, 1.0 - diff / 0.5))  # 0.5 = full penalty
        weights.append(0.5)

    if not signals:
        return 0.5  # neutral when unavailable

    return sum(s * w for s, w in zip(signals, weights)) / sum(weights)
```

### C4. Updated Default Weights

In `app/core/constants.py`:

```python
DEFAULT_TRANSITION_WEIGHTS: dict[str, float] = {
    "bpm": 0.22,
    "harmonic": 0.20,
    "energy": 0.23,
    "spectral": 0.15,
    "groove": 0.10,
    "timbral": 0.10,
}
```

### C5. Backward Compatibility

All new TrackFeatures fields default to `None`. When a sub-signal's input is `None`:
- That sub-signal is skipped
- Remaining sub-signals' weights are renormalized within the component
- Behavior identical to pre-P2 for tracks without P1/P2 features

---

## Part D: Context-Aware Transition Weights

### D1. TransitionIntent Enum

New file or addition to existing types: `app/core/transition_intent.py`

```python
class TransitionIntent(StrEnum):
    MAINTAIN = "maintain"
    RAMP_UP = "ramp_up"
    COOL_DOWN = "cool_down"
    CONTRAST = "contrast"
```

### D2. Weight Modifiers

```python
INTENT_WEIGHT_MODIFIERS: dict[TransitionIntent, dict[str, float]] = {
    TransitionIntent.MAINTAIN: {
        "bpm": 0.28, "harmonic": 0.18, "energy": 0.15,
        "spectral": 0.15, "groove": 0.14, "timbral": 0.10,
    },
    TransitionIntent.RAMP_UP: {
        "bpm": 0.20, "harmonic": 0.25, "energy": 0.30,
        "spectral": 0.10, "groove": 0.05, "timbral": 0.10,
    },
    TransitionIntent.COOL_DOWN: {
        "bpm": 0.20, "harmonic": 0.20, "energy": 0.25,
        "spectral": 0.15, "groove": 0.05, "timbral": 0.15,
    },
    TransitionIntent.CONTRAST: {
        "bpm": 0.15, "harmonic": 0.12, "energy": 0.18,
        "spectral": 0.20, "groove": 0.15, "timbral": 0.20,
    },
}
```

### D3. Auto-Detection from Set Position

```python
def infer_intent(
    set_position: float,  # 0.0-1.0
    energy_delta_lufs: float,
) -> TransitionIntent:
    if set_position < 0.2:
        return TransitionIntent.RAMP_UP
    if set_position > 0.85:
        return TransitionIntent.COOL_DOWN
    if energy_delta_lufs > 2.0:
        return TransitionIntent.RAMP_UP
    if energy_delta_lufs < -2.0:
        return TransitionIntent.COOL_DOWN
    return TransitionIntent.MAINTAIN
```

### D4. Integration Points

- `TransitionScorer.score()` accepts optional `intent: TransitionIntent | None`
- If `None`, uses `DEFAULT_TRANSITION_WEIGHTS`
- If provided, uses `INTENT_WEIGHT_MODIFIERS[intent]`
- GA optimizer calls `infer_intent(position, energy_delta)` for each pair
- `rebuild_set` constraints can specify explicit intent per transition
- `recommend_transition()` receives intent for type selection:
  - RAMP_UP: prefer NM_DRUM_SWAP, EQ
  - COOL_DOWN: prefer DISSOLVE, NM_FADE
  - CONTRAST: prefer ECHO, SHUFFLE
  - MAINTAIN: prefer FILTER, FADE

---

## Part E: ORM & Migration

### E1. New Columns

| Column | Type | Nullable | Source |
|--------|------|----------|--------|
| `spectral_complexity_mean` | Float | Yes | SpectralComplexityAnalyzer |
| `pitch_salience_mean` | Float | Yes | PitchSalienceAnalyzer |
| `bpm_histogram_first_peak_weight` | Float | Yes | BpmHistogramAnalyzer |
| `bpm_histogram_second_peak_bpm` | Float | Yes | BpmHistogramAnalyzer |
| `bpm_histogram_second_peak_weight` | Float | Yes | BpmHistogramAnalyzer |
| `phrase_boundaries_ms` | VARCHAR(2000) | Yes | PhraseAnalyzer |
| `dominant_phrase_bars` | SmallInteger | Yes | PhraseAnalyzer |

### E2. filter_features Update

Add `phrase_boundaries_ms` to `vector_columns` set for JSON serialization.

### E3. Migration

Alembic migration using `batch_alter_table` for SQLite compatibility. Same pattern as P1 migration `a46fe524044f`.

---

## Part F: Testing Strategy

### F1. Unit Tests per Analyzer (4 files)

Each follows P1 pattern:
- `test_spectral_complexity.py` — happy path (synthetic signal), silence, graceful skip without essentia
- `test_pitch_salience.py` — tonal signal (high salience), percussive (low), silence
- `test_bpm_histogram.py` — stable BPM (high first_peak_weight), polyrhythmic, too few intervals
- `test_phrase.py` — synthetic pattern with clear phrase boundaries, short signal fallback

All use `pytest.importorskip("essentia")` or `pytest.importorskip("librosa")`.

### F2. Scoring Tests

- `test_score_harmonic_with_tonnetz` — tonnetz cosine similarity contributes 30%
- `test_score_spectral_dissonance_penalty` — two high-dissonance tracks penalized
- `test_score_groove_with_beat_loudness` — beat_loudness_band_ratio cosine similarity
- `test_score_bpm_stability_factor` — unstable BPM penalizes score
- `test_score_timbral` — spectral contrast + pitch salience proximity
- `test_backward_compat` — tracks without P2 features get same scores as before

### F3. Context-Aware Weights Tests

- `test_infer_intent_ramp_up` — position < 0.2
- `test_infer_intent_cool_down` — position > 0.85
- `test_infer_intent_energy_delta` — large energy delta overrides position
- `test_intent_weights_sum_to_one` — all 4 intents have weights summing to 1.0
- `test_scorer_with_intent` — scorer uses modified weights

### F4. Classifier Tests

- `test_profiles_include_new_features` — all 15 profiles have danceability, dissonance targets
- `test_classifier_with_p2_features` — synthetic track with known features classifies correctly
- `test_classifier_backward_compat` — missing P2 features don't crash

### F5. Integration Tests

- `test_pipeline_discovers_p2_analyzers` — registry.discover() finds new 4
- `test_pipeline_e2e_with_p2` — full pipeline run includes P2 features
- `test_bpm_histogram_depends_on_beat` — Phase 2 receives beats_intervals
- `test_phrase_depends_on_beat` — Phase 2 receives beat_times

### F6. Parity Test

- `test_scoring_parity_without_p2` — existing test tracks without P2 features produce identical TransitionScores as before P2 changes

---

## Part G: BeatDetector Prerequisite

BpmHistogramAnalyzer needs `beats_intervals` in prior_results. Currently BeatDetector exports `beat_times` but not intervals.

**Change**: Add `beats_intervals` to BeatDetector output:
```python
# In beat.py _extract():
beat_times = [...]
beats_intervals = np.diff(beat_times).tolist() if len(beat_times) > 1 else []
return {
    "beat_times": beat_times,
    "beats_intervals": beats_intervals,  # NEW
    # ... other outputs
}
```

Minimal change, no new column needed (intervals are derived, not stored).

---

## Scope Summary

| Category | Items | Effort |
|----------|-------|--------|
| New analyzers | 4 (SpectralComplexity, PitchSalience, BpmHistogram, Phrase) | 2 days |
| ORM + migration | 7 columns + filter_features | 0.5 day |
| MoodClassifier integration | 10 new features in 15 profiles | 1 day |
| TransitionScorer integration | 4 enriched components + 1 new + TrackFeatures extension | 1.5 days |
| Context-aware weights | TransitionIntent enum + modifiers + auto-detection + GA integration | 1 day |
| BeatDetector prerequisite | Add beats_intervals export | 0.5 day |
| Testing | ~30 tests across 6 categories | included |
| **Total** | | **~6.5 days** |

## Out of Scope

- SpectralBandwidth (marginal over MFCC)
- Vocal ML detection (PitchSalience covers the use case)
- Phrase-based mix point replacement (phrase adds fallback, doesn't replace StructureAnalyzer)
- Feature calibration on real data (post-P2 task)
- Discogs-EffNet embeddings (P3)
- CLAP embeddings (P3)
- Graph-based set ordering (P3)
