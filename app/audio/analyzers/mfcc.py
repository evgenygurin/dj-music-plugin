"""MFCC extractor — librosa-based Mel-Frequency Cepstral Coefficients.

Computes: mfcc_mean (13-coefficient vector as list[float]).
"""

from __future__ import annotations

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer
from app.config import settings


class MFCCExtractor(BaseAnalyzer):
    """Extract 13 MFCC coefficients using librosa."""

    name = "mfcc"
    capabilities = {"mfcc", "timbre"}
    required_packages = ["librosa"]

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Extract MFCC features."""
        import librosa

        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")

        n_mfcc = settings.audio_mfcc_n_coeffs  # default 13

        mfcc = librosa.feature.mfcc(y=samples, sr=sr, n_mfcc=n_mfcc)
        mfcc_mean = np.mean(mfcc, axis=1).tolist()

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "mfcc_mean": [round(v, 4) for v in mfcc_mean],
            },
        )
