# tests/test_audio/test_pipeline_refactored.py
"""Tests for refactored AnalysisPipeline — DI, context, parallelism."""

from __future__ import annotations

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
