"""Tests for knowledge://audio-features-field-guide column coverage."""

from __future__ import annotations

import json

import pytest

from app.controllers.resources.knowledge_audio_features_guide import (
    _build_payload,
    audio_features_field_guide,
)
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track


def test_guide_documents_all_track_audio_features_columns() -> None:
    cols = {c.name for c in TrackAudioFeaturesComputed.__table__.columns}
    documented = set(_build_payload()["fields"].keys())
    assert cols == documented


def test_guide_documents_all_tracks_table_columns() -> None:
    cols = {c.name for c in Track.__table__.columns}
    documented = set(_build_payload()["library_track_columns"].keys())
    assert cols == documented


@pytest.mark.asyncio
async def test_audio_features_field_guide_returns_parseable_json() -> None:
    raw = await audio_features_field_guide()
    data = json.loads(raw)
    assert data["title"]
    assert "fields" in data
    assert len(data["fields"]) >= 1
