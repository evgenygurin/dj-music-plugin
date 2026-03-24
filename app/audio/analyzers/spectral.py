"""Spectral analyzer — pure numpy implementation.

Computes: spectral_centroid_hz, spectral_rolloff_85, spectral_rolloff_95,
spectral_flatness, spectral_flux_mean, spectral_flux_std.
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer


class SpectralAnalyzer(BaseAnalyzer):
    """Spectral analysis using pure numpy FFT."""

    name = "spectral"
    capabilities = {"spectral"}
    required_packages: list[str] = []

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Compute spectral features from audio signal."""
        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(
                analyzer_name=self.name,
                success=False,
                error="Empty audio signal",
            )

        frame_length = 2048
        hop_length = 512
        n_frames = max(1, (len(samples) - frame_length) // hop_length + 1)

        centroids: list[float] = []
        rolloff_85_list: list[float] = []
        rolloff_95_list: list[float] = []
        flatness_list: list[float] = []
        prev_magnitude: np.ndarray | None = None
        flux_list: list[float] = []

        for i in range(n_frames):
            start = i * hop_length
            end = min(start + frame_length, len(samples))
            frame = samples[start:end]

            # Zero-pad if needed
            if len(frame) < frame_length:
                frame = np.pad(frame, (0, frame_length - len(frame)))

            # Apply Hann window
            window = np.hanning(len(frame))
            windowed = frame * window

            # FFT
            fft_vals = np.fft.rfft(windowed)
            magnitude = np.abs(fft_vals)
            freqs = np.fft.rfftfreq(frame_length, d=1.0 / sr)

            # Spectral centroid
            total_mag = np.sum(magnitude)
            centroid = float(np.sum(freqs * magnitude) / total_mag) if total_mag > 0 else 0.0
            centroids.append(centroid)

            # Spectral rolloff
            cumsum = np.cumsum(magnitude)
            if total_mag > 0:
                rolloff_85 = float(freqs[np.searchsorted(cumsum, 0.85 * total_mag)])
                rolloff_95 = float(freqs[np.searchsorted(cumsum, 0.95 * total_mag)])
            else:
                rolloff_85 = 0.0
                rolloff_95 = 0.0
            rolloff_85_list.append(rolloff_85)
            rolloff_95_list.append(rolloff_95)

            # Spectral flatness (geometric mean / arithmetic mean)
            mag_positive = magnitude[magnitude > 0]
            if len(mag_positive) > 0 and total_mag > 0:
                log_mean = float(np.mean(np.log(mag_positive + 1e-10)))
                geometric_mean = np.exp(log_mean)
                arithmetic_mean = float(np.mean(magnitude))
                flatness = float(geometric_mean / (arithmetic_mean + 1e-10))
            else:
                flatness = 0.0
            flatness_list.append(flatness)

            # Spectral flux
            if prev_magnitude is not None:
                diff = magnitude - prev_magnitude
                flux = float(np.sum(diff**2))
                flux_list.append(flux)
            prev_magnitude = magnitude.copy()

        spectral_centroid_hz = float(np.mean(centroids)) if centroids else 0.0
        spectral_rolloff_85 = float(np.mean(rolloff_85_list)) if rolloff_85_list else 0.0
        spectral_rolloff_95 = float(np.mean(rolloff_95_list)) if rolloff_95_list else 0.0
        spectral_flatness = float(np.mean(flatness_list)) if flatness_list else 0.0

        if flux_list:
            spectral_flux_mean = float(np.mean(flux_list))
            spectral_flux_std = float(np.std(flux_list))
        else:
            spectral_flux_mean = 0.0
            spectral_flux_std = 0.0

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "spectral_centroid_hz": spectral_centroid_hz,
                "spectral_rolloff_85": spectral_rolloff_85,
                "spectral_rolloff_95": spectral_rolloff_95,
                "spectral_flatness": spectral_flatness,
                "spectral_flux_mean": spectral_flux_mean,
                "spectral_flux_std": spectral_flux_std,
            },
        )
