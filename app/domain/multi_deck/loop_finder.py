"""Loopable section finder for sustained multi-deck layering."""

from __future__ import annotations

from typing import Any


def find_loops(
    sections: list[dict[str, Any]],
    bpm: float | None,
    track_id: int,
    min_bars: int = 8,
    max_bars: int = 32,
    exclude_vocals: bool = True,
    min_energy_stability: float = 0.7,
) -> dict[str, Any]:
    """Find loopable sections from already-loaded track data; performs no I/O."""
    effective_bpm = bpm if bpm is not None else 120.0
    bar_duration_ms = 240_000.0 / effective_bpm
    loops = []
    for sec in sections:
        length_ms = sec.get("end_ms", 0) - sec.get("start_ms", 0)
        bars = length_ms / bar_duration_ms
        if bars < min_bars or bars > max_bars:
            continue

        stem_energy = sec.get("stem_energy") or {}
        vocals_energy = stem_energy.get("vocals", 0)
        if exclude_vocals and vocals_energy > 0.15:
            continue

        energy = sec.get("energy") or 0.5
        energy_stability = energy * (1.0 - vocals_energy)
        if energy_stability >= min_energy_stability:
            loops.append(
                {
                    "section_type": sec.get("section_type"),
                    "start_ms": sec.get("start_ms"),
                    "end_ms": sec.get("end_ms"),
                    "bars": round(bars, 1),
                    "energy_stability": round(energy_stability, 3),
                    "stem_energy": stem_energy,
                    "loopable": True,
                    "cue_point_ms": sec.get("start_ms"),
                }
            )

    loops.sort(key=lambda lp: lp["energy_stability"], reverse=True)
    return {
        "track_id": track_id,
        "bpm": round(effective_bpm, 1),
        "bar_duration_ms": round(bar_duration_ms, 1),
        "loops": loops,
    }
