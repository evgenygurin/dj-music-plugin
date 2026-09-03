"""Energy budget calculator — combined LUFS + per-band allocation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

from app.domain.multi_deck.models import BandBudget, EnergyBudgetResult, StemLayer


class StemFeature(Protocol):
    """Minimal stem feature shape required by the energy budget policy."""

    stem_name: str
    integrated_lufs: float | None
    energy_sub: float | None
    energy_low: float | None
    energy_lowmid: float | None
    energy_mid: float | None
    energy_highmid: float | None
    energy_high: float | None


class StemFeatureReader(Protocol):
    """Port for loading stem features; infrastructure implements this protocol."""

    async def get_all_for_track(self, track_id: int) -> Sequence[StemFeature]: ...


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
    feature_reader: StemFeatureReader,
    layers: list[StemLayer],
    gain_db: list[float] | None = None,
    target_lufs: float = -8.0,
) -> EnergyBudgetResult:
    if gain_db is None:
        gain_db = [0.0] * len(layers)

    features = {}
    for layer in layers:
        rows = await feature_reader.get_all_for_track(layer.track_id)
        match = [r for r in rows if getattr(r, "stem_name", None) == layer.stem_name]
        if match:
            features[(layer.track_id, layer.stem_name)] = match[0]

    total_power = 0.0
    per_band_energy: dict[str, float] = {b: 0.0 for b in _BANDS}
    for i, layer in enumerate(layers):
        f = features.get((layer.track_id, layer.stem_name))
        if f is None:
            continue
        integrated_lufs = f.integrated_lufs
        if integrated_lufs is None:
            continue
        gain = gain_db[i]
        total_power += 10.0 ** ((integrated_lufs + gain) / 10.0)
        power_gain = 10.0 ** (gain / 10.0)
        for band in _BANDS:
            value = getattr(f, _ENERGY_COLS[band], None)
            val = float(value) if isinstance(value, (int, float)) else 0.0
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

    recommendations = [
        f"{band} band overloaded. Reduce gain on stems contributing to {band}."
        for band, bb in per_band.items()
        if bb.warning
    ]
    if not recommendations and headroom_db < 1.0:
        recommendations.append(
            f"Low overall headroom ({headroom_db:.1f} dB). Consider reducing gain."
        )

    return EnergyBudgetResult(
        total_lufs=round(total_lufs, 1),
        headroom_db=round(headroom_db, 1),
        per_band=per_band,
        recommendation=(
            "; ".join(recommendations) if recommendations else "All bands within budget."
        ),
    )
