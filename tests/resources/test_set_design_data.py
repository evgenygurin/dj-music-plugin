from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources._feature_catalog import TRACK_FEATURE_CATALOG
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


@pytest.mark.asyncio
async def test_tracks_block_has_labeled_features(monkeypatch: pytest.MonkeyPatch) -> None:
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
    uow.set_versions.get_latest = AsyncMock(
        return_value=MagicMock(
            id=1000, set_id=100, label="v149", generator_run_meta=None, quality_score=0.79
        )
    )
    uow.set_versions.get_items = AsyncMock(
        return_value=[
            MagicMock(
                track_id=1,
                sort_index=0,
                transition_id=None,
                out_section_id=None,
                in_section_id=None,
                mix_in_point_ms=0,
                mix_out_point_ms=224_000,
                planned_eq=None,
                notes=None,
                pinned=False,
            )
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.get_many = AsyncMock(
        return_value={1: MagicMock(id=1, title="Deconstructive Society")}
    )

    feature_row = MagicMock()
    feature_row.track_id = 1
    for name in TRACK_FEATURE_CATALOG:
        if name == "track_id":
            continue
        setattr(feature_row, name, None)
    feature_row.bpm = 130.0
    feature_row.mood = "hypnotic"

    uow.track_features = MagicMock()
    uow.track_features.filter = AsyncMock(return_value=MagicMock(items=[feature_row]))
    uow.transitions = MagicMock()
    uow.transitions.get_pairs_batch = AsyncMock(return_value={})

    monkeypatch.setattr(
        "app.resources.set_design_data.gather_render_studio",
        AsyncMock(
            return_value={
                "version_id": 1000,
                "n_tracks": 1,
                "target_bpm": 130.0,
                "beatgrid": [],
                "job": None,
                "timeline": [],
                "diagnostics": [],
            }
        ),
    )

    payload = json.loads(await set_design_data(id=100, uow=uow))
    tracks = payload["tracks"]

    assert len(tracks) == 1
    track = tracks[0]
    assert track["position"] == 0
    assert track["title"] == "Deconstructive Society"
    assert track["mix_out_point_ms"] == 224_000
    assert track["features"]["bpm"]["value"] == 130.0
    assert track["features"]["bpm"]["label"] == TRACK_FEATURE_CATALOG["bpm"]["label"]
    assert track["features"]["mood"]["value"] == "hypnotic"
