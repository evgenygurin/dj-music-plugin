# Audio Module Refactoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `app/audio/` into a layered architecture with shared computation, parallel execution, and plugin-based analyzer discovery — eliminating all code duplication while preserving external API compatibility.

**Architecture:** Three-layer design: `core/` (DSP primitives, 0 app deps) → `analyzers/` (feature extractors with Template Method + Registry patterns) → `pipeline.py` (orchestrator with `asyncio.to_thread` parallelism). Classification extracted to `classification/` with Strategy pattern.

**Tech Stack:** Python 3.12+, numpy, librosa (optional), scipy (optional), pytest, asyncio

---

## File Structure

### New files to create

| File | Responsibility | Layer |
|------|---------------|-------|
| `app/audio/core/__init__.py` | Re-exports: AudioSignal, AnalyzerResult, FrameParams, AnalysisContext, AudioLoader | L1 |
| `app/audio/core/types.py` | AudioSignal, AnalyzerResult, FrameParams dataclasses | L1 |
| `app/audio/core/context.py` | AnalysisContext — eager STFT, magnitude, freqs, frame_energies | L1 |
| `app/audio/core/loader.py` | AudioLoader — multi-backend file loading with fallback chain | L1 |
| `app/audio/core/framing.py` | compute_frame_energies(), compute_energy_slope() | L1 |
| `app/audio/core/spectral.py` | compute_stft(), band_energies(), spectral_centroid(), etc. | L1 |
| `app/audio/analyzers/base.py` | BaseAnalyzer ABC, @register_analyzer, AnalyzerRegistry | L2 |
| `app/audio/classification/__init__.py` | Re-exports: MoodClassifier, MoodResult, SubgenreProfile | L2b |
| `app/audio/classification/classifier.py` | MoodClassifier — generic Gaussian scoring engine | L2b |
| `app/audio/classification/profiles.py` | SubgenreProfile, FeatureTarget, 15 profile instances | L2b |
| `tests/test_audio/test_core_types.py` | Tests for FrameParams, AudioSignal, AnalyzerResult | — |
| `tests/test_audio/test_core_framing.py` | Tests for compute_frame_energies(), compute_energy_slope() | — |
| `tests/test_audio/test_core_spectral.py` | Tests for compute_stft(), band_energies(), etc. | — |
| `tests/test_audio/test_core_context.py` | Tests for AnalysisContext eager computation | — |
| `tests/test_audio/test_core_loader.py` | Tests for AudioLoader multi-backend loading | — |
| `tests/test_audio/test_analyzer_base.py` | Tests for BaseAnalyzer Template Method, @register_analyzer, auto-discovery | — |
| `tests/test_audio/test_classification.py` | Tests for new MoodClassifier with profiles (extends test_mood.py) | — |
| `tests/test_audio/test_pipeline_refactored.py` | Tests for refactored pipeline: DI, context, to_thread parallelism | — |

### Files to modify

| File | Change |
|------|--------|
| `app/audio/analyzers/__init__.py` | Re-exports: BaseAnalyzer, AnalyzerRegistry, register_analyzer |
| `app/audio/analyzers/loudness.py` | Change base class, sync `_extract(ctx)`, remove guard |
| `app/audio/analyzers/energy.py` | Use `ctx.frame_energies`, `core.spectral.band_energies()` |
| `app/audio/analyzers/spectral.py` | Use `ctx.stft`, `ctx.magnitude`, `ctx.freqs` |
| `app/audio/analyzers/structure.py` | Use `ctx.frame_energies` |
| `app/audio/analyzers/bpm.py` | Change base class, sync `_extract(ctx)` |
| `app/audio/analyzers/key.py` | Change base class, sync `_extract(ctx)` |
| `app/audio/analyzers/beat.py` | Change base class, sync `_extract(ctx)` |
| `app/audio/analyzers/mfcc.py` | Change base class, sync `_extract(ctx)` |
| `app/audio/pipeline.py` | Inject AudioLoader, create AnalysisContext, asyncio.to_thread |
| `app/audio/registry.py` | Add re-export aliases for backward compat (temporary) |
| `app/services/audio_service.py` | Import path changes + AudioLoader injection |
| `app/services/curation_service.py` | Import path change for MoodClassifier |
| `app/mcp/dependencies.py` | Add AudioLoader to pipeline construction |
| `app/server.py` | Update analyzer_lifespan import + add AudioLoader |
| `tests/conftest.py` | Update AnalyzerRegistry import |
| `tests/test_lifespan.py` | Update AnalyzerRegistry import |
| `tests/test_audio/test_analyzers.py` | Update AudioSignal import + adapt to new API |
| `tests/test_audio/test_registry.py` | Update to test new BaseAnalyzer, registry, decorator |
| `tests/test_audio/test_structure.py` | Update AudioSignal import |
| `tests/test_audio/test_mood.py` | Update imports + test MoodResult.top_matches |

### Files to delete (after migration)

| File | Lines | Replaced by |
|------|-------|-------------|
| `app/audio/registry.py` | 104 | `core/types.py` + `analyzers/base.py` |
| `app/audio/mood.py` | 226 | `classification/classifier.py` + `classification/profiles.py` |

---

### Task 1: Create `core/types.py` — immutable data types

**Files:**
- Create: `app/audio/core/__init__.py`
- Create: `app/audio/core/types.py`
- Create: `tests/test_audio/test_core_types.py`

- [ ] **Step 1: Write failing tests for FrameParams, AudioSignal, AnalyzerResult**

```python
# tests/test_audio/test_core_types.py
"""Tests for core audio types."""
from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.types import AnalyzerResult, AudioSignal, FrameParams

class TestFrameParams:
    def test_defaults(self) -> None:
        fp = FrameParams()
        assert fp.frame_length == 2048
        assert fp.hop_length == 512

    def test_custom_values(self) -> None:
        fp = FrameParams(frame_length=4096, hop_length=1024)
        assert fp.frame_length == 4096
        assert fp.hop_length == 1024

    def test_frozen(self) -> None:
        fp = FrameParams()
        with pytest.raises(AttributeError):
            fp.frame_length = 1024  # type: ignore[misc]

class TestAudioSignal:
    def test_creation(self) -> None:
        samples = np.zeros(1000, dtype=np.float32)
        sig = AudioSignal(samples=samples, sample_rate=22050, duration_seconds=1.0)
        assert sig.sample_rate == 22050
        assert sig.file_path == ""

    def test_file_path_optional(self) -> None:
        sig = AudioSignal(
            samples=np.zeros(100, dtype=np.float32),
            sample_rate=22050,
            duration_seconds=0.1,
            file_path="/tmp/test.wav",
        )
        assert sig.file_path == "/tmp/test.wav"

class TestAnalyzerResult:
    def test_success_defaults(self) -> None:
        r = AnalyzerResult(analyzer_name="test")
        assert r.success is True
        assert r.error is None
        assert r.features == {}

    def test_failure(self) -> None:
        r = AnalyzerResult(analyzer_name="test", success=False, error="boom")
        assert r.success is False
        assert r.error == "boom"

    def test_features_dict(self) -> None:
        r = AnalyzerResult(analyzer_name="test", features={"bpm": 128.0})
        assert r.features["bpm"] == 128.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audio.core'`

- [ ] **Step 3: Create `core/__init__.py` and `core/types.py`**

```python
# app/audio/core/__init__.py
"""Core DSP primitives — Layer 1.

Zero app/ dependencies. Pure numpy.
Re-exports public API for convenience.
"""
from app.audio.core.types import AnalyzerResult, AudioSignal, FrameParams

__all__ = [
    "AnalyzerResult",
    "AudioSignal",
    "FrameParams",
]
```

```python
# app/audio/core/types.py
"""Core audio data types — immutable, type-safe.

These types are the foundation of the audio analysis pipeline.
Used across all layers: core, analyzers, pipeline, services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

@dataclass(frozen=True, slots=True)
class FrameParams:
    """Immutable frame/hop configuration. Single source of truth.

    Replaces hardcoded frame_length=2048, hop_length=512 in 3 files.
    """

    frame_length: int = 2048
    hop_length: int = 512

@dataclass
class AudioSignal:
    """Mono audio signal loaded once per pipeline run."""

    samples: np.ndarray  # mono float32
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_types.py -v`
Expected: PASS — all 7 tests green

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/core/__init__.py app/audio/core/types.py tests/test_audio/test_core_types.py
git commit -m "feat(audio): add core/types.py — FrameParams, AudioSignal, AnalyzerResult"
```

---

### Task 2: Create `core/framing.py` — shared frame energy computation

**Files:**
- Create: `app/audio/core/framing.py`
- Create: `tests/test_audio/test_core_framing.py`
- Modify: `app/audio/core/__init__.py` (add re-exports)

- [ ] **Step 1: Write failing tests for compute_frame_energies and compute_energy_slope**

```python
# tests/test_audio/test_core_framing.py
"""Tests for core framing primitives."""
from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.framing import compute_energy_slope, compute_frame_energies

