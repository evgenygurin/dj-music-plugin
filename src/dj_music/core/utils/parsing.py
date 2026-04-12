"""JSON parameter parsing for MCP tool arguments.

Some MCP clients (e.g. Claude Code) send list/dict parameters as JSON strings
instead of parsed objects. FastMCP does NOT auto-parse these. This module
provides helpers to normalize incoming parameters.

Usage in tools:
    from dj_music.core.utils.parsing import ensure_list, ensure_dict

    @tool(...)
    async def my_tool(data: dict | str | None = None) -> dict:
        data = ensure_dict(data)
"""

from __future__ import annotations

import json
from typing import Any


def ensure_list(value: Any) -> list[Any]:
    """Parse value to list. Handles: list (passthrough), JSON string, None -> []."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        # Single comma-separated string? e.g. "1,2,3"
        if "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value]
    return [value]


def ensure_dict(value: Any) -> dict[str, Any] | None:
    """Parse value to dict. Handles: dict (passthrough), JSON string, None."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None
