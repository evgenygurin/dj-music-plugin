from __future__ import annotations

from app.shared.features import TrackFeatures

_VOCAL_PRESENCE_PITCH_SALIENCE = 0.55
_VOCAL_PRESENCE_CENTROID_HZ = 2200.0
_VOCAL_LOW_PITCH_SALIENCE = 0.3
_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40


def _vocal_active(t: TrackFeatures) -> bool:
    if t.voicing_ratio is not None:
        return t.voicing_ratio > 0.3

    if t.pitch_salience_mean is None or t.spectral_centroid_hz is None:
        return False
    if t.pitch_salience_mean <= _VOCAL_PRESENCE_PITCH_SALIENCE:
        return False
    if t.spectral_centroid_hz <= _VOCAL_PRESENCE_CENTROID_HZ:
        return False

    if t.energy_bands is not None and len(t.energy_bands) >= 6:
        total = sum(t.energy_bands)
        if total > 1e-6:
            midband = t.energy_bands[2] + t.energy_bands[3]
            if midband / total < _VOCAL_PRESENCE_MIDBAND_RATIO:
                return False

    return True


def _vocal_low(t: TrackFeatures) -> bool:
    return t.pitch_salience_mean is not None and t.pitch_salience_mean < _VOCAL_LOW_PITCH_SALIENCE


def _vocal_data_missing(t: TrackFeatures) -> bool:
    return t.pitch_salience_mean is None or t.spectral_centroid_hz is None
