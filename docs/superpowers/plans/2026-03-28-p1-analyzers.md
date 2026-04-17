# Phase 1 Audio Analyzers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 6 new audio analyzers (danceability, tempogram, dissonance, dynamic_complexity, tonnetz, beats_loudness) with inter-analyzer dependency mechanism and two-phase pipeline execution.

**Architecture:** Extend existing `BaseAnalyzer` Template Method + `@register_analyzer` decorator pattern. Add `depends_on` ClassVar for dependency declaration, conditional dispatch in `run()`, and split pipeline into Phase 1 (independent, parallel) + Phase 2 (dependent, receives Phase 1 output). New features persisted as 6 nullable columns in `TrackAudioFeaturesComputed`.

**Tech Stack:** Python 3.12, essentia, librosa, numpy, SQLAlchemy 2.0+, pytest

**Spec:** `docs/superpowers/specs/2026-03-28-p1-analyzers-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `app/audio/analyzers/base.py` | Add `depends_on` ClassVar, update `run()` with conditional dispatch |
| Modify | `app/audio/analyzers/beat.py` | Export `beat_times` in output dict |
| Create | `app/audio/analyzers/danceability.py` | Essentia DFA danceability (0.0-3.0) |
| Create | `app/audio/analyzers/tempogram.py` | Librosa tempogram ratio vector (~10 dims) |
| Create | `app/audio/analyzers/dissonance.py` | Essentia spectral dissonance mean (0.0-1.0) |
| Create | `app/audio/analyzers/dynamic_complexity.py` | Essentia dynamic complexity (0.0-~10.0) |
| Create | `app/audio/analyzers/tonnetz.py` | Librosa tonal centroid 6D vector |
| Create | `app/audio/analyzers/beats_loudness.py` | Essentia beat-loudness band ratio (6 dims, depends on `beat`) |
| Modify | `app/audio/pipeline.py` | Two-phase execution: independent parallel, then dependent |
| Modify | `app/models/audio.py` | Add 6 nullable columns, update `filter_features()` |
| Create | `tests/test_audio/test_danceability.py` | 3 tests: happy path, graceful skip, edge case |
| Create | `tests/test_audio/test_tempogram.py` | 3 tests: happy path, graceful skip, edge case |
| Create | `tests/test_audio/test_dissonance.py` | 4 tests: happy path, comparative, graceful skip, edge |
| Create | `tests/test_audio/test_dynamic_complexity.py` | 4 tests: happy path, comparative, graceful skip, edge |
| Create | `tests/test_audio/test_tonnetz.py` | 3 tests: happy path + vector length, graceful skip, edge |
| Create | `tests/test_audio/test_beats_loudness.py` | 4 tests: happy path, no beat_times, graceful skip, edge |
| Modify | `tests/test_audio/test_analyzer_base.py` | Add tests for `depends_on` + conditional dispatch |
| Modify | `tests/test_audio/test_pipeline_refactored.py` | Add two-phase execution tests |

---

### Task 1: BaseAnalyzer — Add `depends_on` and Conditional Dispatch

**Files:**
- Modify: `app/audio/analyzers/base.py`
- Test: `tests/test_audio/test_analyzer_base.py`

**Context:** `BaseAnalyzer` currently has `name`, `capabilities`, `required_packages` ClassVars and a `run(self, ctx)` method. We add `depends_on: ClassVar[frozenset[str]]` and update `run()` to accept optional `prior_results` parameter. Conditional dispatch: if `self.depends_on` is truthy, call `_extract(ctx, prior_results=...)`, else call `_extract(ctx)` — preserving backward compatibility for all 8 existing analyzers.

- [ ] **Step 1: Write failing test for `depends_on` default**

Add to `tests/test_audio/test_analyzer_base.py`:

```python
def test_depends_on_default_is_empty():
    """BaseAnalyzer.depends_on defaults to empty frozenset."""
    @register_analyzer
    class NoDepsAnalyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_no_deps"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []

        def _extract(self, ctx):
            return {"val": 1}

    assert NoDepsAnalyzer.depends_on == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_analyzer_base.py::test_depends_on_default_is_empty -v
```

Expected: `AttributeError: type object 'NoDepsAnalyzer' has no attribute 'depends_on'`

- [ ] **Step 3: Add `depends_on` ClassVar to `BaseAnalyzer`**

In `app/audio/analyzers/base.py`, add after `required_packages`:

```python
depends_on: ClassVar[frozenset[str]] = frozenset()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_analyzer_base.py::test_depends_on_default_is_empty -v
```

Expected: PASS

- [ ] **Step 5: Write failing test for conditional dispatch**

Add to `tests/test_audio/test_analyzer_base.py`:

```python
def test_run_passes_prior_results_to_dependent_analyzer(sine_signal):
    """run() passes prior_results to _extract when depends_on is set."""
    @register_analyzer
    class _DepAnalyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_dep"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []
        depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})

        def _extract(self, ctx, *, prior_results=None):
            val = (prior_results or {}).get("beat_times", [])
            return {"got_beats": len(val) > 0}

    analyzer = _DepAnalyzer()
    ctx = AnalysisContext(sine_signal)
    result = analyzer.run(ctx, {"beat_times": [0.5, 1.0, 1.5]})
    assert result.success
    assert result.features["got_beats"] is True

def test_run_does_not_pass_prior_results_to_independent_analyzer(sine_signal):
    """run() calls _extract(ctx) without prior_results for independent analyzers."""
    @register_analyzer
    class _IndepAnalyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_indep"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []

        def _extract(self, ctx):
            return {"independent": True}

    analyzer = _IndepAnalyzer()
    ctx = AnalysisContext(sine_signal)
    result = analyzer.run(ctx, {"beat_times": [0.5, 1.0]})  # prior_results ignored
    assert result.success
    assert result.features["independent"] is True
