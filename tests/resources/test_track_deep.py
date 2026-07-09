from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_track_deep_features_returns_json() -> None:
    from app.resources.track_deep import track_deep_features

    uow = MagicMock()
    uow.stem_features = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(return_value=[])

    payload = json.loads(await track_deep_features(id=1, uow=uow))

    assert payload["track_id"] == 1
    assert "stems" in payload


@pytest.mark.asyncio
async def test_track_deep_features_with_stems() -> None:
    from app.resources.track_deep import track_deep_features

    uow = MagicMock()
    from types import SimpleNamespace

    class _ColumnsDict(dict):
        def __iter__(self):
            return iter(self.values())

    mock_feature = MagicMock()
    mock_feature.stem_name = "original"
    mock_feature._mock_methods = None  # allow __table__ magic attribute
    mock_feature.__table__ = MagicMock()
    mock_feature.__table__.columns = _ColumnsDict({
        "id": SimpleNamespace(name="id"),
        "track_id": SimpleNamespace(name="track_id"),
        "pipeline_run_id": SimpleNamespace(name="pipeline_run_id"),
        "created_at": SimpleNamespace(name="created_at"),
        "updated_at": SimpleNamespace(name="updated_at"),
        "stem_name": SimpleNamespace(name="stem_name"),
        "bpm": SimpleNamespace(name="bpm"),
        "bpm_confidence": SimpleNamespace(name="bpm_confidence"),
    })
    mock_feature.bpm = 128.0
    mock_feature.bpm_confidence = 0.95
    uow.stem_features = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(return_value=[mock_feature])

    payload = json.loads(await track_deep_features(id=1, uow=uow))

    assert payload["track_id"] == 1
    assert "original" in payload["stems"]
    assert payload["stems"]["original"]["bpm"] == 128.0


@pytest.mark.asyncio
async def test_track_structure_returns_sections() -> None:
    from app.resources.track_deep import track_structure

    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(
        return_value=[{"id": 10, "section_type": 1, "start_ms": 0, "end_ms": 32000, "energy": 0.5}]
    )

    payload = json.loads(await track_structure(id=1, uow=uow))

    assert payload["track_id"] == 1
    assert len(payload["sections"]) == 1
    assert payload["sections"][0]["id"] == 10


@pytest.mark.asyncio
async def test_track_structure_empty_when_no_sections() -> None:
    from app.resources.track_deep import track_structure

    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_track_sections = AsyncMock(return_value=[])

    payload = json.loads(await track_structure(id=1, uow=uow))

    assert payload["track_id"] == 1
    assert payload["sections"] == []


@pytest.mark.asyncio
async def test_track_waveform_returns_bytes() -> None:
    from unittest.mock import patch

    from app.resources.track_deep import track_waveform

    uow = MagicMock()
    mock_client = MagicMock()
    mock_client.download = AsyncMock(return_value=b'{"samples": []}')

    with (
        patch("app.providers.supabase.config.SupabaseStorageSettings") as mock_settings_cls,
        patch("app.providers.supabase.storage_client.SupabaseStorageClient", return_value=mock_client),
    ):
        mock_settings = MagicMock()
        mock_settings.url = "http://test"
        mock_settings.service_key = "test-key"
        mock_settings_cls.return_value = mock_settings

        result = await track_waveform(id=1, uow=uow)

    parsed = json.loads(result)
    assert parsed == {"samples": []}
