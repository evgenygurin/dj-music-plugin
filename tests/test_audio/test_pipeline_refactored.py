# tests/test_audio/test_pipeline_refactored.py
"""Tests for refactored AnalysisPipeline — DI, context, parallelism."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest

from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AudioSignal
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
    async def test_pipeline_creates_analysis_context(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """Pipeline creates AnalysisContext from signal (eager STFT)."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake/path.wav", analyzers=["loudness"])
        assert result.success_count >= 1
        assert "integrated_lufs" in result.features

    async def test_pipeline_uses_injected_loader(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """Pipeline calls AudioLoader.load() — no inline loading."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        await pipeline.analyze("/fake/path.wav", analyzers=["loudness"])
        loader.load.assert_called_once_with("/fake/path.wav")

    async def test_pipeline_merges_features(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """Pipeline merges features from multiple analyzers."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake/path.wav", analyzers=["loudness", "energy"])
        assert "integrated_lufs" in result.features
        assert "energy_mean" in result.features

    async def test_pipeline_max_duration_clips(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """Pipeline clips audio to max_duration."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake/path.wav", analyzers=["loudness"], max_duration=0.5)
        assert result.success_count >= 1

    async def test_pipeline_handles_empty_analyzers_list(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """Empty analyzers list runs all available."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake/path.wav")
        # Should run some analyzers (at least loudness, energy, spectral, structure)
        assert result.success_count >= 4

    async def test_pipeline_default_loader(self, registry: AnalyzerRegistry) -> None:
        """Pipeline creates default AudioLoader if none injected."""
        pipeline = AnalysisPipeline(registry)
        assert pipeline._loader is not None
        assert isinstance(pipeline._loader, AudioLoader)

    async def test_pipeline_errors_property(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """errors property lists only failed analyzers."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake/path.wav", analyzers=["loudness", "energy"])
        # All should succeed — errors list should be empty
        assert result.errors == []

    async def test_pipeline_success_count(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """success_count matches number of succeeded results."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze(
            "/fake/path.wav", analyzers=["loudness", "energy", "spectral"]
        )
        assert result.success_count == len([r for r in result.results if r.success])

    async def test_pipeline_unknown_analyzer_skipped(
        self, signal: AudioSignal, registry: AnalyzerRegistry
    ) -> None:
        """Unknown analyzer name is silently skipped."""
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = signal
        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze(
            "/fake/path.wav", analyzers=["loudness", "nonexistent_xyz"]
        )
        assert result.success_count == 1


from typing import ClassVar


async def test_pipeline_two_phase_dependent_receives_prior(tmp_path, monkeypatch):
    """Dependent analyzers in Phase 2 receive Phase 1 results via prior_results."""
    sf = pytest.importorskip("soundfile")

    from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer

    # Create a simple WAV file
    sr = 22050
    duration = 2.0
    samples = (
        np.random.default_rng(42).standard_normal(int(sr * duration)).astype(np.float32) * 0.3
    )
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
    sf = pytest.importorskip("soundfile")

    from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer

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


async def test_pipeline_discovers_new_p1_analyzers():
    """Auto-discovery finds all 14 analyzers including 6 new P1 ones."""
    pytest.importorskip("librosa")
    from app.audio.analyzers.base import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()

    available = set(registry.list_available())

    # New P1 analyzers should be discovered (if their deps are installed)
    p1_names = {
        "danceability",
        "tempogram",
        "dissonance",
        "dynamic_complexity",
        "tonnetz",
        "beats_loudness",
    }
    # At least some should be available (depends on installed libs)
    discovered_p1 = p1_names & available
    assert len(discovered_p1) > 0, f"No P1 analyzers discovered. Available: {available}"


async def test_pipeline_populates_beat_loudness_when_beats_available(tmp_path):
    """E2E: beat_loudness_band_ratio is populated when BeatDetector succeeds."""
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    import numpy as np

    from app.audio.pipeline import AnalysisPipeline

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
            samples[start:end] = 0.8 * np.sin(2 * np.pi * 60 * np.arange(end - start) / sr).astype(
                np.float32
            )

    wav_path = tmp_path / "kick_test.wav"
    sf.write(str(wav_path), samples, sr)

    reg = AnalyzerRegistry()
    reg.discover()
    pipeline = AnalysisPipeline(reg)
    result = await pipeline.analyze(str(wav_path))

    # beats_loudness requires essentia — only assert if it was available
    beats_loudness_available = "beats_loudness" in reg.list_available()
    if "beat_times" in result.features and beats_loudness_available:
        assert "beat_loudness_band_ratio" in result.features, (
            "beat_loudness_band_ratio should be populated when beat_times is available"
        )
        vec = result.features["beat_loudness_band_ratio"]
        assert isinstance(vec, list)
        assert len(vec) == 6