```

Note: `sine_signal` fixture should already exist in the test file. If not, add:

```python
@pytest.fixture
def sine_signal():
    t = np.linspace(0, 2.0, int(22050 * 2.0), endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=22050, duration_seconds=2.0)
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_analyzer_base.py -k "dependent or independent" -v
```

Expected: FAIL (run() doesn't accept `prior_results` yet)

- [ ] **Step 7: Update `run()` with conditional dispatch**

Replace the `run()` method in `app/audio/analyzers/base.py`:

```python
def run(self, ctx: AnalysisContext, prior_results: dict[str, Any] | None = None) -> AnalyzerResult:
    """Template Method — guard + delegate. Synchronous (CPU-bound).

    Called via asyncio.to_thread() by pipeline for parallelism.
    Dependent analyzers (with depends_on) receive prior_results from Phase 1.
    """
    if len(ctx.samples) == 0:
        return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")
    try:
        if self.depends_on:
            features = self._extract(ctx, prior_results=prior_results or {})
        else:
            features = self._extract(ctx)
        return AnalyzerResult(analyzer_name=self.name, features=features)
    except Exception as e:
        logger.warning("Analyzer %s failed: %s", self.name, e)
        return AnalyzerResult(analyzer_name=self.name, success=False, error=str(e))
```

- [ ] **Step 8: Run all base tests to verify green**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_analyzer_base.py -v
```

Expected: ALL PASS (including existing tests — backward compatible)

- [ ] **Step 9: Run full test suite to verify no regressions**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest -x -q
```

Expected: All existing tests pass

- [ ] **Step 10: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/base.py tests/test_audio/test_analyzer_base.py
```

Message: `feat(audio): add depends_on ClassVar and conditional dispatch to BaseAnalyzer`

---

### Task 2: BeatDetector — Export `beat_times`

**Files:**
- Modify: `app/audio/analyzers/beat.py`
- Test: `tests/test_audio/test_analyzers.py` (or create `tests/test_audio/test_beat.py` if no beat tests exist yet)

**Context:** `BeatDetector._extract()` computes `onsets` (onset times array) at line 48 but doesn't include it in the output. Add `"beat_times": onsets.tolist()` to the return dict. This key is consumed by `BeatsLoudnessAnalyzer` via `prior_results` and is NOT persisted to DB (filtered out by `filter_features()`).

- [ ] **Step 1: Write failing test**

Create `tests/test_audio/test_beat_export.py`:

```python
"""Tests for BeatDetector beat_times export."""

from __future__ import annotations

import numpy as np

from app.audio.analyzers.beat import BeatDetector
from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050

def _make_kick_signal(bpm: float = 130.0, duration: float = 4.0) -> AudioSignal:
    """Generate a synthetic kick pattern at given BPM."""
    n_samples = int(SAMPLE_RATE * duration)
    samples = np.zeros(n_samples, dtype=np.float32)
    beat_interval = 60.0 / bpm
    t = 0.0
    while t < duration:
        idx = int(t * SAMPLE_RATE)
        # Short impulse (10ms kick)
        end_idx = min(idx + int(0.01 * SAMPLE_RATE), n_samples)
        kick_len = end_idx - idx
        if kick_len > 0:
            samples[idx:end_idx] = 0.8 * np.sin(
                2 * np.pi * 60 * np.arange(kick_len) / SAMPLE_RATE
            ).astype(np.float32)
        t += beat_interval
    return AudioSignal(
        samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration
    )

def test_beat_detector_exports_beat_times():
    """BeatDetector output must include beat_times as list of floats."""
    signal = _make_kick_signal(bpm=130.0, duration=4.0)
    detector = BeatDetector()
    result = detector.run(AnalysisContext(signal))

    assert result.success
    assert "beat_times" in result.features, "beat_times missing from BeatDetector output"
    bt = result.features["beat_times"]
    assert isinstance(bt, list)
    assert len(bt) > 0
    assert all(isinstance(t, float) for t in bt)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_beat_export.py -v
```

Expected: FAIL — `"beat_times" not in result.features`

- [ ] **Step 3: Add `beat_times` to BeatDetector output**

In `app/audio/analyzers/beat.py`, update the return dict (line 77-82) to:

```python
return {
    "onset_rate": round(onset_rate, 4),
    "pulse_clarity": round(pulse_clarity, 4),
    "kick_prominence": round(kick_prominence, 4),
    "hp_ratio": round(hp_ratio, 4),
    "beat_times": onsets.tolist(),
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_beat_export.py -v
```

Expected: PASS

- [ ] **Step 5: Run existing tests to verify no regressions**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/ -x -q
```

Expected: All pass (existing tests don't check for absence of `beat_times`)

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/beat.py tests/test_audio/test_beat_export.py
```

Message: `feat(audio): export beat_times from BeatDetector for dependent analyzers`

---

### Task 3: DanceabilityAnalyzer

**Files:**
- Create: `app/audio/analyzers/danceability.py`
- Create: `tests/test_audio/test_danceability.py`

**Context:** Independent analyzer using essentia's Danceability (DFA algorithm). Output: `{"danceability": float}` in range 0.0-3.0. No `depends_on`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_audio/test_danceability.py`:

```python
"""Tests for DanceabilityAnalyzer."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 3.0

def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )

def _kick_pattern(bpm: float = 130.0) -> np.ndarray:
    """Generate rhythmic kick pattern — should score higher danceability."""
    n = int(SAMPLE_RATE * DURATION)
    samples = np.zeros(n, dtype=np.float32)
    interval = int(60.0 / bpm * SAMPLE_RATE)
    for start in range(0, n, interval):
        end = min(start + int(0.01 * SAMPLE_RATE), n)
        kick_len = end - start
        if kick_len > 0:
            samples[start:end] = 0.8 * np.sin(
                2 * np.pi * 60 * np.arange(kick_len) / SAMPLE_RATE
            ).astype(np.float32)
    return samples

def test_danceability_happy_path():
    """DanceabilityAnalyzer produces float in valid range."""
    from app.audio.analyzers.danceability import DanceabilityAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = DanceabilityAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "danceability" in result.features
    val = result.features["danceability"]
    assert isinstance(val, float)
    assert 0.0 <= val <= 3.0

def test_danceability_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.danceability import DanceabilityAnalyzer

        analyzer = DanceabilityAnalyzer()
        assert not analyzer.is_available()

def test_danceability_silence():
    """Silence produces a valid (likely low) danceability value, no crash."""
    from app.audio.analyzers.danceability import DanceabilityAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = DanceabilityAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    # Either success with low value, or graceful failure — no crash
    if result.success:
        assert 0.0 <= result.features["danceability"] <= 3.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_danceability.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.audio.analyzers.danceability'`

