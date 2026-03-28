#!/usr/bin/env python3
"""End-to-end verification of the refactored audio pipeline.

Loads a real MP3, runs all 8 analyzers (sequential + parallel),
classifies mood, and prints a full feature report with timing breakdown.

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

    # ── 2. AnalysisContext (eager precompute) ──
    from app.audio.core.context import AnalysisContext

    with Timer() as t:
        ctx = AnalysisContext(signal)
    timing.record(
        "AnalysisContext",
        t.elapsed,
        f"STFT {ctx.stft.shape}, {len(ctx.frame_energies)} frames",
    )
    print(f"[2/7] AnalysisContext: STFT {ctx.stft.shape} ({t.elapsed:.2f}s)")

    # ── 3. Individual analyzers (sequential, for per-analyzer timing) ──
    from app.audio.analyzers import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()

    print(f"[3/7] Analyzers (sequential, {len(registry.list_all())} registered):")
    seq_features: dict = {}
    seq_total = 0.0
    for name in sorted(registry.list_all()):
        analyzer = registry.get(name)
        assert analyzer is not None
        with Timer() as t:
            result = analyzer.run(ctx)
        seq_total += t.elapsed
        n = len(result.features) if result.features else 0
        status = "OK" if result.success else f"FAIL: {result.error}"
        print(f"      {name:12s} -> {status} ({n} feat, {t.elapsed:.2f}s)")
        timing.record(f"  analyzer/{name}", t.elapsed, f"{n} features")
        if result.features:
            seq_features.update(result.features)
    timing.record("Sequential total", seq_total, f"{len(seq_features)} features")

    # ── 4. Pipeline (parallel via asyncio.to_thread) ──
    from app.audio.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline(registry=registry, loader=loader)
    with Timer() as t:
        pipe_result = await pipeline.analyze(track_path)
    speedup = seq_total / t.elapsed if t.elapsed > 0 else 0
    timing.record(
        "Pipeline (parallel)",
        t.elapsed,
        f"{pipe_result.success_count}/{len(pipe_result.results)} OK, {speedup:.1f}x speedup",
    )
    print(
        f"[4/7] Pipeline (parallel): {pipe_result.success_count}/{len(pipe_result.results)} OK "
        f"({t.elapsed:.2f}s, {speedup:.1f}x speedup vs sequential)"
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

    if pipe_result.success_count != 8:
        errors.append(f"Analyzers: {pipe_result.success_count}/8")
    print(f"  Analyzers:      {pipe_result.success_count}/8 OK")

    if len(f) != 47:
        errors.append(f"Features: {len(f)}/47")
    print(f"  Features:       {len(f)}/47")

    if not (60 <= f["bpm"] <= 200):
        errors.append(f"BPM {f['bpm']} outside range")
    print(f"  BPM range:      {'OK' if 60 <= f['bpm'] <= 200 else 'FAIL'}")

    if f["integrated_lufs"] >= 0:
        errors.append(f"LUFS {f['integrated_lufs']} should be negative")
    print(f"  LUFS negative:  {'OK' if f['integrated_lufs'] < 0 else 'FAIL'}")

    if seq_features.keys() != f.keys():
        diff = seq_features.keys() ^ f.keys()
        errors.append(f"Sequential vs parallel key mismatch: {diff}")
    print(f"  Seq/Par match:  {'OK' if seq_features.keys() == f.keys() else 'FAIL'}")

    if speedup < 1.0:
        errors.append(f"No parallel speedup: {speedup:.1f}x")
    print(f"  Parallel gain:  {speedup:.1f}x")

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
