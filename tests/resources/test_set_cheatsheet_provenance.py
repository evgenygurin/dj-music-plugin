from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.set import set_cheatsheet
from app.shared.features import TrackFeatures


@pytest.mark.asyncio
async def test_cheatsheet_shows_key_provenance_and_transition_plan() -> None:
    uow = MagicMock()
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(return_value=MagicMock(id=1000, set_id=100))
    uow.set_versions.get_items = AsyncMock(
        return_value=[
            MagicMock(
                track_id=1,
                sort_index=1,
                in_section_id=11,
                out_section_id=12,
                mix_in_point_ms=0,
                mix_out_point_ms=224_000,
            ),
            MagicMock(
                track_id=2,
                sort_index=2,
                in_section_id=21,
                out_section_id=22,
                mix_in_point_ms=0,
                mix_out_point_ms=240_000,
            ),
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(side_effect=[MagicMock(title="A"), MagicMock(title="B")])
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(
        return_value={
            1: TrackFeatures(
                bpm=136.0,
                audio_bpm=135.8,
                beatport_bpm=136.0,
                bpm_source="beatport",
                key_code=8,
                key_source="beatport",
                audio_key_code=14,
                audio_key_confidence=0.55,
                beatport_key="C Minor",
                beatport_camelot="5A",
                beatport_confidence="high",
                integrated_lufs=-10.0,
            ),
            2: TrackFeatures(
                bpm=136.0,
                key_code=10,
                key_source="audio",
                audio_key_code=10,
                audio_key_confidence=0.8,
                integrated_lufs=-9.5,
            ),
        }
    )
    uow.transitions = MagicMock()
    uow.transitions.get_pairs_batch = AsyncMock(
        return_value={
            (1, 2): MagicMock(
                overall_quality=0.87,
                fx_type="drum_swap",
                transition_bars=32,
                hard_reject=False,
            )
        }
    )

    payload = json.loads(await set_cheatsheet(id=100, uow=uow))
    first = payload["lines"][0]

    assert first["key"] == "5A"
    assert first["key_code"] == 8
    assert first["key_source"] == "beatport"
    assert first["audio_key"] == "8A"
    assert first["beatport_key"] == "C Minor"
    assert first["beatport_camelot"] == "5A"
    assert first["key_agreement"] is False
    assert first["bpm_source"] == "beatport"
    assert first["next_transition"] == {
        "to_track_id": 2,
        "overall": 0.87,
        "fx_type": "drum_swap",
        "bars": 32,
        "hard_reject": False,
    }
    assert first["mix_out_point_ms"] == 224_000
