# Phase 1: New Audio Analyzers — Design Spec

> Date: 2026-03-28
> Scope: 6 new analyzers in `app/audio/analyzers/`, pipeline two-phase execution, DB migration
> Approach: Analyzer-first, DB migration last
> Status: Approved

## 1. Problem Statement

The refactored audio module extracts 47 features via 8 analyzers. Research identified 6 high-value features missing from the current pipeline that are computationally cheap, well-supported by essentia/librosa, and directly useful for subgenre classification and transition scoring in future enrichment cycles.

| Feature | Library | Value for DJ mixing |
|---------|---------|---------------------|
| Danceability | essentia | Separates ambient/dub (low) from peak_time/driving (high) |
| Tempogram Ratio | librosa | Detects metric complexity (straight vs polyrhythmic) |
| Dissonance | essentia | Distinguishes clean melodic from harsh industrial textures |
| Dynamic Complexity | essentia | Identifies tracks with drops/builds vs flat energy |
| Tonnetz | librosa | 6D tonal space — richer harmonic descriptor than key alone |
| Beats Loudness Band Ratio | essentia | Per-band loudness at beat positions — rhythmic timbre fingerprint |

## 2. Goals

- Add 6 new analyzers following existing `BaseAnalyzer` + `@register_analyzer` pattern
- Introduce dependency mechanism (`depends_on`) for inter-analyzer data flow
- Two-phase pipeline execution (independent parallel, then dependent)
- Persist new features in 6 new nullable DB columns
- 100% backward compatible — no changes to existing analyzers, classifier, or scoring

## 3. Non-Goals

- Classifier enrichment (SubgenreProfile weights for new features) — separate future cycle
- Scoring enrichment (TransitionScorer using new features) — separate future cycle
- Changes to TrackFeatures dataclass or feature_conversion.py — separate future cycle
- Using the 20 existing unused features — separate analysis

## 4. Analyzer Contracts

### 4.1 New Analyzer Files

6 new files in `app/audio/analyzers/`, each following the existing pattern:

| File | Class | `name` | Library | `required_packages` | Output keys |
|------|-------|--------|---------|---------------------|-------------|
| `danceability.py` | `DanceabilityAnalyzer` | `"danceability"` | essentia | `["essentia"]` | `danceability: float` (0.0-3.0, DFA algorithm) |
| `tempogram.py` | `TempogramAnalyzer` | `"tempogram"` | librosa | `["librosa"]` | `tempogram_ratio: list[float]` (~10 dims) |
| `dissonance.py` | `DissonanceAnalyzer` | `"dissonance"` | essentia | `["essentia"]` | `dissonance_mean: float` (0.0-1.0) |
| `dynamic_complexity.py` | `DynamicComplexityAnalyzer` | `"dynamic_complexity"` | essentia | `["essentia"]` | `dynamic_complexity: float` (unbounded, typically 0-10) |
| `tonnetz.py` | `TonnetzAnalyzer` | `"tonnetz"` | librosa | `["librosa"]` | `tonnetz_vector: list[float]` (6 dims) |
| `beats_loudness.py` | `BeatsLoudnessAnalyzer` | `"beats_loudness"` | essentia | `["essentia"]` | `beat_loudness_band_ratio: list[float]` (6 dims) |

### 4.2 Analyzer Pattern (reference)

Each analyzer follows the existing `BaseAnalyzer` Template Method pattern:

```python
from typing import Any, ClassVar
from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class DanceabilityAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "danceability"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es
        dfa = es.Danceability()
        result, _ = dfa(ctx.samples)
        return {"danceability": float(result)}
```

### 4.3 Output Value Ranges

| Key | Type | Range | Notes |
|-----|------|-------|-------|
| `danceability` | `float` | 0.0 - 3.0 | Essentia DFA algorithm. Techno avg ~1.5-2.5 |
| `tempogram_ratio` | `list[float]` | Each 0.0-1.0 | Normalized autocorrelation at BPM ratios |
| `dissonance_mean` | `float` | 0.0 - 1.0 | Mean spectral dissonance across frames |
| `dynamic_complexity` | `float` | 0.0 - ~10.0 | Loudness variance descriptor. Flat=low, builds=high |
| `tonnetz_vector` | `list[float]` | Each -1.0 to 1.0 | 6 tonal centroid features from chroma |
| `beat_loudness_band_ratio` | `list[float]` | Each 0.0-1.0 | 6-band beat-synchronous loudness ratios |

## 5. Dependency Mechanism

### 5.1 Problem

`BeatsLoudnessAnalyzer` needs `beat_times` (beat positions array) from `BeatDetector`. Currently, analyzers run independently with no inter-analyzer data flow.

### 5.2 Solution: `depends_on` ClassVar + Two-Phase Execution

**BaseAnalyzer changes** (backward-compatible):