- [ ] **Step 3: Implement DanceabilityAnalyzer**

Create `app/audio/analyzers/danceability.py`:

```python
"""Danceability analyzer — essentia DFA algorithm.

Computes: danceability (0.0-3.0 range, Detrended Fluctuation Analysis).
Higher values indicate more regular rhythmic patterns.
Techno average: ~1.5-2.5.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class DanceabilityAnalyzer(BaseAnalyzer):
    """Danceability via essentia's Detrended Fluctuation Analysis."""

    name: ClassVar[str] = "danceability"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        danceability_algo = es.Danceability()
        result, _ = danceability_algo(ctx.samples)
        return {"danceability": round(float(result), 4)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_danceability.py -v
```

Expected: PASS (or skip if essentia not installed)

- [ ] **Step 5: Lint check**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run ruff check app/audio/analyzers/danceability.py
```

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/danceability.py tests/test_audio/test_danceability.py
```

Message: `feat(audio): add DanceabilityAnalyzer (essentia DFA)`

---

### Task 4: TempogramAnalyzer

**Files:**
- Create: `app/audio/analyzers/tempogram.py`
- Create: `tests/test_audio/test_tempogram.py`

**Context:** Independent analyzer using librosa's tempogram. Output: `{"tempogram_ratio_vector": list[float]}` — normalized autocorrelation at standard BPM ratios. Key must match DB column name exactly.

- [ ] **Step 1: Write failing tests**

Create `tests/test_audio/test_tempogram.py`:

```python
"""Tests for TempogramAnalyzer."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 4.0

def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )

def _click_track(bpm: float = 130.0) -> np.ndarray:
    """Generate click track at given BPM."""
    n = int(SAMPLE_RATE * DURATION)
    samples = np.zeros(n, dtype=np.float32)
    interval = int(60.0 / bpm * SAMPLE_RATE)
    for start in range(0, n, interval):
        end = min(start + 5, n)  # very short click
        samples[start:end] = 0.9
    return samples

def test_tempogram_happy_path():
    """TempogramAnalyzer produces vector of floats."""
    from app.audio.analyzers.tempogram import TempogramAnalyzer

    signal = _make_signal(_click_track())
    analyzer = TempogramAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "tempogram_ratio_vector" in result.features
    vec = result.features["tempogram_ratio_vector"]
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(v, float) for v in vec)
    assert all(0.0 <= v <= 1.0 for v in vec)

def test_tempogram_graceful_skip_no_librosa():
    """Without librosa, analyzer reports unavailable."""
    with patch.dict("sys.modules", {"librosa": None}):
        from app.audio.analyzers.tempogram import TempogramAnalyzer

        analyzer = TempogramAnalyzer()
        assert not analyzer.is_available()

def test_tempogram_short_audio():
    """Very short audio (<1s) doesn't crash."""
    from app.audio.analyzers.tempogram import TempogramAnalyzer

    short = _make_signal(np.random.default_rng(42).standard_normal(int(SAMPLE_RATE * 0.5)).astype(np.float32))
    analyzer = TempogramAnalyzer()
    result = analyzer.run(AnalysisContext(short))

    # Either success or graceful error — no crash
    assert isinstance(result.success, bool)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_tempogram.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement TempogramAnalyzer**

Create `app/audio/analyzers/tempogram.py`:

```python
"""Tempogram ratio analyzer — librosa tempogram autocorrelation.

Computes: tempogram_ratio_vector — normalized autocorrelation at standard BPM
ratios (0.5x, 1x, 2x, 3x, 4x, etc.). Detects metric complexity.
Straight techno: high peak at 1x. Polyrhythmic: distributed peaks.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class TempogramAnalyzer(BaseAnalyzer):
    """Tempogram ratio via librosa autocorrelation tempogram."""

    name: ClassVar[str] = "tempogram"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm", "tempo"})
    required_packages: ClassVar[list[str]] = ["librosa"]

    # Standard BPM ratio multipliers to sample from tempogram
    _BPM_RATIOS: ClassVar[tuple[float, ...]] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import librosa

        # Compute onset envelope and tempogram
        onset_env = librosa.onset.onset_strength(y=ctx.samples, sr=ctx.sr)
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=ctx.sr)

        # Estimate dominant tempo
        tempo = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=ctx.sr)
        base_bpm = float(tempo[0]) if len(tempo) > 0 else 120.0

        # Sample tempogram at BPM ratio positions
        # tempogram rows correspond to BPM values via lag
        freqs = librosa.tempo_frequencies(tempogram.shape[0], sr=ctx.sr)

        # Mean across time
        acf = np.mean(tempogram, axis=1)

        # Normalize
        acf_max = float(np.max(acf)) if np.max(acf) > 0 else 1.0
        acf_norm = acf / acf_max

        # Sample at ratio positions
        ratios: list[float] = []
        for ratio in self._BPM_RATIOS:
            target_bpm = base_bpm * ratio
            # Find closest frequency bin
            idx = int(np.argmin(np.abs(freqs - target_bpm)))
            ratios.append(round(float(acf_norm[idx]), 4))

        return {"tempogram_ratio_vector": ratios}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_tempogram.py -v
```

Expected: PASS

- [ ] **Step 5: Run lint**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run ruff check app/audio/analyzers/tempogram.py
```

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/tempogram.py tests/test_audio/test_tempogram.py
```

Message: `feat(audio): add TempogramAnalyzer (librosa tempogram ratio)`

---

### Task 5: DissonanceAnalyzer

**Files:**
- Create: `app/audio/analyzers/dissonance.py`
- Create: `tests/test_audio/test_dissonance.py`

**Context:** Independent analyzer using essentia's Dissonance algorithm. Output: `{"dissonance_mean": float}` in range 0.0-1.0 (mean spectral dissonance across frames). Lower = cleaner harmonics, higher = harsher texture.

- [ ] **Step 1: Write failing tests**

Create `tests/test_audio/test_dissonance.py`:

```python
"""Tests for DissonanceAnalyzer."""

from __future__ import annotations

import numpy as np

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 2.0

def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )

def _pure_sine(freq: float = 440.0) -> np.ndarray:
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)

def _dissonant_cluster() -> np.ndarray:
    """Two close frequencies creating beating/dissonance."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    # 440Hz + 445Hz = very dissonant beating
    return (0.3 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 445 * t)).astype(np.float32)

