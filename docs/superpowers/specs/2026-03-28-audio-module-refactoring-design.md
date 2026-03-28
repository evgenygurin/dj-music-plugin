# Audio Module Refactoring — Design Spec

> Date: 2026-03-28
> Scope: `app/audio/` + services (`AudioService`, `TieredPipeline`, `CurationService`)
> Approach: Layered Architecture with Plugin Registry
> Status: Draft

## 1. Problem Statement

The `app/audio/` module (1,739 lines, 8 analyzers) has accumulated structural debt:

| Problem | Evidence | SOLID violation |
|---------|----------|-----------------|
| Duplicated frame energy computation | `energy.py:44-54` = `structure.py:71-81` (identical loop) | DRY |
| Duplicated FFT/windowing | `spectral.py`, `energy.py`, `key.py` each compute STFT independently | DRY |
| 8 copies of empty signal guard | Every analyzer: `if len(samples) == 0: return AnalyzerResult(...)` | DRY |
| Hardcoded `frame_length=2048, hop_length=512` | In 3 files (`energy.py`, `spectral.py`, `structure.py`) | DRY |
| Audio loading in Pipeline | 70 lines nested try/except in `pipeline.py:90-164` | SRP |
| Hardcoded analyzer discovery | `discover()` imports 8 classes explicitly | OCP |
| Mutable class-level defaults | `BaseAnalyzer.capabilities: set[str] = set()` — shared state | Encapsulation |
| Sequential analyzer execution | `for name in analyzer_names:` loop in pipeline | Performance |
| Data mixed with logic | 122-line `SUBGENRE_PROFILES` dict inline in `mood.py` | SRP |
| No shared computation | Each analyzer recomputes FFT from scratch | Performance |

## 2. Goals

- Eliminate all code duplication (DRY)
- Clean separation: DSP primitives -> Analyzers -> Pipeline (SRP)
- Plugin architecture for analyzers — new analyzer = one file (OCP)
- Shared computation via lazy `AnalysisContext` (Performance)
- Parallel analyzer execution (Performance)
- Type-safe, immutable data structures (Correctness)
- Preserve external API compatibility for services (Backward compat)

## 3. Non-Goals

- ML-based classification (rule-based is correct for ~680 tracks)
- Streaming/real-time analysis (offline batch only)
- Computation graph / DAG engine (overkill for 8 analyzers)
- Changes to DB models (`app/models/audio.py`)
- Changes to MCP tools

## 4. Architecture

### 4.1 Layer Diagram

```text
Layer 1: core/          DSP primitives (0 app/ deps, pure numpy)
            |
Layer 2: analyzers/     Feature extractors (depend on core/)
         classification/ Mood classifier (depend on core/)
            |
Layer 3: pipeline.py    Orchestrator (uses L1 + L2)
            |
         services/      AudioService, TieredPipeline, CurationService
```

### 4.2 Directory Structure

```text
app/audio/
├── core/                          # Layer 1: DSP primitives
│   ├── __init__.py                # re-exports: AudioSignal, AnalyzerResult, FrameParams,
│   │                              #   AnalysisContext, AudioLoader
│   ├── types.py                   # AudioSignal, AnalyzerResult, FrameParams
│   ├── context.py                 # AnalysisContext (lazy STFT, energies, freqs, magnitude)
│   ├── loader.py                  # AudioLoader (soundfile -> librosa -> wave fallback)
│   ├── framing.py                 # compute_frame_energies(), compute_energy_slope()
│   └── spectral.py                # compute_stft(), band_energies(), spectral_centroid(),
│                                  #   spectral_rolloff(), spectral_flatness()
│
├── analyzers/                     # Layer 2: Feature extractors
│   ├── __init__.py                # re-exports: BaseAnalyzer, AnalyzerRegistry,
│   │                              #   register_analyzer
│   ├── base.py                    # BaseAnalyzer ABC (Template Method), @register_analyzer
│   │                              #   decorator, AnalyzerRegistry (auto-discovery)
│   ├── loudness.py                # LoudnessAnalyzer — EBU R128 (K-weighting, gated LUFS,
│   │                              #   true peak, crest factor, LRA)
│   ├── energy.py                  # EnergyAnalyzer — frame energy + 6-band decomposition
│   │                              #   (uses core.framing, core.spectral)
│   ├── spectral.py                # SpectralAnalyzer — centroid, rolloff, flatness, flux,
│   │                              #   slope, contrast (uses core.spectral via ctx)
│   ├── structure.py               # StructureAnalyzer — novelty-based section detection
│   │                              #   (uses core.framing via ctx.frame_energies)
│   ├── bpm.py                     # BPMDetector — librosa beat tracking
│   ├── key.py                     # KeyDetector — chroma CQT + Krumhansl-Kessler + HNR
│   ├── beat.py                    # BeatDetector — onset rate, pulse clarity, kick, HP ratio
│   └── mfcc.py                    # MFCCExtractor — 13 MFCC coefficients
│
├── classification/                # Layer 2b: Mood/genre classification
│   ├── __init__.py                # re-exports: MoodClassifier, MoodResult,
│   │                              #   SubgenreProfile, ALL_PROFILES
│   ├── classifier.py              # MoodClassifier — generic Gaussian scoring engine
│   └── profiles.py                # SubgenreProfile dataclass, FeatureTarget dataclass,
│                                  #   15 techno subgenre profile instances, ALL_PROFILES tuple
│
├── pipeline.py                    # Layer 3: AnalysisPipeline (parallel via asyncio.gather,
│                                  #   creates AnalysisContext, delegates loading to AudioLoader)
├── level_config.py                # AnalysisLevel enum, get_analyzers_for_level(),
│                                  #   get_clip_duration() — UNCHANGED
├── timeseries.py                  # TimeseriesStorage (NPZ) — UNCHANGED
└── temp_download.py               # temp_download_track() context manager — UNCHANGED
```

