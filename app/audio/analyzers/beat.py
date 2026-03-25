"""Beat detector — librosa-based rhythm analysis.

Computes: onset_rate, pulse_clarity, kick_prominence, hp_ratio.
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer


class BeatDetector(BaseAnalyzer):
    """Rhythm analysis: onset detection, pulse clarity, kick prominence."""

    name = "beat"
    capabilities = {"rhythm", "beat"}
    required_packages = ["librosa"]

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Analyze rhythmic features."""
        import librosa

        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")

        # Onset detection
        onset_env = librosa.onset.onset_strength(y=samples, sr=sr)
        onsets = librosa.onset.onset_detect(y=samples, sr=sr, units="time")
        onset_rate = (
            float(len(onsets) / signal.duration_seconds) if signal.duration_seconds > 0 else 0.0
        )

        # Pulse clarity (tempogram autocorrelation peak)
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        pulse_clarity = 0.0
        if tempogram.size > 0:
            # Mean autocorrelation at dominant tempo lag
            acf = np.mean(tempogram, axis=1)
            if len(acf) > 1:
                pulse_clarity = float(np.max(acf[1:]) / (acf[0] + 1e-10))
                pulse_clarity = max(0.0, min(1.0, pulse_clarity))

        # Harmonic-percussive separation for kick prominence and HP ratio
        harmonic, percussive = librosa.effects.hpss(samples)

        h_rms = float(np.sqrt(np.mean(harmonic**2)))
        p_rms = float(np.sqrt(np.mean(percussive**2)))
        hp_ratio = h_rms / (p_rms + 1e-10)

        # Kick prominence: energy in low frequencies of percussive component
        # Low-pass the percussive signal at ~200Hz
        s_perc = np.abs(librosa.stft(percussive))
        freqs = librosa.fft_frequencies(sr=sr)
        low_mask = freqs < 200
        total_perc_energy = float(np.sum(s_perc**2))
        low_perc_energy = float(np.sum(s_perc[low_mask, :] ** 2))
        kick_prominence = low_perc_energy / (total_perc_energy + 1e-10)

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "onset_rate": round(onset_rate, 4),
                "pulse_clarity": round(pulse_clarity, 4),
                "kick_prominence": round(kick_prominence, 4),
                "hp_ratio": round(hp_ratio, 4),
            },
        )
