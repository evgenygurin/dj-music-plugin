"""Reusable Pydantic type aliases for MCP tool parameters.

Claude Code and some HTTP MCP transports wire ``dict[str, Any]`` tool
parameters as JSON strings instead of native objects. A plain
``dict[str, Any]`` annotation then crashes on Pydantic validation
with ``Input should be a valid dictionary [type=dict_type]``.

``JsonDict`` and ``JsonDictOrNone`` transparently coerce a JSON string
to a dict before validation, so tools can keep declaring the natural
type and still accept both calling conventions.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import BeforeValidator


def _coerce_json_dict(v: Any) -> Any:
    """Parse a JSON string into a dict; pass through everything else."""
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValueError(f"expected JSON object, got invalid JSON: {exc}") from exc
        if parsed is not None and not isinstance(parsed, dict):
            raise ValueError(f"expected JSON object, got {type(parsed).__name__}")
        return parsed
    return v


JsonDict = Annotated[dict[str, Any], BeforeValidator(_coerce_json_dict)]
JsonDictOrNone = Annotated[dict[str, Any] | None, BeforeValidator(_coerce_json_dict)]
