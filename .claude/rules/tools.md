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
- **`entity_get.include_relations` loads for real (v1.6.1).** Each declared relation has a loader in `EntityConfig.relation_loaders` (wired in `app/registry/defaults.py`); the dispatcher attaches the payload under the relation name in `data`, AFTER `fields` projection. Supported: track × `artists|features`, playlist × `items`, set × `versions`, set_version × `items`, audio_file × `beatgrids`. Keys of `relations` and `relation_loaders` must stay in sync — pinned by `tests/tools/entity/test_get_include_relations.py`.
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

### Set-build flow (curate → optimize → version → review)

- **`sequence_optimize` orders the WHOLE pool you pass — it does not
  subset.** Pass exactly the final track list you want in the set (e.g.
  18 ids), not a 100-track candidate pool expecting it to pick ~18. To
  go from a wide pool to an N-track set, curate down to N first (filters
  + manual selection), then optimize ordering.
- **Two different quality numbers.** `sequence_optimize` returns a
  *pre-section* fitness score; `entity_create(entity="set_version")`
  (the `set_version_build` handler) recomputes a **section-aware** score
  that is usually **higher** (it resolves `SectionContext` + builds
  Neural-Mix recipes). Compare versions by the `set_version`
  `quality_score`, not the raw optimizer score.
- **GA maximises pairwise transition quality, NOT the macro energy
  arc.** Left to itself it scatters energy and can park the loudest /
  fastest tracks at the end. The two-thirds rule (global energy peak at
  ~0.6–0.7, local teases at 0.3/0.5, dissolve at the end — see
  `docs/research/2026-06-23-techno-deep-research-and-set-construction.md`
  §3) must be imposed by **hand-ordering / curation** or via a
  `template`; then `set_version_build` re-scores.
  A clean-arc order may score a few points below the GA-optimal order on
  pairwise quality — that gap is the intentional energy contrast the arc
  needs (research rewards sawtooth energy, penalises near-zero variance).
- **`template`-aware fitness fights mood mismatch.** Template slots
  target moods like `driving` / `hypnotic` / `peak_time`, which the
  classifier (catch-all-penalised) rarely assigns to a real
  `acid` / `industrial` / `detroit` crate. Passing `template=roller_90`
  on such a pool *lowers* the score vs no template. For acid/industrial
  rollers, optimize without a template and shape the arc by curation.
- **L2 feature columns that are mostly NULL — don't filter on them.**
  On an L2 library `bpm_confidence` and `true_peak_db` are largely NULL,
  so `bpm_confidence__gte` / `true_peak_db__lte` silently collapse the
  result set (NULL fails `>=`/`<=`). Filter on the L2-populated columns
  instead: `mood`, `bpm`, `key_code`, `energy_mean`, `key_confidence`,
  `variable_tempo`. Verify clipping/peak later, on the L5'd set tracks.
- **`local://sets/{id}/transitions`** carries `overall` + `hard_reject`
  only; for the per-pair Neural-Mix preset + component scores use
  `entity_list(entity="transition", filters={"from_track_id__in": [...],
  "to_track_id__in": [...]})` — there is **no** `set_version_id` filter
  (transitions are keyed by track pair, not by version).

## FastMCP upgrade-watch (pinned `>=3.2.4,<3.4`, current upstream 3.4.2)

Full delta analysis:
`docs/research/2026-07-05-techno-2026-deltas-and-fastmcp-34.md` §6. Load it
before bumping the pin. Tool-surface highlights:

- **`prefab-ui` must be pinned to an exact version** — official docs require it
  (frequent breaking changes); the transitive `fastmcp[apps] → prefab_ui>=0.19`
  violates that. Pin explicitly when upgrading.
- **`ToolError` / `ResourceError` / `PromptError` pierce
  `mask_error_details=True`** — user-facing errors must go through these (or
  `DomainErrorMiddleware`), everything else is masked in prod.
- **`ToolResult(is_error=True)` (3.4.0)** — soft errors returned (not raised)
  that the LLM should see as a result; complements typed `ToolError`.
- **`@tool(timeout=N)`** — standard slow-op guard; incompatible with
  `run_in_thread=False`.
- **Long ops (>120s, e.g. batch MP3 download) → candidate for `task=True`**
  (SEP-1686) instead of UoW rollback on timeout; needs `fastmcp[tasks]` +
  client support (Claude Code support **unconfirmed**). Until then batch under
  the timeout (see `.claude/rules/audio.md` L5-finalization).
- **Per-session visibility** `ctx.enable_components(tags=...)` sends
  `list_changed`, but Claude Code caches the tool list — keep `tool_invoke` as
  the escape hatch; do not rely on `unlock_namespace` mid-session.
- **Component versioning** (`version=` + `VersionFilter`) + **tool
  fingerprinting** (`sha256(tool.key + to_mcp_tool())` manifest) are the
  canonical anti-drift paths for evolving tool contracts across plugin releases.
