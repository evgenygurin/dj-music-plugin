"""Structured-output model for key_compatibility tool."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class KeyCompatibilityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_key: int
    to_key: int
    from_camelot: str
    to_camelot: str
    distance: int
    relation: str
    compatibility_score: float
    description: str
