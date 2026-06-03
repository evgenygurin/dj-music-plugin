"""Schema introspection resource tests.

Module-level xfail until Phase 5 wires the FastMCP server and registers
entities + providers in lifespan.
"""

from __future__ import annotations

import json

import pytest

pytestmark = [
    pytest.mark.asyncio,
]


@pytest.mark.xfail(reason="Phase 5 server wiring: registries populated by lifespan", strict=False)
async def test_schema_entities_index(client: object) -> None:
    result = await client.read_resource("schema://entities")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert "entities" in payload
    assert "track" in payload["entities"]
    assert "playlist" in payload["entities"]


@pytest.mark.xfail(reason="Phase 5 server wiring: registries populated by lifespan", strict=False)
async def test_schema_entities_track(client: object) -> None:
    result = await client.read_resource("schema://entities/track")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["name"] == "track"
    assert "operations" in payload
    assert "presets" in payload
    assert "view_schema" in payload
    assert payload["view_schema"]["type"] == "object"


async def test_schema_entities_unknown_raises(client: object) -> None:
    with pytest.raises(Exception):
        await client.read_resource("schema://entities/nonsense_entity")  # type: ignore[attr-defined]


@pytest.mark.xfail(reason="Phase 5 server wiring: registries populated by lifespan", strict=False)
async def test_schema_providers_index(client: object) -> None:
    result = await client.read_resource("schema://providers")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert "providers" in payload
    assert "yandex" in payload["providers"]


@pytest.mark.xfail(reason="Phase 5 server wiring: registries populated by lifespan", strict=False)
async def test_schema_provider_yandex(client: object) -> None:
    result = await client.read_resource("schema://providers/yandex")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["name"] == "yandex"
    assert "entities_supported" in payload
    assert "operations" in payload
    assert payload["operations"]["search"] is True


async def test_schema_provider_unknown_raises(client: object) -> None:
    with pytest.raises(Exception):
        await client.read_resource("schema://providers/spotify")  # type: ignore[attr-defined]
