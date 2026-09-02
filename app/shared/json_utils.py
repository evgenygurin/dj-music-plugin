"""Helpers for JSON serialization of FastMCP structured outputs.

FastMCP v3 returns Pydantic BaseModels in `result.data` (hydrated) and raw dicts
in `result.structured_content`. Stdlib `json.dumps(result.data)` fails because
json doesn't know BaseModel. Use these helpers per
https://github.com/prefecthq/fastmcp/blob/main/docs/clients/tools.mdx
"""

from __future__ import annotations

import json
from typing import Any


def pydantic_json_dumps(obj: Any, **kwargs: Any) -> str:
    """json.dumps that handles Pydantic BaseModel / RootModel via model_dump.

    Example:
        res = await client.call_tool("render_validate_grid", {"version_id": 248})
        print(pydantic_json_dumps(res.data, indent=2, ensure_ascii=False))
        # equivalent to json.dumps(res.structured_content, ...) or
        # json.dumps(res.data.model_dump(mode="json"), ...)
    """

    def _default(o: Any) -> Any:
        if hasattr(o, "model_dump"):
            try:
                return o.model_dump(mode="json")
            except Exception:
                return o.model_dump()
        # Fallback for other non-serializable types
        return str(o)

    return json.dumps(obj, default=_default, **kwargs)


def to_jsonable(obj: Any) -> Any:
    """Convert Pydantic model (or any) to JSON-serializable Python primitives."""
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except Exception:
            return obj.model_dump()
    return obj
