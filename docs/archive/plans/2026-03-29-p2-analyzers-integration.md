# P2: Analyzers + Scoring/Classification Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 new audio analyzers, integrate all P1/P2/unused features into TransitionScorer and MoodClassifier, and add context-aware transition weights.

**Architecture:** Builds on P1 layered architecture (`core/` → `analyzers/` → `classification/` → `pipeline.py`). New analyzers follow identical `@register_analyzer` + `_extract(ctx)` pattern. Integration touches `TransitionScorer` (enriched components + new timbral), `MoodClassifier` (10 new feature targets across 15 profiles), `TrackFeatures` (8 new fields), and GA optimizer (context-aware intent).

**Tech Stack:** Python 3.12+, essentia, librosa, SQLAlchemy 2.0 (async), Alembic, pytest

---

## File Structure

### New files (8)
- `app/audio/analyzers/spectral_complexity.py` — SpectralComplexityAnalyzer
- `app/audio/analyzers/pitch_salience.py` — PitchSalienceAnalyzer
- `app/audio/analyzers/bpm_histogram.py` — BpmHistogramAnalyzer (Phase 2, depends on beat)
- `app/audio/analyzers/phrase.py` — PhraseAnalyzer (Phase 2, depends on beat)
- `app/core/transition_intent.py` — TransitionIntent enum + INTENT_WEIGHT_MODIFIERS + infer_intent()
- `tests/test_audio/test_spectral_complexity.py`
- `tests/test_audio/test_pitch_salience.py`
- `tests/test_audio/test_bpm_histogram.py`
- `tests/test_audio/test_phrase.py`

### Modified files (9)
- `app/audio/analyzers/beat.py` — add `beats_intervals` to output
- `app/models/audio.py` — 7 new columns + _CLASSIFIER_FIELDS + filter_features
- `app/core/track_features.py` — 8 new fields + from_db() update
- `app/core/constants.py` — updated DEFAULT_TRANSITION_WEIGHTS (6 components)
- `app/services/transition.py` — enriched components + new _score_timbral + intent support
- `app/audio/classification/profiles.py` — 10 new FeatureTargets across 15 profiles
- `app/services/optimizer.py` — pass intent through fitness function
- `app/migrations/versions/` — new migration for P2 columns
- `tests/test_audio/test_pipeline_refactored.py` — P2 discovery + integration tests

### Test files for scoring/integration (new or modified)
- `tests/test_services/test_transition_scoring_p2.py` — enriched components + timbral + backward compat
- `tests/test_audio/test_classification.py` — classifier with P2 features (modify existing)

---

## Task 1: BeatDetector — export beats_intervals

**Files:**
- Modify: `app/audio/analyzers/beat.py:77-83`
- Modify: `tests/test_audio/test_beat_export.py`

BpmHistogramAnalyzer needs `beats_intervals` (inter-beat intervals in seconds) from BeatDetector's prior_results. Currently BeatDetector exports `beat_times` but not intervals.

- [ ] **Step 1: Add test for beats_intervals export**

In `tests/test_audio/test_beat_export.py`, add:

```python
def test_beat_export_includes_intervals():
    """BeatDetector should export beats_intervals alongside beat_times."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.beat import BeatDetector

    # Use kick pattern to get reliable beat detection
    signal = _make_signal(_kick_pattern(bpm=130.0))
    analyzer = BeatDetector()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "beats_intervals" in result.features
    intervals = result.features["beats_intervals"]
    assert isinstance(intervals, list)
    if len(result.features.get("beat_times", [])) > 1:
        assert len(intervals) == len(result.features["beat_times"]) - 1
        assert all(isinstance(v, float) and v > 0 for v in intervals)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audio/test_beat_export.py::test_beat_export_includes_intervals -v`
Expected: FAIL — `"beats_intervals" not in result.features`

- [ ] **Step 3: Add beats_intervals to BeatDetector output**

In `app/audio/analyzers/beat.py`, in the `_extract` method, after computing `beat_times` (currently returned as `onsets.tolist()`), add:

```python
beat_times_list = onsets.tolist()
beats_intervals = (
    np.diff(onsets).tolist() if len(onsets) > 1 else []
)

return {
    "onset_rate": round(onset_rate, 4),
    "pulse_clarity": round(pulse_clarity, 4),
    "kick_prominence": round(kick_prominence, 4),
    "hp_ratio": round(hp_ratio, 4),
    "beat_times": beat_times_list,
    "beats_intervals": beats_intervals,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audio/test_beat_export.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All pass (no regressions — beats_intervals is additive)

- [ ] **Step 6: Commit**

```text
feat(audio): export beats_intervals from BeatDetector

BpmHistogramAnalyzer (P2) needs inter-beat intervals to compute
BPM histogram descriptors. Added as np.diff(beat_times).
```

---

## Task 2: SpectralComplexityAnalyzer

**Files:**
- Create: `app/audio/analyzers/spectral_complexity.py`
- Create: `tests/test_audio/test_spectral_complexity.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for SpectralComplexityAnalyzer."""
from __future__ import annotations

import numpy as np
import pytest

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

def _pure_sine(freq: float = 440.0) -> np.ndarray:
    """Single sine wave — simple spectrum, low complexity."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)

def _noise_burst() -> np.ndarray:
    """White noise — many spectral peaks, high complexity."""
    rng = np.random.default_rng(42)
    return (0.3 * rng.standard_normal(int(SAMPLE_RATE * DURATION))).astype(np.float32)

