"""JSON-safe row export for ``TrackAudioFeaturesComputed`` (MCP resources)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.db.models.audio import TrackAudioFeaturesComputed


def computed_features_row_to_jsonable(row: TrackAudioFeaturesComputed) -> dict[str, Any]:
    """Return all columns of ``track_audio_features_computed`` as JSON-friendly values."""
    out: dict[str, Any] = {}
    for col in row.__table__.columns:
        out[col.name] = _json_safe_value(getattr(row, col.name))
    return out


def _json_safe_value(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, bool | int | float | str):
        return val
    if isinstance(val, datetime | date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    return str(val)
