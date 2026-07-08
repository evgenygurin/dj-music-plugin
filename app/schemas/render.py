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
    flagged: int = 0
    windows: list[dict[str, Any]] = Field(default_factory=list)


class RenderVerifyResult(BaseModel):
    version_id: int
    summary: str = ""
    passed: int = 0
    warned: int = 0
    failed: int = 0
    exit_code: int = 0
    checks: list[dict[str, Any]] = Field(default_factory=list)
