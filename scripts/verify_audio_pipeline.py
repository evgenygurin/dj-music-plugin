#!/usr/bin/env python3
"""End-to-end verification of the audio pipeline.

Loads a real MP3, runs the production pipeline (all registered analyzers
with per-analyzer clip duration + parallel dispatch), classifies mood,
and prints a feature report with a runtime budget check.

Usage:
    uv run python scripts/verify_audio_pipeline.py [path_to_mp3]

If no path given, picks the first real (non-iCloud-stub) MP3 from the library.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── Timing helpers ──────────────────────────────────


@dataclass
class TimingEntry:
    """Single timed operation."""

    label: str
    elapsed: float
    detail: str = ""


@dataclass
class TimingReport:
    """Accumulates timing entries and prints a summary table."""

    entries: list[TimingEntry] = field(default_factory=list)
    _start: float = field(default_factory=time.perf_counter)

    def record(self, label: str, elapsed: float, detail: str = "") -> None:
        self.entries.append(TimingEntry(label, elapsed, detail))

    @property
    def total(self) -> float:
        return time.perf_counter() - self._start

    def print_summary(self) -> None:
        print("\n" + "=" * 64)
        print("TIMING SUMMARY")
        print("=" * 64)
        max_label = max(len(e.label) for e in self.entries)
        for e in self.entries:
            bar = "█" * int(e.elapsed * 10)  # 1 block = 100ms
            detail = f"  ({e.detail})" if e.detail else ""
            print(f"  {e.label:<{max_label}}  {e.elapsed:6.2f}s  {bar}{detail}")
        print(f"  {'TOTAL':<{max_label}}  {self.total:6.2f}s")
        print("=" * 64)


class Timer:
    """Context manager for timing a block."""

    def __init__(self) -> None:
        self.elapsed: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed = time.perf_counter() - self._start


# ── Track discovery ─────────────────────────────────


def find_real_mp3(library_root: str | None = None) -> str:
    """Find first non-iCloud-stub MP3 file > 500KB."""
    root = library_root or os.path.expanduser(
        "~/Library/Mobile Documents/com~apple~CloudDocs/dj-techno-set-builder/library"
    )
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.lower().endswith(".mp3"):
                continue
            path = os.path.join(dirpath, fname)
            stat = os.stat(path)
            if stat.st_size < 500_000:
                continue
            is_real = (stat.st_blocks * 512) >= (stat.st_size * 0.9)
            if is_real:
                return path
    raise FileNotFoundError(f"No real MP3 files found in {root}")


# ── Main pipeline test ──────────────────────────────


async def run_verification(track_path: str) -> bool:
    """Run full E2E verification. Returns True if all checks pass."""

    timing = TimingReport()
    track_name = Path(track_path).stem
    file_size_mb = os.path.getsize(track_path) / (1024 * 1024)

    print("=" * 64)
    print("AUDIO PIPELINE E2E VERIFICATION")
    print(f"Track: {track_name}")
    print(f"File:  {file_size_mb:.1f} MB")
    print("=" * 64)

    # ── 1. AudioLoader ──
    from app.audio.core.loader import AudioLoader

    loader = AudioLoader()
    with Timer() as t:
        signal = await loader.load(track_path)
    timing.record(
        "AudioLoader",
        t.elapsed,
        f"{len(signal.samples)} samples, {signal.sample_rate} Hz, {signal.duration_seconds:.1f}s",
    )
    print(f"\n[1/7] AudioLoader: {signal.duration_seconds:.1f}s audio loaded ({t.elapsed:.2f}s)")

    # ── 2. AnalysisContext (eager precompute on full track for inspection) ──
    from app.audio.core.context import AnalysisContext

    with Timer() as t:
        ctx = AnalysisContext(signal)
    timing.record(
        "AnalysisContext",
        t.elapsed,
        f"STFT {ctx.stft.shape}, {len(ctx.frame_energies)} frames",
    )
    print(f"[2/7] AnalysisContext: STFT {ctx.stft.shape} ({t.elapsed:.2f}s)")

    # ── 3. Pipeline (production path: parallel + per-analyzer clip) ──
    # The pipeline is the only thing production code calls. Run it once
    # and use its per-analyzer timings for the breakdown — running every
    # analyzer twice (sequential + parallel) doubled the verify time and
    # measured cold-vs-warm CPU rather than real concurrency benefit.
    from app.audio.analyzers import AnalyzerRegistry
    from app.audio.pipeline import AnalysisPipeline

    registry = AnalyzerRegistry()
    registry.discover()
    all_analyzers = sorted(registry.list_all())
    print(f"[3/7] Analyzers registered: {len(all_analyzers)}")
    for name in all_analyzers:
        a = registry.get(name)
        clip = f"clip={a.clip_duration_s:.0f}s" if a and a.clip_duration_s else "full"
        deps = f" deps={sorted(a.depends_on)}" if a and a.depends_on else ""
        print(f"      {name:20s}  {clip}{deps}")

    pipeline = AnalysisPipeline(registry=registry, loader=loader)
    print("[4/7] Pipeline run (production path):")
    pipe_timer = Timer()
    with pipe_timer:
        pipe_result = await pipeline.analyze(track_path)
    print(
        f"      {pipe_result.success_count}/{len(pipe_result.results)} OK in "
        f"{pipe_timer.elapsed:.2f}s"
    )
    for r in sorted(pipe_result.results, key=lambda r: -r.elapsed_s):
        n = len(r.features) if r.features else 0
        status = "OK" if r.success else f"FAIL: {r.error}"
        print(f"      {r.analyzer_name:20s} -> {status} ({n} feat, {r.elapsed_s:.2f}s)")
        timing.record(f"  analyzer/{r.analyzer_name}", r.elapsed_s, f"{n} features")
    timing.record(
        "Pipeline (parallel)",
        pipe_timer.elapsed,
        f"{pipe_result.success_count}/{len(pipe_result.results)} OK",
    )

    f = pipe_result.features

    # ── 5. MoodClassifier ──
    from app.audio.classification import ALL_PROFILES, MoodClassifier

    classifier = MoodClassifier(profiles=ALL_PROFILES)
    with Timer() as t:
        mood = classifier.classify(f)
    timing.record("MoodClassifier", t.elapsed, f"{mood.mood} ({mood.confidence:.3f})")
    print(f"[5/7] MoodClassifier: {mood.mood} ({t.elapsed:.4f}s)")

    # ── 6. Feature report ──
    print("\n[6/7] Feature report:")

    print("  BPM & Rhythm:")
    print(f"    bpm:             {f['bpm']:.1f}")
    print(f"    bpm_confidence:  {f['bpm_confidence']:.3f}")
    print(f"    bpm_stability:   {f['bpm_stability']:.3f}")
    print(f"    onset_rate:      {f['onset_rate']:.2f}")
    print(f"    kick_prominence: {f['kick_prominence']:.3f}")
    print(f"    pulse_clarity:   {f['pulse_clarity']:.3f}")
    print(f"    hp_ratio:        {f['hp_ratio']:.3f}")

    print("  Loudness:")
    print(f"    integrated_lufs: {f['integrated_lufs']:.2f}")
    print(f"    rms_dbfs:        {f['rms_dbfs']:.2f}")
    print(f"    true_peak_db:    {f['true_peak_db']:.2f}")
    print(f"    crest_factor_db: {f['crest_factor_db']:.2f}")
    print(f"    loudness_range:  {f['loudness_range_lu']:.2f}")

    print("  Spectral:")
    print(f"    centroid_hz:     {f['spectral_centroid_hz']:.1f}")
    print(f"    flatness:        {f['spectral_flatness']:.4f}")
    print(f"    slope:           {f['spectral_slope']:.4f}")
    print(f"    rolloff_85:      {f['spectral_rolloff_85']:.1f}")
    print(f"    flux_mean:       {f['spectral_flux_mean']:.4f}")

    print("  Harmony:")
    print(f"    key_code:        {f['key_code']}")
    print(f"    key_confidence:  {f['key_confidence']:.3f}")
    print(f"    chroma_entropy:  {f['chroma_entropy']:.4f}")
    print(f"    hnr_db:          {f['hnr_db']:.2f}")

    print("  Energy:")
    print(f"    energy_mean:     {f['energy_mean']:.4f}")
    print(f"    energy_max:      {f['energy_max']:.4f}")
    print(f"    sub_ratio:       {f['energy_sub_ratio']:.3f}")
    print(f"    low_ratio:       {f['energy_low_ratio']:.3f}")
    print(f"    mid_ratio:       {f['energy_mid_ratio']:.3f}")
    print(f"    high_ratio:      {f['energy_high_ratio']:.3f}")

    print(f"  MFCC: {len(f['mfcc_mean'])} coefficients")
    print(f"    first 5: {[round(x, 2) for x in f['mfcc_mean'][:5]]}")

    print(f"  Structure: {f['section_count']} sections")

    # ── Phase 3 advanced features ──
    p3_keys = [
        "danceability",
        "dissonance_mean",
        "dynamic_complexity",
        "spectral_complexity_mean",
        "pitch_salience_mean",
        "bpm_histogram_first_peak_weight",
        "bpm_histogram_second_peak_bpm",
    ]
    p3_present = {k: f.get(k) for k in p3_keys if f.get(k) is not None}
    if p3_present:
        print("\n  Phase 3 Advanced:")
        for k, v in p3_present.items():
            if isinstance(v, float):
                print(f"    {k:32s} {v:.4f}")
            else:
                print(f"    {k:32s} {v}")

    p3_vector_keys = ["tonnetz_vector", "tempogram_ratio_vector", "beat_loudness_band_ratio"]
    for vk in p3_vector_keys:
        val = f.get(vk)
        if val is not None and isinstance(val, (list, tuple)):
            print(f"    {vk:32s} [{', '.join(f'{x:.3f}' for x in val[:6])}]")

    print(f"\n  Mood: {mood.mood} (confidence: {mood.confidence:.3f})")
    print("  Top 5:")
    for name, score in mood.top_matches[:5]:
        print(f"    {name:20s} {score:.3f}")

    # ── 7. Sanity checks ──
    print("\n[7/7] Sanity checks:")
    errors: list[str] = []

    none_keys = [k for k, v in f.items() if v is None]
    if none_keys:
        errors.append(f"None values: {none_keys}")
    print(f"  None values:    {len(none_keys)}/{len(f)}")

    total_analyzers = len(registry.list_all())
    if pipe_result.success_count < 8:
        errors.append(f"Core analyzers: {pipe_result.success_count}/8")
    print(f"  Core analyzers: {pipe_result.success_count}/8 OK")
    print(f"  All analyzers:  {pipe_result.success_count}/{total_analyzers} OK")

    min_features = 47  # core features
    if len(f) < min_features:
        errors.append(f"Features: {len(f)}/{min_features}")
    print(f"  Features:       {len(f)} (min {min_features})")

    if not (60 <= f["bpm"] <= 200):
        errors.append(f"BPM {f['bpm']} outside range")
    print(f"  BPM range:      {'OK' if 60 <= f['bpm'] <= 200 else 'FAIL'}")

    if f["integrated_lufs"] >= 0:
        errors.append(f"LUFS {f['integrated_lufs']} should be negative")
    print(f"  LUFS negative:  {'OK' if f['integrated_lufs'] < 0 else 'FAIL'}")

    # Pipeline must complete in reasonable time on typical 6-min techno track.
    # 25s budget = 60s clip x ~6 heavy librosa analyzers in worst case (with
    # GIL contention). Spot-check, not a strict bound.
    if pipe_timer.elapsed > 25.0:
        errors.append(f"Pipeline too slow: {pipe_timer.elapsed:.1f}s (budget 25s)")
    print(
        f"  Runtime budget: {'OK' if pipe_timer.elapsed <= 25.0 else 'FAIL'} "
        f"({pipe_timer.elapsed:.1f}s ≤ 25s)"
    )

    # ── Timing summary ──
    timing.print_summary()

    # ── Final verdict ──
    if errors:
        print(f"\nFAILED: {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return False

    print("\nALL CHECKS PASSED")
    return True


def main() -> None:
    if len(sys.argv) > 1:
        track_path = sys.argv[1]
        if not os.path.isfile(track_path):
            print(f"File not found: {track_path}", file=sys.stderr)
            sys.exit(1)
    else:
        print("No track path given, searching library for a real MP3...")
        track_path = find_real_mp3()
        print(f"Found: {Path(track_path).name}\n")

    ok = asyncio.run(run_verification(track_path))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