async def test_pipeline_discovers_p2_analyzers():
    """Auto-discovery finds P2 analyzers."""
    pytest.importorskip("librosa")
    from app.audio.analyzers.base import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()
    available = set(registry.list_available())

    p2_names = {"spectral_complexity", "pitch_salience", "bpm_histogram", "phrase"}
    discovered = p2_names & available
    assert len(discovered) > 0, f"No P2 analyzers discovered. Available: {available}"


def test_scoring_parity_without_p2():
    """Tracks without P2 features produce valid scores (no crash, no NaN)."""
    from app.core.track_features import TrackFeatures
    from app.services.transition import TransitionScorer

    scorer = TransitionScorer()
    a = TrackFeatures(
        bpm=130.0,
        key_code=0,
        integrated_lufs=-8.0,
        spectral_centroid_hz=2000.0,
        spectral_flatness=0.2,
        energy_mean=0.5,
        onset_rate=4.0,
        kick_prominence=0.5,
        hnr_db=5.0,
        chroma_entropy=3.0,
    )
    b = TrackFeatures(
        bpm=132.0,
        key_code=1,
        integrated_lufs=-9.0,
        spectral_centroid_hz=2200.0,
        spectral_flatness=0.25,
        energy_mean=0.55,
        onset_rate=4.2,
        kick_prominence=0.6,
        hnr_db=6.0,
        chroma_entropy=3.5,
    )
    score = scorer.score(a, b)
    assert 0.0 <= score.overall <= 1.0
    assert not score.hard_reject


# ── Stitched multi-window clip strategy ────────────────────────────────


