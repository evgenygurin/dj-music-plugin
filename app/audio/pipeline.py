# app/audio/pipeline.py
"""Analysis pipeline — orchestrates analyzers with parallel execution.

Builds one AnalysisContext per unique clip duration (full track + 60s clip
for heavy librosa analyzers), then dispatches analyzers via
asyncio.to_thread() for CPU-bound concurrency.

Analyzers declare their needed clip via ``BaseAnalyzer.clip_duration_s``:
- ``None`` → full track (loudness, structure, energy)
- ``60.0`` → stitched 60-second clip (beat, bpm, key, spectral, ...)

Heavy librosa ops (effects.hpss, beat_track, chroma_cqt, tonnetz) are O(N)
in samples. On a 6-7 minute techno track the difference is dramatic
(beat: 16s vs 3s). The stitched clip samples 3 windows of 20s from
positions ~17%/50%/83% of the track and concatenates them with short
fades to avoid click artifacts. This is more robust than a single
center window: it skips intro/outro padding while capturing variation
between sections (build vs drop vs breakdown), giving statistically
representative aggregates for techno tracks where harmony, BPM, and
timbre are stable but per-section dynamics differ.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AnalyzerResult, AudioSignal

# Stitched-clip strategy parameters. Three windows from across the track
# at positions corresponding to (i + 0.5) / N for i in 0..N-1, i.e. 1/6,
# 3/6, 5/6 of duration. Skips intro/outro, captures section variation.
_DEFAULT_N_WINDOWS = 3
_FADE_MS = 20.0

_LIBROSA_WARMED_UP = False


def _warmup_librosa() -> None:
    """Pre-import librosa submodules on the main thread.

    Without this, multiple worker threads concurrently triggering the lazy
    loader inside librosa/scipy hit a circular-import race the first time
    each submodule is touched (``Module 'scipy' has no attribute '_lib'``,
    ``cannot import name 'PytestTester'``). Warming up once on the main
    thread before any ``asyncio.to_thread(analyzer.run, ...)`` dispatch
    eliminates the race.
    """
    global _LIBROSA_WARMED_UP
    if _LIBROSA_WARMED_UP:
        return
    try:
        import librosa
        import librosa.beat
        import librosa.effects
        import librosa.feature
        import librosa.feature.rhythm
        import librosa.feature.spectral
        import librosa.onset  # noqa: F401
    except ImportError:
        # librosa is optional — only librosa-dependent analyzers will fail
        pass
    _LIBROSA_WARMED_UP = True


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

        # Eliminate scipy/librosa lazy-loader races before threaded dispatch
        if any("librosa" in a.required_packages for a in instances):
            _warmup_librosa()

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

    centered=True selects a representative excerpt of `duration_s` seconds
    using the stitched multi-window strategy (default 3 x 20s windows
    from positions ~1/6, 3/6, 5/6 of the track). This captures variation
    between sections (intro/build/drop/breakdown) better than a single
    center window while keeping the same compute budget.

    centered=False takes the head — used for caller-supplied max_duration
    legacy behavior.

    Falls back to a single centered window when the track is too short
    for non-overlapping sub-windows.
    """
    sr = signal.sample_rate
    n_total = int(duration_s * sr)
    if n_total >= len(signal.samples):
        return signal

    if not centered:
        return AudioSignal(
            samples=signal.samples[:n_total],
            sample_rate=sr,
            duration_seconds=n_total / sr,
            file_path=signal.file_path,
        )

    samples = _build_stitched_clip(signal.samples, sr, duration_s, _DEFAULT_N_WINDOWS)
    return AudioSignal(
        samples=samples,
        sample_rate=sr,
        duration_seconds=len(samples) / sr,
        file_path=signal.file_path,
    )


def _build_stitched_clip(
    samples: np.ndarray, sr: int, duration_s: float, n_windows: int
) -> np.ndarray:
    """Build a stitched clip by sampling N windows across the source.

    Each window is `duration_s / n_windows` seconds long, centered at
    position ``(i + 0.5) / n_windows`` of the source. Windows are
    fade-blended at their boundaries with a short hann ramp to avoid
    click artifacts that would create false onsets in beat detection.

    If windows would overlap (track too short), falls back to a single
    centered window of `duration_s` seconds.
    """
    n_total = int(duration_s * sr)
    win_size = n_total // n_windows
    fade_len = min(int(_FADE_MS / 1000.0 * sr), win_size // 4)

    # Span needed for non-overlapping windows: n_windows * win_size.
    # If source is shorter, fall back to single centered window.
    if len(samples) < n_windows * win_size:
        start = (len(samples) - n_total) // 2
        return samples[start : start + n_total].copy()

    # Hann fade-in and fade-out ramps applied to each window
    if fade_len > 0:
        ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))
        ramp = ramp.astype(samples.dtype)
    else:
        ramp = np.empty(0, dtype=samples.dtype)

    pieces: list[np.ndarray] = []
    for i in range(n_windows):
        center = int((i + 0.5) / n_windows * len(samples))
        start = max(0, center - win_size // 2)
        end = min(len(samples), start + win_size)
        start = max(0, end - win_size)  # right-align if we hit the end
        window = samples[start:end].copy()
        if fade_len > 0:
            window[:fade_len] *= ramp
            window[-fade_len:] *= ramp[::-1]
        pieces.append(window)

    return np.concatenate(pieces)
