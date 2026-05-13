"""Process-wide fallback storage for lifespan-yielded MCP state.

When in-process callers (unit tests, ad-hoc scripts) invoke
``mcp.call_tool()`` directly, FastMCP does not enter its own lifespan, so
``ctx.request_context.lifespan_context`` is empty and DI factories raise
"X not initialized — check ... composition".

This module is the fallback that ``_read_lifespan`` in ``app/server/di.py``
consults when the typed lifespan_context lookup returns None. Test
fixtures populate the dict by entering the composed MCP lifespan and
copying its yielded keys here.

Stateful by design — process-scoped singleton state. Tests should call
``clear()`` between cases that mutate it.
"""

from __future__ import annotations

from typing import Any

_state: dict[str, Any] = {}


def set_state(key: str, value: Any) -> None:
    _state[key] = value


def get_state(key: str) -> Any:
    return _state.get(key)


def update(items: dict[str, Any]) -> None:
    _state.update(items)


def clear() -> None:
    _state.clear()
