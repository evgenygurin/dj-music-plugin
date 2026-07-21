"""Structured-output model for energy_arc_plan tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArcSlotResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int
    target_bpm: float
    target_energy: float
    label: str


class EnergyArcResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    shape: str
    num_tracks: int
    bpm_start: float
    bpm_peak: float
    bpm_end: float
    slots: list[ArcSlotResult] = Field(default_factory=list)
