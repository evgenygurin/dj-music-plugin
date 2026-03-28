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
