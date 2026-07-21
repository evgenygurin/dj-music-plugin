"""Structured-output model for auto_fix tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FixItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    at_s: float
    action: str


class AutoFixResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    dry_run: bool
    defects_found: int = 0
    fixes: list[FixItem] = Field(default_factory=list)
    fixed_path: str | None = None