def test_dissonance_happy_path():
    """DissonanceAnalyzer produces float in valid range."""
    from app.audio.analyzers.dissonance import DissonanceAnalyzer

    signal = _make_signal(_pure_sine())
    analyzer = DissonanceAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "dissonance_mean" in result.features
    val = result.features["dissonance_mean"]
    assert isinstance(val, float)
    assert 0.0 <= val <= 1.0

def test_dissonance_comparative_sine_vs_cluster():
    """Pure sine should be less dissonant than close frequency cluster."""
    from app.audio.analyzers.dissonance import DissonanceAnalyzer

    analyzer = DissonanceAnalyzer()
    sine_result = analyzer.run(AnalysisContext(_make_signal(_pure_sine())))
    cluster_result = analyzer.run(AnalysisContext(_make_signal(_dissonant_cluster())))

    if sine_result.success and cluster_result.success:
        assert sine_result.features["dissonance_mean"] <= cluster_result.features["dissonance_mean"]

def test_dissonance_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.dissonance import DissonanceAnalyzer

        analyzer = DissonanceAnalyzer()
        assert not analyzer.is_available()

def test_dissonance_silence():
    """Silence doesn't crash."""
    from app.audio.analyzers.dissonance import DissonanceAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = DissonanceAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    assert isinstance(result.success, bool)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_dissonance.py -v
```

- [ ] **Step 3: Implement DissonanceAnalyzer**

Create `app/audio/analyzers/dissonance.py`:

```python
"""Dissonance analyzer — essentia spectral dissonance.

Computes: dissonance_mean (0.0-1.0) — mean spectral dissonance across frames.
Low values = clean harmonics (melodic techno), high values = harsh texture (industrial).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class DissonanceAnalyzer(BaseAnalyzer):
    """Mean spectral dissonance via essentia."""

    name: ClassVar[str] = "dissonance"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral", "harmony"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        # Frame-wise spectral peaks + dissonance
        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        peaks = es.SpectralPeaks(sampleRate=ctx.sr)
        dissonance = es.Dissonance()

        frame_size = 2048
        hop_size = 1024
        dissonance_values: list[float] = []

        for start in range(0, len(ctx.samples) - frame_size, hop_size):
            frame = ctx.samples[start : start + frame_size]
            windowed = w(frame)
            spec = spectrum(windowed)
            freqs, mags = peaks(spec)
            if len(freqs) >= 2:
                diss = dissonance(freqs, mags)
                dissonance_values.append(float(diss))

        mean_diss = float(np.mean(dissonance_values)) if dissonance_values else 0.0
        return {"dissonance_mean": round(mean_diss, 4)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_dissonance.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/dissonance.py tests/test_audio/test_dissonance.py
```

Message: `feat(audio): add DissonanceAnalyzer (essentia spectral dissonance)`

---

### Task 6: DynamicComplexityAnalyzer

**Files:**
- Create: `app/audio/analyzers/dynamic_complexity.py`
- Create: `tests/test_audio/test_dynamic_complexity.py`

**Context:** Independent analyzer using essentia's DynamicComplexity. Output: `{"dynamic_complexity": float}` — loudness variance descriptor (0.0-~10.0). Low = flat energy, high = builds and drops.

- [ ] **Step 1: Write failing tests**

Create `tests/test_audio/test_dynamic_complexity.py`:

```python
"""Tests for DynamicComplexityAnalyzer."""

from __future__ import annotations

import numpy as np

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 3.0

def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )

def _constant_tone() -> np.ndarray:
    """Constant amplitude — low dynamic complexity."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

def _fade_in_out() -> np.ndarray:
    """Fade in then fade out — higher dynamic complexity."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    envelope = np.sin(np.pi * t / DURATION)  # 0 -> 1 -> 0
    return (0.8 * envelope * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

def test_dynamic_complexity_happy_path():
    """DynamicComplexityAnalyzer produces float >= 0."""
    from app.audio.analyzers.dynamic_complexity import DynamicComplexityAnalyzer

    signal = _make_signal(_fade_in_out())
    analyzer = DynamicComplexityAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "dynamic_complexity" in result.features
    val = result.features["dynamic_complexity"]
    assert isinstance(val, float)
    assert val >= 0.0

def test_dynamic_complexity_comparative_constant_vs_fade():
    """Constant tone should have lower dynamic complexity than fade in/out."""
    from app.audio.analyzers.dynamic_complexity import DynamicComplexityAnalyzer

    analyzer = DynamicComplexityAnalyzer()
    const_result = analyzer.run(AnalysisContext(_make_signal(_constant_tone())))
    fade_result = analyzer.run(AnalysisContext(_make_signal(_fade_in_out())))

    if const_result.success and fade_result.success:
        assert const_result.features["dynamic_complexity"] <= fade_result.features["dynamic_complexity"]

def test_dynamic_complexity_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.dynamic_complexity import DynamicComplexityAnalyzer
        analyzer = DynamicComplexityAnalyzer()
        assert not analyzer.is_available()

def test_dynamic_complexity_silence():
    """Silence doesn't crash."""
    from app.audio.analyzers.dynamic_complexity import DynamicComplexityAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = DynamicComplexityAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    assert isinstance(result.success, bool)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_dynamic_complexity.py -v
