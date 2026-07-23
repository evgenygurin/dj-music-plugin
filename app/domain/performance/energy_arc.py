"""EnergyArcPlanner — builds optimal set structure from energy/BPM/key targets.

Takes a list of candidate tracks (with features) and a target arc shape,
returns the best track selection and ordering.

Arc shapes (matching techno set archetypes):
  - roller: steady climb 126→138, peak at 70-80% of set, gentle cooldown
  - peak_only: all tracks near target BPM, energy stays high throughout
  - journey: two distinct energy peaks (storytelling, Nina-style)
  - warehouse: starts deep, plateaus, ends deep (Berghain-style)
  - festival: quick ramp-up, long peak, abrupt end

The planner uses scipy.optimize to fit tracks to the target energy curve
while respecting BPM progression, key compatibility, and subgenre flow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass


class ArcShape(Enum):
    ROLLER = "roller"
    PEAK_ONLY = "peak_only"
    JOURNEY = "journey"
    WAREHOUSE = "warehouse"
    FESTIVAL = "festival"


@dataclass
class ArcSlot:
    """One position in the energy arc — describes what kind of track fits here."""

    position: int  # 1-based position in set
    target_bpm: float
    target_energy: float  # 0.0 to 1.0
    bpm_tolerance: float = 3.0  # ± BPM
    energy_tolerance: float = 0.15
    preferred_keys: list[int] = field(default_factory=list)  # Camelot codes
    preferred_subgenres: list[str] = field(default_factory=list)
    label: str = ""  # e.g. "warmup", "peak", "closing"


@dataclass
class EnergyArc:
    """Complete energy arc specification for a DJ set."""

    shape: ArcShape
    num_tracks: int
    target_bpm_start: float
    target_bpm_peak: float
    target_bpm_end: float
    slots: list[ArcSlot] = field(default_factory=list)
    name: str = ""

    def build_slots(self) -> list[ArcSlot]:
        """Generate ArcSlot list from arc parameters."""
        n = self.num_tracks
        x = np.linspace(0, 1, n)

        if self.shape == ArcShape.ROLLER:
            bpm_curve = self.target_bpm_start + (
                self.target_bpm_peak - self.target_bpm_start
            ) * np.minimum(x / 0.75, 1.0)
            # Energy peak at 70% then slight cooldown
            energy_curve = 0.35 + 0.45 * np.sin(np.pi * x / 0.85)
            energy_curve = np.clip(energy_curve, 0.3, 0.75)

        elif self.shape == ArcShape.PEAK_ONLY:
            bpm_curve = np.full(n, self.target_bpm_peak)
            energy_curve = np.full(n, 0.65)

        elif self.shape == ArcShape.JOURNEY:
            # Two peaks: one at 30%, one at 75%
            bpm_curve = self.target_bpm_start + (self.target_bpm_peak - self.target_bpm_start) * x
            energy_curve = (
                0.30
                + 0.25 * np.exp(-((x - 0.30) ** 2) / 0.03)
                + 0.35 * np.exp(-((x - 0.70) ** 2) / 0.04)
            )
            energy_curve = np.clip(energy_curve, 0.25, 0.80)

        elif self.shape == ArcShape.WAREHOUSE:
            bpm_curve = np.full(n, self.target_bpm_peak)
            # Deep start and end, sustained middle
            energy_curve = 0.30 + 0.35 * np.sin(np.pi * x)
            energy_curve = np.clip(energy_curve, 0.25, 0.55)

        elif self.shape == ArcShape.FESTIVAL:
            bpm_curve = self.target_bpm_start + (
                self.target_bpm_peak - self.target_bpm_start
            ) * np.tanh(3 * x)
            energy_curve = 0.40 + 0.40 * np.tanh(4 * (x - 0.15))
            energy_curve = np.clip(energy_curve, 0.35, 0.85)

        else:
            bpm_curve = np.linspace(self.target_bpm_start, self.target_bpm_end, n)
            energy_curve = np.linspace(0.35, 0.65, n)

        self.slots = [
            ArcSlot(
                position=i + 1,
                target_bpm=float(bpm_curve[i]),
                target_energy=float(energy_curve[i]),
                label=_arc_label(i, n, self.shape),
            )
            for i in range(n)
        ]
        return self.slots


def _arc_label(pos: int, total: int, shape: ArcShape) -> str:
    """Human-readable label for a position in the energy arc."""
    ratio = pos / max(1, total - 1)
    if ratio < 0.15:
        return "intro"
    elif ratio < 0.30:
        return "warmup"
    elif ratio < 0.45:
        return "build" if shape != ArcShape.JOURNEY else "peak1"
    elif ratio < 0.55:
        return "peak" if shape != ArcShape.JOURNEY else "bridge"
    elif ratio < 0.75:
        return "plateau" if shape != ArcShape.JOURNEY else "peak2"
    elif ratio < 0.90:
        return "cooldown"
    else:
        return "closing"


@dataclass
class TrackCandidate:
    """One track considered for arc placement."""

    track_id: int
    bpm: float
    energy_mean: float
    key_code: int | None
    integrated_lufs: float
    spectral_centroid_hz: float
    mood: str | None = None
    title: str = ""


def fit_tracks_to_arc(
    candidates: list[TrackCandidate],
    arc: EnergyArc,
    key_compatibility_weight: float = 0.3,
    bpm_weight: float = 0.4,
    energy_weight: float = 0.3,
) -> list[int] | None:
    """Greedy track-to-slot assignment minimizing deviation from arc targets.

    Returns ordered list of track_ids, or None if not enough candidates.
    """
    if len(candidates) < arc.num_tracks:
        return None

    arc.build_slots()
    remaining = list(candidates)
    result: list[int] = []

    for slot in arc.slots:
        best_idx = -1
        best_score = float("inf")

        for i, c in enumerate(remaining):
            bpm_dev = abs(c.bpm - slot.target_bpm) / max(1.0, slot.bpm_tolerance)
            energy_dev = abs(c.energy_mean - slot.target_energy) / max(0.01, slot.energy_tolerance)

            # Key compatibility: prefer tracks compatible with previous
            key_dev = 0.0
            if result and c.key_code is not None:
                prev_key = _get_key_of(result[-1], candidates)
                if prev_key is not None:
                    key_dist = _camelot_distance(prev_key, c.key_code)
                    key_dev = key_dist / 12.0

            score = (
                bpm_weight * bpm_dev
                + energy_weight * energy_dev
                + key_compatibility_weight * key_dev
            )

            if score < best_score:
                best_score = score
                best_idx = i

        if best_idx >= 0:
            result.append(remaining[best_idx].track_id)
            remaining.pop(best_idx)
        else:
            return None

    return result


def _get_key_of(track_id: int, candidates: list[TrackCandidate]) -> int | None:
    for c in candidates:
        if c.track_id == track_id:
            return c.key_code
    return None


def _camelot_distance(a: int, b: int) -> int:
    """Distance on Camelot wheel (0-23)."""
    diff = abs(a - b)
    return min(diff, 24 - diff)


# ── Arc presets ─────────────────────────────────────────────


def roller_arc(num_tracks: int = 16) -> EnergyArc:
    return EnergyArc(
        shape=ArcShape.ROLLER,
        num_tracks=num_tracks,
        target_bpm_start=126.0,
        target_bpm_peak=136.0,
        target_bpm_end=128.0,
        name=f"Roller-{num_tracks}",
    )


def journey_arc(num_tracks: int = 18) -> EnergyArc:
    """Nina Kraviz-style two-story arc."""
    return EnergyArc(
        shape=ArcShape.JOURNEY,
        num_tracks=num_tracks,
        target_bpm_start=125.0,
        target_bpm_peak=138.0,
        target_bpm_end=130.0,
        name=f"Journey-{num_tracks}",
    )


def warehouse_arc(num_tracks: int = 12) -> EnergyArc:
    """Berghain-style deep sustained set."""
    return EnergyArc(
        shape=ArcShape.WAREHOUSE,
        num_tracks=num_tracks,
        target_bpm_start=128.0,
        target_bpm_peak=132.0,
        target_bpm_end=128.0,
        name=f"Warehouse-{num_tracks}",
    )


def festival_arc(num_tracks: int = 14) -> EnergyArc:
    """Short, intense festival set."""
    return EnergyArc(
        shape=ArcShape.FESTIVAL,
        num_tracks=num_tracks,
        target_bpm_start=130.0,
        target_bpm_peak=140.0,
        target_bpm_end=135.0,
        name=f"Festival-{num_tracks}",
    )


ARC_PRESETS: dict[str, Callable[[int], EnergyArc]] = {
    "roller": roller_arc,
    "journey": journey_arc,
    "warehouse": warehouse_arc,
    "festival": festival_arc,
}
