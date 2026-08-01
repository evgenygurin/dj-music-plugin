"""Structured-output models for the render tools (Plan 2 surface)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RenderBeatgridResult(BaseModel):
    version_id: int
    tracks: list[dict[str, Any]] = Field(default_factory=list)


class RenderMixdownResult(BaseModel):
    job_id: str
    version_id: int
    out_path: str
    duration_s: float
    true_peak_db: float | None = None
    level_jumps: int = 0
    near_silent_s: int = 0


class RenderDiagnosticsResult(BaseModel):
    job_id: str
    overall_rms_db: float
    integrated_lufs: float | None = None
    loudness_range_lu: float | None = None
    overall_flatness: float | None = None
    overall_onset_db: float | None = None
    flagged: int = 0
    windows: list[dict[str, Any]] = Field(default_factory=list)
    flow: dict[str, Any] | None = None


class TrackGridCheck(BaseModel):
    track_id: int
    title: str | None = None
    body_s: float = 0.0
    body_e: float = 0.0
    bpm_measured: float = 0.0
    bpm_dev: float = 0.0
    status: str = "ok"


class TrackPlanCheck(BaseModel):
    """Pre-render warning: stored BPM vs measured grid BPM (the drift source)."""

    track_id: int
    title: str | None = None
    stored_bpm: float | None = None
    bpm_measured: float | None = None
    bpm_dev: float | None = None
    status: str = "ok"


class GridCheckResult(BaseModel):
    version_id: int
    job_id: str
    mix_path: str
    target_bpm: float
    tracks: list[TrackGridCheck] = Field(default_factory=list)
    plan_checks: list[TrackPlanCheck] = Field(default_factory=list)
    max_dev_bpm: float = 0.0
    mean_abs_dev_bpm: float = 0.0
    ok_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    summary: str = ""
