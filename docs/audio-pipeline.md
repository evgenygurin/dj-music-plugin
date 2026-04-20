# Audio Analysis Pipeline

## Analyzer Registry

Plugin-based architecture: analyzers register themselves with capabilities and required dependencies.

```text
AnalyzerRegistry (18 implemented)
├── core (always available, pure Python + numpy)
│   ├── LoudnessAnalyzer        → integrated_lufs, short_term, momentary, rms, peak, crest, LRA
│   ├── EnergyAnalyzer          → mean, max, std, slope, 7-band breakdown, ratios
│   ├── SpectralAnalyzer        → centroid, rolloff, flatness, flux, slope, contrast, HNR
│   └── StructureAnalyzer       → section boundaries (intro, drop, breakdown, outro, ...)
│
├── librosa (requires [audio] extra)
│   ├── BPMDetector             → bpm, confidence, stability, variable_tempo
│   ├── KeyDetector             → key_code, confidence, atonality, chroma_vector
│   ├── BeatDetector            → beat positions, onset_rate, pulse_clarity, kick_prominence, hp_ratio
│   ├── MFCCExtractor           → 13-coefficient vector
│   ├── TempogramAnalyzer       → tempogram ratio vector
│   ├── TonnetzAnalyzer         → tonnetz features for harmonic analysis
│   ├── BpmHistogramAnalyzer    → BPM histogram (depends on beat)
│   └── PhraseAnalyzer          → phrase boundaries (depends on beat)
│
├── essentia (requires [audio] extra)
│   ├── BeatsLoudnessAnalyzer   → beat-loudness band ratios
│   ├── DanceabilityAnalyzer    → danceability score (unbounded)
│   ├── DissonanceAnalyzer      → dissonance mean
│   ├── DynamicComplexityAnalyzer → dynamic complexity score
│   ├── PitchSalienceAnalyzer   → pitch salience mean
│   └── SpectralComplexityAnalyzer → spectral complexity mean
│
└── NOT YET IMPLEMENTED (planned, requires [stems] extra)
    └── StemSeparator           → vocals, drums, bass, other (demucs/htdemucs)
```

## Pipeline Orchestration

```python
# Pipeline runs all available analyzers, handles partial failures
pipeline = AnalysisPipeline(registry)
result = await pipeline.analyze(audio_path, track_id)

# result.features: dict of computed features (47 values)
# result.sections: list of detected sections
# result.errors: list of {analyzer, error} for failed analyzers
# result.pipeline_run_id: FK to feature_extraction_runs table
```

**Partial failure**: if BPMDetector fails (librosa not installed), pipeline continues with other analyzers. Known errors bubble up, unexpected errors wrapped in `PipelineError`.

### Per-Analyzer Clip Duration

Heavy librosa analyzers (`beat`, `bpm`, `key`, `spectral`, `mfcc`, `tonnetz`,
`tempogram`, `pitch_salience`) declare a 60-second clip via the
`clip_duration_s` ClassVar on `BaseAnalyzer`. The pipeline groups analyzers
by their requested clip duration and builds **one** `AnalysisContext` per
unique value — typically two contexts per track:

- **Full-track context** for `loudness` (LUFS integration), `structure`
  (section detection), `energy` (cheap pure-numpy).
- **Stitched 60s context** for everything else.

`librosa.effects.hpss`, `chroma_cqt`, `beat_track`, etc. are all O(N) in
samples — clipping to 60s gives ~5x speedup on a 6-7 minute techno track
with negligible loss of fidelity (BPM, key, MFCC, timbre are stable across
the track).

#### Stitched Multi-Window Strategy

Instead of a single center window, the 60-second clip is built from
**3 windows of 20s** sampled at positions ~1/6, 3/6, 5/6 of the source.
Each window gets a 20ms hann-fade in and out to avoid click artifacts at
the boundaries (which would otherwise create false onsets in beat
detection). Then they are concatenated:

```text
source: [intro] ─── [build] ─── [drop] ─── [break] ─── [outro]
                ↑              ↑                ↑
              W1 (20s)      W2 (20s)         W3 (20s)
                                ↓
            stitched 60s clip with hann fades at joins
```