class TestComputeFrameEnergies:
    def test_silence_gives_zeros(self) -> None:
        samples = np.zeros(4096, dtype=np.float32)
        energies = compute_frame_energies(samples, frame_length=2048, hop_length=512)
        assert len(energies) > 0
        assert float(np.max(energies)) == 0.0

    def test_sine_wave_normalized(self) -> None:
        """Normalized energies should be in [0, 1]."""
        t = np.linspace(0, 1.0, 22050, endpoint=False)
        samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        energies = compute_frame_energies(samples, frame_length=2048, hop_length=512)
        assert float(np.max(energies)) <= 1.0 + 1e-6
        assert float(np.min(energies)) >= 0.0

    def test_frame_count_correct(self) -> None:
        """Number of frames should match (n_samples - frame_length) // hop_length + 1."""
        n_samples = 22050
        samples = np.zeros(n_samples, dtype=np.float32)
        energies = compute_frame_energies(samples, frame_length=2048, hop_length=512)
        expected_frames = max(1, (n_samples - 2048) // 512 + 1)
        assert len(energies) == expected_frames

    def test_louder_signal_higher_energy_before_normalization(self) -> None:
        """A louder signal should still normalize to max=1.0."""
        t = np.linspace(0, 1.0, 22050, endpoint=False)
        quiet = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        loud = (0.9 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        e_quiet = compute_frame_energies(quiet, 2048, 512)
        e_loud = compute_frame_energies(loud, 2048, 512)
        # Both should be normalized to max ≈ 1.0
        assert float(np.max(e_quiet)) == pytest.approx(1.0, abs=0.01)
        assert float(np.max(e_loud)) == pytest.approx(1.0, abs=0.01)

    def test_empty_signal_returns_single_zero(self) -> None:
        samples = np.array([], dtype=np.float32)
        energies = compute_frame_energies(samples, 2048, 512)
        assert len(energies) == 1
        assert energies[0] == 0.0

class TestComputeEnergySlope:
    def test_constant_energy_zero_slope(self) -> None:
        energies = np.ones(100) * 0.5
        slope = compute_energy_slope(energies)
        assert slope == pytest.approx(0.0, abs=1e-10)

    def test_increasing_energy_positive_slope(self) -> None:
        energies = np.linspace(0.0, 1.0, 100)
        slope = compute_energy_slope(energies)
        assert slope > 0.0

    def test_single_frame_zero_slope(self) -> None:
        energies = np.array([0.5])
        slope = compute_energy_slope(energies)
        assert slope == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_framing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audio.core.framing'`

- [ ] **Step 3: Implement `core/framing.py`**

```python
# app/audio/core/framing.py
"""Frame-level energy computation — extracted from energy.py and structure.py.

Pure functions, zero side effects, zero app/ dependencies.
Eliminates the duplicated frame energy loop in energy.py:44-54 and structure.py:71-81.
"""
from __future__ import annotations

import numpy as np

def compute_frame_energies(
    samples: np.ndarray,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    """Compute normalized short-time frame energies.

    Returns array of energies normalized to [0, 1] (max = 1.0).
    For empty/silent signals, returns array of zeros.
    """
    n_samples = len(samples)
    if n_samples == 0:
        return np.zeros(1, dtype=np.float64)

    n_frames = max(1, (n_samples - frame_length) // hop_length + 1)
    frame_energies = np.zeros(n_frames, dtype=np.float64)

    for i in range(n_frames):
        start = i * hop_length
        end = min(start + frame_length, n_samples)
        frame = samples[start:end]
        frame_energies[i] = float(np.mean(frame**2))

    # Normalize to [0, 1]
    max_energy = float(np.max(frame_energies))
    if max_energy > 0:
        frame_energies = frame_energies / max_energy

    return frame_energies

def compute_energy_slope(energies: np.ndarray) -> float:
    """Compute energy slope via linear regression.

    Returns slope coefficient. Positive = energy increasing over time.
    """
    n_frames = len(energies)
    if n_frames <= 1:
        return 0.0

    x = np.arange(n_frames, dtype=np.float64)
    slope, _ = np.polyfit(x, energies, 1)
    return float(slope)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_framing.py -v`
Expected: PASS — all 8 tests green

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/core/framing.py tests/test_audio/test_core_framing.py
git commit -m "feat(audio): add core/framing.py — shared frame energy computation"
```

---

### Task 3: Create `core/spectral.py` — shared spectral primitives

> **Note:** This file shares the name `spectral.py` with `analyzers/spectral.py`. No ambiguity because absolute imports are used everywhere (`from app.audio.core.spectral import ...` vs `from app.audio.analyzers.spectral import ...`). `core/spectral.py` contains pure DSP primitives; `analyzers/spectral.py` is the feature extractor that consumes them.

**Files:**
- Create: `app/audio/core/spectral.py`
- Create: `tests/test_audio/test_core_spectral.py`

- [ ] **Step 1: Write failing tests for spectral primitives**

```python
# tests/test_audio/test_core_spectral.py
"""Tests for core spectral primitives."""
from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.spectral import (
    band_energies,
    compute_stft,
    spectral_centroid,
    spectral_flatness,
    spectral_rolloff,
)

SAMPLE_RATE = 22050

def _sine_samples(freq: float = 440.0, duration: float = 1.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)

class TestComputeStft:
    def test_output_shape(self) -> None:
        samples = _sine_samples()
        stft = compute_stft(samples, frame_length=2048, hop_length=512)
        # n_fft_bins = frame_length // 2 + 1 = 1025
        assert stft.shape[0] == 1025
        # n_frames = (n_samples - frame_length) // hop_length + 1
        expected_frames = max(1, (len(samples) - 2048) // 512 + 1)
        assert stft.shape[1] == expected_frames

    def test_complex_output(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        assert np.iscomplexobj(stft)

class TestBandEnergies:
    def test_sine_440_in_lowmid(self) -> None:
        """440 Hz sine should have most energy in lowmid (250-500 Hz)."""
        stft = compute_stft(_sine_samples(440.0), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        bands = {"sub": (20, 60), "low": (60, 250), "lowmid": (250, 500), "mid": (500, 2000)}
        result = band_energies(magnitude, freqs, bands)
        assert result["lowmid"] > result["sub"]
        assert result["lowmid"] > result["mid"]

    def test_returns_all_bands(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        bands = {"low": (60, 250), "mid": (250, 2000), "high": (2000, 8000)}
        result = band_energies(magnitude, freqs, bands)
        assert set(result.keys()) == {"low", "mid", "high"}

class TestSpectralCentroid:
    def test_sine_centroid_near_freq(self) -> None:
        stft = compute_stft(_sine_samples(440.0), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        centroid = spectral_centroid(magnitude, freqs)
        assert 400.0 < centroid < 500.0

class TestSpectralRolloff:
    def test_rolloff_95_gte_85(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        magnitude = np.abs(stft)
        freqs = np.fft.rfftfreq(2048, d=1.0 / SAMPLE_RATE)
        r85 = spectral_rolloff(magnitude, freqs, 0.85)
        r95 = spectral_rolloff(magnitude, freqs, 0.95)
        assert r95 >= r85

class TestSpectralFlatness:
    def test_sine_low_flatness(self) -> None:
        stft = compute_stft(_sine_samples(), 2048, 512)
        magnitude = np.abs(stft)
        flat = spectral_flatness(magnitude)
        assert flat < 0.1

    def test_noise_higher_flatness(self) -> None:
        rng = np.random.default_rng(42)
        noise = (0.3 * rng.standard_normal(22050)).astype(np.float32)
        stft = compute_stft(noise, 2048, 512)
        magnitude = np.abs(stft)
        flat = spectral_flatness(magnitude)
        assert flat > 0.3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_spectral.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `core/spectral.py`**

```python
# app/audio/core/spectral.py
"""Spectral DSP primitives — extracted from spectral.py, energy.py, key.py.

Pure functions, zero side effects, zero app/ dependencies.
Eliminates duplicated FFT/windowing code across 3 analyzer files.
"""
from __future__ import annotations

import numpy as np

def compute_stft(
    samples: np.ndarray,
    frame_length: int = 2048,
    hop_length: int = 512,
    window: str = "hann",
) -> np.ndarray:
    """Compute Short-Time Fourier Transform.

    Returns complex STFT matrix of shape (n_fft_bins, n_frames)
    where n_fft_bins = frame_length // 2 + 1.
    """
    n_samples = len(samples)
    n_fft_bins = frame_length // 2 + 1
    n_frames = max(1, (n_samples - frame_length) // hop_length + 1)

    stft_matrix = np.zeros((n_fft_bins, n_frames), dtype=np.complex128)

    if window == "hann":
        win = np.hanning(frame_length)
    else:
        win = np.ones(frame_length)

    for i in range(n_frames):
        start = i * hop_length
        end = min(start + frame_length, n_samples)
        frame = samples[start:end]

        # Zero-pad if needed
        if len(frame) < frame_length:
            frame = np.pad(frame, (0, frame_length - len(frame)))

        windowed = frame * win
        stft_matrix[:, i] = np.fft.rfft(windowed)

    return stft_matrix

def band_energies(
    magnitude: np.ndarray,
    freqs: np.ndarray,
    bands: dict[str, tuple[float, float]],
) -> dict[str, float]:
    """Compute relative energy in each frequency band.

    Args:
        magnitude: |STFT| matrix, shape (n_fft_bins, n_frames).
                   If 2D, uses mean across frames. If 1D, uses directly.
        freqs: FFT frequency bin centers, shape (n_fft_bins,).
        bands: Band name → (low_hz, high_hz).

    Returns:
        Dict of band name → relative energy (0-1, sums to ~1.0).
    """
    if magnitude.ndim == 2:
        mag_mean = np.mean(magnitude, axis=1)
    else:
        mag_mean = magnitude

    power = mag_mean**2
    total_energy = float(np.sum(power))
    if total_energy == 0:
        return {name: 0.0 for name in bands}

    result: dict[str, float] = {}
    for name, (low_hz, high_hz) in bands.items():
        mask = (freqs >= low_hz) & (freqs < high_hz)
        band_energy = float(np.sum(power[mask]))
        result[name] = band_energy / total_energy

    return result

def spectral_centroid(magnitude: np.ndarray, freqs: np.ndarray) -> float:
    """Compute spectral centroid (weighted mean frequency).

    If 2D magnitude matrix, returns mean centroid across frames.
    """
    if magnitude.ndim == 2:
        centroids = []
        for i in range(magnitude.shape[1]):
            frame_mag = magnitude[:, i]
            total = float(np.sum(frame_mag))
            if total > 0:
                centroids.append(float(np.sum(freqs * frame_mag) / total))
            else:
                centroids.append(0.0)
        return float(np.mean(centroids)) if centroids else 0.0

    total = float(np.sum(magnitude))
    return float(np.sum(freqs * magnitude) / total) if total > 0 else 0.0

def spectral_rolloff(magnitude: np.ndarray, freqs: np.ndarray, pct: float = 0.85) -> float:
    """Compute spectral rolloff frequency.

    Returns frequency below which `pct` of total spectral energy lies.
    If 2D magnitude, returns mean rolloff across frames.
    """
    if magnitude.ndim == 2:
        rolloffs = []
        for i in range(magnitude.shape[1]):
            frame_mag = magnitude[:, i]
            total = float(np.sum(frame_mag))
            if total > 0:
                cumsum = np.cumsum(frame_mag)
                idx = np.searchsorted(cumsum, pct * total)
                idx = min(idx, len(freqs) - 1)
                rolloffs.append(float(freqs[idx]))
            else:
                rolloffs.append(0.0)
        return float(np.mean(rolloffs)) if rolloffs else 0.0

    total = float(np.sum(magnitude))
    if total <= 0:
        return 0.0
    cumsum = np.cumsum(magnitude)
    idx = np.searchsorted(cumsum, pct * total)
    idx = min(idx, len(freqs) - 1)
    return float(freqs[idx])

def spectral_flatness(magnitude: np.ndarray) -> float:
    """Compute spectral flatness (geometric mean / arithmetic mean).

    Returns value in [0, 1]. 1.0 = white noise, 0.0 = pure tone.
    If 2D magnitude, returns mean flatness across frames.
    """
    if magnitude.ndim == 2:
        flatness_values = []
        for i in range(magnitude.shape[1]):
            flatness_values.append(_flatness_1d(magnitude[:, i]))
        return float(np.mean(flatness_values)) if flatness_values else 0.0

    return _flatness_1d(magnitude)

def _flatness_1d(mag: np.ndarray) -> float:
    """Flatness for a single frame."""
    positive = mag[mag > 0]
    if len(positive) == 0:
        return 0.0
    log_mean = float(np.mean(np.log(positive + 1e-10)))
    geometric_mean = np.exp(log_mean)
    arithmetic_mean = float(np.mean(mag))
    if arithmetic_mean <= 0:
        return 0.0
    return float(geometric_mean / (arithmetic_mean + 1e-10))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_spectral.py -v`
Expected: PASS — all 9 tests green

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/core/spectral.py tests/test_audio/test_core_spectral.py
git commit -m "feat(audio): add core/spectral.py — shared STFT, band energies, centroid, rolloff, flatness"
```

---

### Task 4: Create `core/loader.py` — extracted audio loading

**Files:**
- Create: `app/audio/core/loader.py`
- Create: `tests/test_audio/test_core_loader.py`
- Modify: `app/audio/core/__init__.py` (add re-exports)

- [ ] **Step 1: Write failing tests for AudioLoader**

```python
# tests/test_audio/test_core_loader.py
"""Tests for AudioLoader — multi-backend audio file loading."""
from __future__ import annotations

import struct
import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

from app.audio.core.loader import AudioLoader
from app.audio.core.types import AudioSignal

def _write_wav(path: Path, samples: np.ndarray, sr: int = 22050) -> None:
    """Write a mono WAV file."""
    int_samples = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_samples.tobytes())

@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    """Create a test WAV file with 1 second of 440Hz sine."""
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path = tmp_path / "test.wav"
    _write_wav(path, samples, sr)
    return path

class TestAudioLoader:
    async def test_load_returns_audio_signal(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert isinstance(signal, AudioSignal)

    async def test_load_correct_sample_rate(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert signal.sample_rate == 22050

    async def test_load_mono_signal(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert signal.samples.ndim == 1

    async def test_load_file_not_found(self) -> None:
        loader = AudioLoader(target_sr=22050)
        with pytest.raises(FileNotFoundError):
            await loader.load("/nonexistent/path.wav")

    async def test_load_duration_approximately_correct(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert 0.9 < signal.duration_seconds < 1.1

    async def test_custom_target_sr(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=16000)
        signal = await loader.load(str(wav_file))
        assert signal.sample_rate == 16000
        # Should have fewer samples due to lower sample rate
        assert len(signal.samples) < 22050

    async def test_file_path_preserved(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert signal.file_path == str(wav_file)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_loader.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `core/loader.py`**

Extract the 70-line `AnalysisPipeline._load_audio()` into a standalone class:

```python
# app/audio/core/loader.py
"""Multi-backend audio file loader.

Extracted from AnalysisPipeline._load_audio() (70 lines, SRP violation).
Fallback chain: soundfile -> librosa -> wave (stdlib).
Resamples to target sample rate if needed.

Zero app/ dependencies — target_sr passed as constructor parameter.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.audio.core.types import AudioSignal

class AudioLoader:
    """Load audio files as mono float32 numpy arrays.

    Supports MP3, WAV, FLAC, OGG via soundfile/librosa (preferred)
    or WAV-only via wave module (fallback).
    """

    def __init__(self, target_sr: int = 22050) -> None:
        self._target_sr = target_sr

    async def load(self, file_path: str) -> AudioSignal:
        """Load and resample audio file to mono float32.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            msg = f"Audio file not found: {file_path}"
            raise FileNotFoundError(msg)

        samples, file_sr = self._read_file(path)

        # Resample if needed
        if file_sr != self._target_sr:
            samples = self._resample(samples, file_sr, self._target_sr)

        duration = len(samples) / self._target_sr

        return AudioSignal(
            samples=samples,
            sample_rate=self._target_sr,
            duration_seconds=duration,
            file_path=file_path,
        )

    def _read_file(self, path: Path) -> tuple[np.ndarray, int]:
        """Read audio file using fallback chain.

        Returns (mono_samples_float32, original_sample_rate).
        """
        # Try soundfile first (handles WAV, FLAC, OGG natively)
        try:
            import soundfile as sf

            samples, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
            return samples.mean(axis=1), file_sr
        except Exception:
            pass

        # Try librosa (handles MP3 via audioread/ffmpeg)
        try:
            import librosa

            samples, file_sr = librosa.load(str(path), sr=None, mono=True)
            return samples, file_sr
        except Exception:
            pass

        # Final fallback: wave module (WAV only)
        import wave

        with wave.open(str(path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            file_sr = wf.getframerate()
            raw_data = wf.readframes(wf.getnframes())

        if sampwidth == 2:
            dtype = np.int16
        elif sampwidth == 4:
            dtype = np.int32
        else:
            dtype = np.uint8

        samples = np.frombuffer(raw_data, dtype=dtype).astype(np.float32)
        if sampwidth == 1:
            samples = (samples - 128.0) / 128.0
        elif sampwidth == 2:
            samples /= 32768.0
        elif sampwidth == 4:
            samples /= 2147483648.0

        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        return samples, file_sr

    @staticmethod
    def _resample(samples: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio. Tries librosa first, falls back to linear interp."""
        try:
            import librosa

            return librosa.resample(samples, orig_sr=orig_sr, target_sr=target_sr)
        except ImportError:
            ratio = target_sr / orig_sr
            new_length = int(len(samples) * ratio)
            indices = np.linspace(0, len(samples) - 1, new_length)
            return np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)
```

- [ ] **Step 4: Update `core/__init__.py` with re-exports**

```python
# app/audio/core/__init__.py
"""Core DSP primitives — Layer 1.

Zero app/ dependencies. Pure numpy.
Re-exports public API for convenience.
"""
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AnalyzerResult, AudioSignal, FrameParams

__all__ = [
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "FrameParams",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_loader.py -v`
Expected: PASS — all 7 tests green

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/ -v`
Expected: PASS — all existing tests still green

- [ ] **Step 7: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/core/loader.py app/audio/core/__init__.py tests/test_audio/test_core_loader.py
git commit -m "feat(audio): add core/loader.py — extracted AudioLoader with fallback chain"
```

---

### Task 5: Create `core/context.py` — shared AnalysisContext

**Files:**
- Create: `app/audio/core/context.py`
- Create: `tests/test_audio/test_core_context.py`
- Modify: `app/audio/core/__init__.py` (add re-export)

- [ ] **Step 1: Write failing tests for AnalysisContext**

```python
# tests/test_audio/test_core_context.py
"""Tests for AnalysisContext — eager shared computation."""
from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal, FrameParams

SAMPLE_RATE = 22050

def _make_signal(duration: float = 1.0, freq: float = 440.0) -> AudioSignal:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)

class TestAnalysisContext:
    def test_samples_accessible(self) -> None:
        signal = _make_signal()
        ctx = AnalysisContext(signal)
        assert len(ctx.samples) == len(signal.samples)

    def test_sr_matches_signal(self) -> None:
        signal = _make_signal()
        ctx = AnalysisContext(signal)
        assert ctx.sr == SAMPLE_RATE

    def test_stft_shape(self) -> None:
        signal = _make_signal()
        ctx = AnalysisContext(signal)
        n_fft_bins = 2048 // 2 + 1
        assert ctx.stft.shape[0] == n_fft_bins

    def test_magnitude_nonnegative(self) -> None:
        ctx = AnalysisContext(_make_signal())
        assert float(np.min(ctx.magnitude)) >= 0.0

    def test_magnitude_matches_stft(self) -> None:
        ctx = AnalysisContext(_make_signal())
        expected = np.abs(ctx.stft)
        np.testing.assert_array_almost_equal(ctx.magnitude, expected)

    def test_freqs_length_matches_stft(self) -> None:
        ctx = AnalysisContext(_make_signal())
        assert len(ctx.freqs) == ctx.stft.shape[0]

    def test_frame_energies_normalized(self) -> None:
        ctx = AnalysisContext(_make_signal())
        assert float(np.max(ctx.frame_energies)) <= 1.0 + 1e-6
        assert float(np.min(ctx.frame_energies)) >= 0.0

    def test_custom_frame_params(self) -> None:
        signal = _make_signal()
        params = FrameParams(frame_length=4096, hop_length=1024)
        ctx = AnalysisContext(signal, params)
        assert ctx.stft.shape[0] == 4096 // 2 + 1

    def test_empty_signal(self) -> None:
        signal = AudioSignal(
            samples=np.array([], dtype=np.float32),
            sample_rate=SAMPLE_RATE,
            duration_seconds=0.0,
        )
        ctx = AnalysisContext(signal)
        assert len(ctx.frame_energies) >= 1

    def test_thread_safety_read_only(self) -> None:
        """Context should be usable from multiple threads (read-only)."""
        import concurrent.futures

        ctx = AnalysisContext(_make_signal())

        def read_ctx() -> float:
            return float(np.mean(ctx.magnitude))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(read_ctx) for _ in range(8)]
            results = [f.result() for f in futures]

        # All threads should get the same result
        assert all(r == pytest.approx(results[0], abs=1e-10) for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_context.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `core/context.py`**

```python
# app/audio/core/context.py
"""AnalysisContext — eagerly-computed shared intermediates.

All STFT, magnitude, frequency bins, and frame energies are computed
once in __init__, then shared read-only across all analyzers.

Why eager, not lazy:
    Analyzers run in parallel via thread pool. Lazy properties would
    create check-then-act race conditions. Eager computation makes
    context immutable after construction — thread-safe by design.

Memory: For 60s track at 22050 Hz: STFT ~4 MB, frame_energies ~10 KB.
"""
from __future__ import annotations

import numpy as np

from app.audio.core.framing import compute_frame_energies
from app.audio.core.spectral import compute_stft
from app.audio.core.types import AudioSignal, FrameParams

class AnalysisContext:
    """Read-only shared computation context for a pipeline run.

    All properties are computed in __init__. Thread-safe: multiple
    analyzers can read from the same context concurrently.
    """

    __slots__ = (
        "_signal",
        "_params",
        "_stft",
        "_magnitude",
        "_freqs",
        "_frame_energies",
    )

    def __init__(
        self,
        signal: AudioSignal,
        params: FrameParams | None = None,
    ) -> None:
        self._signal = signal
        self._params = params or FrameParams()

        # Eagerly compute all shared intermediates
        self._stft = compute_stft(
            signal.samples,
            self._params.frame_length,
            self._params.hop_length,
        )
        self._magnitude = np.abs(self._stft)
        self._freqs = np.fft.rfftfreq(
            self._params.frame_length,
            d=1.0 / signal.sample_rate,
        )
        self._frame_energies = compute_frame_energies(
            signal.samples,
            self._params.frame_length,
            self._params.hop_length,
        )

    @property
    def samples(self) -> np.ndarray:
        return self._signal.samples

    @property
    def sr(self) -> int:
        return self._signal.sample_rate

    @property
    def duration(self) -> float:
        return self._signal.duration_seconds

    @property
    def file_path(self) -> str:
        return self._signal.file_path

    @property
    def params(self) -> FrameParams:
        return self._params

    @property
    def stft(self) -> np.ndarray:
        return self._stft

    @property
    def magnitude(self) -> np.ndarray:
        return self._magnitude

    @property
    def freqs(self) -> np.ndarray:
        return self._freqs

    @property
    def frame_energies(self) -> np.ndarray:
        return self._frame_energies
```

- [ ] **Step 4: Update `core/__init__.py` — add AnalysisContext re-export**

```python
# app/audio/core/__init__.py
"""Core audio types and DSP primitives — Layer 1 (0 app deps)."""
from app.audio.core.context import AnalysisContext
from app.audio.core.framing import compute_energy_slope, compute_frame_energies
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AnalyzerResult, AudioSignal, FrameParams

__all__ = [
    "AnalysisContext",
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "FrameParams",
    "compute_energy_slope",
    "compute_frame_energies",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_core_context.py -v`
Expected: PASS — all 10 tests green

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/core/context.py app/audio/core/__init__.py tests/test_audio/test_core_context.py
git commit -m "feat(audio): add core/context.py — eager AnalysisContext for thread-safe parallelism"
```

---

### Task 6: Create `analyzers/base.py` — BaseAnalyzer + Registry + decorator

**Files:**
- Create: `app/audio/analyzers/base.py`
- Modify: `app/audio/analyzers/__init__.py` (re-exports)
- Create: `tests/test_audio/test_analyzer_base.py`

- [ ] **Step 1: Write failing tests for new BaseAnalyzer, @register_analyzer, AnalyzerRegistry**

```python
# tests/test_audio/test_analyzer_base.py
"""Tests for BaseAnalyzer Template Method, @register_analyzer, AnalyzerRegistry."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest

from app.audio.analyzers.base import (
    BaseAnalyzer,
    AnalyzerRegistry,
    _ANALYZER_REGISTRY,
    register_analyzer,
)
from app.audio.core.context import AnalysisContext
from app.audio.core.types import AnalyzerResult, AudioSignal

@pytest.fixture(autouse=True)
def _clean_registry():
    """Save/restore global registry to prevent test pollution."""
    snapshot = dict(_ANALYZER_REGISTRY)
    yield
    _ANALYZER_REGISTRY.clear()
    _ANALYZER_REGISTRY.update(snapshot)

def _make_ctx(n_samples: int = 22050) -> AnalysisContext:
    signal = AudioSignal(
        samples=np.random.default_rng(42).standard_normal(n_samples).astype(np.float32),
        sample_rate=22050,
        duration_seconds=n_samples / 22050,
    )
    return AnalysisContext(signal)

class TestBaseAnalyzerTemplateMethod:
    def test_empty_signal_returns_failure(self) -> None:
        @register_analyzer
        class EmptyTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_empty"
            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {"value": 1}

        signal = AudioSignal(
            samples=np.array([], dtype=np.float32),
            sample_rate=22050,
            duration_seconds=0.0,
        )
        ctx = AnalysisContext(signal)
        result = EmptyTestAnalyzer().run(ctx)
        assert result.success is False
        assert "Empty signal" in (result.error or "")
        # Cleanup handled by _clean_registry fixture

    def test_successful_extraction(self) -> None:
        @register_analyzer
        class SuccessTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_success"
            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {"bpm": 128.0}

        ctx = _make_ctx()
        result = SuccessTestAnalyzer().run(ctx)
        assert result.success is True
        assert result.features["bpm"] == 128.0
        assert result.analyzer_name == "_test_success"
        # Cleanup handled by _clean_registry fixture

    def test_exception_in_extract_caught(self) -> None:
        @register_analyzer
        class FailTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_fail"
            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                raise ValueError("deliberate error")

        ctx = _make_ctx()
        result = FailTestAnalyzer().run(ctx)
        assert result.success is False
        assert "deliberate error" in (result.error or "")
        # Cleanup handled by _clean_registry fixture

class TestRegisterAnalyzerDecorator:
    def test_registers_in_global_dict(self) -> None:
        @register_analyzer
        class RegTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_reg"
            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {}

        assert "_test_reg" in _ANALYZER_REGISTRY
        assert _ANALYZER_REGISTRY["_test_reg"] is RegTestAnalyzer
        # Cleanup handled by _clean_registry fixture

class TestAnalyzerRegistry:
    """NOTE: discover() tests moved to Task 7 — they require @register_analyzer on real analyzers."""

    def test_get_nonexistent_returns_none(self) -> None:
        registry = AnalyzerRegistry()
        assert registry.get("nonexistent") is None

    def test_manual_register(self) -> None:
        @register_analyzer
        class ManualTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_manual"
            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {"x": 1}

        registry = AnalyzerRegistry()
        registry.register(ManualTestAnalyzer())
        assert registry.get("_test_manual") is not None
        assert registry.list_all() == ["_test_manual"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_analyzer_base.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `analyzers/base.py`**

```python
# app/audio/analyzers/base.py
"""BaseAnalyzer ABC, @register_analyzer decorator, AnalyzerRegistry.

GoF patterns:
    - Template Method: run() handles empty signal guard + error wrapping;
      subclass implements _extract(ctx).
    - Registry: @register_analyzer decorator populates global dict.
      AnalyzerRegistry.discover() uses pkgutil.iter_modules() for auto-scan.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AnalyzerResult, AudioSignal

logger = logging.getLogger(__name__)

# Global registry populated by @register_analyzer decorator
_ANALYZER_REGISTRY: dict[str, type[BaseAnalyzer]] = {}

def register_analyzer(cls: type[BaseAnalyzer]) -> type[BaseAnalyzer]:
    """Decorator for auto-registration. Pattern: Lhotse @register_extractor."""
    _ANALYZER_REGISTRY[cls.name] = cls
    return cls

class BaseAnalyzer(ABC):
    """Base class for all audio analyzers (Template Method pattern).

    Subclasses implement _extract(ctx) -> dict. The run() method handles:
    - Empty signal guard (eliminates 8 duplicate checks)
    - Exception wrapping into AnalyzerResult
    - Uniform error reporting

    All analyzers are synchronous (CPU-bound). Pipeline dispatches them
    via asyncio.to_thread() for parallelism.
    """

    name: ClassVar[str] = ""
    capabilities: ClassVar[frozenset[str]] = frozenset()
    required_packages: ClassVar[list[str]] = []

    def run(self, ctx: AnalysisContext) -> AnalyzerResult:
        """Template Method — guard + delegate. Synchronous (CPU-bound).

        Called via asyncio.to_thread() by pipeline for parallelism.
        """
        if len(ctx.samples) == 0:
            return AnalyzerResult(
                analyzer_name=self.name, success=False, error="Empty signal"
            )
        try:
            features = self._extract(ctx)
            return AnalyzerResult(analyzer_name=self.name, features=features)
        except Exception as e:
            logger.warning("Analyzer %s failed: %s", self.name, e)
            return AnalyzerResult(
                analyzer_name=self.name, success=False, error=str(e)
            )

    @abstractmethod
    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Subclass implements. Synchronous — pure computation, no I/O."""
        ...

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """DEPRECATED shim — keeps pipeline.py working until Task 9.

        Bridges old async API (pipeline calls `await analyzer.analyze(signal)`)
        to new sync API (`self.run(ctx)`). Removed in Task 9 when pipeline
        switches to `asyncio.to_thread(a.run, ctx)`.
        """
        ctx = AnalysisContext(signal)
        return self.run(ctx)

    def is_available(self) -> bool:
        """Check if required packages are installed."""
        for pkg in self.required_packages:
            try:
                __import__(pkg)
            except ImportError:
                return False
        return True

class AnalyzerRegistry:
    """Registry of available audio analyzers.

    Uses auto-discovery via pkgutil.iter_modules() — new analyzer = one file
    with @register_analyzer decorator. No hardcoded import list.
    """

    def __init__(self) -> None:
        self._analyzers: dict[str, BaseAnalyzer] = {}

    def register(self, analyzer: BaseAnalyzer) -> None:
        """Register an analyzer instance."""
        self._analyzers[analyzer.name] = analyzer

    def get(self, name: str) -> BaseAnalyzer | None:
        """Get analyzer by name."""
        return self._analyzers.get(name)

    def list_available(self) -> list[str]:
        """List names of analyzers whose dependencies are satisfied."""
        return [name for name, a in self._analyzers.items() if a.is_available()]

    def list_all(self) -> list[str]:
        """List all registered analyzer names."""
        return list(self._analyzers.keys())

    def discover(self) -> None:
        """Auto-scan analyzers/ package. No hardcoded imports.

        Wraps each import in try/except to handle optional dependencies
        (librosa-based analyzers: bpm, key, beat, mfcc).
        """
        import importlib
        import pkgutil

        import app.audio.analyzers as pkg

        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name in ("base", "__init__"):
                continue
            try:
                importlib.import_module(f"app.audio.analyzers.{info.name}")
            except ImportError:
                pass  # Optional dependency not installed — skip silently

        # Instantiate all registered analyzers
        for name, cls in _ANALYZER_REGISTRY.items():
            if name in self._analyzers:
                continue
            try:
                instance = cls()
                if instance.is_available():
                    self._analyzers[name] = instance
            except ImportError:
                pass
```

- [ ] **Step 4: Update `analyzers/__init__.py`**

```python
# app/audio/analyzers/__init__.py
"""Audio analyzers — Layer 2 feature extractors.

Re-exports public API for convenience.
"""
from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer, register_analyzer

__all__ = [
    "AnalyzerRegistry",
    "BaseAnalyzer",
    "register_analyzer",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_analyzer_base.py -v`
Expected: PASS — all tests green

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/analyzers/base.py app/audio/analyzers/__init__.py tests/test_audio/test_analyzer_base.py
git commit -m "feat(audio): add analyzers/base.py — BaseAnalyzer Template Method + @register_analyzer + auto-discovery"
```

---

### Task 7: Migrate ALL 8 analyzers to new base class (atomic step)

**Files:**
- Modify: `app/audio/analyzers/loudness.py`
- Modify: `app/audio/analyzers/energy.py`
- Modify: `app/audio/analyzers/spectral.py`
- Modify: `app/audio/analyzers/structure.py`
- Modify: `app/audio/analyzers/bpm.py`
- Modify: `app/audio/analyzers/key.py`
- Modify: `app/audio/analyzers/beat.py`
- Modify: `app/audio/analyzers/mfcc.py`
- Modify: `app/audio/registry.py` (add backward-compat re-exports)

**Why atomic:** Old `async analyze(signal)` and new sync `_extract(ctx)` have incompatible base classes. Migrating one-by-one leaves codebase in broken state.

- [ ] **Step 1: Migrate all 8 analyzers**

For each analyzer, apply these changes:
1. Change import: `from app.audio.registry import ...` → `from app.audio.analyzers.base import BaseAnalyzer, register_analyzer` + `from app.audio.core.context import AnalysisContext`
2. Add `@register_analyzer` decorator
3. Change `capabilities` from `set` to `frozenset`
4. Replace `async def analyze(self, signal: AudioSignal) -> AnalyzerResult:` with `def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:`
5. Remove empty signal guard (handled by `BaseAnalyzer.run()`)
6. Replace `signal.samples` with `ctx.samples`, `signal.sample_rate` with `ctx.sr`
7. Return `dict` instead of `AnalyzerResult`
8. For energy.py: use `ctx.frame_energies` and `from app.audio.core.spectral import band_energies`
9. For structure.py: use `ctx.frame_energies`
10. For spectral.py: use `ctx.stft`, `ctx.magnitude`, `ctx.freqs`

**Example — energy.py after migration:**

```python
# app/audio/analyzers/energy.py
"""Energy analyzer — frame energy + 6-band decomposition."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.spectral import band_energies as compute_band_energies

ENERGY_BANDS: dict[str, tuple[float, float]] = {
    "sub": (20.0, 60.0),
    "low": (60.0, 250.0),
    "lowmid": (250.0, 500.0),
    "mid": (500.0, 2000.0),
    "highmid": (2000.0, 4000.0),
    "high": (4000.0, 8000.0),
}

@register_analyzer
class EnergyAnalyzer(BaseAnalyzer):
    """Energy computation using shared frame energies + core spectral bands."""

    name: ClassVar[str] = "energy"
    capabilities: ClassVar[frozenset[str]] = frozenset({"energy"})
    required_packages: ClassVar[list[str]] = []

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        # Use shared frame energies from context (eliminates duplication)
        normalized_energies = ctx.frame_energies

        energy_mean = float(np.mean(normalized_energies))
        energy_max = float(np.max(normalized_energies))
        energy_std = float(np.std(normalized_energies))

        # Energy slope
        from app.audio.core.framing import compute_energy_slope

        energy_slope = compute_energy_slope(normalized_energies)

        # 6-band energy via shared STFT (eliminates duplicated FFT)
        bands = compute_band_energies(ctx.magnitude, ctx.freqs, ENERGY_BANDS)

        # Compute ratios
        band_total = sum(bands.values()) or 1.0
        band_ratios = {f"{name}_ratio": val / band_total for name, val in bands.items()}

        return {
            "energy_mean": energy_mean,
            "energy_max": energy_max,
            "energy_std": energy_std,
            "energy_slope": energy_slope,
            **{f"energy_{name}": val for name, val in bands.items()},
            **{f"energy_{name}": val for name, val in band_ratios.items()},
        }
```

**Example — loudness.py (minimal changes, uses own windowing):**

```python
# Key changes only — the K-weighting helpers stay unchanged
@register_analyzer
class LoudnessAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "loudness"
    capabilities: ClassVar[frozenset[str]] = frozenset({"loudness"})
    required_packages: ClassVar[list[str]] = []

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        samples = ctx.samples
        sr = ctx.sr
        # ... rest of computation unchanged, returns dict instead of AnalyzerResult
```

**Example — bpm.py (librosa-based, minimal changes):**

```python
@register_analyzer
class BPMDetector(BaseAnalyzer):
    name: ClassVar[str] = "bpm"
    capabilities: ClassVar[frozenset[str]] = frozenset({"tempo", "rhythm"})
    required_packages: ClassVar[list[str]] = ["librosa"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import librosa
        samples = ctx.samples
        sr = ctx.sr
        # ... rest unchanged, returns dict
```

- [ ] **Step 2: Add backward-compat re-exports to `registry.py`**

```python
# app/audio/registry.py — TEMPORARY backward compat re-exports
"""Backward compatibility — re-exports from new locations.

TODO: Remove after all consumers updated (Task 10).
"""
from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer  # noqa: F401
from app.audio.core.types import AnalyzerResult, AudioSignal  # noqa: F401
```

- [ ] **Step 3: Add discover() integration tests (moved from Task 6)**

Append to `tests/test_audio/test_analyzer_base.py`:

```python
class TestAnalyzerRegistryDiscover:
    """These tests require @register_analyzer on real analyzers (Task 7)."""

    def test_discover_finds_core_analyzers(self) -> None:
        registry = AnalyzerRegistry()
        registry.discover()
        available = registry.list_available()
        assert "loudness" in available
        assert "energy" in available
        assert "spectral" in available
        assert "structure" in available

    def test_get_returns_instance(self) -> None:
        registry = AnalyzerRegistry()
        registry.discover()
        analyzer = registry.get("loudness")
        assert analyzer is not None
        assert analyzer.name == "loudness"

    def test_list_all_includes_optional(self) -> None:
        """If librosa is installed, optional analyzers should be listed."""
        registry = AnalyzerRegistry()
        registry.discover()
        all_names = registry.list_all()
        # Core 4 always present
        assert len(all_names) >= 4
```

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/ -v`
Expected: PASS — all tests green. Pipeline tests pass because `BaseAnalyzer.analyze()` shim (added in Task 6) bridges the old async API to the new sync `run(ctx)`. Backward-compat re-exports ensure old imports work.

- [ ] **Step 5: Run lint**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run ruff check app/audio/ && uv run ruff format --check app/audio/`
Expected: PASS — no lint errors

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/analyzers/ app/audio/registry.py tests/test_audio/test_analyzer_base.py
git commit -m "refactor(audio): migrate all 8 analyzers to BaseAnalyzer Template Method + @register_analyzer"
```

---

### Task 8: Create `classification/` — profiles + classifier

**Files:**
- Create: `app/audio/classification/__init__.py`
- Create: `app/audio/classification/profiles.py`
- Create: `app/audio/classification/classifier.py`
- Modify: `app/audio/mood.py` (add backward-compat re-exports)
- Create: `tests/test_audio/test_classification.py`

- [ ] **Step 1: Write tests for new classification module**

```python
# tests/test_audio/test_classification.py
"""Tests for classification module — profiles + classifier."""
from __future__ import annotations

import pytest

from app.audio.classification import MoodClassifier, MoodResult
from app.audio.classification.profiles import ALL_PROFILES, FeatureTarget, SubgenreProfile
from app.core.constants import TechnoSubgenre

class TestSubgenreProfile:
    def test_frozen(self) -> None:
        profile = ALL_PROFILES[0]
        with pytest.raises(AttributeError):
            profile.subgenre = TechnoSubgenre.ACID  # type: ignore[misc]

    def test_all_15_profiles(self) -> None:
        assert len(ALL_PROFILES) == 15

    def test_all_subgenres_covered(self) -> None:
        covered = {p.subgenre for p in ALL_PROFILES}
        assert covered == set(TechnoSubgenre)

    def test_feature_target_frozen(self) -> None:
        ft = FeatureTarget(weight=1.0, ideal=0.5, tolerance=0.1)
        with pytest.raises(AttributeError):
            ft.weight = 2.0  # type: ignore[misc]

class TestMoodResultTopMatches:
    def test_top_matches_present(self) -> None:
        classifier = MoodClassifier()
        result = classifier.classify({"energy_mean": 0.5})
        assert hasattr(result, "top_matches")
        assert len(result.top_matches) == 3

    def test_top_matches_ordered(self) -> None:
        classifier = MoodClassifier()
        result = classifier.classify({"energy_mean": 0.5})
        scores = [score for _, score in result.top_matches]
        assert scores == sorted(scores, reverse=True)

class TestMoodClassifierWithProfiles:
    def test_injected_profiles(self) -> None:
        """Classifier with subset of profiles should work."""
        subset = ALL_PROFILES[:3]
        classifier = MoodClassifier(profiles=subset)
        result = classifier.classify({"energy_mean": 0.5})
        assert isinstance(result, MoodResult)

    def test_backward_compat_default(self) -> None:
        """Default classifier uses all 15 profiles."""
        classifier = MoodClassifier()
        result = classifier.classify({"energy_mean": 0.5})
        assert len(result.scores) == 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_classification.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `classification/profiles.py`**

Extract `SUBGENRE_PROFILES` dict into frozen dataclasses:

```python
# app/audio/classification/profiles.py
"""Subgenre profiles — frozen dataclasses replacing 122-line inline dict.

Each profile defines feature targets for one of 15 techno subgenres.
Profiles are immutable and type-safe.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import TechnoSubgenre

@dataclass(frozen=True, slots=True)
class FeatureTarget:
    """Target for a single audio feature within a subgenre profile."""

    weight: float
    ideal: float
    tolerance: float

@dataclass(frozen=True, slots=True)
class SubgenreProfile:
    """Scoring profile for one techno subgenre."""

    subgenre: TechnoSubgenre
    features: dict[str, FeatureTarget]
    catch_all_penalty: float = 0.0

# ── 15 Subgenre Profiles ──────────────────────────────────────────────

AMBIENT_DUB = SubgenreProfile(
    subgenre=TechnoSubgenre.AMBIENT_DUB,
    features={
        "energy_mean": FeatureTarget(2.0, 0.1, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.5, 800.0, 500.0),
        "spectral_flatness": FeatureTarget(1.0, 0.15, 0.1),
        "spectral_flux_std": FeatureTarget(1.0, 0.5, 0.5),
        "loudness_range_lu": FeatureTarget(1.5, 12.0, 5.0),
        "crest_factor_db": FeatureTarget(1.0, 15.0, 5.0),
    },
)

DUB_TECHNO = SubgenreProfile(
    subgenre=TechnoSubgenre.DUB_TECHNO,
    features={
        "energy_mean": FeatureTarget(1.5, 0.2, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.5, 1200.0, 600.0),
        "spectral_flatness": FeatureTarget(1.0, 0.2, 0.1),
        "loudness_range_lu": FeatureTarget(2.0, 10.0, 4.0),
        "energy_low": FeatureTarget(1.5, 0.3, 0.15),
        "spectral_flux_std": FeatureTarget(1.0, 1.0, 1.0),
    },
)

MINIMAL = SubgenreProfile(
    subgenre=TechnoSubgenre.MINIMAL,
    features={
        "energy_mean": FeatureTarget(1.5, 0.25, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.0, 1500.0, 700.0),
        "spectral_flatness": FeatureTarget(1.5, 0.1, 0.08),
        "energy_std": FeatureTarget(1.5, 0.1, 0.08),
        "spectral_flux_std": FeatureTarget(1.0, 0.8, 0.5),
        "energy_mid": FeatureTarget(1.0, 0.15, 0.1),
    },
)

DETROIT = SubgenreProfile(
    subgenre=TechnoSubgenre.DETROIT,
    features={
        "energy_mean": FeatureTarget(1.5, 0.4, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.5, 2000.0, 800.0),
        "energy_mid": FeatureTarget(1.5, 0.2, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 5.0, 3.0),
        "crest_factor_db": FeatureTarget(1.0, 10.0, 4.0),
        "energy_highmid": FeatureTarget(1.0, 0.15, 0.1),
    },
)

MELODIC_DEEP = SubgenreProfile(
    subgenre=TechnoSubgenre.MELODIC_DEEP,
    features={
        "energy_mean": FeatureTarget(1.0, 0.35, 0.15),
        "spectral_centroid_hz": FeatureTarget(2.0, 1200.0, 500.0),
        "spectral_flatness": FeatureTarget(1.5, 0.08, 0.05),
        "energy_mid": FeatureTarget(1.5, 0.25, 0.1),
        "loudness_range_lu": FeatureTarget(1.0, 8.0, 3.0),
        "spectral_flux_std": FeatureTarget(1.0, 2.0, 1.5),
    },
)

PROGRESSIVE = SubgenreProfile(
    subgenre=TechnoSubgenre.PROGRESSIVE,
    features={
        "energy_mean": FeatureTarget(1.0, 0.4, 0.15),
        "energy_slope": FeatureTarget(2.0, 0.001, 0.001),
        "spectral_centroid_hz": FeatureTarget(1.0, 2000.0, 800.0),
        "energy_std": FeatureTarget(1.5, 0.2, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 5.0, 3.0),
        "loudness_range_lu": FeatureTarget(1.0, 8.0, 3.0),
    },
)

HYPNOTIC = SubgenreProfile(
    subgenre=TechnoSubgenre.HYPNOTIC,
    features={
        "energy_mean": FeatureTarget(1.0, 0.45, 0.15),
        "spectral_flux_std": FeatureTarget(2.0, 0.5, 0.4),
        "energy_std": FeatureTarget(2.0, 0.05, 0.04),
        "spectral_centroid_hz": FeatureTarget(1.0, 1800.0, 700.0),
        "spectral_flatness": FeatureTarget(1.0, 0.12, 0.08),
        "energy_low": FeatureTarget(1.0, 0.25, 0.1),
    },
    catch_all_penalty=1.0,  # applied via settings.mood_catch_all_penalty
)

DRIVING = SubgenreProfile(
    subgenre=TechnoSubgenre.DRIVING,
    features={
        "energy_mean": FeatureTarget(1.5, 0.55, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.0, 2500.0, 1000.0),
        "energy_low": FeatureTarget(1.5, 0.25, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 8.0, 4.0),
        "crest_factor_db": FeatureTarget(1.0, 8.0, 3.0),
        "energy_std": FeatureTarget(1.0, 0.12, 0.08),
    },
    catch_all_penalty=1.0,
)

TRIBAL = SubgenreProfile(
    subgenre=TechnoSubgenre.TRIBAL,
    features={
        "energy_mean": FeatureTarget(1.5, 0.5, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.0, 1800.0, 700.0),
        "energy_low": FeatureTarget(2.0, 0.3, 0.12),
        "energy_sub": FeatureTarget(1.5, 0.15, 0.08),
        "spectral_flux_std": FeatureTarget(1.0, 3.0, 2.0),
        "energy_std": FeatureTarget(1.0, 0.15, 0.1),
    },
)

BREAKBEAT = SubgenreProfile(
    subgenre=TechnoSubgenre.BREAKBEAT,
    features={
        "energy_mean": FeatureTarget(1.0, 0.5, 0.15),
        "spectral_flux_std": FeatureTarget(2.0, 8.0, 4.0),
        "energy_std": FeatureTarget(2.0, 0.25, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.0, 2500.0, 1000.0),
        "crest_factor_db": FeatureTarget(1.0, 12.0, 4.0),
        "energy_highmid": FeatureTarget(1.0, 0.18, 0.08),
    },
)

PEAK_TIME = SubgenreProfile(
    subgenre=TechnoSubgenre.PEAK_TIME,
    features={
        "energy_mean": FeatureTarget(2.0, 0.7, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.0, 3000.0, 1000.0),
        "energy_low": FeatureTarget(1.5, 0.25, 0.1),
        "crest_factor_db": FeatureTarget(1.0, 6.0, 3.0),
        "spectral_flux_mean": FeatureTarget(1.0, 10.0, 5.0),
        "loudness_range_lu": FeatureTarget(1.0, 5.0, 3.0),
    },
)

ACID = SubgenreProfile(
    subgenre=TechnoSubgenre.ACID,
    features={
        "spectral_centroid_hz": FeatureTarget(2.5, 4000.0, 1500.0),
        "spectral_flatness": FeatureTarget(1.5, 0.25, 0.1),
        "energy_mean": FeatureTarget(1.0, 0.55, 0.15),
        "energy_highmid": FeatureTarget(1.5, 0.22, 0.1),
        "spectral_flux_mean": FeatureTarget(1.0, 8.0, 4.0),
        "spectral_rolloff_85": FeatureTarget(1.0, 5000.0, 2000.0),
    },
)

RAW = SubgenreProfile(
    subgenre=TechnoSubgenre.RAW,
    features={
        "energy_mean": FeatureTarget(1.5, 0.65, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.5, 3500.0, 1200.0),
        "spectral_flatness": FeatureTarget(1.5, 0.3, 0.12),
        "crest_factor_db": FeatureTarget(1.0, 5.0, 3.0),
        "loudness_range_lu": FeatureTarget(1.0, 4.0, 2.0),
        "spectral_flux_std": FeatureTarget(1.0, 5.0, 3.0),
    },
)

INDUSTRIAL = SubgenreProfile(
    subgenre=TechnoSubgenre.INDUSTRIAL,
    features={
        "energy_mean": FeatureTarget(1.5, 0.75, 0.15),
        "spectral_centroid_hz": FeatureTarget(1.5, 4000.0, 1500.0),
        "spectral_flatness": FeatureTarget(2.0, 0.35, 0.12),
        "loudness_range_lu": FeatureTarget(1.5, 3.0, 2.0),
        "crest_factor_db": FeatureTarget(1.0, 4.0, 2.0),
        "energy_high": FeatureTarget(1.0, 0.15, 0.08),
    },
)

HARD_TECHNO = SubgenreProfile(
    subgenre=TechnoSubgenre.HARD_TECHNO,
    features={
        "energy_mean": FeatureTarget(2.0, 0.85, 0.1),
        "spectral_centroid_hz": FeatureTarget(1.0, 3500.0, 1500.0),
        "energy_low": FeatureTarget(1.5, 0.3, 0.12),
        "crest_factor_db": FeatureTarget(1.0, 3.0, 2.0),
        "loudness_range_lu": FeatureTarget(1.0, 3.0, 2.0),
        "spectral_flux_mean": FeatureTarget(1.0, 12.0, 5.0),
    },
)

ALL_PROFILES: tuple[SubgenreProfile, ...] = (
    AMBIENT_DUB, DUB_TECHNO, MINIMAL, DETROIT, MELODIC_DEEP, PROGRESSIVE,
    HYPNOTIC, DRIVING, TRIBAL, BREAKBEAT, PEAK_TIME, ACID, RAW, INDUSTRIAL,
    HARD_TECHNO,
)

# Catch-all subgenres identified by non-zero penalty in profile
CATCH_ALL_SUBGENRES: frozenset[TechnoSubgenre] = frozenset(
    p.subgenre for p in ALL_PROFILES if p.catch_all_penalty > 0
)
```

- [ ] **Step 4: Create `classification/classifier.py`**

```python
# app/audio/classification/classifier.py
"""MoodClassifier — generic Gaussian scoring engine (Strategy pattern).

Classifier is generic; profiles are swappable via constructor injection.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.config import settings
from app.core.constants import TechnoSubgenre

from .profiles import ALL_PROFILES, CATCH_ALL_SUBGENRES, SubgenreProfile

@dataclass
class MoodResult:
    """Result of mood classification."""

    mood: TechnoSubgenre
    confidence: float
    scores: dict[TechnoSubgenre, float] = field(default_factory=dict)
    reasoning: str = ""
    top_matches: list[tuple[TechnoSubgenre, float]] = field(default_factory=list)

class MoodClassifier:
    """Rule-based classifier for 15 techno subgenres (Strategy pattern).

    Profiles are injected via constructor — swappable for testing,
    custom genre sets, or A/B experiments.
    """

    def __init__(
        self, profiles: Sequence[SubgenreProfile] = ALL_PROFILES
    ) -> None:
        self._profiles = profiles

    def classify(self, features: dict[str, Any]) -> MoodResult:
        """Classify audio features into a techno subgenre."""
        scores: dict[TechnoSubgenre, float] = {}

        for profile in self._profiles:
            scores[profile.subgenre] = self._score_profile(profile, features)

        # Penalize catch-all subgenres
        for subgenre in CATCH_ALL_SUBGENRES:
            if subgenre in scores:
                scores[subgenre] *= settings.mood_catch_all_penalty

        # Find winner and compute confidence
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_scores[0][0]
        winner_score = sorted_scores[0][1]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

        confidence = float((winner_score - second_score) / (winner_score + 1e-10))
        confidence = float(np.clip(confidence, 0.0, 1.0))

        top_matches = [(sg, round(sc, 4)) for sg, sc in sorted_scores[:3]]

        reasoning = (
            f"Top match: {winner.value} (score={winner_score:.3f}), "
            f"runner-up: {sorted_scores[1][0].value} (score={second_score:.3f})"
        )

        return MoodResult(
            mood=winner,
            confidence=confidence,
            scores=scores,
            reasoning=reasoning,
            top_matches=top_matches,
        )

    def _score_profile(
        self, profile: SubgenreProfile, features: dict[str, Any]
    ) -> float:
        """Score features against a profile using Gaussian similarity."""
        total_score = 0.0
        total_weight = 0.0

        for feature_name, target in profile.features.items():
            value = features.get(feature_name)
            if value is None:
                continue

            diff = float(value) - target.ideal
            similarity = float(np.exp(-(diff**2) / (2.0 * target.tolerance**2)))

            total_score += target.weight * similarity
            total_weight += target.weight

        if total_weight == 0:
            return 0.0

        return total_score / total_weight
```

- [ ] **Step 5: Create `classification/__init__.py`**

```python
# app/audio/classification/__init__.py
"""Mood classification — Layer 2b."""
from app.audio.classification.classifier import MoodClassifier, MoodResult
from app.audio.classification.profiles import ALL_PROFILES, SubgenreProfile

__all__ = ["ALL_PROFILES", "MoodClassifier", "MoodResult", "SubgenreProfile"]
```

- [ ] **Step 6: Add backward-compat re-exports to `mood.py`**

```python
# app/audio/mood.py — TEMPORARY backward compat
"""Backward compatibility — re-exports from new locations.

TODO: Remove after all consumers updated (Task 10).
"""
from app.audio.classification.classifier import MoodClassifier, MoodResult  # noqa: F401
from app.audio.classification.profiles import (  # noqa: F401
    ALL_PROFILES,
    CATCH_ALL_SUBGENRES as _CATCH_ALL_SUBGENRES,
)

# Re-create SUBGENRE_PROFILES dict for backward compat with tests
SUBGENRE_PROFILES = {
    p.subgenre: {
        name: (t.weight, t.ideal, t.tolerance)
        for name, t in p.features.items()
    }
    for p in ALL_PROFILES
}
```

- [ ] **Step 7: Run classification tests + existing mood tests**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_classification.py tests/test_audio/test_mood.py -v`
Expected: PASS — all tests green (backward compat ensures old tests still work)

- [ ] **Step 8: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/classification/ app/audio/mood.py tests/test_audio/test_classification.py
git commit -m "feat(audio): add classification/ — SubgenreProfile dataclasses + generic MoodClassifier"
```

---

### Task 9: Refactor `pipeline.py` — inject loader, eager context, parallel execution

**Files:**
- Modify: `app/audio/pipeline.py`
- Modify: `app/audio/analyzers/base.py` (remove deprecated `analyze()` shim)
- Create: `tests/test_audio/test_pipeline_refactored.py`

- [ ] **Step 1: Remove deprecated `analyze()` shim from BaseAnalyzer**

In `app/audio/analyzers/base.py`, delete the `async def analyze(self, signal)` method added in Task 6. Pipeline now calls `run(ctx)` directly via `asyncio.to_thread()`.

- [ ] **Step 2: Refactor pipeline.py**

Key changes:
1. Accept `AudioLoader` in constructor (DI)
2. Create `AnalysisContext` once per track (eager computation)
3. Use `asyncio.to_thread()` for parallel analyzer dispatch
4. Remove inline `_load_audio()` method (replaced by AudioLoader)
5. Keep `PipelineResult` in this file

```python
# app/audio/pipeline.py
"""Analysis pipeline — orchestrates analyzers with parallel execution.

Creates AnalysisContext once (eager STFT/magnitude), then dispatches
all analyzers via asyncio.to_thread() for true CPU-bound parallelism.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.core.context import AnalysisContext
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AnalyzerResult, AudioSignal

@dataclass
class PipelineResult:
    """Combined result from all analyzers in a pipeline run."""

    results: list[AnalyzerResult] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[dict[str, str]]:
        return [
            {"analyzer": r.analyzer_name, "error": r.error or "unknown"}
            for r in self.results
            if not r.success
        ]

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

class AnalysisPipeline:
    """Runs analyzers on audio files with shared context and parallel execution."""

    def __init__(self, registry: AnalyzerRegistry, loader: AudioLoader | None = None) -> None:
        self.registry = registry
        self._loader = loader or AudioLoader()

    async def analyze(
        self,
        file_path: str,
        analyzers: list[str] | None = None,
        max_duration: float | None = None,
    ) -> PipelineResult:
        """Run analyzers on audio file. Returns combined features."""
        signal = await self._loader.load(file_path)

        # Clip audio to max_duration if specified
        if max_duration and signal.duration_seconds > max_duration:
            max_samples = int(max_duration * signal.sample_rate)
            signal = AudioSignal(
                samples=signal.samples[:max_samples],
                sample_rate=signal.sample_rate,
                duration_seconds=max_duration,
                file_path=signal.file_path,
            )

        # Eager context: STFT, magnitude, freqs, frame_energies computed once
        ctx = AnalysisContext(signal)

        # Resolve analyzer instances
        analyzer_names = analyzers or self.registry.list_available()
        instances = []
        for name in analyzer_names:
            analyzer = self.registry.get(name)
            if analyzer and analyzer.is_available():
                instances.append(analyzer)

        # True parallelism — CPU-bound work offloaded to thread pool
        results: list[AnalyzerResult] = list(
            await asyncio.gather(
                *(asyncio.to_thread(a.run, ctx) for a in instances)
            )
        )

        return PipelineResult(
            results=results,
            features=self._merge_features(results),
        )

    @staticmethod
    def _merge_features(results: list[AnalyzerResult]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for result in results:
            if result.success:
                merged.update(result.features)
        return merged
```

- [ ] **Step 3: Write dedicated pipeline tests**

```python
# tests/test_audio/test_pipeline_refactored.py
"""Tests for refactored AnalysisPipeline — DI, context, parallelism."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.audio.core.loader import AudioLoader
from app.audio.core.types import AudioSignal
from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.pipeline import AnalysisPipeline

@pytest.fixture
def signal() -> AudioSignal:
    rng = np.random.default_rng(42)
    samples = rng.standard_normal(44100).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=44100, duration_seconds=1.0)

@pytest.fixture
def registry() -> AnalyzerRegistry:
    reg = AnalyzerRegistry()
    reg.discover()
    return reg

class TestPipelineCreatesContext:
    async def test_pipeline_creates_analysis_context(self, signal, registry) -> None:
        """Pipeline creates AnalysisContext from signal (eager STFT)."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake/path.wav", analyzers=["loudness"])
        assert result.success_count >= 1
        assert "lufs_i" in result.features

    async def test_pipeline_uses_injected_loader(self, signal, registry) -> None:
        """Pipeline calls AudioLoader.load() — no inline loading."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        await pipeline.analyze("/fake/path.wav", analyzers=["loudness"])
        loader.load.assert_called_once_with("/fake/path.wav")

    async def test_pipeline_dispatches_via_to_thread(self, signal, registry) -> None:
        """Pipeline uses asyncio.to_thread for CPU-bound analyzers."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        with patch("app.audio.pipeline.asyncio.to_thread", wraps=__import__("asyncio").to_thread) as mock_tt:
            result = await pipeline.analyze("/fake/path.wav", analyzers=["loudness", "energy"])
            assert mock_tt.call_count >= 2  # one per analyzer

    async def test_pipeline_merges_features(self, signal, registry) -> None:
        """Pipeline merges features from multiple analyzers."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake/path.wav", analyzers=["loudness", "energy"])
        assert "lufs_i" in result.features
        assert "energy_mean" in result.features
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_pipeline_refactored.py tests/test_audio/ -v`
Expected: PASS — all tests green (pipeline + new dedicated tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/audio/pipeline.py app/audio/analyzers/base.py tests/test_audio/test_pipeline_refactored.py
git commit -m "refactor(audio): pipeline uses AudioLoader DI + eager AnalysisContext + asyncio.to_thread parallelism"
```

---

### Task 10: Update services — import paths + AudioLoader injection

**Files:**
- Modify: `app/services/audio_service.py`
- Modify: `app/services/curation_service.py`
- Modify: `app/mcp/dependencies.py`
- Modify: `app/server.py`

- [ ] **Step 1: Update audio_service.py imports**

```python
# Changes in app/services/audio_service.py:
# OLD: from app.audio.mood import MoodClassifier
# NEW: from app.audio.classification import MoodClassifier
# OLD: from app.audio.pipeline import AnalysisPipeline
# (no change — pipeline stays in same location)
```

- [ ] **Step 2: Update curation_service.py imports**

```python
# Changes in app/services/curation_service.py:
# OLD: from app.audio.mood import MoodClassifier
# NEW: from app.audio.classification import MoodClassifier
```

- [ ] **Step 3: Update mcp/dependencies.py — add AudioLoader**

```python
# In the tiered_pipeline DI provider:
# OLD: pipeline = AnalysisPipeline(registry)
# NEW:
from app.audio.core.loader import AudioLoader
pipeline = AnalysisPipeline(registry, AudioLoader(settings.audio_sample_rate))
```

- [ ] **Step 4: Update server.py — import from new location**

```python
# OLD: from app.audio.registry import AnalyzerRegistry
# NEW: from app.audio.analyzers import AnalyzerRegistry
```

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest -v`
Expected: PASS — all tests green

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add app/services/audio_service.py app/services/curation_service.py app/mcp/dependencies.py app/server.py
git commit -m "refactor(audio): update service imports to new audio module locations"
```

---

### Task 11: Update tests — import paths

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_lifespan.py`
- Modify: `tests/test_audio/test_analyzers.py`
- Modify: `tests/test_audio/test_registry.py`
- Modify: `tests/test_audio/test_structure.py`
- Modify: `tests/test_audio/test_mood.py`

- [ ] **Step 1: Update all test imports**

```python
# tests/conftest.py:
# OLD: from app.audio.registry import AnalyzerRegistry
# NEW: from app.audio.analyzers import AnalyzerRegistry

# tests/test_lifespan.py:
# OLD: from app.audio.registry import AnalyzerRegistry
# NEW: from app.audio.analyzers import AnalyzerRegistry

# tests/test_audio/test_analyzers.py:
# OLD: from app.audio.registry import AudioSignal
# NEW: from app.audio.core import AudioSignal

# tests/test_audio/test_registry.py:
# OLD: from app.audio.registry import AnalyzerRegistry, AnalyzerResult, AudioSignal, BaseAnalyzer
# NEW: from app.audio.analyzers import AnalyzerRegistry, BaseAnalyzer
# NEW: from app.audio.core import AnalyzerResult, AudioSignal
# Also update DummyAnalyzer to use new sync API (_extract + @register_analyzer)

# tests/test_audio/test_structure.py:
# OLD: from app.audio.registry import AudioSignal
# NEW: from app.audio.core import AudioSignal

# tests/test_audio/test_mood.py:
# OLD: from app.audio.mood import (...)
# NEW: from app.audio.classification import MoodClassifier, MoodResult
# NEW: from app.audio.classification.profiles import ALL_PROFILES, CATCH_ALL_SUBGENRES
# Adapt SUBGENRE_PROFILES references to use ALL_PROFILES with FeatureTarget
```

- [ ] **Step 2: Update test_registry.py DummyAnalyzer to new API**

```python
# DummyAnalyzer now uses sync _extract:
from app.audio.analyzers.base import BaseAnalyzer, register_analyzer, _ANALYZER_REGISTRY
from app.audio.core.context import AnalysisContext

@register_analyzer
class DummyAnalyzer(BaseAnalyzer):
    name = "dummy"
    capabilities = frozenset({"test"})

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        return {"value": 42}
```

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest -v`
Expected: PASS — all tests green

- [ ] **Step 4: Run lint + mypy**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run ruff check && uv run ruff format --check && uv run mypy app/`
Expected: PASS — no errors

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add tests/
git commit -m "refactor(audio): update test imports to new audio module structure"
```

---

### Task 12: Delete old files + remove backward-compat aliases

**Files:**
- Delete: `app/audio/registry.py`
- Delete: `app/audio/mood.py`

- [ ] **Step 1: Verify no remaining imports from old paths**

```bash
cd /Users/laptop/dev/dj-music-plugin
rg "from app\.audio\.registry import" --type py
rg "from app\.audio\.mood import" --type py
```

Expected: Zero results (all imports updated in Tasks 10-11)

- [ ] **Step 2: Delete old files**

```bash
cd /Users/laptop/dev/dj-music-plugin
rm app/audio/registry.py app/audio/mood.py
```

- [ ] **Step 3: Update `app/audio/__init__.py` re-exports**

Update top-level `app/audio/__init__.py` to point to new locations:

```python
# app/audio/__init__.py
"""Audio analysis module — layered architecture.

Layers:
    core/       — DSP primitives, types (0 app deps)
    analyzers/  — feature extractors (BaseAnalyzer + registry)
    classification/ — mood/subgenre classifier (Strategy pattern)
    pipeline.py — orchestrator (parallel execution)
"""
from app.audio.analyzers import AnalyzerRegistry, BaseAnalyzer
from app.audio.classification import MoodClassifier, MoodResult
from app.audio.core import AnalysisContext, AnalyzerResult, AudioLoader, AudioSignal, FrameParams

__all__ = [
    "AnalysisContext",
    "AnalyzerRegistry",
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "BaseAnalyzer",
    "FrameParams",
    "MoodClassifier",
    "MoodResult",
]
```

- [ ] **Step 4: Also update `scripts/benchmark_audio.py` if it imports from old paths**

```bash
rg "from app\.audio\.(registry|mood)" scripts/ --type py
```

Update any remaining imports.

- [ ] **Step 5: Run full test suite + lint**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest -v && uv run ruff check && uv run mypy app/`
Expected: PASS — everything green, no broken imports

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add -u app/audio/registry.py app/audio/mood.py
git add app/audio/__init__.py scripts/benchmark_audio.py
git commit -m "refactor(audio): delete registry.py and mood.py — replaced by core/, analyzers/base.py, classification/"
```

---

### Task 13: Final cleanup — update docs, verify metrics

**Files:**
- Modify: `CHANGELOG.md` (add Unreleased section)
- Verify: lint, mypy, all tests, no stale imports

- [ ] **Step 1: Run full verification**

```bash
cd /Users/laptop/dev/dj-music-plugin
uv run pytest -v
uv run ruff check
uv run ruff format --check
uv run mypy app/
```

Expected: PASS — all green

- [ ] **Step 2: Verify refactoring metrics from spec**

```bash
# Duplicated frame energy: should be 0 (grep for the pattern)
rg "np\.mean\(frame\*\*2\)" app/audio/ --type py
# Should only appear in core/framing.py

# Hardcoded 2048/512: should only be in FrameParams defaults
rg "frame_length = 2048" app/audio/ --type py
rg "hop_length = 512" app/audio/ --type py
# Should only appear in core/types.py FrameParams defaults

# Empty signal guards: should only be in BaseAnalyzer.run()
rg "len\(samples\) == 0" app/audio/ --type py
# Should only appear in analyzers/base.py
```

- [ ] **Step 3: Update CHANGELOG.md**

Add to `[Unreleased]` section:
```markdown
### Changed (internal refactoring — no external API changes for services)
- Refactored `app/audio/` into layered architecture: `core/` → `analyzers/` → `pipeline.py`
- Analyzers now use Template Method pattern (sync `_extract(ctx)` instead of `async analyze(signal)`)
- Pipeline uses `asyncio.to_thread()` for parallel CPU-bound analyzer execution
- MoodClassifier uses Strategy pattern with injectable SubgenreProfile dataclasses
- Shared STFT/magnitude/frame_energies via eager AnalysisContext (thread-safe)

### Removed
- `app/audio/registry.py` (split into `core/types.py` + `analyzers/base.py`)
- `app/audio/mood.py` (split into `classification/classifier.py` + `classification/profiles.py`)
- Duplicated frame energy computation (was in energy.py + structure.py)
- Duplicated FFT/windowing (was in spectral.py, energy.py, key.py)
- 8 copies of empty signal guard (now single check in BaseAnalyzer.run())
- Hardcoded frame_length/hop_length (now FrameParams dataclass)
```

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for audio module refactoring"
```

- [ ] **Step 5: Final full test run**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run pytest -v && uv run ruff check && uv run mypy app/`
Expected: PASS — all green, refactoring complete
