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

## Lifespan context key collisions

`db_lifespan | provider_lifespan | ...` merges yielded dicts left→right. Later lifespans overwrite earlier on key conflict. Reserved keys: `db_engine`, `db_session_factory`, `provider_registry`, `ym_client`, `analyzer_registry`, `transition_cache`. Use unique keys in new lifespans.

## `@asynccontextmanager` lifespans can't compose with `|`

Legacy `@asynccontextmanager` lifespans aren't composable with `|` directly. Wrap with `ContextManagerLifespan`:
```python
from fastmcp.server.lifespan import ContextManagerLifespan
combined = ContextManagerLifespan(legacy_lifespan) | new_lifespan
```

## `FileSystemProvider` scans at construction

Tool/resource/prompt discovery happens when `FastMCP(providers=[FileSystemProvider(...)])` is called. Adding a new `@tool` file after construction has no effect — server must restart to discover it.
