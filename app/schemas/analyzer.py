"""Analyzer result schemas (L6 deep-analysis contracts)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoudnessProfile(BaseModel):
    """Per-phrase loudness profile: low / mid / high / flux / integrated LUFS."""

    model_config = ConfigDict(frozen=True)

    bar: int
    low: float = Field(ge=-120.0, le=30.0)
    mid: float = Field(ge=-120.0, le=30.0)
    high: float = Field(ge=-120.0, le=30.0)
    flux: float = Field(ge=0.0)
    lufs: float = Field(ge=-70.0, le=10.0)


class EnergyCurve(BaseModel):
    """Energy trajectory over a phrase window."""

    model_config = ConfigDict(frozen=True)

    phrase_index: int
    mean_db: float
    peak_db: float
    slope_db_per_bar: float


class AnalysisDeepResult(BaseModel):
    """Deep-analysis container (read-only, no DB write)."""

    model_config = ConfigDict(frozen=True)

    track_id: int
    phrase_bars: int
    loudness_map: list[LoudnessProfile]
    energy_curve: list[EnergyCurve] | None = None
    harmonic_profile: dict[str, Any] | None = None
