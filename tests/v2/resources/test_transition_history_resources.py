"""Transition history resource tests.

Module-level xfail until Phase 5 fixture wiring.
"""

from __future__ import annotations

import json

import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xfail(
        reason="Phase 5 server wiring: FastMCP app composition + repo surface",
        strict=False,
    ),
]


async def test_best_pairs_default_limit(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://transition_history/best_pairs")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["limit"] == 10
    assert isinstance(payload["pairs"], list)


async def test_best_pairs_with_limit(client: object, seeded_db: object) -> None:
    result = await client.read_resource(  # type: ignore[attr-defined]
        "local://transition_history/best_pairs?limit=3"
    )
    payload = json.loads(result[0].text)
    assert payload["limit"] == 3


async def test_best_pairs_with_track_id(client: object, seeded_db: object) -> None:
    result = await client.read_resource(  # type: ignore[attr-defined]
        "local://transition_history/best_pairs?track_id=1"
    )
    payload = json.loads(result[0].text)
    assert "pairs" in payload


async def test_history_default(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://transition_history/history")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["limit"] == 50
    assert isinstance(payload["entries"], list)


async def test_history_with_limit(client: object, seeded_db: object) -> None:
    result = await client.read_resource(  # type: ignore[attr-defined]
        "local://transition_history/history?limit=5"
    )
    payload = json.loads(result[0].text)
    assert payload["limit"] == 5
