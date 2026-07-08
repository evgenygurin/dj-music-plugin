from __future__ import annotations

from app.domain.camelot.wheel import camelot_distance
from app.shared.features import TrackFeatures

_HARMONIC_KEY_DIST_MAX = 1


def _camelot_compatible(a: TrackFeatures, b: TrackFeatures) -> bool:
    if a.key_code is None or b.key_code is None:
        return False
    return camelot_distance(a.key_code, b.key_code) <= _HARMONIC_KEY_DIST_MAX


def _energy_delta_lufs(a: TrackFeatures, b: TrackFeatures) -> float | None:
    if a.integrated_lufs is None or b.integrated_lufs is None:
        return None
    return b.integrated_lufs - a.integrated_lufs
