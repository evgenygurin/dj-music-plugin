"""BeatportAdapter tests — Provider protocol conformance, no network."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.providers.beatport.adapter import BeatportAdapter, normalize_track
from app.providers.beatport.client import SubscriptionRequiredError
from app.registry.provider import Provider
from app.shared.errors import ValidationError

_RAW_TRACK = {
    "id": 3116788,
    "name": "Structure",
    "mix_name": "Original Mix",
    "bpm": 126,
    "isrc": "GBYNV1100245",
    "length_ms": 508066,
    "artists": [{"name": "Patrick Siech"}],
    "remixers": [],
    "genre": {"id": 6, "name": "Techno (Peak Time / Driving)"},
    "sub_genre": None,
    "key": {"camelot_number": 5, "camelot_letter": "A", "name": "C Minor"},
    "release": {"name": "15 Years Of Drumcode", "label": {"name": "Drumcode"}},
    "slug": "structure",
}


@pytest.fixture
def mock_client() -> AsyncMock:
    c = AsyncMock()
    c.get_track.return_value = _RAW_TRACK
    c.search.return_value = {"tracks": [_RAW_TRACK], "count": 1}
    c.get_account.return_value = {"username": "goldmeat93", "feature": []}
    return c


def test_normalize_track_extracts_genre_and_camelot() -> None:
    n = normalize_track(_RAW_TRACK)
    assert n["genre"] == "Techno (Peak Time / Driving)"
    assert n["camelot"] == "5A"
    assert n["bpm"] == 126
    assert n["label"] == "Drumcode"
    assert n["isrc"] == "GBYNV1100245"


def test_adapter_satisfies_protocol(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    assert isinstance(adapter, Provider)
    assert adapter.name == "beatport"
    assert "track_match" in adapter.entities_supported


async def test_read_track_by_id(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    out = await adapter.read("track", "3116788", {})
    assert out["genre"].startswith("Techno")
    assert out["camelot"] == "5A"


async def test_read_track_requires_id(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    with pytest.raises(ValidationError):
        await adapter.read("track", None, {})


async def test_track_match_high_confidence(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    out = await adapter.read(
        "track_match",
        None,
        {"artist": "Patrick Siech", "title": "Structure", "bpm": 126, "duration_ms": 508000},
    )
    assert out["matched"] is True
    assert out["confidence"] == "high"
    assert out["genre"].startswith("Techno")
    assert out["beatport_id"] == 3116788
    assert out["bpm"] == 126
    assert out["camelot"] == "5A"
    assert out["length_ms"] == 508066
    assert out["isrc"] == "GBYNV1100245"
    assert out["release"] == "15 Years Of Drumcode"
    assert out["label"] == "Drumcode"


async def test_track_match_requires_title(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    with pytest.raises(ValidationError):
        await adapter.read("track_match", None, {"artist": "X"})


async def test_unknown_entity_raises(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    with pytest.raises(ValidationError):
        await adapter.read("playlist", "1", {})


async def test_search_returns_normalized(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    out = await adapter.search("Structure", "tracks", 5)
    assert out["tracks"][0]["genre"].startswith("Techno")


async def test_write_is_read_only(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    with pytest.raises(ValidationError):
        await adapter.write("track", "x", {})


async def test_download_requires_subscription(mock_client: AsyncMock) -> None:
    adapter = BeatportAdapter(client=mock_client)
    with pytest.raises(SubscriptionRequiredError):
        await adapter.download_audio("3116788")
