from __future__ import annotations

from app.config import get_settings
from app.domain.camelot.wheel import camelot_distance
from app.domain.transition.key_utils import key_reliable
from app.shared.features import TrackFeatures


class CamelotDistanceSpec:
    name = "camelot_distance"

    def check(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> str | None:
        settings = get_settings().transition

        key_dist: int | None
        if pre_key_dist is not None:
            key_dist = pre_key_dist
        elif from_t.key_code is not None and to_t.key_code is not None:
            key_dist = camelot_distance(from_t.key_code, to_t.key_code)
        else:
            key_dist = None

        key_floor = settings.hard_reject_key_confidence_floor
        if (
            key_dist is not None
            and key_dist >= settings.hard_reject_camelot_dist
            and key_reliable(from_t, key_floor)
            and key_reliable(to_t, key_floor)
        ):
            return f"Camelot distance {key_dist} >= {settings.hard_reject_camelot_dist}"

        return None