```python
class BaseAnalyzer(ABC):
    name: ClassVar[str] = ""
    capabilities: ClassVar[frozenset[str]] = frozenset()
    required_packages: ClassVar[list[str]] = []
    depends_on: ClassVar[frozenset[str]] = frozenset()  # NEW

    def run(self, ctx: AnalysisContext, prior_results: dict[str, Any] | None = None) -> AnalyzerResult:
        if len(ctx.samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")
        try:
            features = self._extract(ctx, prior_results=prior_results or {})
            return AnalyzerResult(analyzer_name=self.name, features=features)
        except Exception as e:
            logger.warning("Analyzer %s failed: %s", self.name, e)
            return AnalyzerResult(analyzer_name=self.name, success=False, error=str(e))

    @abstractmethod
    def _extract(self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None) -> dict[str, Any]:
        ...
```

**Key design decisions:**
- `prior_results` is `dict[str, Any] | None` (keyword-only, defaults to `None`)
- Existing 8 analyzers don't use `prior_results` — signature change is backward-compatible via `**kwargs` or default
- `depends_on` references analyzer `name` strings, not classes — loose coupling
- If dependency didn't run or failed, dependent analyzer handles gracefully (returns `AnalyzerResult(success=False)`)

### 5.3 BeatDetector Enhancement

`BeatDetector._extract()` must export `beat_times` in its output dict (currently it may not include raw beat positions):

```python
# In beat.py _extract():
return {
    "onset_rate_mean": float(onset_rate),
    "kick_prominence": float(kick_prom),
    # ... existing fields ...
    "beat_times": beat_times.tolist(),  # NEW — numpy array -> list for JSON compat
}
```

### 5.4 BeatsLoudnessAnalyzer Dependency

```python
@register_analyzer
class BeatsLoudnessAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "beats_loudness"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm", "spectral"})
    required_packages: ClassVar[list[str]] = ["essentia"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})  # depends on BeatDetector

    def _extract(self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None) -> dict[str, Any]:
        beat_times = (prior_results or {}).get("beat_times")
        if not beat_times:
            raise ValueError("beat_times not available from BeatDetector")

        import essentia.standard as es
        bl = es.BeatsLoudness(beats=beat_times, sampleRate=ctx.signal.sample_rate)
        loudness, loudness_band_ratio = bl(ctx.samples)
        mean_ratio = [float(x) for x in loudness_band_ratio.mean(axis=0)]
        return {"beat_loudness_band_ratio": mean_ratio}
```

## 6. Pipeline: Two-Phase Execution

### 6.1 Current Pipeline

All analyzers run in parallel via `asyncio.gather()`:

```python
results = list(await asyncio.gather(*(asyncio.to_thread(a.run, ctx) for a in instances)))
```

### 6.2 New Pipeline

Split into Phase 1 (independent) and Phase 2 (dependent):

```python
async def analyze(self, file_path, analyzers=None, max_duration=None) -> PipelineResult:
    # ... load, clip, create ctx (unchanged) ...

    # Partition: independent vs dependent
    independent = [a for a in instances if not a.depends_on]
    dependent = [a for a in instances if a.depends_on]

    # Phase 1: independent — full parallelism (unchanged behavior)
    phase1_results = list(
        await asyncio.gather(*(asyncio.to_thread(a.run, ctx) for a in independent))
    )

    # Build prior_results from Phase 1
    prior = self._merge_features(phase1_results)

    # Phase 2: dependent — sequential or parallel among non-conflicting
    phase2_results = list(
        await asyncio.gather(*(asyncio.to_thread(a.run, ctx, prior) for a in dependent))
    )

    all_results = phase1_results + phase2_results
    return PipelineResult(results=all_results, features=self._merge_features(all_results))
```

**Key properties:**
- Phase 1 behavior is identical to current — no regression
- Phase 2 is additive — only executes when dependent analyzers exist
- `prior_results` passed as positional arg to `run()` (signature: `run(ctx, prior_results=None)`)
- If Phase 1 dependency failed, Phase 2 analyzer gets `None` for that key and handles gracefully

## 7. Database Schema

### 7.1 New Columns

6 new nullable columns in `track_audio_features_computed`:

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `danceability` | `FLOAT` | Yes | Essentia DFA result (0.0-3.0) |
| `dynamic_complexity` | `FLOAT` | Yes | Loudness variance (0.0-~10.0) |
| `dissonance_mean` | `FLOAT` | Yes | Mean spectral dissonance (0.0-1.0) |
| `tonnetz_vector` | `VARCHAR(500)` | Yes | JSON-encoded 6D list, same pattern as `mfcc_vector` |
| `tempogram_ratio_vector` | `VARCHAR(500)` | Yes | JSON-encoded ~10D list |
| `beat_loudness_band_ratio` | `VARCHAR(500)` | Yes | JSON-encoded 6D list |

