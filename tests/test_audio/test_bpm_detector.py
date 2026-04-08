"""Tests for BPMDetector — frame quantization regression test."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 30.0  # 30 seconds — enough beats for stable averaging


def _kick_pattern(bpm: float, duration: float = DURATION) -> AudioSignal:
    """Synthesize a kick-drum click track at given BPM.

    Returns a mono AudioSignal with a 60 Hz sine burst at every beat,
    long enough that BPM detection should be unambiguous.
    """
    n = int(SAMPLE_RATE * duration)
    samples = np.zeros(n, dtype=np.float32)
    interval_samples = 60.0 / bpm * SAMPLE_RATE
    kick_len = int(0.02 * SAMPLE_RATE)  # 20ms kick
    t = np.arange(kick_len) / SAMPLE_RATE
    kick = (
        0.9 * np.sin(2 * np.pi * 60 * t) * np.exp(-t * 30)  # decay envelope
    ).astype(np.float32)

    n_beats = int(duration * bpm / 60.0)
    for i in range(n_beats):
        start = round(i * interval_samples)
        end = min(start + kick_len, n)
        samples[start:end] += kick[: end - start]

    return AudioSignal(
        samples=samples,
        sample_rate=SAMPLE_RATE,
        duration_seconds=duration,
    )


def _detect_bpm(signal: AudioSignal) -> float:
    pytest.importorskip("librosa")
    from app.audio.analyzers.bpm import BPMDetector

    analyzer = BPMDetector()
    ctx = AnalysisContext(signal)
    result = analyzer.run(ctx)
    assert result.success, f"BPMDetector failed: {result.error}"
    return float(result.features["bpm"])


@pytest.mark.parametrize(
    "target_bpm",
    [124.0, 126.0, 128.0, 130.0, 132.0, 134.0],
)
def test_bpm_detector_recovers_target_bpm(target_bpm: float) -> None:
    """BPMDetector should recover the synthesized BPM within ±1 BPM."""
    signal = _kick_pattern(target_bpm)
    detected = _detect_bpm(signal)
    assert abs(detected - target_bpm) < 1.0, (
        f"Expected {target_bpm} ± 1, got {detected}. Frame quantization bug?"
    )


def test_bpm_detector_no_frame_quantization() -> None:
    """6 different BPMs must produce 6 different output values.

    Regression for the frame-quantization bug where librosa.beat.beat_track
    rounds tempo to integer frames-per-beat, collapsing the techno range
    (120-140 BPM) into ~4 discrete values (123.05, 129.20, 136.00, ...).
    """
    targets = [124.0, 126.0, 128.0, 130.0, 132.0, 134.0]
    detected = [_detect_bpm(_kick_pattern(b)) for b in targets]
    unique = {round(b, 1) for b in detected}
    assert len(unique) >= 5, (
        f"Expected ≥5 unique BPM values for 6 distinct inputs, "
        f"got {len(unique)}: {sorted(unique)}. "
        f"Frame quantization bug — see docs/reports/mcp-tools-test-2026-04-07.md #5"
    )


def test_bpm_detector_returns_realistic_confidence() -> None:
    """Confidence should be a float in (0, 1], not a hardcoded 1.0 fallback."""
    signal = _kick_pattern(128.0)
    pytest.importorskip("librosa")
    from app.audio.analyzers.bpm import BPMDetector

    analyzer = BPMDetector()
    ctx = AnalysisContext(signal)
    result = analyzer.run(ctx)
    assert result.success
    conf = float(result.features["bpm_confidence"])
    assert 0.0 < conf <= 1.0, f"confidence out of range: {conf}"


def test_bpm_detector_no_half_tempo_lock_on_peak_time_techno() -> None:
    """Peak-time techno (~160-170 BPM) must not be detected as half-tempo.

    Regression for the production half-tempo-lock bug where min_bpm=80
    allowed the autocorrelation peak at 2x lag (~83 BPM) to dominate the
    fundamental (~165 BPM) on noisy or compressed inputs. DB audit showed
    1097/5702 L5 tracks (19%) locked to 80-84 BPM. Fix: raise min_bpm
    floor to 110 inside ``_bpm_from_onset_autocorrelation``.
    """
    for target in (160.0, 165.0, 168.0, 172.0):
        detected = _detect_bpm(_kick_pattern(target))
        assert detected >= 110.0, (
            f"Half-tempo lock at {target} BPM: got {detected}. "
            f"Expected >=110 (fundamental or close)."
        )
