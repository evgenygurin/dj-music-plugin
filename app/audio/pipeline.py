# app/audio/pipeline.py
"""Analysis pipeline — orchestrates analyzers with parallel execution.

Builds one AnalysisContext per unique clip duration (full track + 60s clip
for heavy librosa analyzers), then dispatches analyzers either via
asyncio.to_thread() (default, ThreadPool) or via a ProcessPoolExecutor
when ``use_processes=True``.

ThreadPool path:
    Cheap (no spawn cost, no pickling), but limited by the Python GIL.
    Many of our analyzers do significant Python work between numpy/C
    calls, so threads compete for the GIL and effective parallelism is
    only ~3-5x even with 8 cores. Per-analyzer wall-clock can be
    inflated 20-30x vs real CPU time on cheap analyzers (bpm, key).

ProcessPool path:
    Each worker is a separate Python interpreter with its own GIL.
    True parallelism — pipeline wall-clock approaches max(per-analyzer
    real CPU). Pays a one-off ~0.5-1s spawn cost per worker (forkserver
    on Linux/macOS) and pickling overhead per dispatch. Worth it when
    the pool is reused across multiple analyses (FastMCP server,
    batch jobs). The pool is created lazily on first use and lives
    until the pipeline is garbage-collected.

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
import contextlib
import importlib
import multiprocessing
import os
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from multiprocessing import shared_memory
from typing import Any

import numpy as np

from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AnalyzerResult, AudioSignal, FrameParams
from app.config import get_settings

# Stitched-clip strategy parameters. Three windows from across the track
# at positions corresponding to (i + 0.5) / N for i in 0..N-1, i.e. 1/6,
# 3/6, 5/6 of duration. Skips intro/outro, captures section variation.
_DEFAULT_N_WINDOWS = 3
_FADE_MS = 20.0

_LIBROSA_WARMED_UP = False

# ── Per-worker AnalysisContext cache (process-pool path) ───────────────
# Module-level OrderedDict acting as an LRU. Lives inside each worker
# process — populated on first task that touches a given clip variant,
# reused by every subsequent task in the SAME analyze() call that needs
# the same clip (typically 4-8 analyzers per clip variant share one
# context, paying the ~150-300ms STFT cost only once per worker per
# call). Cache key includes the SharedMemory name, which is unique per
# analyze() call, so reuse across pipeline calls cannot leak features
# between unrelated tracks. Eviction frees the underlying SharedMemory
# attachment so the segment can be released by the OS once the main
# process unlinks it.
_WorkerCacheKey = tuple[str, int, int, int]
_WorkerCacheEntry = tuple[shared_memory.SharedMemory, AnalysisContext]
_WORKER_CONTEXT_CACHE: OrderedDict[_WorkerCacheKey, _WorkerCacheEntry] = OrderedDict()


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


def _create_shared_clip(
    samples: np.ndarray,
) -> tuple[shared_memory.SharedMemory, str, str, tuple[int, ...]]:
    """Allocate a SharedMemory block and copy ``samples`` into it.

    Returns the live SharedMemory handle (caller must close + unlink it
    in a finally block) plus the (name, dtype, shape) triple needed by
    workers to attach. We always copy because the input may be a non-
    contiguous slice (e.g. a stitched-clip view); the destination is a
    fresh contiguous buffer the worker can wrap with zero-copy
    ``np.ndarray(..., buffer=shm.buf)``.
    """
    contiguous = np.ascontiguousarray(samples)
    shm = shared_memory.SharedMemory(create=True, size=contiguous.nbytes)
    view = np.ndarray(contiguous.shape, dtype=contiguous.dtype, buffer=shm.buf)
    view[...] = contiguous
    return shm, shm.name, contiguous.dtype.str, tuple(contiguous.shape)


def _attach_shared_clip(
    name: str, dtype_str: str, shape: tuple[int, ...]
) -> tuple[shared_memory.SharedMemory, np.ndarray]:
    """Attach to an existing SharedMemory block by name (worker side).

    The returned ndarray is a zero-copy view onto the shared buffer and
    is marked read-only — workers must not mutate input samples (it
    would corrupt every other analyzer reading the same clip).
    """
    shm = shared_memory.SharedMemory(name=name)
    arr = np.ndarray(shape, dtype=np.dtype(dtype_str), buffer=shm.buf)
    arr.setflags(write=False)
    return shm, arr


def _publish_clips_to_shared_memory(
    clips: dict[float | None, np.ndarray],
) -> dict[float | None, tuple[shared_memory.SharedMemory, str, str, tuple[int, ...]]]:
    """Allocate one SharedMemory block per unique clip buffer.

    Multiple clip-duration keys can map to the same underlying ndarray
    (e.g. on a short track every variant collapses to the full
    samples). We dedupe by ``id(samples)`` so duplicates share one
    SharedMemory block — both saving the bytewise copy and ensuring
    every analyzer in the same bucket lands on a single cache entry
    in the worker, regardless of how many clip-duration buckets
    happen to point at the same buffer.

    Module-level so the dispatcher can hand it off to ``to_thread``
    without binding ``self`` (the bytewise copy can be ~10ms on a
    multi-MB clip — small but still off the event loop).
    """
    by_buffer: dict[int, tuple[shared_memory.SharedMemory, str, str, tuple[int, ...]]] = {}
    out: dict[float | None, tuple[shared_memory.SharedMemory, str, str, tuple[int, ...]]] = {}
    for clip, samples in clips.items():
        buf_id = id(samples)
        entry = by_buffer.get(buf_id)
        if entry is None:
            entry = _create_shared_clip(samples)
            by_buffer[buf_id] = entry
        out[clip] = entry
    return out


def _process_analyzer_worker(
    shm_name: str,
    dtype_str: str,
    shape: tuple[int, ...],
    sample_rate: int,
    file_path: str,
    frame_length: int,
    hop_length: int,
    cache_max_size: int,
    analyzer_module: str,
    analyzer_class: str,
    prior_results: dict[str, Any] | None = None,
) -> AnalyzerResult:
    """Run a single analyzer in a worker process.

    Module-level function (required for pickling under
    ProcessPoolExecutor + spawn/forkserver). Receives a SharedMemory
    handle name + the metadata needed to rebuild ``AudioSignal`` and
    ``AnalysisContext`` locally — we cannot pickle the context itself
    because it holds a ``threading.Lock`` for the lazy onset envelope
    cache.

    Two amortizations live here:

    1. Sample transport via SharedMemory: the worker attaches a zero-
       copy view onto the shared buffer instead of receiving a pickled
       multi-MB ndarray on every task.
    2. Per-worker LRU AnalysisContext cache: the first analyzer in a
       given (shm, frame_params) bucket pays the STFT/magnitude/freqs
       cost; every subsequent analyzer in the same call that lands on
       the same worker reuses the cached context.

    The worker also calls ``_warmup_librosa()`` once per process so
    librosa submodule imports are resolved before any analyzer runs
    (the warmup result is cached at module level inside the worker).
    """
    _warmup_librosa()

    cache_key = (shm_name, sample_rate, frame_length, hop_length)
    cached = _WORKER_CONTEXT_CACHE.get(cache_key)
    if cached is not None:
        _shm, ctx = cached
        _WORKER_CONTEXT_CACHE.move_to_end(cache_key)
    else:
        shm, samples = _attach_shared_clip(shm_name, dtype_str, shape)
        signal = AudioSignal(
            samples=samples,
            sample_rate=sample_rate,
            duration_seconds=len(samples) / sample_rate,
            file_path=file_path,
        )
        params = FrameParams(frame_length=frame_length, hop_length=hop_length)
        ctx = AnalysisContext(signal, params=params)
        _WORKER_CONTEXT_CACHE[cache_key] = (shm, ctx)
        while len(_WORKER_CONTEXT_CACHE) > cache_max_size:
            _, (old_shm, _old_ctx) = _WORKER_CONTEXT_CACHE.popitem(last=False)
            with contextlib.suppress(Exception):
                old_shm.close()

    module = importlib.import_module(analyzer_module)
    cls = getattr(module, analyzer_class)
    analyzer = cls()
    result: AnalyzerResult = analyzer.run(ctx, prior_results=prior_results)
    return result


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
    """Runs analyzers on audio files with shared context and parallel execution.

    Two dispatch modes:
        ``use_processes=False`` (default): asyncio.to_thread → ThreadPool.
            Cheap, no spawn cost, but GIL-bound.
        ``use_processes=True``: ProcessPoolExecutor with forkserver.
            True parallelism, ~2x faster on a multi-analyzer pipeline,
            pays a one-off pool startup cost.

    Pool lifecycle: created lazily on first analyze() call,
    held for the lifetime of the pipeline. Use as a long-lived
    instance (FastMCP server, batch script) to amortize spawn cost.
    """

    def __init__(
        self,
        registry: AnalyzerRegistry,
        loader: AudioLoader | None = None,
        use_processes: bool = False,
        max_workers: int | None = None,
    ) -> None:
        self.registry = registry
        self._loader = loader or AudioLoader()
        self._use_processes = use_processes
        self._max_workers = max_workers or max(1, (os.cpu_count() or 4))
        self._pool: ProcessPoolExecutor | None = None

        # Self-tuning per-analyzer cost estimates (seconds), populated
        # from real ``AnalyzerResult.elapsed_s`` values after each call.
        # Used purely for ProcessPool dispatch ordering — heavier
        # analyzers are submitted first so the FIFO worker queue picks
        # them up immediately. NEVER substituted into any feature: a
        # missing or failed analyzer still produces None / a failed
        # AnalyzerResult, never a synthetic value.
        # First call: empty dict, no sorting (registry order). Every
        # subsequent call uses the most recently observed elapsed times.
        self._observed_costs: dict[str, float] = {}

    def _get_pool(self) -> ProcessPoolExecutor:
        """Lazily build the ProcessPool on first use.

        Uses ``forkserver`` start method which is safe on macOS (where
        ``fork`` is unsupported with threads/Cocoa) and faster than
        ``spawn`` because the server process keeps a warm interpreter
        between worker forks. Also pre-warms librosa once in each
        worker via the worker function itself, so per-task warmup
        cost is paid only on the first task each worker handles.
        """
        if self._pool is None:
            ctx = multiprocessing.get_context("forkserver")
            self._pool = ProcessPoolExecutor(max_workers=self._max_workers, mp_context=ctx)
        return self._pool

    def shutdown(self) -> None:
        """Release the worker pool. Safe to call multiple times."""
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None

    def __del__(self) -> None:
        # Best-effort cleanup. Errors during interpreter shutdown are
        # silently ignored — workers get killed by the OS anyway.
        with contextlib.suppress(Exception):
            self.shutdown()

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

        Async hygiene: every CPU-bound or import-bound step is offloaded
        to a worker (thread or process) so the caller's event loop stays
        responsive throughout. The only main-thread work is trivial
        bookkeeping (list comprehensions over analyzer instances, dict
        merges of features) which completes in microseconds.
        """
        signal = await self._loader.load(file_path)

        # Explicit caller-supplied clip — wrap the numpy work in to_thread
        # so a long max_duration call doesn't block the event loop.
        if max_duration and signal.duration_seconds > max_duration:
            signal = await asyncio.to_thread(_clip_signal, signal, max_duration)

        # Resolve analyzer instances (trivial dict lookups, no offload needed)
        analyzer_names = analyzers or self.registry.list_available()
        instances = [a for n in analyzer_names if (a := self.registry.get(n)) and a.is_available()]

        # Pre-warm librosa to eliminate scipy/librosa lazy-loader races.
        # In process mode the workers warm up themselves on their first
        # task, so we skip the main-process warmup entirely. In thread
        # mode we still need it on the main process — but we offload the
        # ~5s import work to a worker thread so the event loop stays free.
        needs_warmup = not self._use_processes and any(
            "librosa" in a.required_packages for a in instances
        )
        if needs_warmup:
            await asyncio.to_thread(_warmup_librosa)

        # Partition by dependency: independent first, then dependent
        independent = [a for a in instances if not a.depends_on]
        dependent = [a for a in instances if a.depends_on]

        if self._use_processes:
            phase1_results, return_ctx = await self._run_phase_processes(signal, independent)
            all_results = list(phase1_results)
            if dependent:
                prior = self._merge_features(phase1_results)
                phase2_results, _ = await self._run_phase_processes(
                    signal, dependent, prior_results=prior
                )
                all_results.extend(phase2_results)
        else:
            # Build one context per unique clip duration. Most heavy
            # analyzers share clip_duration_s=60, so typically we build
            # at most 2 contexts (full + 60s). STFT shared across bucket
            # members in the thread path.
            #
            # _build_contexts does the STFT/magnitude/freqs work (~0.5-1s
            # on a long track). Offloaded to to_thread so it doesn't
            # block the event loop.
            contexts = await asyncio.to_thread(self._build_contexts, signal, instances)
            phase1_results = list(
                await asyncio.gather(
                    *(asyncio.to_thread(a.run, contexts[a.clip_duration_s]) for a in independent)
                )
            )
            all_results = list(phase1_results)
            if dependent:
                prior = self._merge_features(phase1_results)
                phase2_results = list(
                    await asyncio.gather(
                        *(
                            asyncio.to_thread(a.run, contexts[a.clip_duration_s], prior)
                            for a in dependent
                        )
                    )
                )
                all_results.extend(phase2_results)
            return_ctx = contexts.get(None) or next(iter(contexts.values()), None)

        # Update self-tuning cost map for the next call's dispatch order.
        # Only successful runs contribute (a failed analyzer's elapsed
        # may be a fast crash and is unrepresentative of its real cost).
        for r in all_results:
            if r.success and r.elapsed_s > 0:
                self._observed_costs[r.analyzer_name] = r.elapsed_s

        return PipelineResult(
            results=all_results,
            features=self._merge_features(all_results),
            context=return_ctx if return_context else None,
        )

    async def _run_phase_processes(
        self,
        signal: AudioSignal,
        instances: list[BaseAnalyzer],
        prior_results: dict[str, Any] | None = None,
    ) -> tuple[list[AnalyzerResult], AnalysisContext | None]:
        """Dispatch a phase of analyzers via the ProcessPool.

        Each analyzer runs in its own worker call. The worker rebuilds
        a local AnalysisContext from the supplied clip samples — we
        cannot pickle the context itself because it holds a
        threading.Lock for the lazy onset envelope cache.

        Each analyzer gets the clip variant matching its
        ``clip_duration_s`` so heavy librosa analyzers see the stitched
        60s clip while ``loudness``/``structure`` see the full track.
        """
        if not instances:
            return [], None

        pool = self._get_pool()
        loop = asyncio.get_running_loop()
        params = FrameParams()  # default frame params; matches AnalysisContext default
        cache_max_size = get_settings().audio.process_worker_cache_size

        # Pre-compute clip variants once per unique clip duration.
        # Stitched-window construction does numpy concat + hann fades
        # (~50-100ms on a 6 min track) — small but still blocks the
        # event loop, so offload to a worker thread.
        clips = await asyncio.to_thread(_build_clip_variants_for_instances, signal, instances)

        # Publish each unique clip variant into a SharedMemory block.
        # Workers attach zero-copy views via the block name instead of
        # receiving the multi-MB ndarray pickled on every task. This
        # alone removes ~1-2s of pickling overhead on a multi-analyzer
        # phase. The bytewise copy from the source ndarray to the shm
        # buffer is offloaded to a worker thread so it never touches
        # the event loop.
        shm_blocks: dict[
            float | None,
            tuple[shared_memory.SharedMemory, str, str, tuple[int, ...]],
        ] = {}
        try:
            shm_blocks = await asyncio.to_thread(_publish_clips_to_shared_memory, clips)

            # Sort by descending observed cost so heavy analyzers are
            # submitted first. ProcessPoolExecutor dispatches FIFO
            # across workers, so the earliest tasks land in workers
            # immediately — putting the heaviest analyzer at the head
            # ensures it starts running on its own core from t=0
            # instead of waiting in the queue while cheap analyzers
            # tie up workers.
            #
            # Costs come from the previous call's ``elapsed_s``. On
            # the first call ``_observed_costs`` is empty so all
            # analyzers have cost 0.0 — sorting is a no-op and
            # dispatch order is the registry order. From the second
            # call onward, dispatch is optimal for the actual measured
            # workload of THIS pipeline.
            sorted_instances = sorted(
                instances,
                key=lambda a: self._observed_costs.get(a.name, 0.0),
                reverse=True,
            )

            futures = []
            for analyzer in sorted_instances:
                _shm, shm_name, dtype_str, shape = shm_blocks[analyzer.clip_duration_s]
                cls = type(analyzer)
                futures.append(
                    loop.run_in_executor(
                        pool,
                        _process_analyzer_worker,
                        shm_name,
                        dtype_str,
                        shape,
                        signal.sample_rate,
                        signal.file_path,
                        params.frame_length,
                        params.hop_length,
                        cache_max_size,
                        cls.__module__,
                        cls.__name__,
                        prior_results,
                    )
                )

            results = list(await asyncio.gather(*futures))
        finally:
            # Release SharedMemory in the main process. ``unlink`` removes
            # the segment name from /dev/shm so it never appears as a
            # leak even when workers still hold attached views inside
            # their LRU AnalysisContext cache. The OS frees the backing
            # bytes once the last attachment is dropped (which happens
            # via LRU eviction or worker shutdown). The per-worker LRU
            # bounds memory growth at
            # ``max_workers * cache_max_size * avg_clip_size`` so we
            # don't need an explicit fan-out eviction task on every
            # call — keeping the dispatch path lean.
            seen_shm_ids: set[int] = set()
            for shm, _name, _dtype, _shape in shm_blocks.values():
                if id(shm) in seen_shm_ids:
                    continue
                seen_shm_ids.add(id(shm))
                with contextlib.suppress(Exception):
                    shm.close()
                with contextlib.suppress(Exception):
                    shm.unlink()

        # No shared context to return from worker processes — caller
        # gets None and the PipelineResult.context will be None too.
        return results, None

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


def _build_clip_variants_for_instances(
    signal: AudioSignal, instances: list[BaseAnalyzer]
) -> dict[float | None, np.ndarray]:
    """Pre-compute clip variant samples once per unique clip duration.

    Module-level helper so it can be offloaded to ``asyncio.to_thread``
    from inside ``_run_phase_processes`` without binding ``self``.
    """
    clips: dict[float | None, np.ndarray] = {}
    for clip_duration in {a.clip_duration_s for a in instances}:
        if clip_duration is None or signal.duration_seconds <= clip_duration:
            clips[clip_duration] = signal.samples
        else:
            clipped = _clip_signal(signal, clip_duration, centered=True)
            clips[clip_duration] = clipped.samples
    return clips


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
