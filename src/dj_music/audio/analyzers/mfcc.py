"""MFCC extractor — librosa-based Mel-Frequency Cepstral Coefficients.

Computes: mfcc_mean (13-coefficient vector as list[float]).
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from dj_music.audio.analyzers.base import BaseAnalyzer, register_analyzer
from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.tonal import compute_mfcc
from dj_music.core.config import settings


@register_analyzer
class MFCCExtractor(BaseAnalyzer):
    """Extract 13 MFCC coefficients using librosa."""

    name: ClassVar[str] = "mfcc"
    capabilities: ClassVar[frozenset[str]] = frozenset({"mfcc", "timbre"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    # MFCC mean-across-time is the timbral fingerprint — stable across the
    # track. 60s clip is industry standard (used by audio-fingerprinting libs).
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Extract MFCC features."""
        import librosa  # noqa: F401

        n_mfcc = settings.audio_mfcc_n_coeffs  # default 13

        mfcc = compute_mfcc(
            ctx.magnitude,
            ctx.freqs,
            ctx.sr,
            n_mfcc=n_mfcc,
        )
        mfcc_mean = np.mean(mfcc, axis=1).tolist()

        return {
            "mfcc_mean": [round(v, 4) for v in mfcc_mean],
        }
