---
description: MCP tool implementation patterns (FastMCP v3) — v1 layout
globs: app/tools/**/*.py
---

# MCP Tools (v1)

v1 has **14 generic tool dispatchers** (6 entity CRUD + 3 provider + 2 compute
+ 1 sync + `unlock_namespace` + `tool_invoke`) plus **6 Prefab UI tools**
(`app/tools/ui/`) — 20 tools total. No narrow per-operation tools.
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
- **Visibility (current state).** `DISABLED_NAMESPACE_TAGS` in
  `app/server/visibility.py` is an empty frozenset — **every namespace
  is visible at startup**. Rationale: Claude Code does not always honour
  `notifications/tools/list_changed` mid-session, so a server-side
  `mcp.disable(tags=...)` would hide tools without the client knowing
  they became unlockable. `unlock_namespace` still exists for clients
  that do honour the notification and for audit-log workflows.
  `KNOWN_NAMESPACES` (advertised via `unlock_namespace`):
  `crud:destructive`, `provider:write`, `sync`, `ui:read`.

## Prefab Apps (UI tools)

- v1.0.3+ ships 6 Prefab UI tools under `app/tools/ui/` (see
  `docs/tool-catalog.md` § UI / Prefab Apps).
- Each UI tool carries `meta={"ui": True}` — standalone-decorator
  equivalent of `@mcp.tool(app=True)`. FastMCP auto-registers a
  `ui://` renderer resource per tool at startup.
- Tags: `{"namespace:ui:read", "ui", "read"}`. The namespace is in
  `KNOWN_NAMESPACES` but not in `DISABLED_NAMESPACE_TAGS` — always
  visible.
- Tools must ALWAYS provide a JSON fallback: call `supports_ui(ctx)`
  from `app/tools/ui/_fallback.py`; when False, return a Pydantic
  model (one per UI tool, defined in `_fallback.py`) so non-Prefab
  clients still receive structured data.
- Add new UI tools to `ALWAYS_VISIBLE_TOOLS` in
  `app/server/transforms.py` — otherwise `BM25SearchTransform` hides
  them behind a BM25 search query.
- Reuse existing handlers / repositories / domain via `Depends()`.
  Never duplicate business logic in a UI tool.
- Palette constants live in `app/shared/ui_colors.py` — single
  source of truth for UI tool colors.

## FK gates + validation envelopes (v1.3.7)

- **FK gate is auto-derived.** `app/tools/entity/_fk_gate.py:validate_fk_constraints(uow, config, validated, partial_keys=...)` runs before any `entity_create` / `entity_update` persist. `EntityConfig.fk_constraints` is built at `register_default_entities()` time from `cls.__table__.foreign_keys ∩ Create/Update schema fields` — zero manual declarations, drift-impossible. Handler-only fields not present as columns (e.g. `TrackCreate.playlist_id`) live in `_HANDLER_ONLY_FKS` override map.
- **Pydantic → Domain error translation.** `entity_create` / `entity_update` wrap raw `pydantic.ValidationError` into typed `app.shared.errors.ValidationError("invalid payload for entity 'X': ...")` so production envelopes (`mask_details=True`) stay informative instead of collapsing to a blank `"internal error"`.
- **`DomainErrorMiddleware`** wraps `on_read_resource` + `on_get_prompt` envelopes in addition to tools — `NotFoundError` from a resource template surfaces as `"not found: ..."`, not `"internal error: Error reading resource ..."`.
- **`AggregateResult.value`** union has `bool` BEFORE `int` so `entity_aggregate(entity="track_features", operation="distinct", field="variable_tempo")` returns `[false, true]` (not `[0, 1]`).
- **Server-side validation gates** (each returns typed `ValidationError`): `entity_get.include_relations` rejects typos; `local://tracks/{id}/suggest_next?energy_direction` ∈ `{up, down, flat, None}`; `transition.scoring_profile` against `uow.scoring_profiles.get_by_name`; `transition.fx_type` against `NeuralMixTransition` enum; `transition.persist=false` honoured by handler; `sequence_optimize.pinned` not in pool / `excluded` covering full pool — typed reject; `ui_score_pool_matrix` rejects duplicate ids; `ui_transition_score` rejects `from == to`; `unlock_namespace` accepts `ui:read`; `entity_update(entity="set")` enforces BPM range invariant on partial updates.
- **`provider_read.id`** accepts `int | str` (YM track IDs are numeric). `YandexAdapter.read("track_batch", ...)` accepts both canonical `track_ids` and legacy `ids`; numeric IDs are stringified.

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
- `entity_create(entity="set_version", ...)` handler schema is strict
  (`extra="forbid"`): only `set_id`, `label`, `track_order`,
  `quality_score?`, `generator_run_meta?` are accepted. `algorithm` /
  `template` / `pinned` / `excluded` belong to `sequence_optimize`,
  not the `set_version_build` handler.
