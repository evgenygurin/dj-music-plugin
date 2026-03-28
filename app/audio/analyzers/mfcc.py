"""MFCC extractor — librosa-based Mel-Frequency Cepstral Coefficients.

Computes: mfcc_mean (13-coefficient vector as list[float]).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext
from app.config import settings


@register_analyzer
class MFCCExtractor(BaseAnalyzer):
    """Extract 13 MFCC coefficients using librosa."""

    name: ClassVar[str] = "mfcc"
    capabilities: ClassVar[frozenset[str]] = frozenset({"mfcc", "timbre"})
    required_packages: ClassVar[list[str]] = ["librosa"]

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Extract MFCC features."""
        import librosa

        samples = ctx.samples
        sr = ctx.sr

        n_mfcc = settings.audio_mfcc_n_coeffs  # default 13

        mfcc = librosa.feature.mfcc(y=samples, sr=sr, n_mfcc=n_mfcc)
        mfcc_mean = np.mean(mfcc, axis=1).tolist()

        return {
            "mfcc_mean": [round(v, 4) for v in mfcc_mean],
        }
