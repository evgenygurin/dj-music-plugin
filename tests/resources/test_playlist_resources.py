"""Playlist resource tests.

Like Chunk A's track tests, these depend on Phase 5 server wiring
(``build_mcp_app_for_tests``) + completed repository surface. Module-level
``xfail`` until Phase 5.
"""

from __future__ import annotations

import json

import pytest

pytestmark = [
    pytest.mark.asyncio,
]


@pytest.mark.xfail(
    reason="Phase 5 server wiring: FastMCP app composition + repo surface",
    strict=False,
)
async def test_read_playlist_summary(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://playlists/10")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["id"] == 10
    assert payload["name"] == "Test PL"
    assert "tracks" not in payload


@pytest.mark.xfail(
    reason="Phase 5 server wiring: FastMCP app composition + repo surface",
    strict=False,
)
async def test_read_playlist_with_tracks(client: object, seeded_db: object) -> None:
    result = await client.read_resource(  # type: ignore[attr-defined]
        "local://playlists/10?include_tracks=true"
    )
    payload = json.loads(result[0].text)
    assert payload["id"] == 10
    assert isinstance(payload.get("tracks"), list)
    assert len(payload["tracks"]) == 3
    assert payload["tracks"][0]["track_id"] == 1


async def test_read_playlist_missing_raises(client: object) -> None:
    with pytest.raises(Exception):
        await client.read_resource("local://playlists/99999")  # type: ignore[attr-defined]


@pytest.mark.xfail(
    reason="Phase 5 server wiring: FastMCP app composition + repo surface",
    strict=False,
)
async def test_playlist_audit(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://playlists/10/audit")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["playlist_id"] == 10
    assert payload["total_tracks"] == 3
    assert "passed" in payload and "failed" in payload
    assert isinstance(payload["per_track"], list)
    assert len(payload["per_track"]) == 3
