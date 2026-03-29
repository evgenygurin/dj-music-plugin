#!/usr/bin/env python3
"""Verify Phase 3 advanced analyzers on a real MP3 file.

Tests all 10 P3 analyzers individually, validates feature ranges,
and reports timing. Uses the same real-file discovery as verify_audio_pipeline.py.

Usage:
    uv run python scripts/verify_p3_features.py [path_to_mp3]
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# ── P3 analyzer names and expected features ──────────

P3_ANALYZERS = [
    "danceability",
    "dissonance",
    "dynamic_complexity",
    "spectral_complexity",
    "pitch_salience",
    "tonnetz",
    "tempogram",
    "beats_loudness",
    "bpm_histogram",
    "phrase",
]

# Expected feature keys per analyzer (subset for validation)
P3_EXPECTED_FEATURES: dict[str, list[str]] = {
    "danceability": ["danceability"],
    "dissonance": ["dissonance_mean"],
    "dynamic_complexity": ["dynamic_complexity"],
    "spectral_complexity": ["spectral_complexity_mean"],
    "pitch_salience": ["pitch_salience_mean"],
    "tonnetz": ["tonnetz_mean"],
    "tempogram": ["tempogram_ratios"],
    "beats_loudness": ["beats_loudness_band_ratios"],
    "bpm_histogram": ["bpm_histogram_first_peak_weight", "bpm_histogram_second_peak_bpm"],
    "phrase": ["phrase_boundaries"],
}

# Feature range checks: (key, min, max) — None means no bound
# Note: essentia Danceability raw range is 0-3, NOT 0-1
P3_RANGE_CHECKS: list[tuple[str, float | None, float | None]] = [
    ("danceability", 0.0, 3.0),
    ("dissonance_mean", 0.0, 1.0),
    ("dynamic_complexity", 0.0, None),
    ("spectral_complexity_mean", 0.0, None),
    ("pitch_salience_mean", 0.0, 1.0),
]


def find_real_mp3(library_root: str | None = None) -> str:
    """Find first non-iCloud-stub MP3 > 500KB."""
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
            if (stat.st_blocks * 512) >= (stat.st_size * 0.9):
                return path
    raise FileNotFoundError(f"No real MP3 found in {root}")


async def main(track_path: str) -> bool:
    """Run P3 analyzer verification. Returns True if all pass."""
    from app.audio.analyzers import AnalyzerRegistry
    from app.audio.core.context import AnalysisContext
    from app.audio.core.loader import AudioLoader

    track_name = Path(track_path).stem
    file_mb = os.path.getsize(track_path) / (1024 * 1024)

    print("=" * 64)
    print("PHASE 3 ADVANCED ANALYZERS VERIFICATION")
    print(f"Track: {track_name}")
    print(f"File:  {file_mb:.1f} MB")
    print("=" * 64)

    # Load audio
    loader = AudioLoader()
    t0 = time.perf_counter()
    signal = await loader.load(track_path)
    load_time = time.perf_counter() - t0
    print(f"\nAudio loaded: {signal.duration_seconds:.1f}s ({load_time:.2f}s)")

    # Create context
    t0 = time.perf_counter()
    ctx = AnalysisContext(signal)
    ctx_time = time.perf_counter() - t0
    print(f"Context:      STFT {ctx.stft.shape} ({ctx_time:.2f}s)")

    # Discover analyzers
    registry = AnalyzerRegistry()
    registry.discover()
    available = set(registry.list_all())

    print(f"\nRegistered:   {len(available)} analyzers")
    missing = [a for a in P3_ANALYZERS if a not in available]
    if missing:
        print(f"MISSING P3:   {missing}")

    # Run each P3 analyzer
    print(f"\n{'Analyzer':20s} {'Status':8s} {'Time':>8s} {'Features':>8s}  Details")
    print("-" * 80)

    errors: list[str] = []
    all_features: dict = {}
    total_time = 0.0

    for name in P3_ANALYZERS:
        if name not in available:
            print(f"{name:20s} {'SKIP':8s} {'--':>8s} {'--':>8s}  Not registered")
            errors.append(f"{name}: not registered")
            continue

        analyzer = registry.get(name)
        assert analyzer is not None

        t0 = time.perf_counter()
        try:
            result = analyzer.run(ctx)
            elapsed = time.perf_counter() - t0
            total_time += elapsed

            if not result.success:
                print(f"{name:20s} {'FAIL':8s} {elapsed:7.2f}s {'--':>8s}  {result.error}")
                errors.append(f"{name}: {result.error}")
                continue

            n_feat = len(result.features) if result.features else 0
            print(f"{name:20s} {'OK':8s} {elapsed:7.2f}s {n_feat:>8d}  ", end="")

            # Show key features
            if result.features:
                all_features.update(result.features)
                expected = P3_EXPECTED_FEATURES.get(name, [])
                found = [k for k in expected if k in result.features]
                vals = []
                for k in found:
                    v = result.features[k]
                    if isinstance(v, float):
                        vals.append(f"{k}={v:.4f}")
                    elif isinstance(v, (list, tuple)):
                        vals.append(f"{k}=[{len(v)} items]")
                    else:
                        vals.append(f"{k}={v}")
                print(", ".join(vals) if vals else "(no expected keys)")
            else:
                print("(no features)")

        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"{name:20s} {'ERROR':8s} {elapsed:7.2f}s {'--':>8s}  {type(e).__name__}: {e}")
            errors.append(f"{name}: {type(e).__name__}: {e}")

    # Range checks
    print(f"\n{'Range Checks':20s}")
    print("-" * 40)
    for key, lo, hi in P3_RANGE_CHECKS:
        val = all_features.get(key)
        if val is None:
            print(f"  {key:30s} SKIP (not extracted)")
            continue
        ok = True
        if lo is not None and val < lo:
            ok = False
        if hi is not None and val > hi:
            ok = False
        status = "OK" if ok else "FAIL"
        bounds = f"[{lo or '-inf'}, {hi or '+inf'}]"
        print(f"  {key:30s} {status:4s}  {val:.4f}  {bounds}")
        if not ok:
            errors.append(f"{key}={val:.4f} outside {bounds}")

    # Summary
    print(f"\n{'=' * 64}")
    print(f"P3 analyzers:   {len(P3_ANALYZERS) - len(missing)}/{len(P3_ANALYZERS)} available")
    print(f"Features total: {len(all_features)}")
    print(f"Analysis time:  {total_time:.2f}s (P3 only)")
    print(f"Errors:         {len(errors)}")

    if errors:
        print(f"\nFAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  - {e}")
        return False

    print("\nALL P3 CHECKS PASSED")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print(f"Not found: {path}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Searching for a real MP3...")
        path = find_real_mp3()
        print(f"Found: {Path(path).name}\n")

    ok = asyncio.run(main(path))
    sys.exit(0 if ok else 1)
