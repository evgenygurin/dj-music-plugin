"""ScoringProfile DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScoringProfileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    bpm_weight: float
    harmonic_weight: float
    energy_weight: float
    spectral_weight: float
    groove_weight: float
    timbral_weight: float
    description: str | None = None


class ScoringProfileFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name__eq: str | None = None
    name__icontains: str | None = None


class ScoringProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    bpm_weight: float = Field(..., ge=0.0, le=1.0)
    harmonic_weight: float = Field(..., ge=0.0, le=1.0)
    energy_weight: float = Field(..., ge=0.0, le=1.0)
    spectral_weight: float = Field(..., ge=0.0, le=1.0)
    groove_weight: float = Field(..., ge=0.0, le=1.0)
    timbral_weight: float = Field(..., ge=0.0, le=1.0)
    description: str | None = None


class ScoringProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bpm_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    harmonic_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    energy_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    spectral_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    groove_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    timbral_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    description: str | None = None