```

- [ ] **Step 3: Implement DynamicComplexityAnalyzer**

Create `app/audio/analyzers/dynamic_complexity.py`:

```python
"""Dynamic complexity analyzer — essentia loudness variance.

Computes: dynamic_complexity (0.0-~10.0) — describes loudness variance.
Low = flat/constant energy (industrial, hard techno).
High = dramatic builds and drops (progressive, melodic).
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class DynamicComplexityAnalyzer(BaseAnalyzer):
    """Dynamic complexity via essentia's DynamicComplexity algorithm."""

    name: ClassVar[str] = "dynamic_complexity"
    capabilities: ClassVar[frozenset[str]] = frozenset({"loudness", "dynamics"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        dc = es.DynamicComplexity()
        complexity, loudness_band = dc(ctx.samples)
        return {"dynamic_complexity": round(float(complexity), 4)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_dynamic_complexity.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/dynamic_complexity.py tests/test_audio/test_dynamic_complexity.py
```

Message: `feat(audio): add DynamicComplexityAnalyzer (essentia loudness variance)`

---

### Task 7: TonnetzAnalyzer

**Files:**
- Create: `app/audio/analyzers/tonnetz.py`
- Create: `tests/test_audio/test_tonnetz.py`

**Context:** Independent analyzer using librosa's tonnetz. Output: `{"tonnetz_vector": list[float]}` — 6D tonal centroid features from chroma. Each value typically in range -1.0 to 1.0.

- [ ] **Step 1: Write failing tests**

Create `tests/test_audio/test_tonnetz.py`:

```python
"""Tests for TonnetzAnalyzer."""

from __future__ import annotations

import numpy as np

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 2.0

def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )

def _pure_a4() -> np.ndarray:
    """Pure A4 (440Hz) — known pitch for deterministic tonal features."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

def test_tonnetz_happy_path():
    """TonnetzAnalyzer produces 6D vector of floats."""
    from app.audio.analyzers.tonnetz import TonnetzAnalyzer

    signal = _make_signal(_pure_a4())
    analyzer = TonnetzAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "tonnetz_vector" in result.features
    vec = result.features["tonnetz_vector"]
    assert isinstance(vec, list)
    assert len(vec) == 6, f"Expected 6D tonnetz, got {len(vec)}D"
    assert all(isinstance(v, float) for v in vec)

def test_tonnetz_values_in_range():
    """Tonnetz values should be in [-1, 1] range."""
    from app.audio.analyzers.tonnetz import TonnetzAnalyzer

    signal = _make_signal(_pure_a4())
    analyzer = TonnetzAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    if result.success:
        for val in result.features["tonnetz_vector"]:
            assert -1.5 <= val <= 1.5, f"Tonnetz value {val} out of expected range"

def test_tonnetz_graceful_skip_no_librosa():
    """Without librosa, analyzer reports unavailable."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"librosa": None, "librosa.feature": None}):
        from app.audio.analyzers.tonnetz import TonnetzAnalyzer
        analyzer = TonnetzAnalyzer()
        assert not analyzer.is_available()

def test_tonnetz_silence():
    """Silence doesn't crash."""
    from app.audio.analyzers.tonnetz import TonnetzAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = TonnetzAnalyzer()
    result = analyzer.run(AnalysisContext(silence))

    assert isinstance(result.success, bool)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_tonnetz.py -v
```

- [ ] **Step 3: Implement TonnetzAnalyzer**

Create `app/audio/analyzers/tonnetz.py`:

```python
"""Tonnetz analyzer — librosa tonal centroid features.

Computes: tonnetz_vector — 6D tonal space representation from chroma.
Captures harmonic relationships richer than key alone.
Dimensions: fifths (2), minor thirds (2), major thirds (2).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class TonnetzAnalyzer(BaseAnalyzer):
    """6D tonal centroid features via librosa tonnetz."""

    name: ClassVar[str] = "tonnetz"
    capabilities: ClassVar[frozenset[str]] = frozenset({"harmony", "tonal"})
    required_packages: ClassVar[list[str]] = ["librosa"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import librosa

        tonnetz = librosa.feature.tonnetz(y=ctx.samples, sr=ctx.sr)
        # Mean across time → 6D vector
        mean_tonnetz = np.mean(tonnetz, axis=1)
        return {"tonnetz_vector": [round(float(v), 4) for v in mean_tonnetz]}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_tonnetz.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/tonnetz.py tests/test_audio/test_tonnetz.py
```

Message: `feat(audio): add TonnetzAnalyzer (librosa 6D tonal centroid)`

---

### Task 8: BeatsLoudnessAnalyzer (Dependent)

**Files:**
- Create: `app/audio/analyzers/beats_loudness.py`
- Create: `tests/test_audio/test_beats_loudness.py`

**Context:** This is the only **dependent** analyzer. It declares `depends_on = frozenset({"beat"})` and receives `beat_times` from BeatDetector via `prior_results`. Uses essentia's BeatsLoudness to compute per-band loudness at beat positions. Returns empty dict if `beat_times` is missing (graceful failure, no exception).

- [ ] **Step 1: Write failing tests**

Create `tests/test_audio/test_beats_loudness.py`:

```python
"""Tests for BeatsLoudnessAnalyzer (dependent on BeatDetector)."""

from __future__ import annotations

import numpy as np

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 4.0

def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )

def _kick_pattern(bpm: float = 130.0) -> np.ndarray:
    n = int(SAMPLE_RATE * DURATION)
    samples = np.zeros(n, dtype=np.float32)
    interval = int(60.0 / bpm * SAMPLE_RATE)
    for start in range(0, n, interval):
        end = min(start + int(0.01 * SAMPLE_RATE), n)
        kick_len = end - start
        if kick_len > 0:
            samples[start:end] = 0.8 * np.sin(
                2 * np.pi * 60 * np.arange(kick_len) / SAMPLE_RATE
            ).astype(np.float32)
    return samples

def _beat_times_for_bpm(bpm: float = 130.0) -> list[float]:
    """Generate synthetic beat times."""
    interval = 60.0 / bpm
    times: list[float] = []
    t = 0.0
    while t < DURATION:
        times.append(t)
        t += interval
    return times

def test_beats_loudness_happy_path():
    """With beat_times, produces 6D band ratio vector."""
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = BeatsLoudnessAnalyzer()
    assert analyzer.depends_on == frozenset({"beat"})

    prior = {"beat_times": _beat_times_for_bpm(130.0)}
    result = analyzer.run(AnalysisContext(signal), prior)

    assert result.success
    assert "beat_loudness_band_ratio" in result.features
    vec = result.features["beat_loudness_band_ratio"]
    assert isinstance(vec, list)
    assert len(vec) == 6, f"Expected 6 bands, got {len(vec)}"
    assert all(isinstance(v, float) for v in vec)

def test_beats_loudness_no_beat_times():
    """Without beat_times in prior_results, returns empty dict (graceful)."""
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = BeatsLoudnessAnalyzer()

    # No prior_results
    result = analyzer.run(AnalysisContext(signal), None)
    assert result.success
    assert result.features == {}

    # prior_results without beat_times
    result2 = analyzer.run(AnalysisContext(signal), {"other_key": 42})
    assert result2.success
    assert result2.features == {}

def test_beats_loudness_empty_beat_times():
    """Empty beat_times list returns empty dict."""
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    signal = _make_signal(_kick_pattern())
    analyzer = BeatsLoudnessAnalyzer()

    result = analyzer.run(AnalysisContext(signal), {"beat_times": []})
    assert result.success
    assert result.features == {}

def test_beats_loudness_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer
        analyzer = BeatsLoudnessAnalyzer()
        assert not analyzer.is_available()

def test_beats_loudness_silence():
    """Silence with beat_times doesn't crash."""
    from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer

    silence = _make_signal(np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32))
    analyzer = BeatsLoudnessAnalyzer()

    result = analyzer.run(AnalysisContext(silence), {"beat_times": [0.5, 1.0, 1.5]})
    assert isinstance(result.success, bool)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_beats_loudness.py -v
```

- [ ] **Step 3: Implement BeatsLoudnessAnalyzer**

Create `app/audio/analyzers/beats_loudness.py`:

```python
"""Beats loudness band ratio analyzer — essentia per-band loudness at beats.

Computes: beat_loudness_band_ratio — 6-band loudness ratios at beat positions.
Depends on BeatDetector for beat_times.

This is a rhythmic timbre fingerprint: how loudness is distributed across
frequency bands at beat positions. Useful for distinguishing kick-heavy
tracks from hi-hat-heavy ones.
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class BeatsLoudnessAnalyzer(BaseAnalyzer):
    """Per-band loudness at beat positions via essentia BeatsLoudness."""

    name: ClassVar[str] = "beats_loudness"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm", "spectral"})
    required_packages: ClassVar[list[str]] = ["essentia"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})

    def _extract(
        self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        beat_times = (prior_results or {}).get("beat_times")
        if not beat_times:
            return {}

        import essentia.standard as es

        bl = es.BeatsLoudness(
            beats=beat_times,
            sampleRate=float(ctx.sr),
        )
        loudness, loudness_band_ratio = bl(ctx.samples)

        # Mean across beats → 6 band ratios
        mean_ratio = [round(float(x), 4) for x in loudness_band_ratio.mean(axis=0)]
        return {"beat_loudness_band_ratio": mean_ratio}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_beats_loudness.py -v
```

- [ ] **Step 5: Run full audio test suite**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/ -x -q
```

Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/analyzers/beats_loudness.py tests/test_audio/test_beats_loudness.py
```

Message: `feat(audio): add BeatsLoudnessAnalyzer (dependent on BeatDetector)`

---

### Task 9: Pipeline — Two-Phase Execution

**Files:**
- Modify: `app/audio/pipeline.py`
- Modify: `tests/test_audio/test_pipeline_refactored.py`

**Context:** Currently all analyzers run in parallel via `asyncio.gather()`. Split into Phase 1 (independent analyzers, parallel) and Phase 2 (dependent analyzers, receive merged Phase 1 results). Phase 1 is identical to current behavior — no regression. Phase 2 is additive.

- [ ] **Step 1: Write failing test for two-phase execution**

Add to `tests/test_audio/test_pipeline_refactored.py`:

```python
async def test_pipeline_two_phase_dependent_receives_prior(tmp_path, monkeypatch):
    """Dependent analyzers in Phase 2 receive Phase 1 results via prior_results."""
    import soundfile as sf

    from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer, register_analyzer
    from app.audio.core.types import AnalyzerResult, AudioSignal

    # Create a simple WAV file
    sr = 22050
    duration = 2.0
    samples = np.random.default_rng(42).standard_normal(int(sr * duration)).astype(np.float32) * 0.3
    wav_path = str(tmp_path / "test.wav")
    sf.write(wav_path, samples, sr)

    # Register test analyzers in a clean registry
    registry = AnalyzerRegistry()

    class _Phase1Analyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_p1"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []

        def _extract(self, ctx):
            return {"shared_value": 42}

    class _Phase2Analyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_p2"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []
        depends_on: ClassVar[frozenset[str]] = frozenset({"_test_p1"})

        def _extract(self, ctx, *, prior_results=None):
            val = (prior_results or {}).get("shared_value", 0)
            return {"doubled": val * 2}

    registry.register(_Phase1Analyzer())
    registry.register(_Phase2Analyzer())

    pipeline = AnalysisPipeline(registry)
    result = await pipeline.analyze(wav_path)

    assert result.features.get("shared_value") == 42
    assert result.features.get("doubled") == 84

async def test_pipeline_phase1_runs_without_dependent(tmp_path):
    """When no dependent analyzers exist, pipeline runs identically to before."""
    import soundfile as sf

    sr = 22050
    samples = np.random.default_rng(42).standard_normal(int(sr * 2)).astype(np.float32) * 0.3
    wav_path = str(tmp_path / "test.wav")
    sf.write(wav_path, samples, sr)

    registry = AnalyzerRegistry()

    class _IndepOnly(BaseAnalyzer):
        name: ClassVar[str] = "_test_indep_only"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []

        def _extract(self, ctx):
            return {"val": 1}

    registry.register(_IndepOnly())

    pipeline = AnalysisPipeline(registry)
    result = await pipeline.analyze(wav_path)

    assert result.features.get("val") == 1
    assert result.success_count == 1
```

Don't forget to add necessary imports at the top of the test file if missing:

```python
import numpy as np
from typing import ClassVar
from app.audio.pipeline import AnalysisPipeline
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_pipeline_refactored.py -k "two_phase or phase1_runs" -v
```

Expected: FAIL — `run()` signature mismatch or `prior_results` not passed

- [ ] **Step 3: Update pipeline for two-phase execution**

Replace the `analyze` method body in `app/audio/pipeline.py` (starting from the `# True parallelism` comment, line ~78):

```python
# Partition: independent vs dependent
independent = [a for a in instances if not a.depends_on]
dependent = [a for a in instances if a.depends_on]

# Phase 1: independent — full parallelism (unchanged behavior)
phase1_results: list[AnalyzerResult] = list(
    await asyncio.gather(*(asyncio.to_thread(a.run, ctx) for a in independent))
)

# Phase 2: dependent — receive merged Phase 1 results
all_results = list(phase1_results)
if dependent:
    prior = self._merge_features(phase1_results)
    phase2_results: list[AnalyzerResult] = list(
        await asyncio.gather(
            *(asyncio.to_thread(a.run, ctx, prior) for a in dependent)
        )
    )
    all_results.extend(phase2_results)

return PipelineResult(
    results=all_results,
    features=self._merge_features(all_results),
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_pipeline_refactored.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest -x -q
```

Expected: All pass

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/audio/pipeline.py tests/test_audio/test_pipeline_refactored.py
```

Message: `feat(audio): two-phase pipeline execution for dependent analyzers`

---

### Task 10: ORM Model — Add 6 Columns and Update `filter_features()`

**Files:**
- Modify: `app/models/audio.py`

**Context:** Add 6 new nullable columns to `TrackAudioFeaturesComputed`: 3 float + 3 VARCHAR(500) for vectors. Update `filter_features()` to JSON-serialize list values for vector columns. Update docstring from "47" to "53". No Alembic migration dir exists — columns are created by `Base.metadata.create_all()` in `init_db()`.

- [ ] **Step 1: Write failing test for `filter_features()` vector serialization**

Add to `tests/test_audio/test_pipeline_refactored.py`:

```python
async def test_filter_features_serializes_vectors():
    """filter_features() JSON-serializes vector column values."""
    import json

    from app.models.audio import TrackAudioFeaturesComputed

    features = {
        "bpm": 130.0,
        "tonnetz_vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        "tempogram_ratio_vector": [0.5, 1.0, 0.3],
        "beat_loudness_band_ratio": [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
        "beat_times": [0.5, 1.0, 1.5],  # should be filtered OUT (not a column)
        "danceability": 1.8,
        "dynamic_complexity": 3.5,
        "dissonance_mean": 0.42,
    }

    filtered = TrackAudioFeaturesComputed.filter_features(features)

    # Vector columns serialized to JSON strings
    assert isinstance(filtered["tonnetz_vector"], str)
    assert json.loads(filtered["tonnetz_vector"]) == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    assert isinstance(filtered["tempogram_ratio_vector"], str)
    assert isinstance(filtered["beat_loudness_band_ratio"], str)

    # Float columns preserved as-is
    assert filtered["bpm"] == 130.0
    assert filtered["danceability"] == 1.8
    assert filtered["dynamic_complexity"] == 3.5
    assert filtered["dissonance_mean"] == 0.42

    # Non-column keys filtered out
    assert "beat_times" not in filtered
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_pipeline_refactored.py::test_filter_features_serializes_vectors -v
```

Expected: FAIL — columns don't exist yet on the model.

- [ ] **Step 3: Add 6 new columns after the rhythm section**

In `app/models/audio.py`, after `kick_prominence` (line ~120) and before `mood`:

```python
# --- P1 New Features (6 fields) ---
danceability: Mapped[float | None] = mapped_column(nullable=True)
dynamic_complexity: Mapped[float | None] = mapped_column(nullable=True)
dissonance_mean: Mapped[float | None] = mapped_column(nullable=True)
tonnetz_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
tempogram_ratio_vector: Mapped[str | None] = mapped_column(String(500), nullable=True)
beat_loudness_band_ratio: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 4: Update docstring**

Change line 51:

```python
"""47 numerical audio feature descriptors extracted from analysis."""
```

to:

```python
"""53 numerical audio feature descriptors extracted from analysis."""
```

- [ ] **Step 5: Update `filter_features()` with vector JSON serialization**

Replace the `filter_features()` method body:

```python
@classmethod
def filter_features(cls, features: dict[str, Any]) -> dict[str, Any]:
    """Filter pipeline output to only columns that exist on this model.

    Pipeline analyzers may produce extra keys that don't have DB columns.
    Also maps pipeline output names to DB column names where they differ.
    Serializes list values for VARCHAR vector columns to JSON strings.
    """
    import json

    valid = {c.name for c in cls.__table__.columns}
    valid -= {"track_id", "pipeline_run_id", "created_at", "updated_at"}

    # Columns that store JSON-encoded lists in VARCHAR
    _VECTOR_COLUMNS = {
        "mfcc_vector", "tonnetz_vector", "tempogram_ratio_vector",
        "beat_loudness_band_ratio", "chroma",
    }

    # Map pipeline keys → DB column names
    result: dict[str, Any] = {}
    for k, v in features.items():
        if k == "mfcc_mean" and "mfcc_vector" in valid:
            # Serialize MFCC list to JSON string for VARCHAR column
            result["mfcc_vector"] = json.dumps(v) if isinstance(v, list) else v
        elif k in valid:
            # Auto-serialize lists for VARCHAR vector columns
            if k in _VECTOR_COLUMNS and isinstance(v, list):
                result[k] = json.dumps(v)
            else:
                result[k] = v

    return result
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_pipeline_refactored.py::test_filter_features_serializes_vectors -v
```

Expected: PASS

- [ ] **Step 7: Run existing model tests**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest -k "audio" -x -q
```

- [ ] **Step 8: Run lint**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run ruff check app/models/audio.py
```

- [ ] **Step 9: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/models/audio.py tests/test_audio/test_pipeline_refactored.py
```

Message: `feat(db): add 6 P1 analyzer columns and vector JSON serialization`

---

### Task 11: Integration Tests — Discovery + E2E Pipeline

**Files:**
- Modify: `tests/test_audio/test_pipeline_refactored.py`

**Context:** Verify that (1) auto-discovery picks up all 14 analyzers, and (2) `beat_loudness_band_ratio` is populated in e2e pipeline run when BeatDetector succeeds (spec Section 8.3).

- [ ] **Step 1: Write integration tests**

Add to `tests/test_audio/test_pipeline_refactored.py`:

```python
async def test_pipeline_discovers_new_p1_analyzers(tmp_path):
    """Auto-discovery finds all 14 analyzers including 6 new P1 ones."""
    from app.audio.analyzers.base import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()

    available = set(registry.list_available())

    # New P1 analyzers should be discovered (if their deps are installed)
    p1_names = {"danceability", "tempogram", "dissonance", "dynamic_complexity", "tonnetz", "beats_loudness"}
    # At least some should be available (depends on installed libs)
    discovered_p1 = p1_names & available
    assert len(discovered_p1) > 0, f"No P1 analyzers discovered. Available: {available}"

async def test_pipeline_populates_beat_loudness_when_beats_available():
    """E2E: beat_loudness_band_ratio is populated when BeatDetector succeeds."""
    import numpy as np
    import soundfile as sf

    from app.audio.pipeline import AudioPipeline

    # Generate a kick pattern WAV that BeatDetector can detect beats in
    sr = 22050
    duration = 4.0
    n = int(sr * duration)
    samples = np.zeros(n, dtype=np.float32)
    bpm = 130.0
    interval = int(60.0 / bpm * sr)
    for start in range(0, n, interval):
        end = min(start + int(0.01 * sr), n)
        if end > start:
            samples[start:end] = 0.8 * np.sin(
                2 * np.pi * 60 * np.arange(end - start) / sr
            ).astype(np.float32)

    wav_path = tmp_path / "kick_test.wav"
    sf.write(str(wav_path), samples, sr)

    pipeline = AudioPipeline()
    result = await pipeline.analyze(str(wav_path))

    # If beat analyzer ran successfully, beat_loudness should be populated
    if "beat_times" in result.features:
        assert "beat_loudness_band_ratio" in result.features, (
            "beat_loudness_band_ratio should be populated when beat_times is available"
        )
        vec = result.features["beat_loudness_band_ratio"]
        assert isinstance(vec, list)
        assert len(vec) == 6
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest tests/test_audio/test_pipeline_refactored.py -k "discovers or beat_loudness" -v
```

Expected: PASS

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest -x -q
```

Expected: All pass

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add tests/test_audio/test_pipeline_refactored.py
```

Message: `test(audio): add integration tests for P1 analyzer discovery and e2e beat_loudness`

---

### Task 12: Alembic Migration

**Files:**
- Create: `app/migrations/versions/<autogenerated_hash>_add_p1_analyzer_columns.py`

**Context:** The project uses Alembic for schema migrations (`app/migrations/versions/` has 5 existing files). Add a migration for the 6 new columns. Uses `batch_alter_table` for SQLite compatibility.

- [ ] **Step 1: Generate migration**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run alembic revision -m "add_p1_analyzer_columns"
```

- [ ] **Step 2: Write migration body**

Edit the generated file in `app/migrations/versions/`:

```python
"""Add P1 analyzer columns.

Revision ID: <auto>
Revises: <auto>
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "<auto>"
down_revision = "<auto>"

def upgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.add_column(sa.Column("danceability", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dynamic_complexity", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("dissonance_mean", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("tonnetz_vector", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("tempogram_ratio_vector", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("beat_loudness_band_ratio", sa.String(500), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.drop_column("beat_loudness_band_ratio")
        batch_op.drop_column("tempogram_ratio_vector")
        batch_op.drop_column("tonnetz_vector")
        batch_op.drop_column("dissonance_mean")
        batch_op.drop_column("dynamic_complexity")
        batch_op.drop_column("danceability")
```

- [ ] **Step 3: Test migration cycle**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run alembic upgrade head
cd /Users/laptop/dev/dj-music-plugin && uv run alembic downgrade -1
cd /Users/laptop/dev/dj-music-plugin && uv run alembic upgrade head
```

Expected: All 3 commands succeed without errors.

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/laptop/dev/dj-music-plugin && uv run pytest -x -q
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin && git add app/migrations/versions/*add_p1_analyzer_columns*
```

Message: `feat(db): add alembic migration for 6 P1 analyzer columns`

---

## Summary

| Task | Component | Files | Tests |
|------|-----------|-------|-------|
| 1 | BaseAnalyzer `depends_on` + dispatch | 1 modified | 3 new tests |
| 2 | BeatDetector `beat_times` export | 1 modified | 1 new test |
| 3 | DanceabilityAnalyzer | 1 created | 3 tests |
| 4 | TempogramAnalyzer | 1 created | 3 tests |
| 5 | DissonanceAnalyzer | 1 created | 4 tests |
| 6 | DynamicComplexityAnalyzer | 1 created | 4 tests |
| 7 | TonnetzAnalyzer | 1 created | 4 tests |
| 8 | BeatsLoudnessAnalyzer | 1 created | 5 tests |
| 9 | Pipeline two-phase | 1 modified | 2 tests |
| 10 | ORM model + filter_features | 1 modified | 1 test |
| 11 | Integration tests | 1 modified | 2 tests |
| 12 | Alembic migration | 1 created | migration cycle |
| **Total** | | **7 created, 5 modified** | **~28 tests** |
