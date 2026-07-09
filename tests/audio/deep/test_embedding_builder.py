from __future__ import annotations

from app.audio.deep.embedding_builder import build_embeddings


def test_build_embeddings_returns_correct_shapes() -> None:
    features = {
        "mfcc_vector": "[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]",
        "spectral_centroid_hz": 2000.0,
        "spectral_rolloff_85": 4000.0,
        "spectral_rolloff_95": 8000.0,
        "spectral_flux_mean": 0.15,
        "tonnetz_vector": "[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]",
        "key_code": 5,
        "chroma_entropy": 0.95,
        "hnr_db": 20.0,
        "hpcp_entropy": 3.5,
        "hpcp_crest": 4.2,
        "onset_rate": 2.0,
        "pulse_clarity": 0.7,
        "kick_prominence": 0.6,
        "integrated_lufs": -8.0,
        "energy_sub_ratio": 0.2,
        "energy_low_ratio": 0.3,
        "energy_mid_ratio": 0.3,
        "energy_high_ratio": 0.2,
        "crest_factor_db": 12.0,
        "loudness_range_lu": 6.0,
        "danceability": 1.5,
        "dynamic_complexity": 5.0,
        "bpm": 130.0,
        "inharmonicity": 0.1,
        "chords_strength": 0.7,
        "chords_changes_rate": 0.05,
    }

    result = build_embeddings(features)

    assert result["timbral"].shape[0] <= 64
    assert result["harmonic"].shape[0] <= 128
    assert result["rhythmic"].shape[0] <= 32
    assert result["energy"].shape[0] <= 32
    assert result["full"].shape[0] <= 256


def test_build_embeddings_handles_missing_keys() -> None:
    features: dict[str, float | str | None] = {
        "bpm": 130.0,
        "integrated_lufs": -8.0,
    }
    result = build_embeddings(features)
    assert result["full"].shape[0] <= 256
