from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.config import get_settings
from app.shared.features import TrackFeatures

FloatArr = npt.NDArray[np.float64]
BoolArr = npt.NDArray[np.bool_]
IntArr = npt.NDArray[np.int64]

_NAN = np.float64("nan")

_MFCC_DIM = 13
_TONNETZ_DIM = 6
_ENERGY_BAND_DIM = 6
_BEAT_LOUDNESS_DIM = 6


@dataclass(frozen=True)
class FeatureArrays:
    n: int

    bpm: FloatArr
    bpm_stability: FloatArr
    bpm_confidence: FloatArr
    key_confidence: FloatArr
    integrated_lufs: FloatArr
    loudness_range_lu: FloatArr
    crest_factor_db: FloatArr
    energy_slope: FloatArr
    spectral_centroid_hz: FloatArr
    spectral_contrast: FloatArr
    chroma_entropy: FloatArr
    pitch_salience_mean: FloatArr
    onset_rate: FloatArr
    kick_prominence: FloatArr
    hnr_db: FloatArr
    dissonance_mean: FloatArr

    variable_tempo: BoolArr
    atonality: BoolArr
    key_code: IntArr

    mfcc: FloatArr
    mfcc_present: BoolArr
    tonnetz: FloatArr
    tonnetz_present: BoolArr
    energy_bands: FloatArr
    energy_bands_present: BoolArr
    beat_loudness: FloatArr
    beat_loudness_present: BoolArr


def _scalar_arr(values: Sequence[float | None]) -> FloatArr:
    return np.array([_NAN if v is None else float(v) for v in values], dtype=np.float64)


def _bool_arr(values: Sequence[bool | None]) -> BoolArr:
    return np.array([bool(v) if v is not None else False for v in values], dtype=np.bool_)


def _int_arr(values: Sequence[int | None], missing: int = -1) -> IntArr:
    return np.array([missing if v is None else int(v) for v in values], dtype=np.int64)


def _vector_matrix(values: Sequence[Sequence[float] | None], dim: int) -> tuple[FloatArr, BoolArr]:
    n = len(values)
    mat = np.zeros((n, dim), dtype=np.float64)
    present = np.zeros(n, dtype=np.bool_)
    for i, vec in enumerate(values):
        if vec is None or len(vec) == 0:
            continue
        present[i] = True
        cap = min(dim, len(vec))
        mat[i, :cap] = np.asarray(vec[:cap], dtype=np.float64)
    return mat, present


def extract_feature_arrays(tracks: Sequence[TrackFeatures]) -> FeatureArrays:
    mfcc, mfcc_present = _vector_matrix([t.mfcc_vector for t in tracks], _MFCC_DIM)
    tonnetz, tonnetz_present = _vector_matrix([t.tonnetz_vector for t in tracks], _TONNETZ_DIM)
    energy_bands, energy_bands_present = _vector_matrix(
        [t.energy_bands for t in tracks], _ENERGY_BAND_DIM
    )
    beat_loudness, beat_loudness_present = _vector_matrix(
        [t.beat_loudness_band_ratio for t in tracks], _BEAT_LOUDNESS_DIM
    )

    return FeatureArrays(
        n=len(tracks),
        bpm=_scalar_arr([t.bpm for t in tracks]),
        bpm_stability=_scalar_arr([t.bpm_stability for t in tracks]),
        bpm_confidence=_scalar_arr([t.bpm_confidence for t in tracks]),
        key_confidence=_scalar_arr([t.key_confidence for t in tracks]),
        integrated_lufs=_scalar_arr([t.integrated_lufs for t in tracks]),
        loudness_range_lu=_scalar_arr([t.loudness_range_lu for t in tracks]),
        crest_factor_db=_scalar_arr([t.crest_factor_db for t in tracks]),
        energy_slope=_scalar_arr([t.energy_slope for t in tracks]),
        spectral_centroid_hz=_scalar_arr([t.spectral_centroid_hz for t in tracks]),
        spectral_contrast=_scalar_arr([t.spectral_contrast for t in tracks]),
        chroma_entropy=_scalar_arr([t.chroma_entropy for t in tracks]),
        pitch_salience_mean=_scalar_arr([t.pitch_salience_mean for t in tracks]),
        onset_rate=_scalar_arr([t.onset_rate for t in tracks]),
        kick_prominence=_scalar_arr([t.kick_prominence for t in tracks]),
        hnr_db=_scalar_arr([t.hnr_db for t in tracks]),
        dissonance_mean=_scalar_arr([t.dissonance_mean for t in tracks]),
        variable_tempo=_bool_arr([t.variable_tempo for t in tracks]),
        atonality=_bool_arr([t.atonality for t in tracks]),
        key_code=_int_arr([t.key_code for t in tracks], missing=-1),
        mfcc=mfcc,
        mfcc_present=mfcc_present,
        tonnetz=tonnetz,
        tonnetz_present=tonnetz_present,
        energy_bands=energy_bands,
        energy_bands_present=energy_bands_present,
        beat_loudness=beat_loudness,
        beat_loudness_present=beat_loudness_present,
    )


def key_reliable_mask(fa: FeatureArrays, idx: IntArr) -> BoolArr:
    floor = get_settings().transition.hard_reject_key_confidence_floor
    conf = fa.key_confidence[idx]
    return ~fa.atonality[idx] & (np.isnan(conf) | (conf >= floor))
