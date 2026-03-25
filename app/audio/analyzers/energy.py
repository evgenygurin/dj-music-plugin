"""Energy analyzer — pure numpy implementation.

Computes: energy_mean, energy_max, energy_std, energy_slope,
and 7-band frequency breakdown using numpy FFT.
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer

# 7 frequency bands (Hz boundaries)
# Keys match DB column names: energy_sub, energy_low, energy_lowmid, etc.
ENERGY_BANDS: dict[str, tuple[float, float]] = {
    "sub": (20.0, 60.0),
    "low": (60.0, 250.0),
    "lowmid": (250.0, 500.0),
    "mid": (500.0, 2000.0),
    "highmid": (2000.0, 4000.0),
    "high": (4000.0, 8000.0),
}


class EnergyAnalyzer(BaseAnalyzer):
    """Energy computation using pure numpy FFT for band decomposition."""

    name = "energy"
    capabilities = {"energy"}
    required_packages: list[str] = []

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Compute energy metrics and 7-band breakdown."""
        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(
                analyzer_name=self.name,
                success=False,
                error="Empty audio signal",
            )

        # Frame-level energy (short-time energy)
        frame_length = 2048
        hop_length = 512
        n_frames = max(1, (len(samples) - frame_length) // hop_length + 1)

        frame_energies = np.zeros(n_frames)
        for i in range(n_frames):
            start = i * hop_length
            end = min(start + frame_length, len(samples))
            frame = samples[start:end]
            frame_energies[i] = float(np.mean(frame**2))

        # Normalize to [0, 1]
        max_energy = float(np.max(frame_energies)) if np.max(frame_energies) > 0 else 1.0
        normalized_energies = frame_energies / max_energy

        energy_mean = float(np.mean(normalized_energies))
        energy_max = float(np.max(normalized_energies))
        energy_std = float(np.std(normalized_energies))

        # Energy slope (linear regression over time)
        if n_frames > 1:
            x = np.arange(n_frames, dtype=np.float64)
            slope, _ = np.polyfit(x, normalized_energies, 1)
            energy_slope = float(slope)
        else:
            energy_slope = 0.0

        # 6-band energy breakdown via FFT (matches DB columns)
        band_energies = self._compute_band_energies(samples, sr)

        # Compute ratios (band / total band energy)
        band_total = sum(band_energies.values()) or 1.0
        band_ratios = {f"{name}_ratio": val / band_total for name, val in band_energies.items()}

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "energy_mean": energy_mean,
                "energy_max": energy_max,
                "energy_std": energy_std,
                "energy_slope": energy_slope,
                **{f"energy_{name}": val for name, val in band_energies.items()},
                **{f"energy_{name}": val for name, val in band_ratios.items()},
            },
        )

    def _compute_band_energies(self, samples: np.ndarray, sr: int) -> dict[str, float]:
        """Compute energy in each frequency band using FFT."""
        n = len(samples)
        if n == 0:
            return {name: 0.0 for name in ENERGY_BANDS}

        # Compute FFT
        fft_vals = np.fft.rfft(samples)
        fft_magnitude = np.abs(fft_vals) ** 2
        freqs = np.fft.rfftfreq(n, d=1.0 / sr)

        total_energy = float(np.sum(fft_magnitude))
        if total_energy == 0:
            return {name: 0.0 for name in ENERGY_BANDS}

        band_energies: dict[str, float] = {}
        for name, (low_hz, high_hz) in ENERGY_BANDS.items():
            mask = (freqs >= low_hz) & (freqs < high_hz)
            band_energy = float(np.sum(fft_magnitude[mask]))
            band_energies[name] = band_energy / total_energy

        return band_energies
