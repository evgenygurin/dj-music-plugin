"""Key detector — librosa-based musical key analysis.

Computes: key_code (0-23), key_confidence, atonality, chroma_entropy, hnr_db.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.v2.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.v2.audio.core.context import AnalysisContext
from app.v2.audio.core.tonal import compute_pitch_class_chroma
from app.v2.shared.constants import CAMELOT_KEYS

_ROOT_TO_PITCH_CLASS = {
    "C": 0,
    "D♭": 1,
    "D": 2,
    "E♭": 3,
    "E": 4,
    "F": 5,
    "F♯": 6,
    "G": 7,
    "A♭": 8,
    "A": 9,
    "B♭": 10,
    "B": 11,
}
_PITCH_CLASS_MODE_TO_KEY_CODE: dict[tuple[int, int], int] = {}
for _code, (_camelot, _name) in CAMELOT_KEYS.items():
    _root, _mode_name = _name.split()[:2]
    _mode = 0 if _mode_name == "minor" else 1
    _PITCH_CLASS_MODE_TO_KEY_CODE[(_ROOT_TO_PITCH_CLASS[_root], _mode)] = _code


def _compute_hnr_autocorrelation(samples: np.ndarray, sr: int) -> float:
    """Compute Harmonic-to-Noise Ratio via autocorrelation (Boersma 1993).

    Standard method used in Praat and essentia:
    1. Compute autocorrelation of windowed signal
    2. Find peak in valid pitch range (50-500 Hz for music)
    3. HNR = 10 * log10(peak / (1 - peak))

    Returns HNR in dB. Typical range: -10 to +30 dB.
    Techno tracks: usually 0-15 dB.
    """
    # Use ~50ms frames for autocorrelation
    frame_len = int(0.05 * sr)
    if len(samples) < frame_len:
        return 0.0

    # Analyze multiple frames and average
    hop = frame_len // 2
    n_frames = min(50, max(1, (len(samples) - frame_len) // hop))
    hnr_values: list[float] = []

    # Pitch range for music: 50-500 Hz → lag range
    min_lag = max(1, sr // 500)  # 500 Hz
    max_lag = min(frame_len - 1, sr // 50)  # 50 Hz

    for i in range(n_frames):
        start = i * hop
        frame = samples[start : start + frame_len]

        # Apply Hann window
        window = np.hanning(len(frame))
        windowed = frame * window

        # Normalized autocorrelation
        acf = np.correlate(windowed, windowed, mode="full")
        acf = acf[len(acf) // 2 :]  # positive lags only
        if acf[0] == 0:
            continue
        acf = acf / acf[0]  # normalize

        # Find peak in pitch range
        if max_lag > min_lag and max_lag < len(acf):
            search_region = acf[min_lag:max_lag]
            if len(search_region) > 0:
                peak = float(np.max(search_region))
                # Clamp lower bound to a tiny positive value so log10 doesn't
                # see 0 (silence/noise frames produce peak ≈ 0 → -inf + warning).
                peak = max(1e-10, min(0.9999, peak))
                hnr = 10.0 * np.log10(peak / (1.0 - peak))
                hnr_values.append(float(hnr))

    if not hnr_values:
        return 0.0

    return round(float(np.mean(hnr_values)), 2)


@register_analyzer
class KeyDetector(BaseAnalyzer):
    """Musical key detection using chroma features."""

    name: ClassVar[str] = "key"
    capabilities: ClassVar[frozenset[str]] = frozenset({"key", "harmony"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    # chroma_cqt is O(N). Key is constant within a techno track — 60s clip
    # gives the same Krumhansl-Kessler correlation as the full track.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Detect musical key using CQT chroma."""
        import librosa  # noqa: F401

        samples = ctx.samples
        sr = ctx.sr

        chroma = compute_pitch_class_chroma(ctx.magnitude, ctx.freqs)
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
            key_code = _PITCH_CLASS_MODE_TO_KEY_CODE.get((pitch_class, 1), 15)
            if corr_major > best_corr:
                best_corr = corr_major
                best_key = key_code

            # Test minor
            corr_minor = float(np.corrcoef(rotated, minor_profile)[0, 1])
            key_code = _PITCH_CLASS_MODE_TO_KEY_CODE.get((pitch_class, 0), 14)
            if corr_minor > best_corr:
                best_corr = corr_minor
                best_key = key_code

        confidence = max(0.0, min(1.0, (best_corr + 1.0) / 2.0))

        # Chroma entropy (measure of atonality), normalized to 0-1
        # Max entropy for 12 bins (uniform distribution) = log2(12) ≈ 3.585
        chroma_norm = chroma_mean / (np.sum(chroma_mean) + 1e-10)
        raw_entropy = float(-np.sum(chroma_norm * np.log2(chroma_norm + 1e-10)))
        chroma_entropy = raw_entropy / float(np.log2(12))  # 0-1 normalized
        atonality = chroma_entropy > 0.92  # ~3.3/3.585 on original scale

        # HNR (harmonic-to-noise ratio) via autocorrelation (Boersma 1993)
        # Standard method: find peak in autocorrelation, compute ratio
        hnr_db = _compute_hnr_autocorrelation(samples, sr)

        return {
            "key_code": best_key,
            "key_confidence": round(confidence, 4),
            "atonality": atonality,
            "chroma_entropy": round(chroma_entropy, 4),
            "hnr_db": round(hnr_db, 2),
        }
