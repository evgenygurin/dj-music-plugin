from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.set_design_data import set_design_data
from app.shared.errors import NotFoundError


@pytest.mark.asyncio
async def test_unknown_set_raises_not_found() -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await set_design_data(id=999, uow=uow)


@pytest.mark.asyncio
async def test_set_with_no_versions_raises_not_found() -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(
        return_value=MagicMock(
            id=100,
            name="Hypnotic Warehouse 130",
            description=None,
            target_duration_ms=5_400_000,
            target_bpm_min=126.0,
            target_bpm_max=132.0,
            target_energy_arc=None,
            template_name="roller_90",
            source_playlist_id=None,
            ym_playlist_id=None,
        )
    )
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await set_design_data(id=100, uow=uow)


@pytest.mark.asyncio
async def test_set_and_version_blocks_present(monkeypatch: pytest.MonkeyPatch) -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    set_mock = MagicMock(
        id=100,
        description="test set",
        target_duration_ms=5_400_000,
        target_bpm_min=126.0,
        target_bpm_max=132.0,
        target_energy_arc=None,
        template_name="roller_90",
        source_playlist_id=None,
        ym_playlist_id=None,
    )
    set_mock.name = "Hypnotic Warehouse 130"
    uow.sets.get = AsyncMock(return_value=set_mock)
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(
        return_value=MagicMock(
            id=1000, set_id=100, label="v149", generator_run_meta=None, quality_score=0.79
        )
    )
    uow.set_versions.get_items = AsyncMock(return_value=[])
    uow.tracks = MagicMock()
    uow.tracks.get_many = AsyncMock(return_value={})
    uow.track_features = MagicMock()
    uow.track_features.filter = AsyncMock(return_value=MagicMock(items=[]))
    uow.transitions = MagicMock()
    uow.transitions.get_pairs_batch = AsyncMock(return_value={})

    monkeypatch.setattr(
        "app.resources.set_design_data.gather_render_studio",
        AsyncMock(
            return_value={
                "version_id": 1000,
                "n_tracks": 0,
                "target_bpm": None,
                "beatgrid": [],
                "job": None,
                "timeline": [],
                "diagnostics": [],
            }
        ),
    )

    payload = json.loads(await set_design_data(id=100, uow=uow))

    assert payload["set"]["id"] == 100
    assert payload["set"]["name"] == "Hypnotic Warehouse 130"
    assert payload["version"]["id"] == 1000
    assert payload["version"]["label"] == "v149"
    assert payload["version"]["quality_score"] == 0.79
    assert payload["tracks"] == []
    assert payload["transitions"] == []
    assert payload["render"]["version_id"] == 1000
