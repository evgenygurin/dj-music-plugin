"""JSON-aware override for FastMCP's ``ResourcesAsTools`` transform.

Background
----------
FastMCP's stock ``ResourcesAsTools._make_read_resource_tool`` returns the
resource payload as ``str``. When that string already contains a JSON
document (the common case for ``mime_type="application/json"`` resources
in this codebase), FastMCP wraps the tool return in
``{"result": "<json-string>"}`` because primitive ``str`` returns are
serialized into ``structuredContent`` under the default ``result`` key.

The wire-level payload then carries an inner JSON document quoted as a
string, so every double-quote inside it gets escaped (``\\"``) when the
outer envelope is re-serialized for display. The resource itself is fine
— this is purely a tool-output ergonomics issue for tool-only clients.

This module replaces the ``read_resource`` tool with a variant that
parses the JSON content (when ``mime_type="application/json"``) and
returns a structured Pydantic model. The client now sees a nested
object, not an escaped string.

The list_resources tool is preserved unchanged.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Any

from fastmcp.server.dependencies import get_context
from fastmcp.server.transforms import GetToolNext
from fastmcp.server.transforms.resources_as_tools import ResourcesAsTools
from fastmcp.tools.base import Tool
from fastmcp.utilities.versions import VersionSpec
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    pass

_DEFAULT_ANNOTATIONS = ToolAnnotations(readOnlyHint=True)


class ReadResourceItem(BaseModel):
    """One content item returned by ``read_resource``."""

    model_config = ConfigDict(extra="forbid")

    mime_type: str | None = Field(
        default=None,
        description="MIME type of this content item.",
    )
    data: Any = Field(
        default=None,
        description=(
            "Parsed payload. JSON content is decoded into a native object. "
            "Plain text is forwarded as-is. Binary content is base64-encoded."
        ),
    )
    encoding: str | None = Field(
        default=None,
        description="'base64' for binary content, otherwise omitted.",
    )


class ReadResourceResult(BaseModel):
    """Tool-output envelope for ``read_resource``.

    Returning a Pydantic model (rather than ``str``) makes FastMCP put the
    payload into ``structuredContent`` natively, so JSON resources are not
    re-escaped.
    """

    model_config = ConfigDict(extra="forbid")

    uri: str = Field(description="Resource URI that was read.")
    items: list[ReadResourceItem] = Field(
        description="One entry per ``ResourceContent`` returned by the resource.",
    )


def _normalize_item(content_item: Any) -> ReadResourceItem:
    """Decode a single ``ResourceContent`` for tool output.

    Bytes → base64. Strings:
    - If ``mime_type == application/json``, parse strictly.
    - Otherwise, fall back to best-effort JSON parsing when the payload
      starts with ``{``/``[`` (object or array). This recovers from the
      FastMCP 3.2.4 bug where ``ResourceTemplate.convert_result`` drops
      the resource's declared ``application/json`` mime_type and defaults
      to ``text/plain`` — which would otherwise leave clients with a
      raw escaped JSON string. Plain text payloads are forwarded as-is.
    """
    raw = content_item.content
    mime_type = content_item.mime_type

    if isinstance(raw, bytes):
        return ReadResourceItem(
            mime_type=mime_type,
            data=base64.b64encode(raw).decode("ascii"),
            encoding="base64",
        )

    if isinstance(raw, str):
        if mime_type == "application/json":
            try:
                return ReadResourceItem(mime_type=mime_type, data=json.loads(raw))
            except json.JSONDecodeError:
                return ReadResourceItem(mime_type=mime_type, data=raw)

        stripped = raw.lstrip()
        if stripped[:1] in ("{", "["):
            try:
                parsed = json.loads(raw)
                return ReadResourceItem(mime_type="application/json", data=parsed)
            except json.JSONDecodeError:
                pass

    return ReadResourceItem(mime_type=mime_type, data=raw)


class JSONAwareResourcesAsTools(ResourcesAsTools):
    """Same as ``ResourcesAsTools`` but ``read_resource`` returns a model.

    JSON resources land in ``structuredContent`` as a parsed object, so
    consumers see ``{"items":[{"data":{"set_id":45,...}}]}`` instead of
    a quote-escaped string.
    """

    async def list_tools(self, tools: Sequence[Tool]) -> Sequence[Tool]:
        return [
            *tools,
            self._make_list_resources_tool(),
            self._make_read_resource_tool(),
        ]

    async def get_tool(
        self,
        name: str,
        call_next: GetToolNext,
        *,
        version: VersionSpec | None = None,
    ) -> Tool | None:
        if name == "read_resource":
            return self._make_read_resource_tool()
        if name == "list_resources":
            return self._make_list_resources_tool()
        return await call_next(name, version=version)

    def _make_read_resource_tool(self) -> Tool:
        async def read_resource(
            uri: Annotated[str, "The URI of the resource to read."],
        ) -> ReadResourceResult:
            """Read a resource by its URI.

            For static resources, provide the exact URI. For templated
            resources, provide the URI with template parameters filled in.

            Returns a structured envelope: every ``ResourceContent`` item
            is normalised — JSON payloads are parsed into native objects,
            text is returned as-is, binary content is base64-encoded with
            ``encoding="base64"``.
            """
            ctx = get_context()
            result = await ctx.fastmcp.read_resource(uri)
            items = [_normalize_item(item) for item in result.contents]
            return ReadResourceResult(uri=str(uri), items=items)

        return Tool.from_function(fn=read_resource, annotations=_DEFAULT_ANNOTATIONS)