class TestStitchedClip:
    """Cover the multi-window clip strategy used by heavy librosa analyzers."""

    @staticmethod
    def _make_signal(duration_s: float, sr: int = 22050) -> AudioSignal:
        rng = np.random.default_rng(0)
        n = int(duration_s * sr)
        return AudioSignal(
            samples=rng.standard_normal(n).astype(np.float32),
            sample_rate=sr,
            duration_seconds=duration_s,
        )

    def test_clip_passthrough_when_signal_shorter_than_target(self) -> None:
        """A 30s source asked for 60s clip returns the full source unchanged."""
        from app.audio.pipeline import _clip_signal

        sig = self._make_signal(30.0)
        out = _clip_signal(sig, 60.0, centered=True)
        assert out is sig

    def test_clip_centered_returns_target_duration(self) -> None:
        """A 400s source clipped to 60s returns exactly 60s of audio."""
        from app.audio.pipeline import _clip_signal

        sig = self._make_signal(400.0)
        out = _clip_signal(sig, 60.0, centered=True)
        assert out.sample_rate == sig.sample_rate
        # Length within one sample of the target (integer division)
        target = int(60.0 * sig.sample_rate)
        assert abs(len(out.samples) - target) <= 1
        assert abs(out.duration_seconds - 60.0) < 1e-3

    def test_stitched_clip_samples_from_three_distinct_regions(self) -> None:
        """Three windows must be sourced from across the track, not contiguous.

        Mark the source with a slowly-rising ramp and check that the stitched
        clip contains samples from regions that span ≥50% of the source.
        Pure copy-from-the-middle would only span ~15% (60s of 400s).
        """
        from app.audio.pipeline import _clip_signal

        sr = 22050
        duration = 400.0
        n = int(duration * sr)
        # Strictly monotonic ramp 0..1 — every sample's value identifies its
        # original position uniquely
        ramp = (np.arange(n) / n).astype(np.float32)
        sig = AudioSignal(samples=ramp, sample_rate=sr, duration_seconds=duration)

        out = _clip_signal(sig, 60.0, centered=True)

        # Strip the fade-affected boundaries before checking source positions
        # (fade ramps multiply by hann, so values near 0 or 1 are distorted)
        clean = out.samples[2000:-2000]
        clean = clean[clean > 0.01]  # drop fade-zeroed boundary samples
        # Window centers should be near 1/6, 3/6, 5/6 → 0.167, 0.5, 0.833
        # Stitched clip must contain samples from BOTH the lower third and
        # the upper third of the source.
        assert clean.min() < 0.30, f"no early-track samples found, min={clean.min()}"
        assert clean.max() > 0.70, f"no late-track samples found, max={clean.max()}"

    def test_clip_head_only_for_max_duration_legacy(self) -> None:
        """centered=False (caller-supplied max_duration) takes the head."""
        from app.audio.pipeline import _clip_signal

        sr = 22050
        n = sr * 100
        sig = AudioSignal(
            samples=np.arange(n, dtype=np.float32),
            sample_rate=sr,
            duration_seconds=100.0,
        )
        out = _clip_signal(sig, 10.0, centered=False)
        assert out.samples[0] == 0.0
        assert len(out.samples) == sr * 10

    def test_stitched_clip_fades_to_zero_at_window_boundaries(self) -> None:
        """Hann ramps must drive the very first sample of each window to 0."""
        from app.audio.pipeline import _build_stitched_clip

        sr = 22050
        n = sr * 400
        # Constant non-zero signal so fade artifacts are easy to spot
        samples = np.ones(n, dtype=np.float32)
        out = _build_stitched_clip(samples, sr, duration_s=60.0, n_windows=3)

        win_size = int(60.0 * sr) // 3
        # First sample of each window should be ~0 (hann ramp starts at 0)
        for i in range(3):
            assert out[i * win_size] == pytest.approx(0.0, abs=1e-6)
            assert out[(i + 1) * win_size - 1] == pytest.approx(0.0, abs=1e-6)
        # Sample in the middle of a window should be back to ~1
        midpoint = win_size // 2
        assert out[midpoint] == pytest.approx(1.0, rel=1e-3)

    async def test_pipeline_uses_stitched_clip_for_clipped_analyzers(self) -> None:
        """End-to-end: an analyzer with clip_duration_s=60 sees 60s context."""
        from typing import Any

        from app.audio.analyzers.base import BaseAnalyzer
        from app.audio.core.context import AnalysisContext

        sr = 22050
        n = sr * 200  # 200s source
        sig = AudioSignal(
            samples=np.random.default_rng(1).standard_normal(n).astype(np.float32),
            sample_rate=sr,
            duration_seconds=200.0,
        )

        observed: dict[str, float] = {}

        class _Probe(BaseAnalyzer):
            name: ClassVar[str] = "_probe_clip"
            capabilities: ClassVar[frozenset[str]] = frozenset()
            required_packages: ClassVar[list[str]] = []
            clip_duration_s: ClassVar[float | None] = 60.0

            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                observed["duration"] = ctx.duration
                observed["samples"] = float(len(ctx.samples))
                return {"probe_ok": 1.0}

        registry = AnalyzerRegistry()
        registry.register(_Probe())
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = sig

        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake.wav", analyzers=["_probe_clip"])

        assert result.success_count == 1
        # Probe must see ~60s of audio, not the full 200s
        assert observed["duration"] == pytest.approx(60.0, abs=0.1)
        assert observed["samples"] == pytest.approx(sr * 60.0, abs=sr * 0.1)

    async def test_pipeline_full_track_for_unclipped_analyzers(self) -> None:
        """Analyzers with clip_duration_s=None see the full track."""
        from typing import Any

        from app.audio.analyzers.base import BaseAnalyzer
        from app.audio.core.context import AnalysisContext

        sr = 22050
        sig = AudioSignal(
            samples=np.random.default_rng(2).standard_normal(sr * 200).astype(np.float32),
            sample_rate=sr,
            duration_seconds=200.0,
        )

        observed: dict[str, float] = {}

        class _FullProbe(BaseAnalyzer):
            name: ClassVar[str] = "_probe_full"
            capabilities: ClassVar[frozenset[str]] = frozenset()
            required_packages: ClassVar[list[str]] = []
            clip_duration_s: ClassVar[float | None] = None

            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                observed["duration"] = ctx.duration
                return {"full_ok": 1.0}

        registry = AnalyzerRegistry()
        registry.register(_FullProbe())
        loader = AsyncMock(spec=AudioLoader)
        loader.load.return_value = sig

        pipeline = AnalysisPipeline(registry, loader)
        result = await pipeline.analyze("/fake.wav", analyzers=["_probe_full"])

        assert result.success_count == 1
        assert observed["duration"] == pytest.approx(200.0, abs=0.1)


# ── Vectorized sliding-window RMS ──────────────────────────────────────


