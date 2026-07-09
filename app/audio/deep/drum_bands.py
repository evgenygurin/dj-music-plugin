from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


BANDS = {
    "sub_kick":   (20, 60),
    "kick_body":  (60, 150),
    "snare_clap": (150, 2000),
    "hi_hats":    (2000, 10000),
}


def analyze_drum_bands(drums_path: Path, sr: int = 22050) -> dict[str, Any]:
    """Split drums stem into 4 frequency bands, compute per-band features."""
    audio, file_sr = sf.read(str(drums_path), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if file_sr != sr:
        from scipy.signal import resample
        n = int(len(audio) * sr / file_sr)
        audio = resample(audio, n)

    bands: dict[str, dict[str, float]] = {}
    for name, (low, high) in BANDS.items():
        sos = butter(4, [low, high], btype="band", fs=sr, output="sos")
        filtered = sosfiltfilt(sos, audio)
        rms = float(np.sqrt(np.mean(filtered**2)))
        onsets = len(_detect_onsets(filtered, sr))
        onset_rate = onsets / (len(filtered) / sr) if len(filtered) > 0 else 0.0

        bands[name] = {
            "energy": round(rms, 4),
            "onset_rate": round(onset_rate, 2),
        }

    total_energy = sum(b["energy"] for b in bands.values()) or 1.0
    for name in bands:
        bands[name]["ratio"] = round(bands[name]["energy"] / total_energy, 4)

    return {"bands": bands, "sr": sr}


def _detect_onsets(audio: np.ndarray, sr: int) -> np.ndarray:
    import librosa
    try:
        env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=512)
        onsets = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=512)
        return np.asarray(onsets, dtype=int)
    except Exception:
        return np.array([], dtype=int)
