"""Track resource tests — URI template matching + JSON payload shape.

All tests in this module depend on the ``client`` + ``seeded_db`` fixtures,
which require Phase 5 server wiring (``build_mcp_app_for_tests`` and
completed repository surface: ``create(id=...)``, ``add_items``,
``list_from``, ``latest_version``, ``search_by_bpm_range``).

They are marked ``xfail`` module-wide until Phase 5 composes the
FastMCP server and completes those repository methods. The Phase 4 PR
ships the resource implementations in ``app/v2/resources/track.py``;
Phase 5 flips these to ``passed``.
"""

from __future__ import annotations

import json

import pytest

pytestmark = [
    pytest.mark.asyncio,
]


@pytest.mark.xfail(
    reason="Phase 5 server wiring: FastMCP app composition + repo surface", strict=False
)
async def test_read_track_by_id(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1")  # type: ignore[attr-defined]
    assert len(result) == 1
    payload = json.loads(result[0].text)
    assert payload["id"] == 1
    assert payload["title"] == "Alpha"
    assert result[0].mimeType == "application/json"


async def test_read_track_features(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1/features")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["track_id"] == 1
    assert payload["bpm"] == 124.0
    assert payload["mood"] == "hypnotic"


async def test_read_track_audit(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1/audit")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["track_id"] == 1
    assert "passed" in payload
    assert "violations" in payload
    assert "criteria_checked" in payload


async def test_read_track_audit_raises_for_missing(client: object) -> None:
    with pytest.raises(Exception):
        await client.read_resource("local://tracks/99999/audit")  # type: ignore[attr-defined]


async def test_suggest_next_default_limit(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1/suggest_next")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["from_track_id"] == 1
    assert payload["limit"] == 10
    assert "candidates" in payload


async def test_suggest_next_with_query_params(client: object, seeded_db: object) -> None:
    result = await client.read_resource(  # type: ignore[attr-defined]
        "local://tracks/1/suggest_next?limit=3&energy_direction=up"
    )
    payload = json.loads(result[0].text)
    assert payload["limit"] == 3
    assert payload["energy_direction"] == "up"


async def test_suggest_replacement(client: object, seeded_db: object) -> None:
    result = await client.read_resource(  # type: ignore[attr-defined]
        "local://tracks/2/suggest_replacement/100/2"
    )
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["position"] == 2
