from __future__ import annotations

from app.config import get_settings
from app.shared.features import TrackFeatures


class EnergyGapSpec:
    name = "energy_gap"

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

        energy_gap: float | None
        if pre_energy_delta is not None:
            energy_gap = pre_energy_delta
        elif from_t.integrated_lufs is not None and to_t.integrated_lufs is not None:
            energy_gap = abs(from_t.integrated_lufs - to_t.integrated_lufs)
        else:
            energy_gap = None

        if energy_gap is not None and energy_gap > settings.hard_reject_energy_gap_lufs:
            return f"Energy gap {energy_gap:.1f} LUFS > {settings.hard_reject_energy_gap_lufs}"

        return None
