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


def _coerce_json_list(v: Any) -> Any:
    """Parse a JSON-encoded list string into a list; pass through otherwise.

    The same transport quirk that wraps dicts as JSON strings also affects
    lists: MCP shims that stringify complex arguments send ``"[1,2,3]"`` when
    the tool declares ``list[int]``. Pydantic then crashes with
    ``Input should be a valid list``. Normalising at the boundary keeps the
    natural type declaration usable from every MCP client.
    """
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValueError(f"expected JSON array, got invalid JSON: {exc}") from exc
        if parsed is not None and not isinstance(parsed, list):
            raise ValueError(f"expected JSON array, got {type(parsed).__name__}")
        return parsed
    return v


JsonIntList = Annotated[list[int], BeforeValidator(_coerce_json_list)]
JsonIntListOrNone = Annotated[list[int] | None, BeforeValidator(_coerce_json_list)]
JsonStrList = Annotated[list[str], BeforeValidator(_coerce_json_list)]
JsonStrListOrNone = Annotated[list[str] | None, BeforeValidator(_coerce_json_list)]
