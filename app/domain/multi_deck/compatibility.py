"""N-way stem vertical compatibility scorer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from app.domain.multi_deck.models import BandScore, CompatibilityResult, StemLayer
from app.domain.transition.kernels.bpm_distance import bpm_gauss
from app.domain.transition.kernels.camelot_lookup import key_distance


class StemFeature(Protocol):
    """Minimal stem feature shape required by the compatibility policy."""

    stem_name: str
    bpm: float | None
    key_code: int | None
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
_CLASH_THRESHOLD = 0.5


async def compute_stem_compatibility(
    feature_reader: StemFeatureReader,
    layers: list[StemLayer],
) -> CompatibilityResult:
    if len(layers) < 2:
        return CompatibilityResult(
            overall_score=1.0,
            hard_reject=False,
            per_band={b: BandScore(score=1.0, clash=False) for b in _BANDS},
            key_compatibility={"score": 1.0},
            bpm_compatibility={"score": 1.0},
        )

    features = {}
    for layer in layers:
        rows = await feature_reader.get_all_for_track(layer.track_id)
        match = [r for r in rows if getattr(r, "stem_name", None) == layer.stem_name]
        if match:
            features[(layer.track_id, layer.stem_name)] = match[0]

    bpms: list[float] = []
    for feature in features.values():
        bpm = feature.bpm
        if bpm is not None:
            bpms.append(bpm)
    bpm_min = 1.0
    for i in range(len(bpms)):
        for j in range(i + 1, len(bpms)):
            bpm_min = min(bpm_min, bpm_gauss(bpms[i], bpms[j]))

    keys: list[int] = []
    for feature in features.values():
        key_code = feature.key_code
        if key_code is not None:
            keys.append(key_code)
    key_min = 1.0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            key_min = min(key_min, 1.0 - key_distance(keys[i], keys[j]) / 12.0)

    hard_reject = bpm_min < 0.05 or key_min < 0.01
    per_band = {}
    for band in _BANDS:
        col = _ENERGY_COLS[band]
        band_energies: list[tuple[tuple[int, str], float]] = []
        for key, feature in features.items():
            value = getattr(feature, col, None)
            if isinstance(value, (int, float)):
                band_energies.append((key, float(value)))
        high = [(k, e) for k, e in band_energies if e > _CLASH_THRESHOLD]
        clash = len(high) >= 2
        max_e = max((e for _, e in band_energies), default=0.0)
        score = 0.4 if clash else 0.85 + 0.15 * (1.0 - max_e)
        per_band[band] = BandScore(
            score=score,
            clash=clash,
            culprits=[f"{tid}:{stem}" for (tid, stem), _ in high] if clash else [],
        )

    recommendations = []
    for band, bs in per_band.items():
        if bs.clash:
            rec = f"{band} band clash between {', '.join(bs.culprits)}"
            if band == "low":
                rec += " — consider EQ cut at 150-250 Hz on one stem"
            elif band == "sub":
                rec += " — reduce gain on one kick or apply low-shelf"
            recommendations.append(rec)

    overall = 0.3 * bpm_min + 0.3 * key_min + 0.4 * np.mean([bs.score for bs in per_band.values()])
    return CompatibilityResult(
        overall_score=round(float(overall), 4),
        hard_reject=hard_reject,
        per_band=per_band,
        key_compatibility={"score": round(key_min, 4), "keys": keys},
        bpm_compatibility={"score": round(bpm_min, 4), "bpms": bpms},
        recommendations=recommendations,
    )
