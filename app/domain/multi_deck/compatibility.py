"""N-way stem vertical compatibility scorer."""

from __future__ import annotations

import numpy as np

from app.domain.multi_deck.models import BandScore, CompatibilityResult, StemLayer
from app.domain.transition.kernels.bpm_distance import bpm_gauss
from app.domain.transition.kernels.camelot_lookup import key_distance
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
_CLASH_THRESHOLD = 0.5  # high energy in same band → clash warning


async def compute_stem_compatibility(
    uow: UnitOfWork,
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
        rows = await uow.stem_features.get_all_for_track(layer.track_id)
        match = [r for r in rows if r.stem_name == layer.stem_name]
        if match:
            f = match[0]
            features[(layer.track_id, layer.stem_name)] = f

    # BPM compatibility — minimum pairwise gauss
    bpms = [bpm for k in features if (bpm := features[k].bpm) is not None]
    bpm_min = 1.0
    if len(bpms) >= 2:
        for i in range(len(bpms)):
            for j in range(i + 1, len(bpms)):
                bpm_min = min(bpm_min, bpm_gauss(bpms[i], bpms[j]))

    # Key compatibility — minimum pairwise Camelot distance
    keys = [key for k in features if (key := features[k].key_code) is not None]
    key_min = 1.0
    if len(keys) >= 2:
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                kd = key_distance(keys[i], keys[j])
                key_min = min(key_min, 1.0 - kd / 12.0)

    # Hard constraints
    hard_reject = bpm_min < 0.05 or key_min < 0.01

    # Per-band clash detection
    per_band = {}
    for band in _BANDS:
        col = _ENERGY_COLS[band]
        band_energies = []
        for k, f in features.items():
            val = getattr(f, col, None)
            if val is not None:
                band_energies.append((k, val))
        high = [(k, e) for k, e in band_energies if (e or 0) > _CLASH_THRESHOLD]
        clash = len(high) >= 2
        max_e = max((e for _, e in band_energies), default=0)
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

    band_scores = [bs.score for bs in per_band.values()]
    overall = 0.3 * bpm_min + 0.3 * key_min + 0.4 * np.mean(band_scores)

    return CompatibilityResult(
        overall_score=round(float(overall), 4),
        hard_reject=hard_reject,
        per_band={b: per_band[b] for b in _BANDS},
        key_compatibility={
            "score": round(key_min, 4),
            "keys": [features[k].key_code for k in features],
        },
        bpm_compatibility={
            "score": round(bpm_min, 4),
            "bpms": [features[k].bpm for k in features],
        },
        recommendations=recommendations,
    )
