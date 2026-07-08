from __future__ import annotations

from app.shared.features import TrackFeatures


def key_reliable(t: TrackFeatures, confidence_floor: float) -> bool:
    if t.atonality is True:
        return False
    return not (t.key_confidence is not None and t.key_confidence < confidence_floor)