### 4.3 Files Removed

| File | Lines | Replacement |
|------|-------|-------------|
| `registry.py` | 104 | Split into `core/types.py` (AudioSignal, AnalyzerResult) + `analyzers/base.py` (BaseAnalyzer, AnalyzerRegistry, @register_analyzer) |
| `mood.py` | 226 | Split into `classification/classifier.py` (MoodClassifier, MoodResult) + `classification/profiles.py` (SubgenreProfile, FeatureTarget, 15 profiles) |

## 5. Design Details

### 5.1 Core Types (`core/types.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import numpy as np

@dataclass(frozen=True, slots=True)
class FrameParams:
    """Immutable frame/hop configuration. Single source of truth.
    Replaces hardcoded frame_length=2048, hop_length=512 in 3 files."""
    frame_length: int = 2048
    hop_length: int = 512

@dataclass
class AudioSignal:
    """Mono audio signal loaded once per pipeline run."""
    samples: np.ndarray      # mono float32
    sample_rate: int
    duration_seconds: float
    file_path: str = ""

@dataclass
class AnalyzerResult:
    """Result from a single analyzer run."""
    analyzer_name: str
    features: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None
```

### 5.2 Analysis Context (`core/context.py`)

Eagerly-computed shared intermediates. Pattern from SigFeat/librosa.

All shared intermediates are computed upfront in `__init__`, then shared
read-only across all analyzers in a pipeline run.

**Computed properties:**
- `stft` — windowed STFT matrix (used by spectral, energy band decomposition, key)
- `magnitude` — `|STFT|` (used by spectral features, band energy)
- `freqs` — FFT frequency bins (used by spectral, energy)
- `frame_energies` — normalized short-time energy array (used by energy, structure)

**Why eager, not lazy:** Analyzers run in parallel via thread pool (see 5.8).
Lazy properties would create check-then-act race conditions under concurrent
access. Since all analyzers need STFT/magnitude anyway, eager computation
eliminates the race without meaningful overhead.

**Thread safety:** All properties are computed once in `__init__`, then
read-only. Multiple threads can safely read the same `AnalysisContext`.

**Memory:** For a 60s track at 22050 Hz: STFT ~4 MB, frame_energies ~10 KB.
Acceptable for offline analysis.

**Sample rate assumption:** Context assumes `AudioLoader` has already
resampled to the target sample rate (default 22050 Hz). STFT with
`frame_length=2048` at 22050 Hz gives Nyquist of 11025 Hz — sufficient
for all analyzers including spectral contrast bands up to 11025 Hz.

### 5.3 Audio Loader (`core/loader.py`)

Extracted from `AnalysisPipeline._load_audio()` (70 lines, SRP violation).

```python
class AudioLoader:
    """Multi-backend audio file loader.

    Fallback chain: soundfile -> librosa -> wave (stdlib).
    Resamples to target sample rate if needed.
    """
    def __init__(self, target_sr: int = 22050):
        self._target_sr = target_sr

    async def load(self, file_path: str) -> AudioSignal: ...
