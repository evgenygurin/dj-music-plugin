"""Static MCP tool discovery used by the HTTP wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolRegistry:
    """Cached MCP tool metadata for discovery and HTTP validation."""

    tools: list[dict[str, Any]]

    @classmethod
    def discover(cls, controllers_dir: Path | None = None) -> ToolRegistry:
        """Discover MCP tools without starting the full server lifespan."""
        from fastmcp.server.providers.filesystem_discovery import discover_and_import
        from fastmcp.tools import Tool

        mcp_dir = controllers_dir or (Path(__file__).resolve().parents[4] / "app" / "controllers")
        result = discover_and_import(mcp_dir)

        tools: list[dict[str, Any]] = []
        for _path, component in result.components:
            if not isinstance(component, Tool):
                continue
            tools.append(
                {
                    "name": component.name,
                    "description": component.description or "",
                    "tags": sorted(component.tags) if component.tags else [],
                    "annotations": (
                        component.annotations.model_dump(exclude_none=True)
                        if component.annotations
                        else None
                    ),
                    "input_schema": component.parameters or {},
                    "timeout": component.timeout,
                }
            )

        tools.sort(key=lambda tool: tool["name"])
        return cls(tools=tools)

    def list_tools(self, tag: str | None = None) -> list[dict[str, Any]]:
        """List tools, optionally filtering by tag."""
        if tag is None:
            return list(self.tools)
        return [tool for tool in self.tools if tag in tool.get("tags", [])]

    def get_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Return tool metadata by name."""
        for tool in self.tools:
            if tool["name"] == tool_name:
                return tool
        return None

    def get_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Return a tool's input schema by name."""
        tool = self.get_tool(tool_name)
        return None if tool is None else tool["input_schema"]
