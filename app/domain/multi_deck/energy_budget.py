"""Energy budget calculator — combined LUFS + per-band allocation."""

from __future__ import annotations

import math

from app.domain.multi_deck.models import BandBudget, EnergyBudgetResult, StemLayer
from app.repositories.unit_of_work import UnitOfWork

_BANDS = ["sub", "low", "lowmid", "mid", "highmid", "high"]
_ENERGY_COLS = {
    "sub": "energy_sub",
    "low": "energy_low",
    "lowmid": "energy_lowmid",
    "mid": "energy_mid",
    "highmid": "energy_highmid",
    "high": "energy_high",
}


async def compute_energy_budget(
    uow: UnitOfWork,
    layers: list[StemLayer],
    gain_db: list[float] | None = None,
    target_lufs: float = -8.0,
) -> EnergyBudgetResult:
    if gain_db is None:
        gain_db = [0.0] * len(layers)

    features = {}
    for layer in layers:
        rows = await uow.stem_features.get_all_for_track(layer.track_id)
        match = [r for r in rows if r.stem_name == layer.stem_name]
        if match:
            features[(layer.track_id, layer.stem_name)] = match[0]

    total_power = 0.0
    per_band_energy: dict[str, float] = {b: 0.0 for b in _BANDS}

    for i, layer in enumerate(layers):
        f = features.get((layer.track_id, layer.stem_name))
        if f is None or f.integrated_lufs is None:
            continue
        gain = gain_db[i]
        total_power += 10.0 ** ((f.integrated_lufs + gain) / 10.0)
        power_gain = 10.0 ** (gain / 10.0)
        for band in _BANDS:
            col = _ENERGY_COLS[band]
            val = getattr(f, col, None) or 0.0
            per_band_energy[band] += val * power_gain

    total_lufs = 10.0 * math.log10(total_power) if total_power > 0.0 else 0.0
    headroom_db = target_lufs - total_lufs
    per_band = {}
    for band in _BANDS:
        band_lufs = per_band_energy[band]
        band_headroom = target_lufs - band_lufs
        per_band[band] = BandBudget(
            total_lufs=round(band_lufs, 1),
            headroom_db=round(band_headroom, 1),
            warning=band_headroom < 0,
        )

    recommendations = []
    for band, bb in per_band.items():
        if bb.warning:
            recommendations.append(
                f"{band} band overloaded. Reduce gain on stems contributing to {band}."
            )
    if not recommendations and headroom_db < 1.0:
        recommendations.append(
            f"Low overall headroom ({headroom_db:.1f} dB). Consider reducing gain."
        )

    return EnergyBudgetResult(
        total_lufs=round(total_lufs, 1),
        headroom_db=round(headroom_db, 1),
        per_band=per_band,
        recommendation="; ".join(recommendations)
        if recommendations
        else "All bands within budget.",
    )
