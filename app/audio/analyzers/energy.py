"""Energy analyzer — uses shared core primitives.

Computes: energy_mean, energy_max, energy_std, energy_slope,
and 6-band frequency breakdown using core.spectral.band_energies.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.framing import compute_energy_slope
from app.audio.core.spectral import band_energies

# 6 frequency bands (Hz boundaries)
# Keys match DB column names: energy_sub, energy_low, energy_lowmid, etc.
ENERGY_BANDS: dict[str, tuple[float, float]] = {
    "sub": (20.0, 60.0),
    "low": (60.0, 250.0),
    "lowmid": (250.0, 500.0),
    "mid": (500.0, 2000.0),
    "highmid": (2000.0, 4000.0),
    "high": (4000.0, 8000.0),
}


@register_analyzer
class EnergyAnalyzer(BaseAnalyzer):
    """Energy computation using shared frame energies and core band_energies."""

    name: ClassVar[str] = "energy"
    capabilities: ClassVar[frozenset[str]] = frozenset({"energy"})
    required_packages: ClassVar[list[str]] = []

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Compute energy metrics and 6-band breakdown."""
        # Use pre-computed normalized frame energies from AnalysisContext
        normalized_energies = ctx.frame_energies

        energy_mean = float(np.mean(normalized_energies))
        energy_max = float(np.max(normalized_energies))
        energy_std = float(np.std(normalized_energies))

        # Energy slope via shared utility
        energy_slope = compute_energy_slope(normalized_energies)

        # 6-band energy breakdown via shared core.spectral.band_energies
        be = band_energies(ctx.magnitude, ctx.freqs, ENERGY_BANDS)

        # Compute ratios (band / total band energy)
        band_total = sum(be.values()) or 1.0
        band_ratios = {f"{name}_ratio": val / band_total for name, val in be.items()}

        return {
            "energy_mean": energy_mean,
            "energy_max": energy_max,
            "energy_std": energy_std,
            "energy_slope": energy_slope,
            **{f"energy_{name}": val for name, val in be.items()},
            **{f"energy_{name}": val for name, val in band_ratios.items()},
        }
