from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from app.audio.deep.cross_similarity import compute_cross_similarity


def test_compute_cross_similarity_returns_result(tmp_path: Path) -> None:
    sr = 44100
    rng = np.random.default_rng(42)
    sig_a = rng.random(sr * 3).astype(np.float32) * 0.3
    sig_b = rng.random(sr * 3).astype(np.float32) * 0.3

    pa = tmp_path / "a.wav"
    pb = tmp_path / "b.wav"
    sf.write(str(pa), sig_a, sr)
    sf.write(str(pb), sig_b, sr)

    result = compute_cross_similarity(pa, pb, "original")

    assert result.best_match_offset_ms is not None or result.matrix_shape is not None
