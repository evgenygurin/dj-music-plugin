from __future__ import annotations

import json
from typing import Any

import numpy as np


def _safe_json_float_array(value: Any, max_len: int = 13) -> np.ndarray:
    if value is None:
        return np.zeros(max_len, dtype=np.float32)
    if isinstance(value, str):
        try:
            arr = np.array(json.loads(value), dtype=np.float32)
            return arr[:max_len] if len(arr) > max_len else np.pad(arr, (0, max_len - len(arr)))
        except (json.JSONDecodeError, ValueError):
            return np.zeros(max_len, dtype=np.float32)
    if isinstance(value, (int, float)):
        return np.array([float(value)], dtype=np.float32)
    return np.zeros(max_len, dtype=np.float32)


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _key_onehot(key_code: int | None, dims: int = 24) -> np.ndarray:
    onehot = np.zeros(dims, dtype=np.float32)
    if key_code is not None and 0 <= key_code < dims:
        onehot[key_code] = 1.0
    return onehot


def build_embeddings(features: dict[str, Any]) -> dict[str, np.ndarray]:
    mfcc = _safe_json_float_array(features.get("mfcc_vector"), 13)

    timbral = np.concatenate(
        [
            mfcc,
            np.array(
                [
                    _safe_float(features.get(k))
                    for k in (
                        "spectral_centroid_hz",
                        "spectral_rolloff_85",
                        "spectral_rolloff_95",
                        "spectral_flux_mean",
                        "spectral_flatness",
                        "spectral_slope",
                        "spectral_contrast",
                        "spectral_complexity_mean",
                    )
                ],
                dtype=np.float32,
            ),
        ]
    )
    timbral = np.pad(timbral, (0, max(0, 64 - len(timbral))))[:64]

    tonnetz = _safe_json_float_array(features.get("tonnetz_vector"), 6)
    hpcp_features = np.array(
        [
            _safe_float(features.get("hpcp_entropy")),
            _safe_float(features.get("hpcp_crest")),
        ],
        dtype=np.float32,
    )
    harmonic = np.concatenate(
        [
            tonnetz,
            hpcp_features,
            _key_onehot(features.get("key_code")),
            np.array(
                [
                    _safe_float(features.get("chroma_entropy")),
                    _safe_float(features.get("hnr_db")),
                    _safe_float(features.get("dissonance_mean")),
                    _safe_float(features.get("inharmonicity")),
                    _safe_float(features.get("chords_strength")),
                    _safe_float(features.get("chords_changes_rate")),
                ],
                dtype=np.float32,
            ),
        ]
    )
    harmonic = np.pad(harmonic, (0, max(0, 128 - len(harmonic))))[:128]

    beat_loudness = _safe_json_float_array(features.get("beat_loudness_band_ratio"), 6)
    rhythmic = np.concatenate(
        [
            np.array(
                [
                    _safe_float(features.get("onset_rate")),
                    _safe_float(features.get("pulse_clarity")),
                    _safe_float(features.get("kick_prominence")),
                    _safe_float(features.get("bpm_stability")),
                    _safe_float(features.get("danceability")),
                ],
                dtype=np.float32,
            ),
            beat_loudness,
        ]
    )
    rhythmic = np.pad(rhythmic, (0, max(0, 32 - len(rhythmic))))[:32]

    energy = np.array(
        [
            _safe_float(features.get(k))
            for k in (
                "integrated_lufs",
                "energy_sub_ratio",
                "energy_low_ratio",
                "energy_lowmid_ratio",
                "energy_mid_ratio",
                "energy_highmid_ratio",
                "energy_high_ratio",
                "crest_factor_db",
                "loudness_range_lu",
                "energy_slope",
                "dynamic_complexity",
            )
        ],
        dtype=np.float32,
    )
    energy = np.pad(energy, (0, max(0, 32 - len(energy))))[:32]

    full = np.concatenate([timbral, harmonic, rhythmic, energy])
    full = np.pad(full, (0, max(0, 256 - len(full))))[:256]

    return {
        "timbral": np.pad(timbral, (0, max(0, 256 - len(timbral))))[:256],
        "harmonic": np.pad(harmonic, (0, max(0, 256 - len(harmonic))))[:256],
        "rhythmic": np.pad(rhythmic, (0, max(0, 256 - len(rhythmic))))[:256],
        "energy": np.pad(energy, (0, max(0, 256 - len(energy))))[:256],
        "full": full,
    }
