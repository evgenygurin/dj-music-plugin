from __future__ import annotations

from app.shared.features import TrackFeatures

_HARMONIC_MOTIF_MAX_PITCH_SALIENCE = 0.35
_HARMONIC_MOTIF_MIN_CENTROID_HZ = 800.0
_HARMONIC_MOTIF_MAX_CENTROID_HZ = 2400.0


def _harmonic_motif(t: TrackFeatures) -> bool:
    if t.pitch_salience_mean is None or t.spectral_centroid_hz is None:
        return False
    if not t.tonnetz_vector:
        return False
    return (
        t.pitch_salience_mean <= _HARMONIC_MOTIF_MAX_PITCH_SALIENCE
        and _HARMONIC_MOTIF_MIN_CENTROID_HZ
        <= t.spectral_centroid_hz
        <= _HARMONIC_MOTIF_MAX_CENTROID_HZ
    )
