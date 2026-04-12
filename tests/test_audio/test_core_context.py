"""Tests for AnalysisContext — eager shared computation."""

from __future__ import annotations

import numpy as np
import pytest

from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.types import AudioSignal, FrameParams

SAMPLE_RATE = 22050


def _make_signal(duration: float = 1.0, freq: float = 440.0) -> AudioSignal:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)


class TestAnalysisContext:
    def test_samples_accessible(self) -> None:
        signal = _make_signal()
        ctx = AnalysisContext(signal)
        assert len(ctx.samples) == len(signal.samples)

    def test_sr_matches_signal(self) -> None:
        signal = _make_signal()
        ctx = AnalysisContext(signal)
        assert ctx.sr == SAMPLE_RATE

    def test_stft_shape(self) -> None:
        signal = _make_signal()
        ctx = AnalysisContext(signal)
        n_fft_bins = 2048 // 2 + 1
        assert ctx.stft.shape[0] == n_fft_bins

    def test_magnitude_nonnegative(self) -> None:
        ctx = AnalysisContext(_make_signal())
        assert float(np.min(ctx.magnitude)) >= 0.0

    def test_magnitude_matches_stft(self) -> None:
        ctx = AnalysisContext(_make_signal())
        expected = np.abs(ctx.stft)
        np.testing.assert_array_almost_equal(ctx.magnitude, expected)

    def test_freqs_length_matches_stft(self) -> None:
        ctx = AnalysisContext(_make_signal())
        assert len(ctx.freqs) == ctx.stft.shape[0]

    def test_frame_energies_normalized(self) -> None:
        ctx = AnalysisContext(_make_signal())
        assert float(np.max(ctx.frame_energies)) <= 1.0 + 1e-6
        assert float(np.min(ctx.frame_energies)) >= 0.0

    def test_custom_frame_params(self) -> None:
        signal = _make_signal()
        params = FrameParams(frame_length=4096, hop_length=1024)
        ctx = AnalysisContext(signal, params)
        assert ctx.stft.shape[0] == 4096 // 2 + 1

    def test_empty_signal(self) -> None:
        signal = AudioSignal(
            samples=np.array([], dtype=np.float32),
            sample_rate=SAMPLE_RATE,
            duration_seconds=0.0,
        )
        ctx = AnalysisContext(signal)
        assert len(ctx.frame_energies) >= 1

    def test_thread_safety_read_only(self) -> None:
        """Context should be usable from multiple threads (read-only)."""
        import concurrent.futures

        ctx = AnalysisContext(_make_signal())

        def read_ctx() -> float:
            return float(np.mean(ctx.magnitude))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(read_ctx) for _ in range(8)]
            results = [f.result() for f in futures]

        assert all(r == pytest.approx(results[0], abs=1e-10) for r in results)
