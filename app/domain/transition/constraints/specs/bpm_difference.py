from __future__ import annotations

from app.config import get_settings
from app.domain.transition.math_helpers import bpm_distance
from app.shared.features import TrackFeatures


class BpmDifferenceSpec:
    name = "bpm_difference"

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

        bpm_diff: float | None
        if pre_bpm_dist is not None:
            bpm_diff = pre_bpm_dist
        elif from_t.bpm is not None and to_t.bpm is not None:
            bpm_diff = bpm_distance(from_t.bpm, to_t.bpm)
        else:
            bpm_diff = None

        if bpm_diff is not None and bpm_diff > settings.hard_reject_bpm_diff:
            return f"BPM diff {bpm_diff:.1f} > {settings.hard_reject_bpm_diff}"

        return None