### 7.2 Design Decisions

- **All nullable**: existing 2,827 rows get `NULL` — no backfill required
- **VARCHAR(500) for vectors**: same pattern as existing `mfcc_vector` and `chroma` columns
- **JSON encoding**: `json.dumps(list)` for vectors, `json.loads()` for reading — consistent with existing code
- **No CHECK constraints**: ranges are soft (will vary by track), not hard invariants
- **Backward compatible**: NULL columns don't affect existing queries or services

### 7.3 Alembic Migration

Single migration file adding 6 columns with `batch_alter_table` for SQLite compatibility:

```python
def upgrade():
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.add_column(sa.Column("danceability", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("dynamic_complexity", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("dissonance_mean", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("tonnetz_vector", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("tempogram_ratio_vector", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("beat_loudness_band_ratio", sa.String(500), nullable=True))

def downgrade():
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.drop_column("beat_loudness_band_ratio")
        batch_op.drop_column("tempogram_ratio_vector")
        batch_op.drop_column("tonnetz_vector")
        batch_op.drop_column("dissonance_mean")
        batch_op.drop_column("dynamic_complexity")
        batch_op.drop_column("danceability")
```

### 7.4 ORM Model Update

Add 6 new `mapped_column()` entries to `TrackAudioFeaturesComputed` in `app/models/features.py`:

```python
danceability: Mapped[float | None] = mapped_column(Float, nullable=True)
dynamic_complexity: Mapped[float | None] = mapped_column(Float, nullable=True)
dissonance_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
tonnetz_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
tempogram_ratio_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
beat_loudness_band_ratio: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

## 8. Testing Strategy

### 8.1 Unit Tests (per analyzer)

6 new test files in `tests/utils/`:

| File | Tests | Synthetic signal |
|------|-------|------------------|
| `test_danceability.py` | Happy path (120 BPM kick), graceful skip (no essentia), edge (silence) | Kick pattern at 120 BPM |
| `test_tempogram.py` | Happy path (click track), graceful skip (no librosa), edge (short audio) | Sine + 130 BPM clicks |
| `test_dissonance.py` | Happy path (sine=low), comparative (sine < noise), graceful skip | Pure sine vs white noise |
| `test_dynamic_complexity.py` | Happy path (fade), comparative (constant < fade), graceful skip | Constant vs fade in/out |
| `test_tonnetz.py` | Happy path (440Hz), vector length check (== 6), graceful skip | Pure 440Hz sine (A4) |
| `test_beats_loudness.py` | Happy path (with beat_times), no beat_times error, graceful skip | Kick pattern with known beats |

### 8.2 Test Design Rules

- **Property checks**: validate type, range, vector length — not exact floating-point values
- **Comparative tests**: relative assertions (`sine_dissonance < noise_dissonance`) — robust to library version changes
- **Graceful skip**: mock `ImportError` for optional library, verify `AnalyzerResult(success=False)`
- **Edge cases**: silence, very short audio (< 1 sec) — no crash, sensible error or default
- **Minimum 3 tests per analyzer**: happy path + graceful skip + edge case

### 8.3 Integration Tests

- Existing `verify_audio_pipeline.py` auto-discovers new analyzers via `registry.discover()` — no modifications needed
- Pipeline two-phase execution tested by running full pipeline with all 14 analyzers (8 existing + 6 new)
- Verify `beat_loudness_band_ratio` is populated when `BeatDetector` succeeds

### 8.4 Migration Tests

- Standard alembic cycle: `upgrade head` -> `downgrade -1` -> `upgrade head`
- Verify columns created, dropped, and re-created cleanly
- No data migration needed (all new columns are nullable)

## 9. Implementation Order

1. **BaseAnalyzer**: add `depends_on` ClassVar + `prior_results` parameter
2. **BeatDetector**: export `beat_times` in output dict
3. **5 independent analyzers**: danceability, tempogram, dissonance, dynamic_complexity, tonnetz
4. **1 dependent analyzer**: beats_loudness
5. **Pipeline**: two-phase execution
6. **Tests**: 6 test files + pipeline integration
7. **ORM model**: add 6 columns to `TrackAudioFeaturesComputed`
8. **Alembic migration**: single migration file

## 10. Future Cycles (Out of Scope)

| Cycle | Scope | Depends on |
|-------|-------|------------|
| Classifier Enrichment | Add P1 features to `SubgenreProfile` weights | This spec |
| Scoring Enrichment | Add P1 features to `TransitionScorer` components | This spec |
| P2 Analyzers | `spectral_contrast`, `rhythm_patterns`, `timbral_similarity`, `onset_strength_profile` | This spec |
| Unused Features | Use 20 existing unused features in classifier/scoring | Independent |
