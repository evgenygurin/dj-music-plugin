"""Transition resource tests.

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


async def test_transition_score_persisted(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://transition/1/2/score")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["from_track_id"] == 1
    assert payload["to_track_id"] == 2
    assert "overall" in payload
    assert "components" in payload
    assert "hard_reject" in payload


async def test_transition_score_missing_features_raises(client: object) -> None:
    with pytest.raises(Exception):
        await client.read_resource("local://transition/999/888/score")  # type: ignore[attr-defined]


async def test_transition_explain(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://transition/1/2/explain")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["from_track_id"] == 1
    assert payload["to_track_id"] == 2
    assert isinstance(payload["narrative"], str)
    assert isinstance(payload["suggestions"], list)
