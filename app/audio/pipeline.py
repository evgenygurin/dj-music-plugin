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
        """List failed analyzers with their error messages."""
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
            await asyncio.gather(*(asyncio.to_thread(a.run, ctx) for a in instances))
        )

        return PipelineResult(
            results=results,
            features=self._merge_features(results),
        )

    @staticmethod
    def _merge_features(results: list[AnalyzerResult]) -> dict[str, Any]:
        """Merge features from all successful analyzer results."""
        merged: dict[str, Any] = {}
        for result in results:
            if result.success:
                merged.update(result.features)
        return merged
