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

Lazy-computed shared intermediates. Pattern from SigFeat/librosa.

Each property computes on first access, caches for subsequent analyzers.
All analyzers in a pipeline run share the same context instance.

**Lazy properties:**
- `stft` — windowed STFT matrix (used by spectral, energy band decomposition, key)
- `magnitude` — `|STFT|` (used by spectral features, band energy)
- `freqs` — FFT frequency bins (used by spectral, energy)
- `frame_energies` — normalized short-time energy array (used by energy, structure)

**Thread safety:** Context is created per-track, used within one async task.
No concurrent mutation concerns since lazy properties are computed once.

**Memory:** For a 60s track at 22050 Hz: STFT ~4 MB, frame_energies ~10 KB.
Acceptable for offline analysis.

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

    async def analyze(self, ctx: AnalysisContext) -> AnalyzerResult:
        """Template Method — guard + delegate."""
        if len(ctx.samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")
        try:
            features = await self._extract(ctx)
            return AnalyzerResult(analyzer_name=self.name, features=features)
        except Exception as e:
            return AnalyzerResult(analyzer_name=self.name, success=False, error=str(e))

    @abstractmethod
    async def _extract(self, ctx: AnalysisContext) -> dict[str, Any]: ...

class AnalyzerRegistry:
    def discover(self) -> None:
        """Auto-scan analyzers/ package. No hardcoded imports."""
        import importlib, pkgutil
        import app.audio.analyzers as pkg
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name != "base":
                importlib.import_module(f"app.audio.analyzers.{info.name}")
        for name, cls in _ANALYZER_REGISTRY.items():
            instance = cls()
            if instance.is_available():
                self._analyzers[name] = instance
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

All analyzers: remove empty signal guard (handled by `BaseAnalyzer.analyze()`), add `@register_analyzer` decorator, change signature to `_extract(self, ctx) -> dict`.

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

**Three changes:**
1. `AudioLoader` injected (was inline `_load_audio`)
2. `AnalysisContext` created once per track
3. `asyncio.gather()` for parallel execution (was sequential `for` loop)

```python
class AnalysisPipeline:
    def __init__(self, registry: AnalyzerRegistry, loader: AudioLoader) -> None:
        self._registry = registry
        self._loader = loader

    async def analyze(self, file_path, analyzers=None, max_duration=None) -> PipelineResult:
        signal = await self._loader.load(file_path)
        # clip if needed ...
        ctx = AnalysisContext(signal)
        instances = [self._registry.get(n) for n in names if ...]
        results = await asyncio.gather(*(a.analyze(ctx) for a in instances))
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
| Files in `app/audio/` | 10 flat | 16 structured (3 subdirs) |
| Pipeline execution | Sequential | Parallel (`asyncio.gather`) |
| Steps to add new analyzer | Edit `discover()` + new file | New file + `@register_analyzer` |
| Data lines in classifier | 122 (inline dict) | 0 (separate `profiles.py`) |
| Mutable class attrs | `set()`, `list` | `frozenset()`, `ClassVar` |

## 8. Migration Strategy

Refactoring order to keep tests green at each step:

1. **Create `core/`** — extract types, framing, spectral, loader. Old code still works.
2. **Create `analyzers/base.py`** — BaseAnalyzer + registry + decorator. Old analyzers untouched.
3. **Migrate analyzers one by one** — each gets `@register_analyzer`, `_extract(ctx)`, uses `core/`. Run tests after each.
4. **Create `classification/`** — extract profiles, classifier. Old import paths still work.
5. **Refactor `pipeline.py`** — inject loader, create context, parallel execution.
6. **Update services** — change import paths, add `AudioLoader()`.
7. **Delete old files** — `registry.py`, `mood.py`.
8. **Update tests** — new import paths, test context sharing.

## 9. Risks

| Risk | Mitigation |
|------|------------|
| `asyncio.gather` changes error behavior | Each analyzer wrapped in try/except by Template Method |
| Lazy context thread safety | Context is per-track, single async task — no concurrency issue |
| `pkgutil.iter_modules` misses files | Fallback: explicit import list as safety net |
| Breaking service imports | Step 6 updates all 4 consumers; grep verifies completeness |
| STFT parameters differ between analyzers | Currently identical (2048/512) — `FrameParams` centralizes |

## 10. Research References

- **Essentia** — AlgorithmFactory + Pool pattern, streaming DAG with fan-out
- **Librosa** — Dual-input pattern (y OR S), hierarchical caching, `_spectrogram()` helper
- **Lhotse** — `@register_extractor` decorator, config-as-dataclass, storage delegation
- **SigFeat** — Feature dependency declaration, auto-graph construction, block processing
- **YAAFE** — Two-layer arch (Python spec + C++ impl), automatic shared node dedup
- **MIRFLEX (ISMIR 2024)** — Modular pluggable extractors, dual output format
- **Spotify** — 42-dim vectors, hybrid rules+ML, batch annotation pipelines
- Industry finding: No commercial DJ software (Rekordbox, Traktor, djay Pro) does automatic subgenre classification — our classifier is a unique capability
