---
description: General Python gotchas not tied to a specific domain
globs: "**/*.py"
---

# General Python Gotchas

## `from __future__ import annotations`

Makes all annotations strings at runtime. If a function needs the actual type at runtime (e.g., `TrackFeatures()` as a default), import the type normally — don't rely on the string annotation.

## Circular imports

repos→services circular imports: use `TYPE_CHECKING` guard + lazy import inside the method body:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.track import TrackService

class TrackRepo:
    def method(self) -> None:
        from app.services.track import TrackService  # lazy
        ...
```

## Ruff removes unused imports

Ruff auto-removes imports that aren't used yet. When adding an import + its usage, do both in a single edit — don't add the import first and the usage later.

## `get_context()` outside request raises RuntimeError

`get_context()` from `fastmcp.server.dependencies` only works inside a live MCP request. Do NOT call it at module level, in `__init__`, or in non-request code paths — raises `RuntimeError`.

## Middleware `fastmcp_context` is None during initialization

`MiddlewareContext.fastmcp_context` is `None` for `on_message` / `on_request` hooks fired before the MCP session handshake completes. Check `if context.fastmcp_context:` before accessing it in custom middleware.