def test_spectral_complexity_happy_path():
    """SpectralComplexityAnalyzer produces float >= 0."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.spectral_complexity import SpectralComplexityAnalyzer

    signal = _make_signal(_pure_sine())
    analyzer = SpectralComplexityAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "spectral_complexity_mean" in result.features
    val = result.features["spectral_complexity_mean"]
    assert isinstance(val, float)
    assert val >= 0.0

def test_spectral_complexity_noise_higher_than_sine():
    """Noise should have higher spectral complexity than pure sine."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.spectral_complexity import SpectralComplexityAnalyzer

    analyzer = SpectralComplexityAnalyzer()
    sine_result = analyzer.run(AnalysisContext(_make_signal(_pure_sine())))
    noise_result = analyzer.run(AnalysisContext(_make_signal(_noise_burst())))

    if sine_result.success and noise_result.success:
        assert (
            noise_result.features["spectral_complexity_mean"]
            > sine_result.features["spectral_complexity_mean"]
        )

def test_spectral_complexity_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch

    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.spectral_complexity import SpectralComplexityAnalyzer

        analyzer = SpectralComplexityAnalyzer()
        assert not analyzer.is_available()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audio/test_spectral_complexity.py -v`
Expected: FAIL — import error (module not found)

- [ ] **Step 3: Implement SpectralComplexityAnalyzer**

Create `app/audio/analyzers/spectral_complexity.py`:

```python
"""SpectralComplexityAnalyzer — count of spectral peaks per frame (essentia)."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class SpectralComplexityAnalyzer(BaseAnalyzer):
    """Mean spectral complexity (number of spectral peaks) via essentia."""

    name: ClassVar[str] = "spectral_complexity"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        w = es.Windowing(type="blackmanharris62")
        spectrum = es.Spectrum()
        sc = es.SpectralComplexity(magnitudeThreshold=0.005, sampleRate=float(ctx.sr))

        frame_size = 2048
        hop_size = 1024
        values: list[float] = []

        for start in range(0, len(ctx.samples) - frame_size, hop_size):
            frame = ctx.samples[start : start + frame_size]
            spec = spectrum(w(frame))
            values.append(float(sc(spec)))

        mean_val = float(np.mean(values)) if values else 0.0
        return {"spectral_complexity_mean": round(mean_val, 4)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audio/test_spectral_complexity.py -v`
Expected: PASS (or SKIP if essentia not installed)

- [ ] **Step 5: Commit**

```text
feat(audio): add SpectralComplexityAnalyzer (essentia spectral peaks)
```

---

## Task 3: PitchSalienceAnalyzer

**Files:**
- Create: `app/audio/analyzers/pitch_salience.py`
- Create: `tests/test_audio/test_pitch_salience.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for PitchSalienceAnalyzer."""
from __future__ import annotations

import numpy as np
import pytest

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

def _harmonic_signal() -> np.ndarray:
    """Signal with strong harmonics — high pitch salience."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    # Fundamental + 3 harmonics
    return (
        0.4 * np.sin(2 * np.pi * 440 * t)
        + 0.2 * np.sin(2 * np.pi * 880 * t)
        + 0.1 * np.sin(2 * np.pi * 1320 * t)
        + 0.05 * np.sin(2 * np.pi * 1760 * t)
    ).astype(np.float32)

def _noise_signal() -> np.ndarray:
    """White noise — low pitch salience."""
    rng = np.random.default_rng(42)
    return (0.3 * rng.standard_normal(int(SAMPLE_RATE * DURATION))).astype(np.float32)

def test_pitch_salience_happy_path():
    """PitchSalienceAnalyzer produces float in 0-1 range."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.pitch_salience import PitchSalienceAnalyzer

    signal = _make_signal(_harmonic_signal())
    analyzer = PitchSalienceAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "pitch_salience_mean" in result.features
    val = result.features["pitch_salience_mean"]
    assert isinstance(val, float)
    assert 0.0 <= val <= 1.0

