from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class CrossSimilarityResult:
    matrix_shape: str | None = None
    best_match_offset_ms: float | None = None
    best_match_score: float | None = None
    alignment_path: list[tuple[int, int]] | None = None
    segment_matches: list[dict[str, object]] | None = field(default_factory=list)


def compute_cross_similarity(
    track_a_path: Path,
    track_b_path: Path,
    stem_name: str = "original",
) -> CrossSimilarityResult:
    try:
        import essentia.standard as es
    except ImportError:
        return CrossSimilarityResult()

    audio_a = es.MonoLoader(filename=str(track_a_path))()
    audio_b = es.MonoLoader(filename=str(track_b_path))()

    w = es.Windowing(type="hann")
    spectrum = es.Spectrum()
    mfcc = es.MFCC()

    def extract_mfcc(audio: np.ndarray) -> np.ndarray:
        frames = []
        hop_generator = es.FrameGenerator(audio, frameSize=4096, hopSize=1024)
        for frame in hop_generator:
            spec = spectrum(w(frame))
            _, coeffs = mfcc(spec)
            frames.append(coeffs)
        return np.array(frames, dtype=np.float32) if frames else np.zeros((1, 13), dtype=np.float32)

    mfcc_a = extract_mfcc(audio_a)
    mfcc_b = extract_mfcc(audio_b)

    csm_algo = es.CrossSimilarityMatrix(
        frameStackSize=9, frameStackStride=1, binarize=False
    )
    csm = csm_algo(mfcc_a, mfcc_b)

    best_idx = int(csm.flatten().argmax())
    best_i, best_j = best_idx // csm.shape[1], best_idx % csm.shape[1]
    best_score = float(csm[best_i, best_j])
    hop_s = 1024 / 44100
    offset_ms = float((best_j - best_i) * hop_s * 1000)

    return CrossSimilarityResult(
        matrix_shape=f"{csm.shape[0]}x{csm.shape[1]}",
        best_match_offset_ms=offset_ms,
        best_match_score=best_score,
    )