**Why multi-window beats single-window**:

1. Skips intro/outro automatically (window centers are at 17%/50%/83%)
2. Captures variation between sections — a track with a sparse breakdown
   in the middle gets balanced sampling from build, drop, and outro,
   not just the breakdown itself
3. Robust to producers who put the heaviest groove in the second half
4. Same compute budget (still 60s of audio total)
5. Statistically better aggregates: mean MFCC, mean chroma, mean centroid
   over 3 distinct regions converge faster to the track-wide value than
   over a single contiguous region

**Why fades**: discontinuities at window boundaries create spectral flux
spikes that look like onsets to `librosa.beat.beat_track`, biasing BPM
detection. A 20ms hann ramp drives the boundary samples to zero
smoothly. Mean-aggregated features (key chroma, MFCC, spectral centroid)
ignore the brief hann attenuation as noise.

**Fallback**: tracks shorter than `n_windows × window_size` (e.g. <60s
when N=3) get a single centered window, since non-overlapping
sub-windows aren't possible.

### Shared Onset Envelope

`bpm`, `beat`, and `tempogram` all consume `librosa.onset.onset_strength`.
Instead of recomputing it three times the pipeline caches it on the
`AnalysisContext` via `ctx.get_onset_env()` — lazy + lock-protected, safe
under concurrent thread dispatch. Saves ~3s per track.

### IBI Outlier Filter (Stitching Gotcha)

The stitched clip **does not preserve beat phase across seams**. A
window ending on a beat-ON phase followed by a window starting at a
different part of the track produces ~2 spurious inter-beat intervals
per track at window boundaries (either ~0 s, "double detection", or
~2x median, "missed beat"). `find_beat_times` can also miss beats in
quiet breakdown sections where prominence/height thresholds don't
fire.

Without filtering, these ~5% outlier IBIs were enough to drive
`cv = std(IBI) / mean(IBI) > 0.15` and false-flag 62.7% of the L3+
library as `variable_tempo=True` (production snapshot 2026-04-20). The
`-0.15 scoring_variable_tempo_penalty` in transition scoring then cost
every affected pair a chunk of its `S_bpm` score.

`app.audio.analyzers.bpm.compute_tempo_stability` drops IBIs outside
`[0.5, 1.5] x median` before the CV computation. Genuine tempo drift
(techno typically < 2% CV; anything > 15% is a clear variable-tempo
signal) lives entirely inside the kept band and is still detected;
doubled / halved / missed-beat artifacts are filtered.

### ProcessPool Path: SharedMemory + Per-Worker Context Cache

When `AnalysisPipeline(use_processes=True)` is enabled, two further
optimizations kick in inside `_run_phase_processes`:

1. **SharedMemory transport for clip samples.** Each unique clip variant
   is published once into a `multiprocessing.shared_memory.SharedMemory`
   block. Workers receive only `(shm_name, dtype, shape)` and attach a
   zero-copy `np.ndarray` view onto the shared buffer instead of
   receiving the multi-MB ndarray pickled on every task. Variants
   pointing at the same underlying buffer (e.g. on a short track every
   clip-duration key collapses to the full samples) are deduped via
   `id(samples)` so a single SharedMemory block is reused. Cleanup is
   `shm.close()` + `shm.unlink()` in a `finally` block — even if
   workers still hold attached views inside their LRU cache, the
   segment name disappears from `/dev/shm` immediately so it never
   shows up as a leak. The OS releases the backing bytes once the last
   worker attachment is dropped.

2. **Per-worker AnalysisContext LRU cache.** Each worker process keeps
   a module-level `OrderedDict` mapping `(shm_name, sample_rate,
   frame_length, hop_length)` → `(SharedMemory, AnalysisContext)`. The
   first analyzer in a given (worker, clip variant) bucket pays the
   STFT/magnitude/freqs/frame_energies cost once; every subsequent
   analyzer in the same `analyze()` call that lands on the same worker
   reuses the cached context, saving ~150–300 ms per cached analyzer.
   Cache size is bounded by `settings.audio_process_worker_cache_size`
   (default 4) and entries are evicted LRU; eviction closes the cached
   SharedMemory attachment so memory is bounded at
   `max_workers * cache_max_size * avg_clip_size`. The shm name is
   unique per `analyze()` call, so cache key collisions across
   unrelated tracks are impossible — features cannot leak between
   pipeline calls.

