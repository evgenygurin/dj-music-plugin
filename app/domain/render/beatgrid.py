"""Beatgrid domain behavior and JSON IO.

``BeatgridEntry`` stays a pure data model in ``models.py``; this module is the
single source for clamping, QA flags, and the beatgrid.json row schema.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.render import RenderSettings
from app.domain.render.models import BeatgridEntry

_GRID_FILENAME = "beatgrid.json"


@dataclass(frozen=True, slots=True)
class BeatgridLimits:
    max_phase_ms: float = 120.0
    max_trim_start_s: float = 8.0
    fixed_flag_threshold_ms: float = 40.0
    fixed_flag_gain_db: float = 1.5

    @classmethod
    def from_settings(cls, _settings: RenderSettings) -> BeatgridLimits:
        return cls()


def clamp_entry(entry: BeatgridEntry, limits: BeatgridLimits) -> BeatgridEntry:
    trim = min(entry.trim_start_s, limits.max_trim_start_s)
    phase = max(-limits.max_phase_ms, min(limits.max_phase_ms, entry.phase_ms))
    refined = min(
        round(trim + phase / 1000.0, 4),
        round(trim + limits.max_phase_ms / 1000.0, 4),
    )
    return BeatgridEntry(
        track_id=entry.track_id,
        trim_start_s=trim,
        refined_trim_s=refined,
        gain_db=entry.gain_db,
        phase_ms=phase,
    )


def entry_flags(entry: BeatgridEntry, limits: BeatgridLimits) -> list[str]:
    if (
        abs(entry.phase_ms) > limits.fixed_flag_threshold_ms
        or abs(entry.gain_db) > limits.fixed_flag_gain_db
    ):
        return ["fixed"]
    return []


def entry_to_row(entry: BeatgridEntry, limits: BeatgridLimits | None = None) -> dict[str, Any]:
    return {
        "track_id": entry.track_id,
        "trim_start_s": entry.trim_start_s,
        "refined_trim_s": entry.refined_trim_s,
        "gain_db": entry.gain_db,
        "phase_ms": entry.phase_ms,
        "flags": entry_flags(entry, limits or BeatgridLimits()),
    }


def entry_from_row(row: Mapping[str, Any]) -> BeatgridEntry:
    refined_trim_s = row.get("refined_trim_s")
    return BeatgridEntry(
        track_id=int(row["track_id"]),
        trim_start_s=float(row["trim_start_s"]),
        refined_trim_s=None if refined_trim_s is None else float(refined_trim_s),
        gain_db=float(row.get("gain_db", 0.0)),
        phase_ms=float(row.get("phase_ms", 0.0)),
    )


class BeatgridIO:
    """File-backed beatgrid.json read/write helpers."""

    @staticmethod
    def read(workspace: str) -> list[BeatgridEntry]:
        rows = json.loads((Path(workspace) / _GRID_FILENAME).read_text())
        return [entry_from_row(row) for row in rows]

    @staticmethod
    def write(workspace: str, entries: Sequence[BeatgridEntry]) -> None:
        path = Path(workspace)
        path.mkdir(parents=True, exist_ok=True)
        (path / _GRID_FILENAME).write_text(
            json.dumps([entry_to_row(entry) for entry in entries], indent=1)
        )
