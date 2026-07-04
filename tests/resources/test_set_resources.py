"""Set resource tests.

Module-level xfail until Phase 5 server wiring + repo surface complete.
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


async def test_set_summary(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/summary")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["template_name"] == "classic_60"
    assert payload["version_count"] == 1
    assert payload["latest_version_id"] == 1000


async def test_set_tracks_view(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/tracks")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["version_id"] == 1000
    assert len(payload["tracks"]) == 3


async def test_set_transitions_view(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/transitions")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert len(payload["transitions"]) == 2


async def test_set_full_view(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/full")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert "summary" in payload and "tracks" in payload and "transitions" in payload


async def test_set_unknown_view_raises(client: object, seeded_db: object) -> None:
    with pytest.raises(Exception):
        await client.read_resource("local://sets/100/nonsense")  # type: ignore[attr-defined]


async def test_set_cheatsheet_default_version(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/cheatsheet")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["version_id"] == 1000
    assert len(payload["lines"]) == 3
    assert payload["lines"][0]["position"] == 1


async def test_set_cheatsheet_with_version(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/cheatsheet?version=1000")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["version_id"] == 1000


async def test_set_narrative(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/narrative")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert isinstance(payload["narrative"], str)


async def test_set_review(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/review")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert "weak_transitions" in payload and "hard_conflicts" in payload


async def test_set_review_with_version(client: object, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/review?version=1000")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["version_id"] == 1000


async def test_set_review_version_from_other_set_raises(client: object, seeded_db: object) -> None:
    with pytest.raises(Exception):
        # version 9999 does not belong to set 100
        await client.read_resource("local://sets/100/review?version=9999")  # type: ignore[attr-defined]


async def test_set_versions_compare(client: object, seeded_db: object) -> None:
    result = await client.read_resource(  # type: ignore[attr-defined]
        "local://sets/100/versions/compare/1000/1000"
    )
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["delta"] == 0.0
    assert payload["changed_positions"] == []
