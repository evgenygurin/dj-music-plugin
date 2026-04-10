"""Tests for tonal helper functions."""

from __future__ import annotations

import numpy as np

from app.audio.core.context import AnalysisContext
from app.audio.core.tonal import compute_mfcc, compute_pitch_class_chroma, tonal_centroid
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 2.0


def _sine(freq: float) -> AudioSignal:
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=DURATION)


def test_compute_pitch_class_chroma_peaks_at_expected_pitch_class() -> None:
    ctx = AnalysisContext(_sine(440.0))

    chroma = compute_pitch_class_chroma(ctx.magnitude, ctx.freqs)
    dominant_pitch_class = int(np.argmax(np.mean(chroma, axis=1)))

    assert chroma.shape[0] == 12
    assert dominant_pitch_class == 9  # A


def test_tonal_centroid_returns_6d_vector_in_expected_range() -> None:
    chroma = np.zeros(12, dtype=np.float64)
    chroma[9] = 1.0

    centroid = tonal_centroid(chroma)

    assert centroid.shape == (6,)
    assert all(-1.5 <= float(value) <= 1.5 for value in centroid)


def test_compute_mfcc_returns_requested_number_of_coefficients() -> None:
    ctx = AnalysisContext(_sine(220.0))

    mfcc = compute_mfcc(ctx.magnitude, ctx.freqs, ctx.sr, n_mfcc=13)

    assert mfcc.shape[0] == 13
    assert mfcc.shape[1] == ctx.magnitude.shape[1]
    assert np.isfinite(mfcc).all()