```

Injected into `AnalysisPipeline` constructor (Dependency Inversion).

`target_sr` is passed as constructor parameter, NOT read from `settings` —
keeps `core/` free of `app/` dependencies. Callers pass `settings.audio_sample_rate`.

### 5.4 DSP Primitives (`core/framing.py`, `core/spectral.py`)

Pure functions, zero side effects, zero app/ dependencies.

**`framing.py`** — extracted from `energy.py:44-58` and `structure.py:71-86`:
- `compute_frame_energies(samples, frame_length, hop_length) -> np.ndarray`
- `compute_energy_slope(energies: np.ndarray) -> float`

**`spectral.py`** — extracted from `spectral.py`, `energy.py`, `key.py`:
- `compute_stft(samples, frame_length, hop_length, window="hann") -> np.ndarray`
- `band_energies(magnitude, freqs, bands) -> dict[str, float]`
- `spectral_centroid(magnitude, freqs) -> float`
- `spectral_rolloff(magnitude, freqs, pct) -> float`
- `spectral_flatness(magnitude) -> float`

### 5.5 Analyzer Base + Registry (`analyzers/base.py`)

**GoF patterns:**
- **Template Method** — `analyze()` handles empty signal guard + error wrapping; subclass implements `_extract(ctx)`.
- **Registry** — `@register_analyzer` decorator populates global dict. `AnalyzerRegistry.discover()` uses `pkgutil.iter_modules()` for auto-scan (Open/Closed).

```python
_ANALYZER_REGISTRY: dict[str, type[BaseAnalyzer]] = {}

def register_analyzer(cls: type[BaseAnalyzer]) -> type[BaseAnalyzer]:
    """Decorator for auto-registration. Pattern: Lhotse @register_extractor."""
    _ANALYZER_REGISTRY[cls.name] = cls
    return cls

