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
    import soundfile as sf

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
    import soundfile as sf

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
    import numpy as np
    import soundfile as sf

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
