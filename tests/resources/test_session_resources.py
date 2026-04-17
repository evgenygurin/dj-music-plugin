"""session:// resource tests.

Module-level xfail until Phase 5 server wiring. Some tests also need a
test-only helper tool (_test_set_session_id) that will be registered in
Phase 5.
"""

from __future__ import annotations

import json

import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xfail(
        reason="Phase 5 server wiring: FastMCP app composition + session_id helper",
        strict=False,
    ),
]


async def test_set_draft_empty_on_fresh_session(client: object) -> None:
    result = await client.read_resource("session://set-draft")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["tracks"] == []
    assert payload["template_name"] is None


async def test_set_draft_reflects_updates(client: object, session_store: object) -> None:
    sid_res = await client.call_tool("_test_set_session_id", {})  # type: ignore[attr-defined]
    sid = sid_res.data
    session_store.update_draft(sid, tracks=[1, 2], template_name="classic_60")  # type: ignore[attr-defined]
    result = await client.read_resource("session://set-draft")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["tracks"] == [1, 2]
    assert payload["template_name"] == "classic_60"


async def test_tool_history_empty_initially(client: object) -> None:
    result = await client.read_resource("session://tool-history")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["entries"] == []


async def test_energy_trend_default(client: object) -> None:
    result = await client.read_resource("session://energy-trend")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["last_n"] == 20
    assert payload["samples"] == []


async def test_energy_trend_with_limit(client: object, session_store: object) -> None:
    sid_res = await client.call_tool("_test_set_session_id", {})  # type: ignore[attr-defined]
    sid = sid_res.data
    for v in (-10.0, -9.0, -8.0):
        session_store.append_energy(sid, v)  # type: ignore[attr-defined]
    result = await client.read_resource("session://energy-trend?limit=2")  # type: ignore[attr-defined]
    payload = json.loads(result[0].text)
    assert payload["last_n"] == 2
    assert payload["samples"] == [-9.0, -8.0]