#### Measured Overhead (6-min synthetic techno, 22050 Hz, ~30 MB buffer)

Isolated micro-benchmarks on the two optimizations, 18 analyzers per
pipeline call (the production workload):

| Step | Baseline (pickle) | SharedMemory | Speedup |
|------|-------------------|--------------|---------|
| Transport (18 × 30 MB) | ~505 ms | ~47 ms | **10.8x** |
| Of which: `_create_shared_clip` (one-time copy) | — | 34 ms | — |
| Of which: worker attach × 18 (zero-copy) | — | 13 ms | — |

| Step | Cost |
|------|------|
| `AnalysisContext` build (cold STFT + magnitude + freqs + frame_energies, 60s clip) | ~178 ms |
| Savings from LRU cache hit (per subsequent analyzer sharing the same clip variant) | ~178 ms |
| Expected savings per worker per call (8 analyzers → 7 cache hits) | **~1.25 s** |

Combined expected wall-clock saving on a warm pool, 18-analyzer
pipeline call: **~1.7 s** (0.46 s transport + ~1.25 s STFT reuse).
Actual end-to-end speedup scales with the ratio of (cached analyzer
cost + transport overhead) to the overall pipeline wall-clock, which
is dominated by the single heaviest librosa analyzer on a real
techno track (`pitch_salience` at ~6.5 s).

## Analyzer Interface

Each analyzer implements:

```python
class BaseAnalyzer(ABC):
    name: str                          # e.g., "bpm"
    capabilities: set[str]             # e.g., {"tempo", "rhythm"}
    required_packages: list[str]       # e.g., ["librosa"]

    @abstractmethod
    async def analyze(self, audio: AudioSignal) -> AnalyzerResult:
        """Run analysis on audio signal."""
        ...

    def is_available(self) -> bool:
        """Check if required packages are installed."""
        ...
```

## Audio Signal

```python
@dataclass
class AudioSignal:
    samples: np.ndarray       # mono float32
    sample_rate: int          # from settings.audio_sample_rate (22050)
    duration_seconds: float
    file_path: Path
```

Loaded once per pipeline run, shared across all analyzers.

## Timeseries Storage

Frame-level data (too large for DB) stored as NPZ files:

```text
cache/timeseries/{track_id}/
├── energy.npz          # energy per frame
├── chroma.npz          # chroma features per frame
├── spectral.npz        # spectral features per frame
└── beats.npz           # beat positions
```

DB table `timeseries_references` stores metadata: frame_count, hop_length, sample_rate, shape.

## Mood Classifier

Rule-based, no ML model. Scores each track against 15 subgenre profiles:

```text
For each subgenre:
  score = weighted_sum(feature_values × subgenre_weights)
  if subgenre in {driving, hypnotic}:
      score *= settings.mood_catch_all_penalty  # prevent domination

Winner = argmax(scores)
Confidence = (winner_score - second_score) / winner_score
```

Key discriminating features:
- `hp_ratio` (harmonic-to-percussive): ambient_dub(high) vs industrial(low)
- `spectral_centroid`: melodic_deep(low) vs acid(high)
- `energy_mean`: ambient_dub(low) vs hard_techno(high)
- `kick_prominence`: minimal(low) vs peak_time(high)
- `loudness_range`: dub_techno(wide) vs industrial(narrow)
- `spectral_flux_std`: hypnotic(low, repetitive) vs breakbeat(high, varied)

## Dependencies

| Extra | Packages | Enables |
|-------|----------|---------|
| (none) | numpy | Core analyzers: loudness, energy, spectral (3 implemented) |
| `[audio]` | librosa, soundfile | BPM, key, beat, MFCC detection (4 implemented) |
| `[stems]` | demucs, torch | Stem separation — NOT YET IMPLEMENTED |

Install: `uv sync --extra audio` or `uv sync --all-extras`
