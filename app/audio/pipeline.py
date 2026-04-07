# app/audio/pipeline.py
"""Analysis pipeline — orchestrates analyzers with parallel execution.

Builds one AnalysisContext per unique clip duration (full track + 60s clip
for heavy librosa analyzers), then dispatches analyzers via
asyncio.to_thread() for CPU-bound concurrency.

Analyzers declare their needed clip via ``BaseAnalyzer.clip_duration_s``:
- ``None`` → full track (loudness, structure, energy)
- ``60.0`` → centered 60-second clip (beat, bpm, key, spectral, ...)

Heavy librosa ops (effects.hpss, beat_track, chroma_cqt, tonnetz) are O(N)
in samples. On a 6-7 minute techno track the difference is dramatic
(beat: 16s vs 3s). For mood classification and transition scoring a 60s
center clip is statistically equivalent — techno has stable BPM/key/timbre.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AnalyzerResult, AudioSignal


@dataclass
class PipelineResult:
    """Combined result from all analyzers in a pipeline run."""

    results: list[AnalyzerResult] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)
    context: AnalysisContext | None = None

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
        return_context: bool = False,
    ) -> PipelineResult:
        """Run analyzers on audio file. Returns combined features.

        ``max_duration`` is an explicit override that clips the source signal
        before any analyzer runs. Per-analyzer clipping (via
        ``clip_duration_s`` ClassVar) is applied on top of this.
        """
        signal = await self._loader.load(file_path)

        # Explicit caller-supplied clip (overrides per-analyzer settings)
        if max_duration and signal.duration_seconds > max_duration:
            signal = _clip_signal(signal, max_duration)

        # Resolve analyzer instances
        analyzer_names = analyzers or self.registry.list_available()
        instances = [
            a for n in analyzer_names if (a := self.registry.get(n)) and a.is_available()
        ]

        # Build one context per unique clip duration. Most heavy analyzers
        # share clip_duration_s=60, so typically we build at most 2 contexts
        # (full + 60s). Spectral STFT is reused across all bucket members.
        contexts = self._build_contexts(signal, instances)

        # Partition by dependency: independent first, then dependent
        independent = [a for a in instances if not a.depends_on]
        dependent = [a for a in instances if a.depends_on]

        # Phase 1: independent
        phase1_results: list[AnalyzerResult] = list(
            await asyncio.gather(
                *(asyncio.to_thread(a.run, contexts[a.clip_duration_s]) for a in independent)
            )
        )

        # Phase 2: dependent — receive merged Phase 1 results
        all_results = list(phase1_results)
        if dependent:
            prior = self._merge_features(phase1_results)
            phase2_results: list[AnalyzerResult] = list(
                await asyncio.gather(
                    *(
                        asyncio.to_thread(a.run, contexts[a.clip_duration_s], prior)
                        for a in dependent
                    )
                )
            )
            all_results.extend(phase2_results)

        # Return the full-track context if available, else any context
        return_ctx = contexts.get(None) or next(iter(contexts.values()), None)
        return PipelineResult(
            results=all_results,
            features=self._merge_features(all_results),
            context=return_ctx if return_context else None,
        )

    @staticmethod
    def _build_contexts(
        signal: AudioSignal, instances: list[BaseAnalyzer]
    ) -> dict[float | None, AnalysisContext]:
        """Build one AnalysisContext per unique clip duration requested.

        Skips clipping if the signal is already shorter than the requested
        clip — those analyzers reuse the full-track context instead.
        """
        needed: set[float | None] = {a.clip_duration_s for a in instances}
        contexts: dict[float | None, AnalysisContext] = {}
        full_ctx: AnalysisContext | None = None

        for clip in needed:
            if clip is None or signal.duration_seconds <= clip:
                if full_ctx is None:
                    full_ctx = AnalysisContext(signal)
                contexts[clip] = full_ctx
            else:
                clipped = _clip_signal(signal, clip, centered=True)
                contexts[clip] = AnalysisContext(clipped)
        return contexts

    @staticmethod
    def _merge_features(results: list[AnalyzerResult]) -> dict[str, Any]:
        """Merge features from all successful analyzer results."""
        merged: dict[str, Any] = {}
        for result in results:
            if result.success:
                merged.update(result.features)
        return merged


def _clip_signal(signal: AudioSignal, duration_s: float, centered: bool = False) -> AudioSignal:
    """Return a clipped copy of the signal.

    centered=True picks a window from the middle of the track (best for
    techno: skips intro/outro, captures the main groove). centered=False
    takes the head — used for max_duration legacy behavior.
    """
    n_samples = int(duration_s * signal.sample_rate)
    if n_samples >= len(signal.samples):
        return signal
    start = (len(signal.samples) - n_samples) // 2 if centered else 0
    return AudioSignal(
        samples=signal.samples[start : start + n_samples],
        sample_rate=signal.sample_rate,
        duration_seconds=n_samples / signal.sample_rate,
        file_path=signal.file_path,
    )
