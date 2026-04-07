# Audio Analysis Pipeline

## Analyzer Registry

Plugin-based architecture: analyzers register themselves with capabilities and required dependencies.

```text
AnalyzerRegistry (7 implemented)
├── core (always available, pure Python + numpy)
│   ├── LoudnessAnalyzer    → integrated_lufs, short_term, momentary, rms, peak, crest, LRA
│   ├── EnergyAnalyzer      → mean, max, std, slope, 7-band breakdown, ratios
│   └── SpectralAnalyzer    → centroid, rolloff, flatness, flux, slope, contrast, HNR
│
├── librosa (requires [audio] extra)
│   ├── BPMDetector         → bpm, confidence, stability, variable_tempo
│   ├── KeyDetector         → key_code, confidence, atonality, chroma_vector
│   ├── BeatDetector        → beat positions, onset_rate, pulse_clarity, kick_prominence, hp_ratio
│   └── MFCCExtractor       → 13-coefficient vector
│
├── NOT YET IMPLEMENTED (planned)
│   ├── GrooveAnalyzer      → rhythmic complexity, swing metrics
│   └── StructureAnalyzer   → section boundaries (intro, drop, breakdown, outro, ...)
│
└── NOT YET IMPLEMENTED (planned, requires [stems] extra)
    └── StemSeparator       → vocals, drums, bass, other (demucs/htdemucs)
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

```
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