class BaseAnalyzer(ABC):
    name: ClassVar[str] = ""
    capabilities: ClassVar[frozenset[str]] = frozenset()  # immutable (was mutable set)
    required_packages: ClassVar[list[str]] = []

    def run(self, ctx: AnalysisContext) -> AnalyzerResult:
        """Template Method — guard + delegate. Synchronous (CPU-bound).

        Called via asyncio.to_thread() by pipeline for parallelism.
        """
        if len(ctx.samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")
        try:
            features = self._extract(ctx)
            return AnalyzerResult(analyzer_name=self.name, features=features)
        except Exception as e:
            return AnalyzerResult(analyzer_name=self.name, success=False, error=str(e))

    @abstractmethod
    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Subclass implements. Synchronous — pure computation, no I/O."""
        ...

class AnalyzerRegistry:
    def discover(self) -> None:
        """Auto-scan analyzers/ package. No hardcoded imports.

        Wraps each import in try/except to handle optional dependencies
        (librosa-based analyzers: bpm, key, beat, mfcc).
        """
        import importlib, pkgutil
        import app.audio.analyzers as pkg
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name in ("base", "__init__"):
                continue
            try:
                importlib.import_module(f"app.audio.analyzers.{info.name}")
            except ImportError:
                pass  # Optional dependency (librosa, scipy) not installed
        for name, cls in _ANALYZER_REGISTRY.items():
            try:
                instance = cls()
                if instance.is_available():
                    self._analyzers[name] = instance
            except ImportError:
                pass  # Optional dependency not installed — skip silently
```

### 5.6 Analyzer Migration

Each analyzer changes from `analyze(signal: AudioSignal)` to `_extract(ctx: AnalysisContext)`.

**Key transformations per analyzer:**

| Analyzer | Before | After |
|----------|--------|-------|
| `energy.py` | Computes frame_energies inline (12 lines) + FFT band decomposition | Uses `ctx.frame_energies` + `core.spectral.band_energies(ctx.magnitude, ctx.freqs)` |
| `structure.py` | Computes frame_energies inline (12 lines, identical copy) | Uses `ctx.frame_energies` |
| `spectral.py` | Computes STFT per-frame in loop (30 lines) | Uses `ctx.stft`, `ctx.magnitude`, `ctx.freqs` |
| `loudness.py` | K-weighting + gated LUFS (self-contained) | Minimal change — uses `ctx.samples`, `ctx.sr` |
| `bpm.py` | librosa beat_track | Uses `ctx.samples`, `ctx.sr` |
| `key.py` | librosa chroma + HNR | Uses `ctx.samples`, `ctx.sr` |
| `beat.py` | librosa HPSS + onset detection | Uses `ctx.samples`, `ctx.sr` |
| `mfcc.py` | librosa MFCC | Uses `ctx.samples`, `ctx.sr` |

All analyzers: remove empty signal guard (handled by `BaseAnalyzer.run()`),
add `@register_analyzer` decorator, change from `async def analyze(signal) -> AnalyzerResult`
to synchronous `def _extract(ctx) -> dict` (CPU-bound, no I/O).

**Note on `settings` in analyzers:** Analyzers that use `settings` (e.g.,
`beat.py` uses `settings.audio_beat_analysis_duration`, `mfcc.py` uses
`settings.audio_mfcc_n_coeffs`) keep those imports. Only `core/` is
app-dependency-free. Analyzers are Layer 2 and may depend on `app.config`.

**Note on `FrameParams` scope:** `FrameParams` applies to STFT-based analyzers
(energy, spectral, structure). `LoudnessAnalyzer` uses its own windowing
(400ms/3s EBU R128 windows) and is unaffected by `FrameParams`.

### 5.7 Classification (`classification/`)

**`profiles.py`** — data as frozen dataclasses:

```python
@dataclass(frozen=True, slots=True)
class FeatureTarget:
    weight: float       # importance
    ideal: float        # Gaussian center
    tolerance: float    # Gaussian sigma

@dataclass(frozen=True, slots=True)
class SubgenreProfile:
    subgenre: TechnoSubgenre
    features: dict[str, FeatureTarget]
    catch_all_penalty: float = 0.0

ALL_PROFILES: tuple[SubgenreProfile, ...] = (AMBIENT_DUB, ..., HARD_TECHNO)
```

**`classifier.py`** — generic engine:

```python
@dataclass(frozen=True, slots=True)
class MoodResult:
    mood: TechnoSubgenre
    confidence: float
    scores: dict[TechnoSubgenre, float]
    reasoning: str
    top_matches: list[tuple[TechnoSubgenre, float]]  # NEW: top-3

class MoodClassifier:
    def __init__(self, profiles: Sequence[SubgenreProfile] = ALL_PROFILES): ...
    def classify(self, features: dict[str, Any]) -> MoodResult: ...
    def _score_profile(self, profile, features) -> float: ...
```

### 5.8 Pipeline Refactoring

**Four changes:**
1. `AudioLoader` injected (was inline `_load_audio`)
2. `AnalysisContext` created once per track (eager computation)
3. `asyncio.to_thread()` for true parallel execution of CPU-bound analyzers
4. `PipelineResult` stays in `pipeline.py` (not moved to `core/types.py`)

**Why `asyncio.to_thread`, not `asyncio.gather`:** All 8 analyzers are CPU-bound
(numpy FFT, matrix ops, librosa calls). None contain `await` in their computation.
Plain `asyncio.gather` would execute them sequentially — identical to the current
`for` loop. `asyncio.to_thread()` offloads each analyzer to the default thread pool,
achieving true parallelism for numpy/C-extension work that releases the GIL.

Analyzers expose synchronous `_extract(ctx) -> dict` (no async needed for pure
computation). `BaseAnalyzer.run(ctx)` wraps it synchronously. Pipeline dispatches
via `asyncio.to_thread(a.run, ctx)`.

```python
class AnalysisPipeline:
    def __init__(self, registry: AnalyzerRegistry, loader: AudioLoader) -> None:
        self._registry = registry
        self._loader = loader

    async def analyze(self, file_path, analyzers=None, max_duration=None) -> PipelineResult:
        signal = await self._loader.load(file_path)
        # clip if needed ...
        ctx = AnalysisContext(signal)  # eager: STFT, magnitude, freqs computed here
        instances = [self._registry.get(n) for n in names if ...]
        # True parallelism — CPU-bound work offloaded to thread pool
        results = await asyncio.gather(
            *(asyncio.to_thread(a.run, ctx) for a in instances)
        )
        # collect + merge ...
```

### 5.9 Service Layer Impact

| Service | Change |
|---------|--------|
| `AudioService.__init__` | `AnalysisPipeline(registry)` -> `AnalysisPipeline(registry, AudioLoader())` |
| `AudioService._classify_existing` | `from app.audio.mood` -> `from app.audio.classification` |
| `TieredPipeline` | No changes — receives pipeline via DI |
| `CurationService` | `from app.audio.mood` -> `from app.audio.classification` |
| `app/mcp/dependencies.py` | Add `AudioLoader()` to pipeline construction |
| `app/server.py` | Same as dependencies |

## 6. Design Patterns Summary

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Template Method** (GoF) | `BaseAnalyzer.analyze()` -> `_extract()` | Eliminate 8 guard copies, uniform error handling |
| **Registry** (GoF) | `@register_analyzer` + `AnalyzerRegistry` | Open/Closed — new analyzer = one file |
| **Strategy** (GoF) | `MoodClassifier(profiles)` | Classifier is generic engine, profiles are swappable |
| **Dependency Injection** | `AnalysisPipeline(registry, loader)` | Testability, SRP |
| **Lazy Initialization** | `AnalysisContext` properties | Shared computation without upfront cost |
| **Facade** | `core/__init__.py` re-exports | Clean public API for layer |

## 7. Metrics

| Metric | Before | After |
|--------|--------|-------|
| Duplicated lines (frame energy) | 12 | 0 |
| Duplicated lines (FFT/windowing) | 18 | 0 |
| Duplicated guard checks | 8 | 1 (BaseAnalyzer) |
| Hardcoded `2048/512` | 3 files | 1 (`FrameParams`) |
| Files in `app/audio/` | 16 flat (+ 2 dirs) | 18 structured (3 subdirs) |
| Pipeline execution | Sequential | Parallel (`asyncio.to_thread`) |
| Steps to add new analyzer | Edit `discover()` + new file | New file + `@register_analyzer` |
| Data lines in classifier | 122 (inline dict) | 0 (separate `profiles.py`) |
| Mutable class attrs | `set()`, `list` | `frozenset()`, `ClassVar` |

## 8. Migration Strategy

Refactoring order to keep tests green at each step:

1. **Create `core/`** — extract types, framing, spectral, loader. Add re-export
   aliases in old `registry.py` so existing imports still work. Tests green.
2. **Create `analyzers/base.py`** — new BaseAnalyzer + registry + decorator.
   Old `registry.py` re-exports new classes for backward compat. Tests green.
3. **Migrate ALL 8 analyzers in one step** — they are small (40-250 lines each)
   and share the same API change (`async analyze(signal)` -> `def _extract(ctx)`).
   Migrating one-by-one is impractical: old and new analyzers have incompatible
   base classes. Run full test suite after. Tests may need import path updates.
4. **Create `classification/`** — extract profiles + classifier. Add re-export
   alias in old `mood.py` for backward compat. Update `test_mood.py` assertions
   to handle new `MoodResult.top_matches` field. Tests green.
5. **Refactor `pipeline.py`** — inject loader, create eager context,
   `asyncio.to_thread()` dispatch. `PipelineResult` stays in `pipeline.py`.
6. **Update services** — change import paths, add `AudioLoader(settings.audio_sample_rate)`.
7. **Update tests** (~15 import statements across 7+ test files):
   - `from app.audio.registry import AudioSignal` -> `from app.audio.core import AudioSignal`
   - `from app.audio.mood import MoodClassifier` -> `from app.audio.classification import MoodClassifier`
   - `from app.audio.registry import AnalyzerRegistry` -> `from app.audio.analyzers import AnalyzerRegistry`
   - Add tests for `AnalysisContext` eager computation.
   - Add tests for `@register_analyzer` auto-discovery.
   - Verify `MoodResult.top_matches` in mood tests.
8. **Delete old files** — `registry.py`, `mood.py` (after all imports updated).
9. **Clean up** — remove re-export aliases, update `CLAUDE.md` files in `app/audio/`.

## 9. Risks

| Risk | Mitigation |
|------|------------|
| `asyncio.to_thread` + shared context | Context is eager (computed in `__init__`), read-only during analysis — no race |
| `pkgutil.iter_modules` + optional deps | Each import wrapped in `try/except ImportError` |
| `pkgutil.iter_modules` misses files | Fallback: explicit import list as safety net in `discover()` |
| Breaking service imports | Step 6 updates all 4 consumers; grep verifies completeness |
| STFT parameters differ between analyzers | Currently identical (2048/512) — `FrameParams` centralizes |
| `core/spectral.py` naming clash with `analyzers/spectral.py` | Both use absolute imports — no ambiguity. Consider renaming to `core/spectral_ops.py` if confusing |
| Test migration scope | ~15 import changes across 7+ files, step 7 details all paths |
| `FrameParams` applied to LoudnessAnalyzer | Documented: `FrameParams` is for STFT-based analyzers only, loudness uses own EBU R128 windows |

## 10. Research References

- **Essentia** — AlgorithmFactory + Pool pattern, streaming DAG with fan-out
- **Librosa** — Dual-input pattern (y OR S), hierarchical caching, `_spectrogram()` helper
- **Lhotse** — `@register_extractor` decorator, config-as-dataclass, storage delegation
- **SigFeat** — Feature dependency declaration, auto-graph construction, block processing
- **YAAFE** — Two-layer arch (Python spec + C++ impl), automatic shared node dedup
- **MIRFLEX (ISMIR 2024)** — Modular pluggable extractors, dual output format
- **Spotify** — 42-dim vectors, hybrid rules+ML, batch annotation pipelines
- Industry finding: No commercial DJ software (Rekordbox, Traktor, djay Pro) does automatic subgenre classification — our classifier is a unique capability
