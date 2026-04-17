---
description: MCP tool implementation patterns (FastMCP v3) — v1 layout
globs: app/tools/**/*.py
---

# MCP Tools (v1)

v1 has **13 generic tool dispatchers** — no narrow per-operation tools.
Add capability by extending `EntityRegistry`, `ProviderRegistry`, or a
handler — not by writing a new `@tool`.

## Canonical structure

- All `@tool` decorators live under `app/tools/` (subdirs organizational).
- Use the standalone `@tool` decorator from `fastmcp` — FileSystemProvider
  auto-discovers recursively.
- One tool per file. File name matches tool name.
- Tool signature pattern:

```python
from typing import Annotated, Any
from fastmcp import tool, Context, CurrentContext, Depends
from pydantic import Field

from app.server.di import get_uow
from app.repositories.unit_of_work import UnitOfWork

@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description="Short (<50 words) — details in param Fields.",
)
async def entity_list(
    entity: Annotated[EntityName, Field(description="Entity type name")],
    filters: Annotated[dict[str, Any] | None, Field(...)] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> EntityListResult:
    ...
```

## Rules

- **Return typed Pydantic models** (see `app/schemas/tool_responses.py`).
- **Never commit** — UoW commits via DI wrapper. Inside the tool call
  `uow.flush()` if you need generated IDs before returning.
- **Dispatch via registries.** `entity_*` look up `EntityRegistry`;
  `provider_*` look up `ProviderRegistry`. Side-effects on
  create/update/delete go into **handlers** (`app/handlers/`), keyed
  in the entity registry.
- **Tags = namespaces.** `namespace:crud:read`,
  `namespace:crud:write`, `namespace:crud:destructive`,
  `namespace:provider:read`, `namespace:provider:write`,
  `namespace:compute`, `namespace:sync`, `namespace:admin`,
  `namespace:workflow` (for prompts).
- **Annotations** (`readOnlyHint`, `destructiveHint`, `idempotentHint`,
  `openWorldHint`) set on every tool.
- **Descriptions ≤ 50 words**; put detail in parameter
  `Field(description=...)`.
- **No lazy imports** inside function bodies.
- **No `if/elif` chains on action params** — use registry dispatch.
- **Hidden namespaces.** `crud:destructive`, `provider:write`, `sync`
  start locked. `unlock_namespace(namespace="...", action="unlock")`
  fires `notifications/tools/list_changed`.

## Gotchas

- `Depends()`: use `param=Depends(factory)`, NOT `Annotated[Type,
  Depends(factory)]` — FastMCP doesn't resolve Annotated-Depends.
- `list_page_size` in config must be ≥ total tool count.
- `entity_create(entity="track", ...)` dispatches to `track_import`
  handler that fetches from provider. Plain ORM insert happens only
  for entities without a registered create handler.
- `entity_update(entity="track_features", ...)` dispatches to
  `track_features_reanalyze` — re-runs the tiered pipeline at a
  higher level.
- `sequence_optimize` calls `transition_score_pool` internally when
  features aren't cached — don't require the caller to score first.