class TestVectorizedSlidingWindowRMS:
    """Numerical parity check for the vectorized loudness helpers.

    The previous implementation used a Python ``for`` loop to compute RMS
    per window. The vectorized form uses ``sliding_window_view`` and a
    single mean-along-axis. This test pins down that the new
    implementation returns identical values for representative inputs,
    so any future regression on the LUFS pipeline gets caught.
    """

    @staticmethod
    def _reference_loop(samples: np.ndarray, window: int, hop: int) -> np.ndarray:
        n = len(samples)
        if n < window or window <= 0:
            return np.array([], dtype=np.float64)
        n_windows = (n - window) // hop + 1
        out = np.empty(n_windows, dtype=np.float64)
        for i in range(n_windows):
            start = i * hop
            block = samples[start : start + window]
            out[i] = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
        return out

    def test_vectorized_matches_python_loop_on_400hz_sine(self) -> None:
        from app.audio.analyzers.loudness import _sliding_window_rms

        sr = 22050
        t = np.arange(int(sr * 30.0)) / sr
        sig = (0.4 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
        for window, hop in [(8820, 2205), (66150, 22050), (4410, 1102)]:
            new = _sliding_window_rms(sig, window, hop)
            ref = self._reference_loop(sig, window, hop)
            assert new.shape == ref.shape
            np.testing.assert_allclose(new, ref, rtol=1e-6, atol=1e-8)

    def test_vectorized_matches_python_loop_on_white_noise(self) -> None:
        from app.audio.analyzers.loudness import _sliding_window_rms

        sr = 22050
        rng = np.random.default_rng(7)
        sig = rng.standard_normal(sr * 60).astype(np.float32)
        new = _sliding_window_rms(sig, window_size=int(0.4 * sr), hop_size=int(0.1 * sr))
        ref = self._reference_loop(sig, window=int(0.4 * sr), hop=int(0.1 * sr))
        np.testing.assert_allclose(new, ref, rtol=1e-6, atol=1e-8)

    def test_short_signal_returns_empty(self) -> None:
        from app.audio.analyzers.loudness import _sliding_window_rms

        sig = np.zeros(100, dtype=np.float32)
        out = _sliding_window_rms(sig, window_size=200, hop_size=50)
        assert out.shape == (0,)

    def test_rms_to_lufs_array_matches_scalar(self) -> None:
        from app.audio.analyzers.loudness import _rms_to_lufs, _rms_to_lufs_array

        rms = np.array([1e-8, 0.001, 0.05, 0.3, 1.0], dtype=np.float64)
        vec = _rms_to_lufs_array(rms)
        scal = np.array([_rms_to_lufs(float(r)) for r in rms])
        np.testing.assert_allclose(vec, scal, rtol=1e-12, atol=1e-12)


# ── Vectorized spectral slope / contrast ───────────────────────────────


class TestVectorizedSpectral:
    """Numerical parity check for vectorized spectral helpers."""

    @staticmethod
    def _make_magnitude(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
        """Build a (n_bins, n_frames) magnitude matrix and matching freqs."""
        n_bins = 1025
        n_frames = 200
        rng = np.random.default_rng(seed)
        # Power-law spectrum so the slope is non-trivial and per-frame
        # variation is realistic.
        base = 1.0 / (np.arange(1, n_bins + 1) ** 0.7)
        mag = (
            (base[:, None] * (1.0 + 0.3 * rng.standard_normal((n_bins, n_frames))))
            .clip(min=1e-6)
            .astype(np.float64)
        )
        freqs = np.linspace(0.0, 11025.0, n_bins).astype(np.float64)
        return mag, freqs

    @staticmethod
    def _reference_slope_loop(mag: np.ndarray, freqs: np.ndarray) -> np.ndarray:
        """Per-frame polyfit reference (the original implementation)."""
        n_frames = mag.shape[1]
        out = np.empty(n_frames, dtype=np.float64)
        valid = freqs > 0
        log_freqs = np.log2(freqs[valid])
        for i in range(n_frames):
            log_mags = 20.0 * np.log10(mag[valid, i] + 1e-10)
            coeffs = np.polyfit(log_freqs, log_mags, 1)
            out[i] = float(coeffs[0])
        return out

    @staticmethod
    def _reference_contrast_loop(
        mag: np.ndarray, freqs: np.ndarray, alpha: float = 0.2
    ) -> np.ndarray:
        from app.audio.analyzers.spectral import _CONTRAST_BANDS_HZ

        n_frames = mag.shape[1]
        out = np.empty(n_frames, dtype=np.float64)
        for i in range(n_frames):
            contrasts: list[float] = []
            for low_hz, high_hz in _CONTRAST_BANDS_HZ:
                mask = (freqs >= low_hz) & (freqs < high_hz)
                band_mags = mag[mask, i]
                if len(band_mags) < 2:
                    continue
                sorted_mags = np.sort(band_mags)
                n_alpha = max(1, int(len(sorted_mags) * alpha))
                peak = float(np.mean(sorted_mags[-n_alpha:]))
                valley = float(np.mean(sorted_mags[:n_alpha]))
                contrasts.append(20.0 * np.log10(peak + 1e-10) - 20.0 * np.log10(valley + 1e-10))
            out[i] = float(np.mean(contrasts)) if contrasts else 0.0
        return out

    def test_vectorized_slope_matches_polyfit_loop(self) -> None:
        from app.audio.analyzers.spectral import _vectorized_spectral_slope

        mag, freqs = self._make_magnitude(seed=1)
        new = _vectorized_spectral_slope(mag, freqs)
        ref = self._reference_slope_loop(mag, freqs)
        # Closed-form OLS slope is mathematically identical to polyfit's
        # least-squares solution for a linear fit.
        np.testing.assert_allclose(new, ref, rtol=1e-9, atol=1e-9)

    def test_vectorized_contrast_matches_per_frame_loop(self) -> None:
        from app.audio.analyzers.spectral import _vectorized_spectral_contrast

        mag, freqs = self._make_magnitude(seed=2)
        new = _vectorized_spectral_contrast(mag, freqs)
        ref = self._reference_contrast_loop(mag, freqs)
        np.testing.assert_allclose(new, ref, rtol=1e-9, atol=1e-9)

    def test_vectorized_slope_zero_when_no_valid_freqs(self) -> None:
        from app.audio.analyzers.spectral import _vectorized_spectral_slope

        mag = np.ones((1, 50), dtype=np.float64)
        freqs = np.array([0.0])  # only DC bin
        out = _vectorized_spectral_slope(mag, freqs)
        np.testing.assert_array_equal(out, np.zeros(50))


# ── ProcessPool dispatch path ──────────────────────────────────────────


class TestProcessPoolDispatch:
    """End-to-end checks for the ProcessPoolExecutor pipeline path.

    These tests spawn real worker processes via the forkserver start
    method, so they're slower than the thread-mode tests. Each test
    instantiates its own pipeline and shuts down the pool to keep
    test isolation clean.
    """

    @staticmethod
    def _make_techno_signal(duration_s: float = 8.0, sr: int = 22050) -> AudioSignal:
        """Build a small synthetic techno-like signal: 130 BPM kick + pad."""
        n = int(sr * duration_s)
        t = np.arange(n) / sr
        # Sub-bass kick at 60 Hz, on-beat at 130 BPM
        kick = np.zeros(n, dtype=np.float32)
        period = int(sr * 60.0 / 130.0)
        for start in range(0, n, period):
            length = min(int(0.05 * sr), n - start)
            env = np.exp(-np.arange(length) / (0.01 * sr)).astype(np.float32)
            kick[start : start + length] += env * np.sin(
                2 * np.pi * 60 * np.arange(length) / sr
            ).astype(np.float32)
        # Pad above to give the spectrum some upper content
        pad = (0.2 * np.sin(2 * np.pi * 220 * t) + 0.1 * np.sin(2 * np.pi * 330 * t)).astype(
            np.float32
        )
        samples = (kick + pad) * 0.7
        return AudioSignal(
            samples=samples.astype(np.float32),
            sample_rate=sr,
            duration_seconds=duration_s,
        )

    async def test_process_pool_runs_pure_numpy_analyzer(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """A core (numpy-only) analyzer must run end-to-end via processes."""
        import soundfile as sf

        from app.audio.pipeline import AnalysisPipeline

        sig = self._make_techno_signal(duration_s=4.0)
        wav_path = tmp_path / "tiny.wav"
        sf.write(str(wav_path), sig.samples, sig.sample_rate)

        pipeline = AnalysisPipeline(registry=registry, use_processes=True, max_workers=2)
        try:
            result = await pipeline.analyze(str(wav_path), analyzers=["loudness", "energy"])
            assert result.success_count == 2
            assert "integrated_lufs" in result.features
            assert "energy_mean" in result.features
            # Returned context is None in process mode (workers can't pickle Lock)
            assert result.context is None
        finally:
            pipeline.shutdown()

    async def test_process_pool_runs_librosa_analyzer(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """A librosa-dependent analyzer must run via processes too.

        This is the case where the warmup matters most: each fresh
        worker imports librosa+scipy on its first task. Verifies the
        worker function calls _warmup_librosa correctly.
        """
        pytest.importorskip("librosa")
        import soundfile as sf

        from app.audio.pipeline import AnalysisPipeline

        sig = self._make_techno_signal(duration_s=4.0)
        wav_path = tmp_path / "tiny.wav"
        sf.write(str(wav_path), sig.samples, sig.sample_rate)

        pipeline = AnalysisPipeline(registry=registry, use_processes=True, max_workers=2)
        try:
            result = await pipeline.analyze(str(wav_path), analyzers=["bpm"])
            assert result.success_count == 1
            assert "bpm" in result.features
            assert result.features["bpm"] > 0
        finally:
            pipeline.shutdown()

    async def test_process_pool_warm_pool_reuses_workers(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """Second analyze() call should reuse the warm pool — no second spawn.

        We don't time it precisely (CI noise), but we verify both calls
        succeed and produce identical features for the same input. If the
        pool was tearing down between calls and respawning, the second
        call would either fail or restart workers from cold.
        """
        import soundfile as sf

        from app.audio.pipeline import AnalysisPipeline

        sig = self._make_techno_signal(duration_s=4.0)
        wav_path = tmp_path / "tiny.wav"
        sf.write(str(wav_path), sig.samples, sig.sample_rate)

        pipeline = AnalysisPipeline(registry=registry, use_processes=True, max_workers=2)
        try:
            r1 = await pipeline.analyze(str(wav_path), analyzers=["loudness"])
            r2 = await pipeline.analyze(str(wav_path), analyzers=["loudness"])
            assert r1.success_count == 1
            assert r2.success_count == 1
            # Identical features for identical input
            assert r1.features["integrated_lufs"] == pytest.approx(
                r2.features["integrated_lufs"], abs=1e-9
            )
        finally:
            pipeline.shutdown()

    def test_pipeline_shutdown_is_idempotent(self, registry: AnalyzerRegistry) -> None:
        """Calling shutdown() multiple times must be safe (no exception)."""
        from app.audio.pipeline import AnalysisPipeline

        pipeline = AnalysisPipeline(registry=registry, use_processes=True, max_workers=2)
        # Pool is created lazily, so shutdown without analyze() is a no-op
        pipeline.shutdown()
        pipeline.shutdown()  # second call should not raise


# ── Async hygiene: event loop must stay responsive during analyze() ────


class TestEventLoopResponsiveness:
    """``analyze()`` must never block the caller's event loop.

    A blocking analyze() is a real production hazard: a FastAPI handler
    or MCP tool that calls await pipeline.analyze() would lock up the
    server for ~5s while librosa imports or ~1s while STFT runs in the
    main thread. These tests run a "ticker" coroutine in parallel with
    analyze() and verify the ticker keeps making progress.
    """

    @staticmethod
    async def _ticker(stop_event: asyncio.Event, ticks: list[float]) -> None:
        """Increment a counter every 10ms until told to stop."""
        start = time.perf_counter()
        while not stop_event.is_set():
            ticks.append(time.perf_counter() - start)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.01)
            except TimeoutError:
                continue

    async def test_thread_mode_analyze_does_not_block_event_loop(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """Thread-mode analyze() must yield to other coroutines.

        We dispatch a 10ms ticker concurrently with a real analyze()
        call. If analyze() blocks (e.g., synchronous _build_contexts
        in main thread), the ticker stops making progress for 0.5-5s
        and the gap between consecutive ticks exceeds the 10ms wait.
        """
        import soundfile as sf

        from app.audio.pipeline import AnalysisPipeline

        # Build a small techno-like signal so analyze() takes 1-3s
        sr = 22050
        duration = 4.0
        n = int(sr * duration)
        rng = np.random.default_rng(0)
        samples = (0.3 * rng.standard_normal(n)).astype(np.float32)
        wav_path = tmp_path / "signal.wav"
        sf.write(str(wav_path), samples, sr)

        pipeline = AnalysisPipeline(registry=registry)  # thread mode

        ticks: list[float] = []
        stop = asyncio.Event()
        ticker_task = asyncio.create_task(self._ticker(stop, ticks))
        try:
            result = await pipeline.analyze(
                str(wav_path), analyzers=["loudness", "energy", "spectral"]
            )
        finally:
            stop.set()
            await ticker_task

        assert result.success_count >= 2

        # Compute the largest gap between consecutive ticks. If the
        # event loop was blocked, there'll be a gap of >0.5s.
        assert len(ticks) >= 2, "ticker did not run at all"
        gaps = [ticks[i + 1] - ticks[i] for i in range(len(ticks) - 1)]
        max_gap = max(gaps) if gaps else 0.0
        # 0.2s budget — well above the 10ms target but well below the
        # ~1s _build_contexts cost we're protecting against.
        assert max_gap < 0.2, (
            f"event loop blocked for {max_gap:.3f}s during analyze() — "
            f"some sync work is not offloaded to to_thread"
        )

    async def test_process_mode_analyze_does_not_block_event_loop(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """Same responsiveness check for ProcessPool path.

        ProcessPool mode has additional sync work in the main process:
        clip variant construction, future submission. All of it should
        be offloaded so the ticker keeps progressing.
        """
        import soundfile as sf

        from app.audio.pipeline import AnalysisPipeline

        sr = 22050
        duration = 4.0
        n = int(sr * duration)
        rng = np.random.default_rng(1)
        samples = (0.3 * rng.standard_normal(n)).astype(np.float32)
        wav_path = tmp_path / "signal.wav"
        sf.write(str(wav_path), samples, sr)

        pipeline = AnalysisPipeline(registry=registry, use_processes=True, max_workers=2)

        ticks: list[float] = []
        stop = asyncio.Event()
        ticker_task = asyncio.create_task(self._ticker(stop, ticks))
        try:
            result = await pipeline.analyze(str(wav_path), analyzers=["loudness", "energy"])
        finally:
            stop.set()
            await ticker_task
            pipeline.shutdown()

        assert result.success_count == 2
        assert len(ticks) >= 2, "ticker did not run at all"
        gaps = [ticks[i + 1] - ticks[i] for i in range(len(ticks) - 1)]
        max_gap = max(gaps) if gaps else 0.0
        # ProcessPool spawn happens inside loop.run_in_executor which
        # returns a future immediately, so the spawn cost lives in the
        # worker process — main thread stays free.
        assert max_gap < 0.5, (
            f"event loop blocked for {max_gap:.3f}s during process-mode "
            f"analyze() — some sync work is not offloaded"
        )


# ── SharedMemory transport + per-worker context cache ─────────────────


class TestSharedMemoryTransport:
    """Verify that the process-pool path uses SharedMemory for clip samples
    and that segments are reliably released after every analyze() call.

    The optimization swaps multi-MB ndarray pickling for a zero-copy
    SharedMemory attach, plus an LRU AnalysisContext cache inside each
    worker so the STFT/magnitude/freqs work is paid only once per
    (worker, clip variant) pair within a call.
    """

    @staticmethod
    def _list_shm_segments() -> set[str]:
        """Snapshot ``/dev/shm`` for posix-shm names (Linux only)."""
        shm_root = Path("/dev/shm")
        if not shm_root.exists():
            return set()
        return {p.name for p in shm_root.iterdir() if p.name.startswith("psm_")}

    @pytest.mark.skipif(
        not Path("/dev/shm").exists(),
        reason="posix shared memory only on Linux",
    )
    async def test_no_shared_memory_leak_after_analyze(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """``/dev/shm`` must not grow across analyze() calls.

        Each call publishes clip variants into freshly-allocated
        SharedMemory blocks, then unlinks them in a finally. Even if
        worker LRU cache still holds attached views, the segment NAMES
        must disappear from ``/dev/shm`` so they don't show up as a
        leak. We allow the count to dip but not grow.
        """
        import soundfile as sf

        sr = 22050
        duration = 4.0
        n = int(sr * duration)
        rng = np.random.default_rng(7)
        samples = (0.3 * rng.standard_normal(n)).astype(np.float32)
        wav_path = tmp_path / "signal.wav"
        sf.write(str(wav_path), samples, sr)

        baseline = self._list_shm_segments()
        pipeline = AnalysisPipeline(registry=registry, use_processes=True, max_workers=2)
        try:
            for _ in range(3):
                result = await pipeline.analyze(
                    str(wav_path), analyzers=["loudness", "energy", "spectral"]
                )
                assert result.success_count == 3
        finally:
            pipeline.shutdown()

        # Workers are gone — give the OS a moment to reap any
        # lingering shared memory references and re-snapshot.
        await asyncio.sleep(0.05)
        after = self._list_shm_segments()
        leaked = after - baseline
        assert not leaked, (
            f"shared memory leaked {len(leaked)} segment(s) after analyze: {sorted(leaked)}"
        )

    async def test_features_identical_to_thread_mode(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """Numerical parity: process-mode features must match thread-mode.

        SharedMemory + worker context cache must not change a single
        feature value — workers see byte-identical samples and build
        a byte-identical AnalysisContext, so every analyzer output
        must match the thread-mode reference within float tolerance.
        """
        import soundfile as sf

        sr = 22050
        n = int(sr * 4.0)
        rng = np.random.default_rng(11)
        samples = (0.3 * rng.standard_normal(n)).astype(np.float32)
        wav_path = tmp_path / "signal.wav"
        sf.write(str(wav_path), samples, sr)

        analyzers = ["loudness", "energy", "spectral"]

        thread_pipe = AnalysisPipeline(registry=registry, use_processes=False)
        thread_result = await thread_pipe.analyze(str(wav_path), analyzers=analyzers)

        proc_pipe = AnalysisPipeline(registry=registry, use_processes=True, max_workers=2)
        try:
            proc_result = await proc_pipe.analyze(str(wav_path), analyzers=analyzers)
        finally:
            proc_pipe.shutdown()

        assert set(thread_result.features.keys()) == set(proc_result.features.keys())
        for key, thread_val in thread_result.features.items():
            proc_val = proc_result.features[key]
            if isinstance(thread_val, (int, float)) and isinstance(proc_val, (int, float)):
                np.testing.assert_allclose(
                    proc_val,
                    thread_val,
                    rtol=1e-9,
                    atol=1e-9,
                    err_msg=f"feature {key} differs between thread and process mode",
                )
            elif isinstance(thread_val, (list, tuple, np.ndarray)):
                np.testing.assert_allclose(
                    np.asarray(proc_val, dtype=float),
                    np.asarray(thread_val, dtype=float),
                    rtol=1e-9,
                    atol=1e-9,
                    err_msg=f"vector feature {key} differs between thread and process mode",
                )
            else:
                assert proc_val == thread_val, f"feature {key} differs"

    async def test_worker_context_cache_reused_within_call(
        self, tmp_path: Path, registry: AnalyzerRegistry
    ) -> None:
        """A second analyzer landing on the same worker reuses the cached context.

        We pin a single worker (``max_workers=1``) so every task in a
        single analyze() call lands on the same process. Three analyzers
        share the same clip variant (full track for loudness/energy/
        spectral). The first builds the AnalysisContext and primes the
        per-worker LRU; the next two MUST hit the cache, otherwise we
        regressed.

        We probe the cache by inspecting the module-level dict via a
        cleanup-task hook submitted on the same pool.
        """
        import soundfile as sf

        from app.audio import pipeline as pipeline_module

        sr = 22050
        n = int(sr * 4.0)
        rng = np.random.default_rng(13)
        samples = (0.3 * rng.standard_normal(n)).astype(np.float32)
        wav_path = tmp_path / "signal.wav"
        sf.write(str(wav_path), samples, sr)

        pipe = AnalysisPipeline(registry=registry, use_processes=True, max_workers=1)
        try:
            result = await pipe.analyze(
                str(wav_path), analyzers=["loudness", "energy", "spectral"]
            )
            assert result.success_count == 3

            # After the call, the LRU on the single worker should hold
            # exactly one entry (one clip variant). We probe it by
            # asking the pool to introspect its module-level cache.
            pool = pipe._get_pool()
            loop = asyncio.get_running_loop()
            cache_size = await loop.run_in_executor(pool, _probe_worker_cache_size)
            assert cache_size == 1, (
                f"expected exactly 1 cached AnalysisContext on the single "
                f"worker (one clip variant shared by 3 analyzers), got "
                f"{cache_size}"
            )

            # And the cache must NEVER exceed the configured LRU bound.
            from app.config import settings

            assert cache_size <= settings.audio_process_worker_cache_size

            # Sanity: the module-level _WORKER_CONTEXT_CACHE in the MAIN
            # process stays empty — the cache lives only in workers.
            assert len(pipeline_module._WORKER_CONTEXT_CACHE) == 0
        finally:
            pipe.shutdown()


def _probe_worker_cache_size() -> int:
    """Module-level helper picklable into a worker process.

    Returns the live size of the per-worker AnalysisContext cache so
    tests can assert reuse vs. eviction. Must NOT be defined inside a
    test class — ProcessPoolExecutor cannot pickle methods.
    """
    from app.audio.pipeline import _WORKER_CONTEXT_CACHE

    return len(_WORKER_CONTEXT_CACHE)