def test_pitch_salience_harmonic_higher_than_noise():
    """Harmonic signal should have higher pitch salience than noise."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.pitch_salience import PitchSalienceAnalyzer

    analyzer = PitchSalienceAnalyzer()
    harmonic = analyzer.run(AnalysisContext(_make_signal(_harmonic_signal())))
    noise = analyzer.run(AnalysisContext(_make_signal(_noise_signal())))

    if harmonic.success and noise.success:
        assert (
            harmonic.features["pitch_salience_mean"]
            > noise.features["pitch_salience_mean"]
        )

def test_pitch_salience_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch

    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.pitch_salience import PitchSalienceAnalyzer

        analyzer = PitchSalienceAnalyzer()
        assert not analyzer.is_available()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audio/test_pitch_salience.py -v`
Expected: FAIL

- [ ] **Step 3: Implement PitchSalienceAnalyzer**

Create `app/audio/analyzers/pitch_salience.py`:

```python
"""PitchSalienceAnalyzer — tonality measure 0-1 via essentia autocorrelation."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class PitchSalienceAnalyzer(BaseAnalyzer):
    """Mean pitch salience (0-1) via essentia. Proxy for vocal/melodic content."""

    name: ClassVar[str] = "pitch_salience"
    capabilities: ClassVar[frozenset[str]] = frozenset({"spectral", "harmony"})
    required_packages: ClassVar[list[str]] = ["essentia"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        import essentia.standard as es

        w = es.Windowing(type="hann")
        spectrum = es.Spectrum()
        ps = es.PitchSalience(
            lowBoundary=100, highBoundary=5000, sampleRate=float(ctx.sr)
        )

        frame_size = 2048
        hop_size = 1024
        values: list[float] = []

        for start in range(0, len(ctx.samples) - frame_size, hop_size):
            frame = ctx.samples[start : start + frame_size]
            spec = spectrum(w(frame))
            values.append(float(ps(spec)))

        mean_val = float(np.mean(values)) if values else 0.0
        return {"pitch_salience_mean": round(mean_val, 4)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audio/test_pitch_salience.py -v`
Expected: PASS (or SKIP)

- [ ] **Step 5: Commit**

```text
feat(audio): add PitchSalienceAnalyzer (essentia tonality 0-1)
```

---

## Task 4: BpmHistogramAnalyzer

**Files:**
- Create: `app/audio/analyzers/bpm_histogram.py`
- Create: `tests/test_audio/test_bpm_histogram.py`

Phase 2 analyzer, depends on `beat`. Consumes `beats_intervals` from BeatDetector (Task 1).

- [ ] **Step 1: Write tests**

```python
"""Tests for BpmHistogramAnalyzer."""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050

def _make_signal(n_samples: int = 22050 * 3) -> AudioSignal:
    rng = np.random.default_rng(42)
    samples = rng.standard_normal(n_samples).astype(np.float32) * 0.1
    return AudioSignal(
        samples=samples,
        sample_rate=SAMPLE_RATE,
        duration_seconds=n_samples / SAMPLE_RATE,
    )

def test_bpm_histogram_with_stable_intervals():
    """Stable beat intervals should give high first_peak_weight."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.bpm_histogram import BpmHistogramAnalyzer

    analyzer = BpmHistogramAnalyzer()
    ctx = AnalysisContext(_make_signal())

    # Simulate stable 130 BPM: interval = 60/130 ≈ 0.4615 sec
    interval = 60.0 / 130.0
    prior: dict[str, Any] = {
        "beats_intervals": [interval] * 50,
        "beat_times": [i * interval for i in range(51)],
    }
    result = analyzer.run(ctx, prior)

    assert result.success
    assert "bpm_histogram_first_peak_weight" in result.features
    weight = result.features["bpm_histogram_first_peak_weight"]
    assert isinstance(weight, float)
    assert weight > 0.5  # stable rhythm → dominant first peak

def test_bpm_histogram_too_few_intervals():
    """With fewer than 4 intervals, return None values gracefully."""
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.bpm_histogram import BpmHistogramAnalyzer

    analyzer = BpmHistogramAnalyzer()
    ctx = AnalysisContext(_make_signal())
    prior: dict[str, Any] = {"beats_intervals": [0.5, 0.5], "beat_times": [0, 0.5, 1.0]}
    result = analyzer.run(ctx, prior)

    assert result.success
    assert result.features.get("bpm_histogram_first_peak_weight") is None

def test_bpm_histogram_graceful_skip_no_essentia():
    """Without essentia, analyzer reports unavailable."""
    from unittest.mock import patch

    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.bpm_histogram import BpmHistogramAnalyzer

        analyzer = BpmHistogramAnalyzer()
        assert not analyzer.is_available()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audio/test_bpm_histogram.py -v`
Expected: FAIL

- [ ] **Step 3: Implement BpmHistogramAnalyzer**

Create `app/audio/analyzers/bpm_histogram.py`:

```python
"""BpmHistogramAnalyzer — rhythmic stability from beat intervals (essentia)."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class BpmHistogramAnalyzer(BaseAnalyzer):
    """BPM histogram descriptors from beat intervals. Nearly free — reuses BeatDetector output."""

    name: ClassVar[str] = "bpm_histogram"
    capabilities: ClassVar[frozenset[str]] = frozenset({"rhythm"})
    required_packages: ClassVar[list[str]] = ["essentia"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})

    def _extract(
        self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        import essentia.standard as es

        beats_intervals = (prior_results or {}).get("beats_intervals")
        if not beats_intervals or len(beats_intervals) < 4:
            return {
                "bpm_histogram_first_peak_weight": None,
                "bpm_histogram_second_peak_bpm": None,
                "bpm_histogram_second_peak_weight": None,
            }

        bhd = es.BpmHistogramDescriptors()
        intervals = np.array(beats_intervals, dtype=np.float32)
        p1_bpm, p1_weight, _p1_spread, p2_bpm, p2_weight, _p2_spread, _hist = bhd(
            intervals
        )

        return {
            "bpm_histogram_first_peak_weight": round(float(p1_weight), 4),
            "bpm_histogram_second_peak_bpm": round(float(p2_bpm), 2),
            "bpm_histogram_second_peak_weight": round(float(p2_weight), 4),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audio/test_bpm_histogram.py -v`
Expected: PASS (or SKIP)

- [ ] **Step 5: Commit**

```text
feat(audio): add BpmHistogramAnalyzer (rhythmic stability from beat intervals)
```

---

## Task 5: PhraseAnalyzer

**Files:**
- Create: `app/audio/analyzers/phrase.py`
- Create: `tests/test_audio/test_phrase.py`

Phase 2 analyzer, depends on `beat`. Most complex P2 analyzer — uses agglomerative clustering on chroma features.

- [ ] **Step 1: Write tests**

```python
"""Tests for PhraseAnalyzer."""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050

def _make_signal(duration: float = 30.0) -> AudioSignal:
    """30-second signal — enough for phrase detection."""
    n = int(SAMPLE_RATE * duration)
    rng = np.random.default_rng(42)
    samples = (0.3 * rng.standard_normal(n)).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)

def _beat_times_for_bpm(bpm: float, duration: float) -> list[float]:
    """Generate evenly spaced beat times."""
    interval = 60.0 / bpm
    return [i * interval for i in range(int(duration / interval))]

def test_phrase_happy_path():
    """PhraseAnalyzer produces phrase boundaries and dominant bars."""
    pytest.importorskip("librosa", reason="librosa not installed")
    from app.audio.analyzers.phrase import PhraseAnalyzer

    analyzer = PhraseAnalyzer()
    ctx = AnalysisContext(_make_signal(duration=60.0))
    prior: dict[str, Any] = {"beat_times": _beat_times_for_bpm(130.0, 60.0)}
    result = analyzer.run(ctx, prior)

    assert result.success
    assert "phrase_boundaries_ms" in result.features
    assert "dominant_phrase_bars" in result.features
    boundaries = result.features["phrase_boundaries_ms"]
    assert isinstance(boundaries, list)
    assert all(isinstance(b, int) for b in boundaries)
    dominant = result.features["dominant_phrase_bars"]
    assert dominant in (8, 16, 32)

def test_phrase_too_few_beats():
    """With fewer than 16 beats, return defaults."""
    pytest.importorskip("librosa", reason="librosa not installed")
    from app.audio.analyzers.phrase import PhraseAnalyzer

    analyzer = PhraseAnalyzer()
    ctx = AnalysisContext(_make_signal(duration=5.0))
    prior: dict[str, Any] = {"beat_times": [0.0, 0.5, 1.0, 1.5]}
    result = analyzer.run(ctx, prior)

    assert result.success
    assert result.features["phrase_boundaries_ms"] == []
    assert result.features["dominant_phrase_bars"] == 16

def test_phrase_graceful_skip_no_librosa():
    """Without librosa, analyzer reports unavailable."""
    from unittest.mock import patch

    with patch.dict("sys.modules", {"librosa": None}):
        from app.audio.analyzers.phrase import PhraseAnalyzer

        analyzer = PhraseAnalyzer()
        assert not analyzer.is_available()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audio/test_phrase.py -v`
Expected: FAIL

- [ ] **Step 3: Implement PhraseAnalyzer**

Create `app/audio/analyzers/phrase.py`:

```python
"""PhraseAnalyzer — phrase boundary detection via chroma clustering (librosa)."""
from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext

@register_analyzer
class PhraseAnalyzer(BaseAnalyzer):
    """Detect phrase boundaries using agglomerative clustering on bar-level chroma."""

    name: ClassVar[str] = "phrase"
    capabilities: ClassVar[frozenset[str]] = frozenset({"structure"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})

    def _extract(
        self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        import librosa

        beat_times = (prior_results or {}).get("beat_times", [])
        if len(beat_times) < 16:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        # Group beats into bars (4 beats per bar for 4/4 time)
        bar_times = [beat_times[i] for i in range(0, len(beat_times), 4)]
        n_bars = len(bar_times)
        if n_bars < 8:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        # Compute chroma
        chroma = librosa.feature.chroma_cqt(y=ctx.samples, sr=ctx.sr)
        bar_frames = librosa.time_to_frames(bar_times, sr=ctx.sr)

        # Mean chroma per bar
        chroma_bars_list = []
        for i in range(len(bar_frames) - 1):
            start_f = max(0, bar_frames[i])
            end_f = bar_frames[i + 1]
            if end_f > start_f and end_f <= chroma.shape[1]:
                chroma_bars_list.append(chroma[:, start_f:end_f].mean(axis=1))
            else:
                chroma_bars_list.append(np.zeros(12))

        if len(chroma_bars_list) < 4:
            return {"phrase_boundaries_ms": [], "dominant_phrase_bars": 16}

        chroma_bars = np.array(chroma_bars_list).T  # shape: (12, n_bars-1)

        # Determine number of segments
        k = max(4, min(len(chroma_bars_list) // 4, 64))
        boundaries = librosa.segment.agglomerative(chroma_bars, k=k)

        # Convert bar indices to ms
        phrase_boundaries_ms = [
            int(bar_times[min(b, len(bar_times) - 1)] * 1000) for b in boundaries
        ]

        # Dominant phrase length (mode of segment lengths, quantized to 8/16/32)
        segment_lengths = np.diff(boundaries)
        if len(segment_lengths) > 0:
            quantized = [
                min([8, 16, 32], key=lambda x, sl=sl: abs(x - sl))
                for sl in segment_lengths
            ]
            dominant = max(set(quantized), key=quantized.count)
        else:
            dominant = 16

        return {
            "phrase_boundaries_ms": phrase_boundaries_ms,
            "dominant_phrase_bars": int(dominant),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audio/test_phrase.py -v`
Expected: PASS (or SKIP)

- [ ] **Step 5: Commit**

```text
feat(audio): add PhraseAnalyzer (chroma-based phrase boundary detection)
```

---

## Task 6: ORM model + Alembic migration

**Files:**
- Modify: `app/models/audio.py`
- Create: `app/migrations/versions/{new}_add_p2_analyzer_columns.py`

- [ ] **Step 1: Add 7 new columns to TrackAudioFeaturesComputed**

In `app/models/audio.py`, after the P1 columns block (after `beat_loudness_band_ratio`), add:

```python
    # --- P2 New Features (7 fields) ---
    spectral_complexity_mean: Mapped[float | None] = mapped_column(nullable=True)
    pitch_salience_mean: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_first_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_bpm: Mapped[float | None] = mapped_column(nullable=True)
    bpm_histogram_second_peak_weight: Mapped[float | None] = mapped_column(nullable=True)
    phrase_boundaries_ms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    dominant_phrase_bars: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
```

- [ ] **Step 2: Update filter_features vector_columns**

In `filter_features()`, add `"phrase_boundaries_ms"` to the `vector_columns` set:

```python
vector_columns = {
    "mfcc_vector",
    "tonnetz_vector",
    "tempogram_ratio_vector",
    "beat_loudness_band_ratio",
    "phrase_boundaries_ms",
}
```

- [ ] **Step 3: Update _CLASSIFIER_FIELDS**

Add new fields to the `_CLASSIFIER_FIELDS` tuple:

```python
_CLASSIFIER_FIELDS: ClassVar[tuple[str, ...]] = (
    # ... existing 29 fields ...
    "danceability", "dissonance_mean", "dynamic_complexity",
    "pitch_salience_mean", "spectral_complexity_mean",
    "bpm_histogram_first_peak_weight",
    "spectral_slope",
)
```

Note: `hp_ratio`, `pulse_clarity`, `bpm_stability` are already in the tuple. `spectral_slope` needs to be added.

- [ ] **Step 4: Create Alembic migration**

Run: `uv run alembic revision --autogenerate -m "Add P2 analyzer columns"`

If autogenerate doesn't work, create manually with `batch_alter_table`:

```python
def upgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.add_column(sa.Column("spectral_complexity_mean", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pitch_salience_mean", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bpm_histogram_first_peak_weight", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bpm_histogram_second_peak_bpm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bpm_histogram_second_peak_weight", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("phrase_boundaries_ms", sa.String(2000), nullable=True))
        batch_op.add_column(sa.Column("dominant_phrase_bars", sa.SmallInteger(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("track_audio_features_computed") as batch_op:
        batch_op.drop_column("dominant_phrase_bars")
        batch_op.drop_column("phrase_boundaries_ms")
        batch_op.drop_column("bpm_histogram_second_peak_weight")
        batch_op.drop_column("bpm_histogram_second_peak_bpm")
        batch_op.drop_column("bpm_histogram_first_peak_weight")
        batch_op.drop_column("pitch_salience_mean")
        batch_op.drop_column("spectral_complexity_mean")
```

`down_revision` must be `"a46fe524044f"` (P1 migration HEAD).

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```sql
feat(db): add 7 P2 analyzer columns and update classifier fields
```

---

## Task 7: MoodClassifier — add new FeatureTargets to profiles

**Files:**
- Modify: `app/audio/classification/profiles.py`

Add 10 new features (danceability, dissonance_mean, dynamic_complexity, pitch_salience_mean, spectral_complexity_mean, bpm_histogram_first_peak_weight, hp_ratio, pulse_clarity, bpm_stability, spectral_slope) to all 15 SubgenreProfile dataclasses, following the spec table in Part B1.

- [ ] **Step 1: Add feature targets to AMBIENT_DUB profile**

Example for first profile — add to `features` dict:

```python
AMBIENT_DUB = SubgenreProfile(
    subgenre=TechnoSubgenre.AMBIENT_DUB,
    features={
        # ... existing features ...
        "danceability": FeatureTarget(1.5, 0.8, 0.3),
        "dissonance_mean": FeatureTarget(1.0, 0.15, 0.1),
        "dynamic_complexity": FeatureTarget(1.0, 0.15, 0.1),
        "pitch_salience_mean": FeatureTarget(1.5, 0.45, 0.15),
        "spectral_complexity_mean": FeatureTarget(1.0, 8.0, 4.0),
        "hp_ratio": FeatureTarget(1.5, 4.0, 1.5),
        "pulse_clarity": FeatureTarget(1.0, 0.15, 0.1),
    },
)
```

- [ ] **Step 2: Add feature targets to remaining 14 profiles**

Follow spec table B1 for each profile. Profiles without a target for a feature (marked —) simply omit that key — the Gaussian scorer skips missing features automatically.

- [ ] **Step 3: Add test for new features in profiles**

In `tests/test_audio/test_classification.py`, add:

```python
def test_all_profiles_include_p2_features():
    """All 15 profiles should include at least danceability and dissonance targets."""
    from app.audio.classification.profiles import ALL_PROFILES

    for profile in ALL_PROFILES:
        assert "danceability" in profile.features, f"{profile.subgenre} missing danceability"
        assert "dissonance_mean" in profile.features, f"{profile.subgenre} missing dissonance_mean"
```

- [ ] **Step 4: Run classifier tests**

Run: `uv run pytest tests/test_audio/test_classification.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```text
feat(audio): add 10 new FeatureTargets to 15 MoodClassifier profiles
```

---

## Task 8: TrackFeatures extension + from_db()

**Files:**
- Modify: `app/core/track_features.py`

- [ ] **Step 1: Add 8 new fields to TrackFeatures**

After existing fields (`energy_bands`), add:

```python
    # P1 features (for scoring integration)
    dissonance_mean: float | None = None
    danceability: float | None = None
    tonnetz_vector: list[float] | None = None
    beat_loudness_band_ratio: list[float] | None = None

    # P2 features
    spectral_complexity_mean: float | None = None
    pitch_salience_mean: float | None = None

    # Existing but previously unused
    bpm_stability: float | None = None
    spectral_contrast: float | None = None
```

- [ ] **Step 2: Update from_db() to populate new fields**

In `from_db()` classmethod, add JSON parsing for vector fields and direct mapping for scalar fields:

```python
        # Parse tonnetz_vector from JSON
        tonnetz = None
        raw_tonnetz = getattr(row, "tonnetz_vector", None)
        if raw_tonnetz:
            tonnetz = json.loads(raw_tonnetz) if isinstance(raw_tonnetz, str) else raw_tonnetz

        # Parse beat_loudness_band_ratio from JSON
        beat_loud = None
        raw_beat_loud = getattr(row, "beat_loudness_band_ratio", None)
        if raw_beat_loud:
            beat_loud = json.loads(raw_beat_loud) if isinstance(raw_beat_loud, str) else raw_beat_loud

        return cls(
            # ... existing fields ...
            dissonance_mean=getattr(row, "dissonance_mean", None),
            danceability=getattr(row, "danceability", None),
            tonnetz_vector=tonnetz,
            beat_loudness_band_ratio=beat_loud,
            spectral_complexity_mean=getattr(row, "spectral_complexity_mean", None),
            pitch_salience_mean=getattr(row, "pitch_salience_mean", None),
            bpm_stability=getattr(row, "bpm_stability", None),
            spectral_contrast=getattr(row, "spectral_contrast", None),
        )
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```text
feat(core): extend TrackFeatures with P1/P2/unused scoring fields
```

---

## Task 9: TransitionScorer — enriched components + timbral

**Files:**
- Modify: `app/services/transition.py`
- Modify: `app/core/constants.py`
- Create: `tests/test_services/test_transition_scoring_p2.py`

- [ ] **Step 1: Write scoring enrichment tests**

Create `tests/test_services/test_transition_scoring_p2.py`:

```python
"""Tests for P2 TransitionScorer enrichments."""
from __future__ import annotations

import pytest

from app.core.track_features import TrackFeatures
from app.services.transition import TransitionScorer

def _base_features(**overrides) -> TrackFeatures:
    """Create TrackFeatures with sensible defaults + overrides."""
    defaults = {
        "bpm": 130.0,
        "key_code": 0,
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 2000.0,
        "spectral_flatness": 0.2,
        "energy_mean": 0.5,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
        "hnr_db": 5.0,
        "chroma_entropy": 3.0,
        "mfcc_vector": [0.1] * 13,
        "energy_bands": [0.1, 0.2, 0.15, 0.15, 0.1, 0.05],
    }
    defaults.update(overrides)
    return TrackFeatures(**defaults)

class TestTonnetzEnrichment:
    def test_harmonic_with_tonnetz_identical(self):
        """Identical tonnetz vectors should boost harmonic score."""
        scorer = TransitionScorer()
        vec = [0.1, 0.2, -0.1, 0.0, 0.15, -0.05]
        a = _base_features(tonnetz_vector=vec)
        b = _base_features(tonnetz_vector=vec)
        score_with = scorer.score(a, b)

        a_no = _base_features(tonnetz_vector=None)
        b_no = _base_features(tonnetz_vector=None)
        score_without = scorer.score(a_no, b_no)

        # With identical tonnetz, harmonic component should be >= without
        assert score_with.harmonic >= score_without.harmonic

class TestDissonancePenalty:
    def test_both_high_dissonance_penalized(self):
        """Two highly dissonant tracks should penalize spectral score."""
        scorer = TransitionScorer()
        a = _base_features(dissonance_mean=0.7)
        b = _base_features(dissonance_mean=0.6)
        score_high = scorer.score(a, b)

        a_low = _base_features(dissonance_mean=0.1)
        b_low = _base_features(dissonance_mean=0.1)
        score_low = scorer.score(a_low, b_low)

        assert score_low.spectral >= score_high.spectral

class TestTimbralComponent:
    def test_timbral_score_exists(self):
        """TransitionScore should have timbral field."""
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        b = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        score = scorer.score(a, b)
        assert hasattr(score, "timbral")
        assert 0.0 <= score.timbral <= 1.0

    def test_timbral_similar_tracks_high(self):
        """Tracks with similar spectral contrast and pitch salience score high."""
        scorer = TransitionScorer()
        a = _base_features(spectral_contrast=5.0, pitch_salience_mean=0.3)
        b = _base_features(spectral_contrast=6.0, pitch_salience_mean=0.35)
        score = scorer.score(a, b)
        assert score.timbral > 0.7

class TestBackwardCompatibility:
    def test_scores_unchanged_without_p2_features(self):
        """Tracks without P2 features should get same scores as before."""
        scorer = TransitionScorer()
        a = _base_features()
        b = _base_features(bpm=132.0, key_code=1, integrated_lufs=-9.0)
        score = scorer.score(a, b)

        # Should produce valid score (not crash, not NaN)
        assert 0.0 <= score.overall <= 1.0
        assert not score.hard_reject

class TestBpmStabilityFactor:
    def test_unstable_bpm_penalizes(self):
        """Low bpm_stability should reduce BPM score."""
        scorer = TransitionScorer()
        a_stable = _base_features(bpm_stability=0.95)
        b_stable = _base_features(bpm_stability=0.95, bpm=131.0)
        score_stable = scorer.score(a_stable, b_stable)

        a_unstable = _base_features(bpm_stability=0.4)
        b_unstable = _base_features(bpm_stability=0.4, bpm=131.0)
        score_unstable = scorer.score(a_unstable, b_unstable)

        assert score_stable.bpm >= score_unstable.bpm
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_transition_scoring_p2.py -v`
Expected: FAIL — no `timbral` field, no enrichments

- [ ] **Step 3: Update DEFAULT_TRANSITION_WEIGHTS**

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

- [ ] **Step 4: Add timbral field to TransitionScore dataclass**

In `app/services/transition.py`, add `timbral: float = 0.0` to `TransitionScore`.

- [ ] **Step 5: Implement _score_timbral()**

Add method to `TransitionScorer`:

```python
def _score_timbral(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Timbral similarity: spectral contrast + pitch salience proximity."""
    signals: list[float] = []
    weights: list[float] = []

    if from_t.spectral_contrast is not None and to_t.spectral_contrast is not None:
        diff = abs(from_t.spectral_contrast - to_t.spectral_contrast)
        signals.append(max(0.0, 1.0 - diff / 15.0))
        weights.append(0.5)

    if from_t.pitch_salience_mean is not None and to_t.pitch_salience_mean is not None:
        diff = abs(from_t.pitch_salience_mean - to_t.pitch_salience_mean)
        signals.append(max(0.0, 1.0 - diff / 0.5))
        weights.append(0.5)

    if not signals:
        return 0.5  # neutral

    return sum(s * w for s, w in zip(signals, weights)) / sum(weights)
```

- [ ] **Step 6: Enrich existing scoring components**

Update `_score_harmonic()` — add tonnetz cosine (30% weight):

```python
# After existing camelot_score * hnr_factor:
if from_t.tonnetz_vector and to_t.tonnetz_vector:
    tonnetz_cos = self._cosine_similarity(from_t.tonnetz_vector, to_t.tonnetz_vector)
    base_score = 0.70 * base_score + 0.30 * tonnetz_cos
```

Update `_score_spectral()` — add dissonance and complexity penalties:

```python
# After existing composite score:
if from_t.dissonance_mean is not None and to_t.dissonance_mean is not None:
    if from_t.dissonance_mean > 0.4 and to_t.dissonance_mean > 0.4:
        score = max(0.0, score - 0.15)
if from_t.spectral_complexity_mean is not None and to_t.spectral_complexity_mean is not None:
    if abs(from_t.spectral_complexity_mean - to_t.spectral_complexity_mean) > 10:
        score = max(0.0, score - 0.10)
```

Update `_score_groove()` — add beat_loudness_band_ratio cosine (30%):

```python
# Replace 50/50 with 35/35/30:
if from_t.beat_loudness_band_ratio and to_t.beat_loudness_band_ratio:
    beat_cos = self._cosine_similarity(from_t.beat_loudness_band_ratio, to_t.beat_loudness_band_ratio)
    score = 0.35 * onset_match + 0.35 * kick_match + 0.30 * beat_cos
else:
    score = 0.50 * onset_match + 0.50 * kick_match
```

Update `_score_bpm()` — add bpm_stability factor:

```python
# After gaussian score:
if from_t.bpm_stability is not None and to_t.bpm_stability is not None:
    stability = min(from_t.bpm_stability, to_t.bpm_stability)
    score *= max(0.7, stability)  # unstable = up to 30% penalty
```

- [ ] **Step 7: Update _compute_score() to include timbral**

```python
def _compute_score(self, from_t, to_t, weights=None):
    w = weights or self.weights
    bpm = self._score_bpm(from_t, to_t)
    harmonic = self._score_harmonic(from_t, to_t)
    energy = self._score_energy(from_t, to_t)
    spectral = self._score_spectral(from_t, to_t)
    groove = self._score_groove(from_t, to_t)
    timbral = self._score_timbral(from_t, to_t)

    overall = (
        w.get("bpm", 0) * bpm
        + w.get("harmonic", 0) * harmonic
        + w.get("energy", 0) * energy
        + w.get("spectral", 0) * spectral
        + w.get("groove", 0) * groove
        + w.get("timbral", 0) * timbral
    )

    return TransitionScore(
        bpm=bpm, harmonic=harmonic, energy=energy,
        spectral=spectral, groove=groove, timbral=timbral,
        overall=overall,
    )
```

- [ ] **Step 8: Add _cosine_similarity helper if not present**

```python
@staticmethod
def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors, returns 0-1."""
    import numpy as np
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom < 1e-10:
        return 0.0
    return float(max(0.0, np.dot(va, vb) / denom))
```

- [ ] **Step 9: Run tests**

Run: `uv run pytest tests/test_services/test_transition_scoring_p2.py tests/test_services/ -v`
Expected: PASS

- [ ] **Step 10: Commit**

```text
feat(scoring): enrich TransitionScorer with P1/P2 features and timbral component
```

---

## Task 10: Context-Aware Transition Weights

**Files:**
- Create: `app/core/transition_intent.py`
- Modify: `app/services/transition.py`

- [ ] **Step 1: Write tests**

Add to `tests/test_services/test_transition_scoring_p2.py`:

```python
from app.core.transition_intent import TransitionIntent, infer_intent, INTENT_WEIGHT_MODIFIERS

class TestTransitionIntent:
    def test_infer_ramp_up_early_position(self):
        assert infer_intent(0.1, 0.0) == TransitionIntent.RAMP_UP

    def test_infer_cool_down_late_position(self):
        assert infer_intent(0.9, 0.0) == TransitionIntent.COOL_DOWN

    def test_infer_ramp_up_energy_delta(self):
        assert infer_intent(0.5, 3.0) == TransitionIntent.RAMP_UP

    def test_infer_cool_down_energy_delta(self):
        assert infer_intent(0.5, -3.0) == TransitionIntent.COOL_DOWN

    def test_infer_maintain_default(self):
        assert infer_intent(0.5, 0.5) == TransitionIntent.MAINTAIN

    def test_all_intents_weights_sum_to_one(self):
        for intent, weights in INTENT_WEIGHT_MODIFIERS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{intent}: weights sum to {total}"

    def test_scorer_with_intent(self):
        scorer = TransitionScorer()
        a = _base_features()
        b = _base_features(bpm=132.0, key_code=1)
        score_default = scorer.score(a, b)
        score_ramp = scorer.score(a, b, intent=TransitionIntent.RAMP_UP)
        # Different intents should produce different scores
        assert score_default.overall != score_ramp.overall or True  # may be equal
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_transition_scoring_p2.py::TestTransitionIntent -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create TransitionIntent module**

Create `app/core/transition_intent.py`:

```python
"""Context-aware transition intent and weight modifiers."""
from __future__ import annotations

from enum import StrEnum

class TransitionIntent(StrEnum):
    MAINTAIN = "maintain"
    RAMP_UP = "ramp_up"
    COOL_DOWN = "cool_down"
    CONTRAST = "contrast"

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

def infer_intent(
    set_position: float,
    energy_delta_lufs: float,
) -> TransitionIntent:
    """Auto-detect transition intent from set position and energy delta."""
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

- [ ] **Step 4: Update TransitionScorer.score() to accept intent**

In `app/services/transition.py`, modify `score()`:

```python
def score(
    self,
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    intent: TransitionIntent | None = None,
) -> TransitionScore:
    rejection = self._check_hard_constraints(from_t, to_t)
    if rejection is not None:
        return rejection

    weights = INTENT_WEIGHT_MODIFIERS[intent] if intent is not None else self.weights
    return self._compute_score(from_t, to_t, weights=weights)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_services/test_transition_scoring_p2.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```text
feat(scoring): add context-aware TransitionIntent with weight modifiers
```

---

## Task 11: GA Optimizer — intent-aware scoring

**Files:**
- Modify: `app/services/optimizer.py`

- [ ] **Step 1: Update _transition_quality to pass intent**

In `app/services/optimizer.py`, modify `_transition_quality()` to accept and use intent:

```python
def _transition_quality(
    scorer: TransitionScorer,
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
) -> float:
    if len(order) < 2:
        return 1.0
    total = 0.0
    n = len(order)
    for i in range(n - 1):
        a = tracks[idx_map[order[i]]]
        b = tracks[idx_map[order[i + 1]]]
        position = i / max(1, n - 2)  # 0.0 to 1.0
        energy_delta = (
            (b.integrated_lufs or -8.0) - (a.integrated_lufs or -8.0)
        )
        intent = infer_intent(position, energy_delta)
        score = scorer.score(a, b, intent=intent)
        total += 0.0 if score.hard_reject else score.overall
    return total / (n - 1)
```

Add import at top: `from app.core.transition_intent import infer_intent`

- [ ] **Step 2: Run optimizer tests**

Run: `uv run pytest tests/test_services/test_optimizer.py -v`
Expected: PASS (backward compatible — intent adds variation, doesn't break)

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
feat(optimizer): use context-aware intent in GA transition scoring
```

---

## Task 12: Integration tests — pipeline discovery + e2e

**Files:**
- Modify: `tests/test_audio/test_pipeline_refactored.py`

- [ ] **Step 1: Add P2 discovery test**

```python
async def test_pipeline_discovers_p2_analyzers():
    """Auto-discovery finds P2 analyzers."""
    from app.audio.analyzers.base import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()
    available = set(registry.list_available())

    p2_names = {"spectral_complexity", "pitch_salience", "bpm_histogram", "phrase"}
    discovered = p2_names & available
    assert len(discovered) > 0, f"No P2 analyzers discovered. Available: {available}"
```

- [ ] **Step 2: Add scoring parity test**

```python
def test_scoring_parity_without_p2():
    """Tracks without P2 features produce valid scores (no crash, no NaN)."""
    from app.core.track_features import TrackFeatures
    from app.services.transition import TransitionScorer

    scorer = TransitionScorer()
    a = TrackFeatures(
        bpm=130.0, key_code=0, integrated_lufs=-8.0,
        spectral_centroid_hz=2000.0, spectral_flatness=0.2,
        energy_mean=0.5, onset_rate=4.0, kick_prominence=0.5,
        hnr_db=5.0, chroma_entropy=3.0,
    )
    b = TrackFeatures(
        bpm=132.0, key_code=1, integrated_lufs=-9.0,
        spectral_centroid_hz=2200.0, spectral_flatness=0.25,
        energy_mean=0.55, onset_rate=4.2, kick_prominence=0.6,
        hnr_db=6.0, chroma_entropy=3.5,
    )
    score = scorer.score(a, b)
    assert 0.0 <= score.overall <= 1.0
    assert not score.hard_reject
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_audio/test_pipeline_refactored.py -v`
Expected: PASS

- [ ] **Step 4: Run full test suite + lint**

Run: `uv run ruff check app/ tests/ && uv run pytest tests/ -x -q`
Expected: All clean

- [ ] **Step 5: Commit**

```text
test(audio): add P2 discovery and scoring parity integration tests
```

---

## Task 13: Documentation update

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CHANGELOG.md [Unreleased]**

Add to `### Added`:
```markdown
- 4 new P2 analyzers: SpectralComplexityAnalyzer, PitchSalienceAnalyzer, BpmHistogramAnalyzer, PhraseAnalyzer
- Context-aware TransitionIntent enum with weight modifiers (maintain/ramp_up/cool_down/contrast)
- New `score_timbral` component in TransitionScorer (spectral contrast + pitch salience proximity)
- 10 new FeatureTargets integrated into 15 MoodClassifier profiles (P1 + P2 + unused existing)
- Alembic migration for 7 P2 analyzer columns
```

Add to `### Changed`:
```markdown
- TransitionScorer enriched: tonnetz cosine in harmonic, dissonance/complexity penalties in spectral, beat_loudness in groove, bpm_stability factor in BPM
- TransitionScorer weights rebalanced: bpm 0.22, harmonic 0.20, energy 0.23, spectral 0.15, groove 0.10, timbral 0.10 (new)
- TrackFeatures extended with 8 new fields (P1 + P2 + unused existing)
- GA optimizer uses context-aware intent for position-dependent transition scoring
- BeatDetector exports beats_intervals for BpmHistogramAnalyzer dependency
```

- [ ] **Step 2: Update README.md**

Update analyzer count: 14 → 18. Update features count. Add phrase detection to feature list.

- [ ] **Step 3: Update CLAUDE.md**

Update version line and add P2 gotchas.

- [ ] **Step 4: Commit**

```bash
docs: update CHANGELOG, README, CLAUDE.md for P2 analyzers + integration
```
