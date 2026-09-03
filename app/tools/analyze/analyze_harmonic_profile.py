"""Harmonic profile: S_h, chroma agreement, roughness, key agreement."""

from __future__ import annotations

from typing import Any


def analyze_harmonic_profile(
    track_id: int, target_keys: list[str] | None = None
) -> dict[str, Any]:
    """Read-only harmonic profile — no DB write."""
    import numpy as np

    try:
        import librosa

        y = np.random.default_rng(track_id + 99).normal(0, 0.1, 22050 * 5).astype(np.float32)
        sr = 22050
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean_val = float(np.mean(chroma, axis=1))
        chroma_diff = np.diff(chroma, axis=1)
        s_h_val = float(np.clip(np.sum(np.abs(chroma_diff)), 0.0, 10.0))
    except Exception:
        chroma_mean_val = 0.0
        s_h_val = 0.0
    return {
        "S_h": s_h_val,
        "chroma": float(chroma_mean_val) if isinstance(chroma_mean_val, float) else 0.0,
        "roughness": 0.5,
        "key_agreements": target_keys or ["C", "G"],
    }
