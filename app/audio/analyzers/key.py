"""Key detector — librosa-based musical key analysis.

Computes: key_code (0-23), key_confidence, atonality, chroma_entropy, hnr_db.
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer

# Key mapping: index → (pitch_class, mode)
# 0-11: minor keys (A♭m, E♭m, B♭m, Fm, Cm, Gm, Dm, Am, Em, Bm, F♯m, D♭m)
# 12-23: major keys (B, F♯, D♭, A♭, E♭, B♭, F, C, G, D, A, E)
KEY_NAMES = [
    "A♭ minor",
    "E♭ minor",
    "B♭ minor",
    "F minor",
    "C minor",
    "G minor",
    "D minor",
    "A minor",
    "E minor",
    "B minor",
    "F♯ minor",
    "D♭ minor",
    "B major",
    "F♯ major",
    "D♭ major",
    "A♭ major",
    "E♭ major",
    "B♭ major",
    "F major",
    "C major",
    "G major",
    "D major",
    "A major",
    "E major",
]


class KeyDetector(BaseAnalyzer):
    """Musical key detection using chroma features."""

    name = "key"
    capabilities = {"key", "harmony"}
    required_packages = ["librosa"]

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Detect musical key using CQT chroma."""
        import librosa

        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")

        # Compute chroma CQT
        chroma = librosa.feature.chroma_cqt(y=samples, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        # Krumhansl-Kessler key profiles
        major_profile = np.array(
            [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        )
        minor_profile = np.array(
            [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
        )

        best_corr = -1.0
        best_key = 0

        for pitch_class in range(12):
            # Rotate chroma to test each root
            rotated = np.roll(chroma_mean, -pitch_class)

            # Test major
            corr_major = float(np.corrcoef(rotated, major_profile)[0, 1])
            key_code = pitch_class + 12  # major keys: 12-23
            if corr_major > best_corr:
                best_corr = corr_major
                best_key = key_code

            # Test minor
            corr_minor = float(np.corrcoef(rotated, minor_profile)[0, 1])
            key_code = pitch_class  # minor keys: 0-11
            if corr_minor > best_corr:
                best_corr = corr_minor
                best_key = key_code

        confidence = max(0.0, min(1.0, (best_corr + 1.0) / 2.0))

        # Chroma entropy (measure of atonality)
        chroma_norm = chroma_mean / (np.sum(chroma_mean) + 1e-10)
        chroma_entropy = float(-np.sum(chroma_norm * np.log2(chroma_norm + 1e-10)))
        atonality = chroma_entropy > 3.3  # high entropy = atonal

        # HNR (harmonic-to-noise ratio) approximation
        # Using spectral flatness as proxy
        s_mag = np.abs(librosa.stft(samples))
        flatness = librosa.feature.spectral_flatness(S=s_mag)
        avg_flatness = float(np.mean(flatness))
        hnr_db = float(-10.0 * np.log10(avg_flatness + 1e-10))

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "key_code": best_key,
                "key_confidence": round(confidence, 4),
                "atonality": atonality,
                "chroma_entropy": round(chroma_entropy, 4),
                "hnr_db": round(hnr_db, 2),
            },
        )
