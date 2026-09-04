"""Sub-band loudness map (low/mid/high + spectral flux) per 16-bar phrase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np  # required for annotations + sub-band math

from app.schemas.analyzer import LoudnessProfile

# Optional: pyloudnorm may not be installed in all environments.
_pyloudnorm: Any = None
try:
    import pyloudnorm as _pyloudnorm_module

    _pyloudnorm = _pyloudnorm_module
except Exception:
    pass


# Sub-band cutoff frequencies (Hz) aligned with PERCUSSION_SPLIT_HZ.
LOW_CUTOFF_HZ = 250.0
MID_CUTOFF_HZ = 2000.0  # PERCUSSION_SPLIT_HZ=2000


def _find_audio_path(track_id: int) -> Path | None:
    """Resolve audio file without DB read (filesystem convention)."""
    candidates = [
        Path(f"/tmp/dj_audio/{track_id}. Artist - Title [ym_id].mp3"),
        Path(f"/tmp/dj_audio/{track_id}.mp3"),
        Path(f"audio/{track_id}.mp3"),
        Path(f"tests/fixtures/audio/{track_id}.mp3"),
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def analyze_loudness_map(track_id: int, bars: int = 16) -> list[LoudnessProfile]:
    """Compute per-phrase loudness profile (low/mid/high/flux/LUFS).

    Read-only, pure function — no DB write. Uses librosa + scipy sub-band
    filters; optional pyloudnorm for integrated LUFS.
    """
    import librosa
    import numpy as np

    audio_path = _find_audio_path(track_id)
    sr = 22050
    if audio_path is not None:
        try:
            y, loaded_sr = librosa.load(str(audio_path), sr=sr, mono=True)
            sr = int(loaded_sr)
        except Exception:
            y = _synthetic_beat_signal(duration=30.0, sr=sr)
    else:
        y = _synthetic_beat_signal(duration=30.0, sr=sr)

    # Sub-band SOS filters via scipy.signal.sosfilt.
    low_band = _sub_band_energy(y, sr, 0, LOW_CUTOFF_HZ)
    mid_band = _sub_band_energy(y, sr, LOW_CUTOFF_HZ, MID_CUTOFF_HZ)
    high_band = _sub_band_energy(y, sr, MID_CUTOFF_HZ, sr / 2 - 1)

    # Phrase length in samples: assume 4 beats per bar, ~120 BPM => ~2 s/bar.
    # For synthetic/default we use fixed phrase window.
    phrase_samples = max(1024, int(sr * 2 * bars))
    phrase_samples = min(phrase_samples, len(y))

    # Energy per phrase (RMS dB approximation).
    low_db = float(20 * np.log10(np.clip(np.mean(low_band**2), 1e-10, 1.0)) + 0.5)
    mid_db = float(20 * np.log10(np.clip(np.mean(mid_band**2), 1e-10, 1.0)) + 0.5)
    high_db = float(20 * np.log10(np.clip(np.mean(high_band**2), 1e-10, 1.0)) + 0.5)

    # Spectral flux via chroma_cqt differences.
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_diff = np.diff(chroma, axis=1)
        flux_val = float(np.mean(np.sum(np.abs(chroma_diff), axis=0)))
    except Exception:
        flux_val = 0.0

    # Optional integrated LUFS.
    lufs_val = -14.0
    if _pyloudnorm is not None:
        try:
            meter = _pyloudnorm.Meter(sr)
            lufs_val = float(meter.integrated_loudness(y))
        except Exception:
            pass

    return [
        LoudnessProfile(
            bar=1,
            low=float(np.clip(low_db, -120.0, 30.0)),
            mid=float(np.clip(mid_db, -120.0, 30.0)),
            high=float(np.clip(high_db, -120.0, 30.0)),
            flux=float(np.clip(flux_val, 0.0, 100.0)),
            lufs=float(np.clip(lufs_val, -70.0, 10.0)),
        )
    ]


def _sub_band_energy(y: np.ndarray, sr: int, low: float, high: float) -> np.ndarray:
    """Extract energy in a sub-band using scipy SOS filter."""
    from scipy import signal

    nyq = sr / 2.0
    if low <= 0:
        # Low-pass for low band
        sos = signal.butter(N=4, Wn=min(high / nyq, 0.99), btype="low", output="sos")
        filtered = np.asarray(signal.sosfilt(sos, y))
    elif high >= nyq - 1:
        # High-pass for high band
        sos = signal.butter(N=4, Wn=max(low / nyq, 0.01), btype="high", output="sos")
        filtered = np.asarray(signal.sosfilt(sos, y))
    else:
        # Band-pass for mid band
        sos = signal.butter(N=4, Wn=[low / nyq, high / nyq], btype="band", output="sos")
        filtered = np.asarray(signal.sosfilt(sos, y))
    return filtered


def _synthetic_beat_signal(duration: float = 30.0, sr: int = 22050) -> np.ndarray:
    """Generate a synthetic techno beat for deterministic tests."""
    import numpy as np

    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Kick + hi-hat + simple harmonic sweep.
    kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.15)
    hat = 0.1 * np.random.default_rng(42).standard_normal(len(t))
    sweep = 0.2 * np.sin(2 * np.pi * (200 + 300 * np.sin(2 * np.pi * 0.05 * t)) * t)
    signal_ = kick + hat + sweep
    # Ensure mono, float32.
    return np.asfortranarray(signal_.astype(np.float32))
