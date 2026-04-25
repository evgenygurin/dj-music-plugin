"""Regression tests for ``JSONAwareResourcesAsTools``.

The stock FastMCP ``ResourcesAsTools.read_resource`` returns ``str`` so
JSON resources land in ``structuredContent`` as
``{"result": "<json-string>"}`` — every quote inside gets escaped on the
wire. Our override returns a ``ReadResourceResult`` Pydantic model so
``data`` is a parsed nested object.

Covered cases:
- ``application/json`` resource that returns a JSON string
- ``application/json`` resource that returns a dict (FastMCP auto-encodes)
- ``text/plain`` resource (plain string forwarded as-is)
- malformed JSON content (graceful fallback to raw string, no crash)
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client, FastMCP

from app.server.json_aware_resources import (
    JSONAwareResourcesAsTools,
    ReadResourceResult,
    _normalize_item,
)


def _make_server() -> FastMCP:
    mcp = FastMCP("test-json-aware")

    @mcp.resource("data://json-string", mime_type="application/json")
    def _r_json_string() -> str:
        return json.dumps({"set_id": 45, "tracks": [{"id": 1}, {"id": 2}]})

    @mcp.resource("data://json-dict", mime_type="application/json")
    def _r_json_dict() -> dict[str, object]:
        return {"value": 42, "ok": True, "list": [1, 2, 3]}

    @mcp.resource("data://text", mime_type="text/plain")
    def _r_text() -> str:
        return "плейн-текст без JSON"

    @mcp.resource("data://malformed", mime_type="application/json")
    def _r_malformed() -> str:
        return "{not: valid json}"

    mcp.add_transform(JSONAwareResourcesAsTools(mcp))
    return mcp


@pytest.mark.asyncio
async def test_json_string_returns_nested_object() -> None:
    """JSON content is decoded into a native dict, not a quoted string."""
    mcp = _make_server()
    async with Client(mcp) as client:
        result = await client.call_tool("read_resource", {"uri": "data://json-string"})
        sc = result.structured_content
        assert sc is not None
        assert sc["uri"] == "data://json-string"
        assert len(sc["items"]) == 1
        item = sc["items"][0]
        assert item["mime_type"] == "application/json"
        # Parsed object — not a string with escaped quotes.
        assert item["data"] == {"set_id": 45, "tracks": [{"id": 1}, {"id": 2}]}
        assert isinstance(item["data"], dict)


@pytest.mark.asyncio
async def test_json_dict_return_is_unwrapped() -> None:
    """Resources returning a dict directly are still decoded once, not twice."""
    mcp = _make_server()
    async with Client(mcp) as client:
        result = await client.call_tool("read_resource", {"uri": "data://json-dict"})
        sc = result.structured_content
        assert sc is not None
        item = sc["items"][0]
        assert item["mime_type"] == "application/json"
        assert item["data"] == {"value": 42, "ok": True, "list": [1, 2, 3]}


@pytest.mark.asyncio
async def test_text_plain_passes_through() -> None:
    """Non-JSON text is forwarded as-is — no parsing, no escape."""
    mcp = _make_server()
    async with Client(mcp) as client:
        result = await client.call_tool("read_resource", {"uri": "data://text"})
        sc = result.structured_content
        assert sc is not None
        item = sc["items"][0]
        assert item["mime_type"] == "text/plain"
        assert item["data"] == "плейн-текст без JSON"


@pytest.mark.asyncio
async def test_template_resource_recovers_lost_mime_type() -> None:
    """FastMCP 3.2.4 drops mime_type on template resources — heuristic recovers it.

    ``ResourceTemplate.convert_result`` calls ``ResourceResult(raw_value)``
    without forwarding ``self.mime_type``, so JSON-string content from
    template resources arrives with ``text/plain``. The transform should
    still parse the body when it looks like JSON.
    """
    mcp = FastMCP("test-template")

    @mcp.resource("data://item/{id}", mime_type="application/json")
    def _r_item(id: str) -> str:
        return json.dumps({"id": id, "title": "Aerial"})

    mcp.add_transform(JSONAwareResourcesAsTools(mcp))

    async with Client(mcp) as client:
        result = await client.call_tool("read_resource", {"uri": "data://item/45"})
        sc = result.structured_content
        assert sc is not None
        item = sc["items"][0]
        # Heuristic upgraded the mime_type back to application/json.
        assert item["mime_type"] == "application/json"
        assert item["data"] == {"id": "45", "title": "Aerial"}


@pytest.mark.asyncio
async def test_text_plain_starting_with_brace_safely_parses() -> None:
    """A text/plain payload that happens to be valid JSON is upgraded.

    This is acceptable because (a) the wire payload is identical, and
    (b) clients parsing structured content benefit from the nested object.
    A truly textual payload would not start with ``{`` or ``[``.
    """
    mcp = FastMCP("test-heuristic")

    @mcp.resource("data://anything", mime_type="text/plain")
    def _r() -> str:
        return '{"ok": true, "n": 7}'

    mcp.add_transform(JSONAwareResourcesAsTools(mcp))
    async with Client(mcp) as client:
        result = await client.call_tool("read_resource", {"uri": "data://anything"})
        item = result.structured_content["items"][0]
        assert item["mime_type"] == "application/json"
        assert item["data"] == {"ok": True, "n": 7}


@pytest.mark.asyncio
async def test_malformed_json_falls_back_to_raw_string() -> None:
    """Bad JSON in an application/json resource doesn't crash the tool."""
    mcp = _make_server()
    async with Client(mcp) as client:
        result = await client.call_tool("read_resource", {"uri": "data://malformed"})
        sc = result.structured_content
        assert sc is not None
        item = sc["items"][0]
        assert item["data"] == "{not: valid json}"


def test_envelope_schema_is_pydantic_model() -> None:
    """``ReadResourceResult`` is a Pydantic model so FastMCP can serialize it."""
    envelope = ReadResourceResult(uri="data://x", items=[])
    assert envelope.model_dump() == {"uri": "data://x", "items": []}


def test_normalize_item_handles_bytes() -> None:
    """Binary content is base64-encoded with ``encoding='base64'`` marker."""

    class _Stub:
        content = b"\x00\x01\x02\x03"
        mime_type = "application/octet-stream"

    normalized = _normalize_item(_Stub())
    assert normalized.encoding == "base64"
    assert normalized.data == "AAECAw=="
    assert normalized.mime_type == "application/octet-stream"
