from __future__ import annotations

from pathlib import Path

import numpy as np

from app.audio.deep.io import TARGET_SAMPLE_RATE, write_flac_atomic

PERCUSSION_SPLIT_HZ = 2_000


def derive_percussion(drums_path: Path, percussion_path: Path, sample_rate: int = TARGET_SAMPLE_RATE) -> None:
    """Derive a high-frequency percussion stem from the model's drums stem.

    This is deliberately post-processing: HTDemucs predicts `drums`, not a
    separate `percussion` source. The low-pass result replaces `drums` and the
    complementary high-pass result becomes `percussion`.
    """
    import soundfile as sf

    data, sr = sf.read(str(drums_path), always_2d=True, dtype="float32")
    if sr != sample_rate:
        raise ValueError(f"Unexpected drums sample rate {sr}; expected {sample_rate}")
    try:
        from scipy.signal import butter, sosfilt
    except ImportError as exc:
        raise RuntimeError("scipy is required for percussion derivation") from exc

    sos = butter(4, PERCUSSION_SPLIT_HZ, btype="highpass", fs=sr, output="sos")
    percussion = np.stack([sosfilt(sos, data[:, channel]) for channel in range(data.shape[1])], axis=1)
    low = data - percussion
    write_flac_atomic(drums_path, low, sr)
    write_flac_atomic(percussion_path, percussion, sr)
