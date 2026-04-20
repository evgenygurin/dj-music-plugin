# DJ Music Plugin — Architecture Blueprint

**Date:** 2026-04-17
**Scope:** Master blueprint for global refactor of `app/`. Supersedes prior scoped specs.
**Status:** Design — awaiting implementation.
**Breaking changes:** allowed (option A — no backward-compat constraints, panel out of scope).
**Successor specs:** Phase 1-7 implementation plans reference this document.

---

## 1. Purpose

The project has grown to 303 Python files, 88 MCP tools, 46 DB tables (15 dead), 7k LOC of services, and muddled layer boundaries. This blueprint defines the canonical target architecture — file structure, naming law, tool/resource/prompt surface, persistence pattern, composition primitives. Every downstream implementation spec (Phase 1 through Phase 7) applies this blueprint to a specific layer.

**Core strategy:** follow FastMCP v3+ conventions, declaratively decompose into atomic tools unified by polymorphism (EntityRegistry, ProviderRegistry, custom handlers), let LLMs compose via prompts / CodeMode / Tool Search — rather than building imperative service/workflow abstractions.

**References:**
- FastMCP v3 docs: <https://github.com/PrefectHQ/fastmcp/tree/main/docs>
- FastMCP v3 examples: <https://github.com/PrefectHQ/fastmcp/tree/main/examples>
- FastMCP v3 release notes: <https://github.com/PrefectHQ/fastmcp/tree/main/v3-notes>
- Product requirements: `REQUIREMENTS.md`
- Current state audit: commit `ce2cd19` (as of 2026-04-17)

---

## 2. Decisions (from brainstorming session 2026-04-17)

| # | Decision | Source |
|---|---|---|
| D1 | **Breaking changes allowed** — no backward-compat shims for MCP tool names, DB schema, or REST endpoints. | User, option A |
| D2 | **Panel untouched** — out of scope for this blueprint. Panel refactor is a separate future project. | User |
| D3 | **Follow FastMCP v3 canonical layout** — `tools/`, `resources/`, `prompts/` at top level, flat within (subdirs are organizational only). | `fastmcp/AGENTS.md`, `src/fastmcp/` structure |
| D4 | **Anchor structure on DB entities** — every aggregate root gets one `models/<entity>.py`, one `repositories/<entity>.py`, one Pydantic schema family. | User |
| D5 | **Polymorphism over proliferation** — 5 generic CRUD tools (`entity_list`, `entity_get`, `entity_create`, `entity_update`, `entity_delete`) + 1 `entity_aggregate` dispatch via `EntityRegistry`. | User |
| D6 | **ProviderRegistry analogous to EntityRegistry** — 3 generic provider tools (`provider_read`, `provider_write`, `provider_search`) + download as `entity_create(entity="audio_file")`. | User |
| D7 | **Custom handlers on create/update/delete** — side-effects (download, analyze, score persist) live as handlers keyed by entity, not as separate tools. | User |
| D8 | **Services layer almost fully removed** — logic lives in tools (via handlers), domain/ (pure compute), prompts (LLM-visible recipes), CodeMode scripts. | User |
| D9 | **Unit of Work** — explicit `UnitOfWork` class, one instance per tool call, injected via `Depends(get_uow)`. DbSession middleware manages lifecycle. | Agreed |
| D10 | **BaseRepository[M]** generic CRUD + Django-style lookups (`bpm__gte`, `mood__in`). Entity-specific methods in subclass. | Agreed |
| D11 | **No GraphQL** — MCP tools are the primary interface; polymorphic CRUD gives 80% of GraphQL's ergonomics for 30% of the code. | User, option "нахуй GraphQL" |
| D12 | **Tool Search (BM25) + Namespace Activation** — ~10 tools always visible, others discoverable / unlockable per session. | FastMCP v3 |
| D13 | **No Domain Events yet** — YAGNI. Add when first real subscriber appears. | Agreed |
| D14 | **Parallel refactor strategy** — build new code under `app/v2/`, migrate in phases, atomic swap at end. Running BFS/L5 campaign must keep working throughout. | Agreed |
| D15 | **Drop dead code**: `app/engines/`, `app/ym/`, `app/infrastructure/`, `app/api/services/ym_audio_proxy.py`, `app/api/services/tool_registry.py`, `app/api/services/signed_url_cache.py`. | User |
| D16 | **Drop 15 dead DB tables**: spotify_\* (×5), beatport_metadata, soundcloud_metadata, embeddings, transition_candidates, dj_saved_loops, dj_cue_points, dj_beatgrid_change_points, dj_set_constraints, dj_set_feedback, labels, track_labels, app_exports. | DB audit |
| D17 | **Feature-flag CodeMode** (`DJ_MCP_CODE_MODE=1`), default off. Enable later when real zero-round-trip pipeline needed. | Agreed |
| D18 | **Versioning** — use `@tool(version="1.0")` / `version="2.0"` where breaking-change transition spans multiple releases. Not a hard requirement for v1 refactor. | FastMCP v3 |

---

## 3. Canonical Directory Structure

Target layout for `app/`. Matches FastMCP v3 source (`src/fastmcp/tools/`, `src/fastmcp/resources/`, `src/fastmcp/prompts/`, etc.) — divergences justified inline.

```text
app/
├── tools/                      # FastMCP convention: all @tool decorators live here
│   ├── entity/                 # 6 generic CRUD tools (polymorphic via EntityRegistry)
│   │   ├── list.py             # entity_list
│   │   ├── get.py              # entity_get
│   │   ├── create.py           # entity_create (dispatches to handler)
│   │   ├── update.py           # entity_update
│   │   ├── delete.py           # entity_delete
│   │   └── aggregate.py        # entity_aggregate (count / distinct / histogram / min_max / group_by)
│   ├── provider/               # generic provider access (polymorphic via ProviderRegistry)
│   │   ├── read.py             # provider_read (track / album / artist / playlist / likes — GET)
│   │   ├── write.py            # provider_write (playlist mutations, likes mutations)
│   │   └── search.py           # provider_search (dedicated — query + type semantics)
│   ├── compute/                # pure compute, no persistence
│   │   ├── score_pool.py       # transition_score_pool (N×N matrix)
│   │   └── sequence_optimize.py # sequence_optimize (GA / greedy strategy dispatch)
│   ├── sync/                   # bi-directional / workflow atoms
│   │   └── playlist_sync.py    # playlist_sync (pull/push/diff via direction param)
│   └── admin/
│       └── unlock_namespace.py # unlock_namespace (per-session visibility activation)
│
├── resources/                  # FastMCP convention: all @resource decorators
│   ├── track.py                # local://tracks/{id}, local://tracks/{id}/features, audit, suggest_next, suggest_replacement
│   ├── playlist.py             # local://playlists/{id}{?include_tracks}
│   ├── set.py                  # local://sets/{id}/{view}, cheatsheet, narrative, review, versions/compare
│   ├── transition.py           # local://transition/{from}/{to}/score, .../explain
│   ├── transition_history.py   # local://transition_history/best_pairs, history{?limit}
│   ├── session.py              # session://set-draft, session://tool-history, session://energy_trend
│   ├── schema.py               # schema://entities/{entity}, schema://entities, schema://providers/{name}
│   └── reference/              # static knowledge blobs
│       ├── camelot.py
│       ├── subgenres.py
│       ├── templates.py
│       └── audit_rules.py
│
├── prompts/                    # FastMCP convention: recipes that chain tool calls
│   ├── dj_expert_session.py
│   ├── build_set_workflow.py
│   ├── deliver_set_workflow.py
│   ├── expand_playlist_workflow.py
│   ├── full_pipeline.py
│   └── quick_mix_check.py
│
├── models/                     # SQLAlchemy ORM — one file per aggregate root
│   ├── base.py                 # Base + TimestampMixin
│   ├── track.py                # Track + Artist + Genre + Release + TrackExternalId
│   ├── playlist.py             # DjPlaylist + DjPlaylistItem
│   ├── set.py                  # DjSet + DjSetVersion + DjSetItem
│   ├── audio_file.py           # DjLibraryItem + DjBeatgrid
│   ├── track_features.py       # TrackAudioFeaturesComputed + TrackSection + TimeseriesReference + FeatureExtractionRun
│   ├── transition.py
│   ├── transition_history.py
│   ├── track_feedback.py
│   ├── track_affinity.py
│   ├── scoring_profile.py
│   ├── provider_metadata.py    # YandexMetadata + RawProviderResponse + Provider
│   └── key.py                  # Key + KeyEdge (reference, read-only)
│
├── repositories/               # Thin: BaseRepository[M] + 3-5 domain methods per entity
│   ├── base.py                 # BaseRepository[M], Page[M], Django-style filter parser
│   ├── unit_of_work.py         # UnitOfWork (lazy repo properties)
│   ├── track.py
│   ├── playlist.py
│   ├── set.py
│   ├── audio_file.py
│   ├── track_features.py
│   ├── transition.py
│   ├── transition_history.py
│   ├── track_feedback.py
│   ├── track_affinity.py
│   ├── scoring_profile.py
│   ├── provider_metadata.py
│   └── key.py
│
├── schemas/                    # Pydantic DTOs — 4 per entity: View, Filter, Create, Update
│   ├── common.py               # Page, EntityListView, EntityAggregateView, EntityRef
│   ├── track.py                # TrackView, TrackFilter, TrackCreate, TrackUpdate
│   ├── playlist.py
│   ├── set.py
│   ├── audio_file.py
│   ├── track_features.py
│   ├── transition.py
│   ├── transition_history.py
│   ├── track_feedback.py
│   ├── track_affinity.py
│   ├── scoring_profile.py
│   └── provider.py
│
├── handlers/                   # Custom create/update/delete handlers for entities with side-effects
│   ├── track_import.py         # entity_create(entity="track") — fetch from provider + persist
│   ├── audio_file_download.py  # entity_create(entity="audio_file") — download + write + register
│   ├── track_features_analyze.py # entity_create(entity="track_features") — run pipeline
│   ├── track_features_reanalyze.py # entity_update(entity="track_features")
│   ├── transition_persist.py   # entity_create(entity="transition") — compute score + persist
│   └── set_version_build.py    # entity_create(entity="set_version") — snapshot ordering
│
├── registry/                   # Polymorphic dispatch
│   ├── entity.py               # EntityRegistry + EntityConfig + register_default_entities()
│   └── provider.py             # ProviderRegistry + Provider protocol
│
├── domain/                     # PURE — no I/O, no DB, no FastMCP, no SQLAlchemy, no httpx
│   ├── transition/
│   │   ├── scorer.py
│   │   ├── components/         # bpm / harmonic / energy / spectral / groove / timbral
│   │   ├── hard_constraints.py
│   │   ├── intent.py
│   │   ├── style.py
│   │   ├── recipe.py
│   │   ├── recipe_engine.py
│   │   ├── section_context.py
│   │   └── weights.py
│   ├── optimization/           # GA + greedy + fitness + 2opt + strategy Protocol
│   ├── camelot/                # wheel math
│   ├── template/               # 8 set templates registry
│   └── audit/                  # techno quality rules
│
├── audio/                      # librosa / essentia pipeline (external-deps machinery)
│   ├── pipeline.py
│   ├── analyzers/              # 18 concrete analyzers (BaseAnalyzer subclass)
│   ├── classification/         # mood classifier
│   └── timeseries.py
│
├── providers/                  # External music platform adapters
│   ├── protocol.py             # Provider Protocol (search/read/write/search/download_audio)
│   ├── registry.py             # Re-exports registry from app/registry/provider.py (transitional; ultimately drop this file)
│   └── yandex/
│       ├── adapter.py          # YandexAdapter(Provider)
│       ├── client.py           # httpx async client (moved from app/ym/client.py)
│       ├── rate_limiter.py
│       └── filters.py
│
├── config/                     # Settings split from 104-field monolith
│   ├── __init__.py             # Settings() facade (re-exports per-domain settings)
│   ├── database.py             # DatabaseSettings
│   ├── yandex.py               # YandexSettings
│   ├── audio.py                # AudioSettings (pipeline + analyzers)
│   ├── transition.py           # TransitionSettings (weights, thresholds)
│   ├── optimization.py         # OptimizationSettings (GA knobs)
│   ├── discovery.py            # DiscoverySettings
│   ├── delivery.py             # DeliverySettings
│   └── mcp.py                  # MCPSettings (cache, retry, rate limits, timeouts)
│
├── shared/                     # Cross-cutting primitives (mirrors fastmcp/utilities/)
│   ├── errors.py               # NotFoundError, ValidationError, ConflictError, NotAllowedError
│   ├── ids.py                  # TrackId, PlaylistId, SetId, ... (type aliases)
│   ├── time.py                 # utc_now, utc_timestamp_iso, sa_now
│   ├── pagination.py           # Page, cursor_encode/decode
│   ├── filters.py              # Django-lookup parser: "bpm__gte" → column op
│   └── constants.py            # Enums + stable IDs (SetTemplate, SectionType, CueKind)
│
├── server/                     # FastMCP composition root
│   ├── app.py                  # build_mcp_server() — FastMCP instance + transforms + middleware
│   ├── lifespan.py             # composed db | provider | audio | cache lifespan
│   ├── di.py                   # Depends() factories (get_uow, get_provider_registry, get_audio_pipeline)
│   ├── middleware/             # 1 file per middleware class
│   │   ├── error_handling.py
│   │   ├── sentry_context.py
│   │   ├── otel_tracing.py
│   │   ├── timing.py
│   │   ├── audit_log.py
│   │   ├── retry.py
│   │   ├── response_limit.py
│   │   ├── response_caching.py
│   │   ├── deprecation_warning.py
│   │   ├── cost_tracking.py
│   │   ├── sampling_budget.py
│   │   ├── progress_throttle.py
│   │   ├── tool_timeout.py
│   │   ├── provider_rate_limit.py
│   │   ├── db_session.py
│   │   └── structured_logging.py
│   ├── transforms.py           # BM25SearchTransform + PromptsAsTools + ResourcesAsTools + optional CodeMode
│   ├── visibility.py           # global tag-based disable + register_unlock_namespace()
│   ├── sampling.py             # LLM sampling fallback config
│   └── observability.py        # Sentry / OTEL bootstrap
│
├── rest/                       # Thin FastAPI wrapper (for Panel HTTP transport only; no business logic)
│   ├── app.py
│   ├── lifespan.py
│   └── routes/
│       ├── health.py
│       └── mcp_proxy.py        # POST /api/tools/{name}/call etc.
│
├── db/                         # DB-layer infra (no models — those live in app/models/)
│   ├── session.py              # async_session_factory, engine
│   ├── seed.py                 # reference data seed (24 keys, 4 providers)
│   └── migrations/             # Alembic
│
├── server.py                   # entrypoint — `fastmcp run app/server.py`
├── telemetry.py
└── _version.py
```

### Where each thing goes (fast lookup)

| Asking... | Goes in |
|---|---|
| Add a new MCP tool | `app/tools/<subdir>/<name>.py` |
| Add a new read-only endpoint | `app/resources/<file>.py` as `@resource(...)` |
| Add a new workflow recipe for LLM | `app/prompts/<name>.py` |
| Add a new entity with side-effects on create | `app/handlers/<entity>_<verb>.py` + `EntityRegistry.register(...)` |
| Add a new music platform (e.g., Spotify) | `app/providers/spotify/{adapter,client,rate_limiter}.py` + `ProviderRegistry.register(...)` |
| Add a new audio analyzer | `app/audio/analyzers/<name>.py` (subclass `BaseAnalyzer`) |
| Add a new transition scoring component | `app/domain/transition/components/<name>.py` |
| Tune a threshold / magic number | `app/config/<domain>.py` — `<Domain>Settings` field |
| Add a middleware | `app/server/middleware/<concern>.py` + register in `app/server/app.py` |

---

## 4. Naming Law

### Rule 1 — Scope via prefix on TOOLS and RESOURCES only

Tool names and resource URIs use three prefix scopes:

- **`entity_*`** — polymorphic CRUD (`entity_list`, `entity_get`, ...). Entity name passed as parameter.
- **`provider_*`** — polymorphic provider access (`provider_read`, `provider_search`, ...). Provider passed as parameter.
- **`<verb>_*`** — atomic actions outside CRUD: `transition_score_pool`, `sequence_optimize`, `playlist_sync`, `unlock_namespace`.

Resource URIs use similar scoping:
- **`local://...`** — data owned by our DB
- **`session://...`** — session-scoped state (draft, tool history)
- **`schema://...`** — introspection (entity schemas, provider capabilities)
- **`reference://...`** — static domain knowledge (camelot, subgenres, templates, audit rules)

### Rule 2 — Inside the code, NO scope prefixes

Models, repos, schemas, handlers do NOT carry `local_` / `provider_` prefixes. Context is clear from directory location.

- `app/models/track.py` — class `Track` (not `LocalTrack`)
- `app/repositories/track.py` — class `TrackRepository` (not `LocalTrackRepository`)
- `app/schemas/track.py` — `TrackView`, `TrackFilter`, `TrackCreate`, `TrackUpdate`
- `app/handlers/track_import.py` — handler function `handle_track_import_create`

### Rule 3 — Verbs come from a closed vocabulary

All action-style tools and handler suffixes use verbs from this list:

```text
analyze | classify | score | build | rebuild | deliver | export |
sync | import | download | push | pull | expand | audit | distribute |
suggest | explain | compare | review
```

If an action doesn't fit, one of:
1. Reframe it as an entity CRUD operation
2. Discuss adding a verb to the vocabulary (change this spec first)

### Rule 4 — `snake_case` everywhere for MCP-facing names

Tool names, resource URIs, parameter names, tag values — always snake_case. FastMCP `NamespaceTransform` produces `api_tool_name` (not `api.tool_name`), matching this convention.

### Rule 5 — Singular entity names, plural only in URI paths

- Entity name (EntityRegistry key, filter param): `"track"`, `"playlist"`, `"set"` — singular
- URI resource collection paths: `local://tracks`, `local://playlists` — plural (REST convention)
- Class names: `Track`, `Playlist`, `DjSet` — singular

### Rule 6 — File name ↔ tool/resource/prompt function name

The file at `app/tools/entity/list.py` registers exactly one tool named `entity_list`. Reading the file name tells you the tool name; grepping for a tool finds exactly one file. No aliasing.

---

## 5. EntityRegistry — polymorphic CRUD core

### 5.1 Design

`EntityRegistry` holds a declarative configuration per entity. All CRUD tools (`entity_list`, `entity_get`, `entity_create`, `entity_update`, `entity_delete`, `entity_aggregate`) dispatch to the right repository and handler via this registry.

```python
# app/registry/entity.py

type HandlerCallable = Callable[
    [Context, UnitOfWork, dict[str, Any]], Awaitable[dict[str, Any] | list[dict[str, Any]]]
]

@dataclass(frozen=True)
class EntityConfig[M: Base, V: BaseModel, F: BaseModel, C: BaseModel, U: BaseModel]:
    name: str                                    # "track", "playlist", ...
    model: type[M]                               # SQLAlchemy class
    repo_attr: str                               # "tracks" → uow.tracks
    view_schema: type[V]                         # TrackView
    filter_schema: type[F]                       # TrackFilter
    create_schema: type[C]                       # TrackCreate
    update_schema: type[U]                       # TrackUpdate
    allowed_ops: frozenset[Literal["list","get","create","update","delete","aggregate"]]
    field_presets: Mapping[str, Sequence[str] | Literal["*"]]   # {"id":[...], "summary":[...], ...}
    default_preset: str                          # "id"
    searchable_fields: Sequence[str]             # for free-text search
    filterable_fields: Mapping[str, Sequence[str]]  # {"bpm": ["eq","gte","lte","range"], ...}
    sortable_fields: Sequence[str]               # ["bpm","title","id"]
    relations: Mapping[str, str]                 # {"artists": "artists", "features": "track_audio_features_computed"}
    tags: frozenset[str]                         # {"namespace:library", ...} for visibility
    create_handler: HandlerCallable | None = None
    update_handler: HandlerCallable | None = None
    delete_handler: HandlerCallable | None = None

class EntityRegistry:
    _registry: ClassVar[dict[str, EntityConfig]] = {}

    @classmethod
    def register(cls, config: EntityConfig) -> None: ...

    @classmethod
    def get(cls, name: str) -> EntityConfig: ...  # raises NotFoundError

    @classmethod
    def names(cls) -> list[str]: ...
```

### 5.2 Registered entities (11 at v1)

| Entity name | Aggregate root table | Custom handlers |
|---|---|---|
| `track` | `tracks` | `create`: import from provider (fetch metadata + insert) |
| `playlist` | `dj_playlists` | — |
| `set` | `dj_sets` | — |
| `set_version` | `dj_set_versions` | `create`: build version snapshot with mix points, recompute transitions |
| `audio_file` | `dj_library_items` | `create`: download from provider + write file + insert DjLibraryItem + init DjBeatgrid |
| `track_features` | `track_audio_features_computed` | `create`: run audio pipeline; `update`: re-analyze with higher level |
| `transition` | `transitions` | `create`: compute score (scorer + domain) + persist |
| `transition_history` | `transition_history` | — |
| `track_feedback` | `track_feedback` | — |
| `track_affinity` | `track_affinity` | — |
| `scoring_profile` | `scoring_profiles` | — |

`keys` and `key_edges` are reference data exposed via `reference://camelot` resource — not registered as entity (read-only static).
`yandex_metadata` + `raw_provider_responses` are joined into `track` reads via `include_relations=["metadata"]` — not user-facing entities.

### 5.3 Example: `entity_list` tool

```python
# app/tools/entity/list.py

from typing import Annotated, Any, Literal
from fastmcp.tools import tool
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext, Depends
from pydantic import Field

from app.registry.entity import EntityRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.schemas.common import EntityListView

EntityName = Literal[
    "track", "playlist", "set", "set_version", "audio_file", "track_features",
    "transition", "transition_history", "track_feedback", "track_affinity",
    "scoring_profile",
]

@tool(
    name="entity_list",
    tags={"namespace:crud", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "List entities of a given type with filtering, sorting, pagination, "
        "and field projection. Entity-specific schemas via schema://entities/{entity}."
    ),
)
async def entity_list(
    entity: EntityName,
    filters: Annotated[dict[str, Any] | None, Field(
        description='Django-style: {"bpm__gte": 120, "mood__in": ["peak_time"]}',
    )] = None,
    search: Annotated[str | None, Field(
        description="Free-text search over entity's searchable_fields",
    )] = None,
    fields: Annotated[list[str] | str | None, Field(
        description='Field list or preset name ("id", "ref", "summary", "scoring", "full").',
    )] = None,
    exclude: list[str] | None = None,
    include_relations: list[str] | None = None,
    sort: list[str] | None = None,
    limit: int = 50,
    cursor: str | None = None,
    with_total: bool = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> EntityListView:
    config = EntityRegistry.get(entity)
    # ... resolve preset, validate filters, dispatch to repo.filter(...),
    #     apply projection, serialize via view_schema
```

### 5.4 `entity_aggregate` tool

Computes summary statistics without returning rows. Operations: `count`, `distinct`, `histogram`, `min_max`, `sum`, `avg`, optionally `group_by`. Critical for Panel dashboard use cases without building an extra API layer.

### 5.5 Custom handlers — mechanism

A handler is an `async (ctx, uow, data) -> dict | list[dict]` function. When `entity_create` fires:

```python
config = EntityRegistry.get(entity)
if config.create_handler is not None:
    result = await config.create_handler(ctx, uow, data)   # side-effects
else:
    # Default: straight INSERT via repo
    validated = config.create_schema.model_validate(data)
    row = await getattr(uow, config.repo_attr).create(**validated.model_dump())
    result = config.view_schema.model_validate(row).model_dump()
```

Handlers live in `app/handlers/` — one file per handler. They receive the `ctx` for progress reporting, `uow` for DB access, and the already-validated data dict.

### 5.6 Schema introspection via resources

```python
# app/resources/schema.py

@resource("schema://entities/{entity}", mime_type="application/json")
def entity_schema(entity: str) -> str:
    config = EntityRegistry.get(entity)
    return json.dumps({
        "name": config.name,
        "operations": sorted(config.allowed_ops),
        "presets": config.field_presets,
        "default_preset": config.default_preset,
        "searchable_fields": config.searchable_fields,
        "filterable_fields": config.filterable_fields,
        "sortable_fields": config.sortable_fields,
        "relations": list(config.relations.keys()),
        "view_schema": config.view_schema.model_json_schema(),
        "filter_schema": config.filter_schema.model_json_schema(),
        "create_schema": config.create_schema.model_json_schema(),
        "update_schema": config.update_schema.model_json_schema(),
    })

@resource("schema://entities", mime_type="application/json")
def entity_schema_index() -> str:
    return json.dumps({"entities": EntityRegistry.names()})
```

LLM reads these once per session to learn what filters/presets/fields each entity supports.

---

## 6. ProviderRegistry — polymorphic platform access

### 6.1 Protocol

```python
# app/providers/protocol.py

class Provider(Protocol):
    name: str

    async def read(self, entity: str, id: str | None, params: dict) -> dict: ...
    async def write(self, entity: str, operation: str, params: dict) -> dict: ...
    async def search(self, query: str, type: str, limit: int) -> dict: ...
    async def download_audio(self, track_id: str) -> Path: ...
    async def close(self) -> None: ...
```

### 6.2 Registry

```python
# app/registry/provider.py

class ProviderRegistry:
    _adapters: dict[str, Provider]
    _default: str | None

    def register(self, adapter: Provider, *, default: bool = False) -> None: ...
    def get(self, name: str) -> Provider: ...
    def default(self) -> Provider: ...
    def names(self) -> list[str]: ...
    async def close_all(self) -> None: ...
```

### 6.3 Three generic tools

- `provider_read(provider, entity, id, params)` — GET operations
- `provider_write(provider, entity, operation, params)` — mutations (playlist modify, likes)
- `provider_search(provider, query, type, limit)` — dedicated (search has unique query semantics)

Audio download is NOT a provider tool — it's `entity_create(entity="audio_file", data={track_ids:[...], source:"yandex"})`. The handler calls `provider.download_audio()` internally.

### 6.4 Adding a new platform

```text
app/providers/spotify/
├── adapter.py        # class SpotifyAdapter(Provider)
├── client.py         # httpx async client
└── rate_limiter.py
```

Plus `ProviderRegistry.register(SpotifyAdapter(...))` in `app/server/lifespan.py`. **Zero new tools.**

---

## 7. Tool Catalog

Complete surface at v1. Total: **13 tools** (11 manager + 2 FastMCP synthetic).

| Name | Tags | Default visibility | Description |
|---|---|---|---|
| `entity_list` | `crud`, `read` | ✓ visible | List entities with filter/sort/paginate/project |
| `entity_get` | `crud`, `read` | ✓ visible | Get single entity by ID |
| `entity_create` | `crud`, `write` | ✓ visible | Create entity (handler may have side-effects) |
| `entity_update` | `crud`, `write` | unlock | Update entity |
| `entity_delete` | `crud`, `write`, `destructive` | unlock | Delete entity |
| `entity_aggregate` | `crud`, `read` | ✓ visible | Count / histogram / group_by |
| `provider_read` | `provider`, `read` | ✓ visible | Read from external platform |
| `provider_write` | `provider`, `write` | unlock | Mutate external platform |
| `provider_search` | `provider`, `read` | ✓ visible | Search external catalog |
| `transition_score_pool` | `compute`, `read` | ✓ visible | N×N score matrix for a track pool |
| `sequence_optimize` | `compute`, `read` | ✓ visible | GA / greedy optimization |
| `playlist_sync` | `sync`, `write` | unlock | Bi-directional playlist sync |
| `unlock_namespace` | `admin` | ✓ visible | Per-session namespace activation |

Plus FastMCP-generated synthetic tools when `BM25SearchTransform` is active:
- `search_tools` — BM25 query over full catalog
- `run_tool` — proxy invoke for hidden tools

**Always-visible count: 9 manager + 2 synthetic = 11.** Four tools unlocked per-session via `unlock_namespace`.

### 7.1 Namespaces

Tag-based groups that govern default visibility and per-session activation.

| Namespace tag | Contains | Default |
|---|---|---|
| `namespace:crud:read` | list/get/aggregate | ON |
| `namespace:crud:write` | create | ON |
| `namespace:crud:destructive` | update/delete | OFF (unlock needed) |
| `namespace:provider:read` | provider_read, provider_search | ON |
| `namespace:provider:write` | provider_write | OFF |
| `namespace:compute` | transition_score_pool, sequence_optimize | ON |
| `namespace:sync` | playlist_sync | OFF |

```python
# session start
# LLM sees 9 tools covering read+simple-create
# To sync playlist:
unlock_namespace(namespace="sync")
# Now playlist_sync is available for this session
```

---

## 8. Resource Catalog

Total: **~26 resources** (18 entity-data + 4 introspection + 4 static reference). All read-only, cost-free, URI-template-based.

### 8.1 Entity views

```text
local://tracks/{id}                          # single track view
local://tracks/{id}/features                 # features by track
local://tracks/{id}/audit                    # techno audit result (computed)
local://tracks/{id}/suggest_next{?limit,energy_direction}
local://tracks/{id}/suggest_replacement/{set_id}/{position}

local://playlists/{id}{?include_tracks}
local://playlists/{id}/audit

local://sets/{id}/{view}                     # view: summary | tracks | transitions | full
local://sets/{id}/cheatsheet{?version}
local://sets/{id}/narrative
local://sets/{id}/review
local://sets/{id}/versions/compare/{a}/{b}

local://transition/{from}/{to}/score
local://transition/{from}/{to}/explain
local://transition_history/best_pairs{?limit}

local://session/set-draft                    # session-scoped: current draft state
local://session/tool-history
local://session/energy_trend{?n}
```

### 8.2 Introspection

```text
schema://entities
schema://entities/{entity}
schema://providers
schema://providers/{provider}
```

### 8.3 Static reference

```text
reference://camelot
reference://subgenres
reference://templates
reference://audit_rules
```

### 8.4 Response types

Per FastMCP v3 breaking change: resources return `str | bytes | ResourceResult`. Dict/list cause `TypeError`. JSON payloads: `json.dumps(...)` + `mime_type="application/json"`.

```python
from fastmcp.resources import ResourceContent, ResourceResult

@resource("local://tracks/{id}/features", mime_type="application/json")
async def track_features(id: int, uow: UnitOfWork = Depends(get_uow)) -> str:
    features = await uow.track_features.get_by_track_id(id)
    if features is None:
        raise NotFoundError(f"track_features for track_id={id}")
    return TrackFeaturesView.model_validate(features).model_dump_json()
```

---

## 9. Prompt Catalog

Total: **6 prompts**. Each is a recipe chaining atomic tools — LLM executes or reads for guidance.

| Prompt | Purpose |
|---|---|
| `dj_expert_session` | Bootstraps reasoning context with DJ knowledge (subgenre descriptions, transition rules, audit criteria) |
| `build_set_workflow` | Step-by-step set building: audit → features → candidates → score_pool → optimize → persist |
| `deliver_set_workflow` | Set delivery: score all transitions → conflict gate (elicitation) → export → copy → sync |
| `expand_playlist_workflow` | Growth: seed → discover similar → filter by feedback → import → download → analyze → re-audit → classify |
| `full_pipeline` | Chained expand + build + deliver |
| `quick_mix_check` | Pair check shortcut: two track IDs → load features → score → explain |

Per FastMCP v3 breaking change: prompts return `fastmcp.prompts.Message` and `PromptResult` (not `mcp.types.PromptMessage`).

```python
from fastmcp.prompts import Message, PromptResult, prompt

@prompt(name="build_set_workflow")
def build_set_workflow(playlist_id: int, template: str = "classic_60") -> PromptResult:
    return PromptResult(
        messages=[Message(f"""
To build a set from playlist {playlist_id} with template '{template}':

1. Load tracks: entity_list(entity="playlist", filters={{"id": {playlist_id}}}, include_relations=["tracks"])
2. For each track, ensure features at analysis_level >= 3:
   entity_create(entity="track_features", data={{"track_ids": [...], "level": 3}})
3. Audit techno compliance: local://tracks/{{id}}/audit for each
4. Filter candidates: entity_list(entity="track", filters={{"id__in": [...]}}, fields="scoring")
5. Compute pair scores: transition_score_pool(track_ids=[...])
6. Run optimizer: sequence_optimize(track_ids=[...], algorithm="ga", template="{template}", pair_scores=...)
7. Persist: entity_create(entity="set_version", data={{"set_id": ..., "track_order": [...]}})

Return: {{"set_id": ..., "version_id": ..., "quality_score": ...}}
""")],
        description=f"Recipe: build set from playlist {playlist_id}",
    )
```

---

## 10. UoW + BaseRepository — persistence pattern

### 10.1 BaseRepository[M]

```python
# app/repositories/base.py

class BaseRepository[M: Base]:
    model: type[M]
    session: AsyncSession

    async def get(self, id: int, *, load_only: Sequence[str] | None = None) -> M | None: ...
    async def list(self, *, limit: int = 50, cursor: str | None = None) -> Page[M]: ...
    async def filter(
        self, *,
        where: dict[str, Any],       # Django-style: bpm__gte, mood__in, title__icontains
        order: Sequence[str],
        limit: int,
        cursor: str | None,
        load_only: Sequence[str] | None = None,
        selectinload: Sequence[str] | None = None,
    ) -> Page[M]: ...
    async def count(self, *, where: dict[str, Any] | None = None) -> int: ...
    async def exists(self, id: int) -> bool: ...
    async def create(self, **data) -> M: ...
    async def update(self, id: int, **data) -> M: ...
    async def delete(self, id: int) -> None: ...
    async def aggregate(
        self, *, operation: str, field: str | None, group_by: str | None, where: dict | None,
    ) -> dict | list[dict]: ...
```

Django-style lookups parsed in `app/shared/filters.py`: `bpm__gte` → `Track.bpm >= value`, `mood__in` → `Track.mood.in_(values)`, etc. Validated against `EntityConfig.filterable_fields` at dispatch time.

### 10.2 Entity-specific repositories

Thin subclass per entity. Only methods that aren't expressible via `filter()`:

```python
# app/repositories/track.py

class TrackRepository(BaseRepository[Track]):
    model = Track

    async def get_provider_id(self, track_id: int, platform: str) -> str | None: ...
    async def get_unanalyzed(self, level: int) -> list[int]: ...
    async def batch_get_by_provider_ids(self, platform: str, ids: list[str]) -> dict[str, Track]: ...
```

No CRUD methods in subclass — inherited. ~30 LOC per repo vs current ~250 LOC.

### 10.3 UnitOfWork

```python
# app/repositories/unit_of_work.py

class UnitOfWork:
    session: AsyncSession

    tracks: TrackRepository              # lazy @property
    playlists: PlaylistRepository
    sets: SetRepository
    set_versions: SetVersionRepository
    audio_files: AudioFileRepository
    track_features: TrackFeaturesRepository
    transitions: TransitionRepository
    transition_history: TransitionHistoryRepository
    track_feedback: TrackFeedbackRepository
    track_affinity: TrackAffinityRepository
    scoring_profiles: ScoringProfileRepository
    provider_metadata: ProviderMetadataRepository
    keys: KeyRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    # commit on success, rollback on exception
```

### 10.4 Transaction boundary = tool call

`DbSessionMiddleware` (innermost before handler) creates `UnitOfWork`, sets it on `ctx`, yields, commits on success / rolls back on exception. Tools consume via `Depends(get_uow)` which reads from `ctx`.

---

## 11. Middleware Pipeline

Order is outermost → innermost (first added wraps all).

Pipeline is **15 middleware** post-PR1 (14 after PR2 drops `ToolCallTimeoutMiddleware` in favour of `@tool(timeout=N)`).

| # | Middleware | Concern | New/Existing |
|---|---|---|---|
| 1 | `DomainErrorMiddleware` | Catch, map domain exceptions to `ToolError` | existing (renamed from `ErrorHandlingMiddleware` to avoid collision with FastMCP's built-in) |
| 2 | `SentryContextMiddleware` | Tag breadcrumbs with tool/session | **new** |
| 3 | `DetailedTimingMiddleware` | Timing histogram | existing |
| 4 | `AuditLogMiddleware` | Log mutations (name + args hash + result) | **new** |
| 5 | `RetryMiddleware` | Transient errors, exponential backoff | existing |
| 6 | `ResponseLimitingMiddleware` | Guard against gigantic responses | existing |
| 7 | `ResponseCachingMiddleware` | Cache read-only tool results | existing (enable) |
| 8 | `DeprecationWarningMiddleware` | Warn on `version="1.0"` tool calls | **new** |
| 9 | `CostTrackingMiddleware` | Count provider calls + LLM tokens | **new** |
| 10 | `SamplingBudgetMiddleware` | Cap `ctx.sample()` per session | **new** |
| 11 | `ProgressThrottleMiddleware` | Throttle progress events to 1/sec | **new** |
| 12 | `ToolCallTimeoutMiddleware` | Per-tool timeout (drops in PR2 — `@tool(timeout=N)`) | existing |
| 13 | `ProviderRateLimitMiddleware` | YM API rate limit (generalized from YMRateLimit) | existing |
| 14 | `DbSessionMiddleware` | Open UoW, commit/rollback | **new** (replaces DI get_db_session) |
| 15 | `StructuredLoggingMiddleware` | Innermost detailed log | existing |

`OTELTracingMiddleware` was removed in PR1: FastMCP v3 ships native OpenTelemetry instrumentation with MCP semantic conventions (`tools/call {name}`, `gen_ai.tool.name`), covering the same spans our custom middleware produced.

### 11.1 Deferred (YAGNI for v1)

- `IdempotencyMiddleware` — hash-based dedup cache
- `CircuitBreakerMiddleware` — fail-fast on downstream outages
- `FeatureFlagMiddleware` — runtime toggle per tool
- `TenantIsolationMiddleware` — not applicable (single-user)
- `RequestDedupMiddleware` — not applicable

---

## 12. FastMCP v3+ Features Used

### 12.1 Adopted

| Feature | Purpose | Ref |
|---|---|---|
| `@tool` / `@resource` / `@prompt` decorators | Core registration | docs/servers/tools.mdx |
| `FileSystemProvider(root="app/")` | Auto-discover all decorators | examples/filesystem-provider/ |
| Pydantic return types → `structuredContent` | Output schema auto-gen | docs/servers/tools.mdx |
| Annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` | Safety hints to clients | docs/servers/tools.mdx |
| Tags + `mcp.disable(tags=...)` + `ctx.enable_components(tags=...)` | Namespace activation | docs/servers/visibility.mdx |
| `BM25SearchTransform(always_visible=[...])` | Tool Search | docs/servers/transforms/tool-search.mdx |
| `PromptsAsTools` + `ResourcesAsTools` | Tool-only client compat | docs/servers/transforms/*.mdx |
| `ToolTransform` + `ArgTransformConfig(hide=True)` | Hide internal params | docs/servers/transforms/tool-transformation.mdx |
| `fastmcp.prompts.Message` + `PromptResult` | v3 prompt types | v3-notes/prompt-internal-types.md |
| `fastmcp.resources.ResourceResult` + `ResourceContent` | v3 resource types | v3-notes/resource-internal-types.md |
| `CurrentContext()` + `Depends()` | DI pattern | docs/servers/dependency-injection.mdx |
| `@lifespan` composition with `\|` | Lifespan chain | docs/servers/lifespan.mdx |
| `list_tools()` / `list_resources()` / `list_prompts()` | v3 canonical API | v3-notes/get-methods-consolidation.md |
| `mcp.mount(sub, namespace="api")` + `FastMCPProvider` | Sub-server composition | v3-notes/provider-architecture.md |
| `ctx.elicit(message, response_type=PydanticModel)` | Mid-call user input | docs/servers/elicitation.mdx |
| `ctx.report_progress(progress, total, message)` | Progress events | docs/servers/progress.mdx |

### 12.2 Feature-flagged (off by default)

- **CodeMode** (`fastmcp.experimental.transforms.code_mode.CodeMode`) — enable with `DJ_MCP_CODE_MODE=1`. When on, LLM sees only `search`, `get_schema`, `execute` meta-tools; writes Python scripts in sandbox. Useful for zero-round-trip `full_pipeline` orchestration. Requires `fastmcp[code-mode]` extra.

### 12.3 Not adopting (for now)

- **Tasks** (`fastmcp[tasks]`, `task_meta` parameter) — deferred until long-running background analysis jobs need true async execution. Current scripts on VM handle this outside MCP.
- **Versioning** (`@tool(version="2.0")`) — breaking-changes allowed per D1, so we don't need dual-version coexistence. Use if specific tool needs rolling migration.

---

## 13. Deletions

### 13.1 Code deletions

| Path | LOC | Reason |
|---|---|---|
| `app/engines/` (8 files) | 348 | Live DJ mixing simulator — experimental dead code |
| `app/ym/` (5 files) | 792 | Replaced by `app/providers/yandex/` |
| `app/infrastructure/` (2 files) | 97 | Unused stub |
| `app/api/services/ym_audio_proxy.py` | ~150 | Panel goes direct, no proxy needed |
| `app/api/services/tool_registry.py` | ~100 | Use MCP `list_tools` directly |
| `app/api/services/signed_url_cache.py` | ~50 | Obsolete with proxy removal |
| `app/controllers/tools/decks.py` (8 tools) | — | Engines-dependent |
| `app/controllers/tools/mixer.py` (7 tools) | — | Engines-dependent |
| `app/controllers/tools/monitoring.py` (1 tool) | — | Engines-dependent |
| `app/controllers/tools/audio_atomic.py` (4 tools) | — | Folded into `entity_create(entity="track_features")` |
| `app/controllers/tools/run_tool.py` | — | FastMCP `BM25SearchTransform` provides synthetic `run_tool` |
| `app/schemas/deck.py`, `app/schemas/mixer.py` | — | Schema for deleted tools |
| `app/services/` (entire tree, 39 files, ~7000 LOC) | 7000 | Replaced by handlers + domain + atomic tools |
| `app/controllers/dependencies/` | — | Replaced by `app/server/di.py` |
| `app/controllers/tools/` flat tree (46 tool files + subdirs) | — | Re-homed under `app/tools/entity/` etc. |
| `app/clients/` (empty) | 0 | Empty stub |
| `app/providers/` (current, empty re-exports) | 0 | Re-created with adapter |

### 13.2 DB schema deletions

Alembic migration in Phase 2. Drop tables and associated ORM models.

| Table | Rows | Reason |
|---|---|---|
| `spotify_metadata`, `spotify_album_metadata`, `spotify_artist_metadata`, `spotify_playlist_metadata`, `spotify_audio_features` | 0 | No Spotify client |
| `beatport_metadata` | 0 | No Beatport client |
| `soundcloud_metadata` | 0 | No SoundCloud client |
| `embeddings` | 0 | Unused |
| `transition_candidates` | 0 | Superseded by live scoring + cache |
| `dj_saved_loops` | 0 | Feature not implemented |
| `dj_cue_points` | 0 | Feature not implemented |
| `dj_beatgrid_change_points` | 0 | Feature not implemented |
| `dj_set_constraints` | 0 | Feature not implemented |
| `dj_set_feedback` | 0 | Feature not implemented |
| `labels`, `track_labels` | 0 | Label metadata not tracked |
| `app_exports` | 2 | Not queried; replaced by `session://tool-history` |

**Post-drop:** 31 live tables.

### 13.3 Config field cleanups

104-field monolith split into 8 files per `app/config/`. Any field referenced only by deleted code is removed. Estimated cleanup: ~15 fields removed, ~89 retained and re-homed.

---

## 14. Migration Map

Lossless mapping of current → target paths for files we keep. **Read this map when implementing each phase.**

### 14.1 Models (15 → 13 files)

| Current | Target | Notes |
|---|---|---|
| `app/db/models/base.py` | `app/models/base.py` | no-op rename of path |
| `app/db/models/track.py` | `app/models/track.py` | merge w/ parts of `ingestion.py` (TrackExternalId, Provider) |
| `app/db/models/audio.py` | `app/models/track_features.py` | split — features part |
| `app/db/models/audio.py` | `app/models/track_features.py` | sections, timeseries, runs |
| `app/db/models/library.py` | `app/models/audio_file.py` | LibraryItem + Beatgrid (drop cues/loops/change_points) |
| `app/db/models/playlist.py` | `app/models/playlist.py` | — |
| `app/db/models/set.py` | `app/models/set.py` | drop SetConstraint, SetFeedback |
| `app/db/models/transition.py` | `app/models/transition.py` | drop TransitionCandidate |
| `app/db/models/transition_history.py` | `app/models/transition_history.py` | — |
| `app/db/models/scoring_profile.py` | `app/models/scoring_profile.py` | — |
| `app/db/models/track_feedback.py` | `app/models/track_feedback.py` | — |
| `app/db/models/track_affinity.py` | `app/models/track_affinity.py` | — |
| `app/db/models/platform.py` | `app/models/provider_metadata.py` | keep YandexMetadata + RawProviderResponse, drop Spotify/Beatport/SoundCloud |
| `app/db/models/ingestion.py` | `app/models/provider_metadata.py` | merged |
| `app/db/models/key.py` | `app/models/key.py` | — |
| `app/db/models/export.py` | **DELETE** | app_exports table dropped |

### 14.2 Repositories (22 → 13 files)

| Current | Target |
|---|---|
| `app/db/repositories/base.py` | `app/repositories/base.py` (rewrite with generics + Django filter) |
| `app/db/repositories/unit_of_work.py` | `app/repositories/unit_of_work.py` (expand) |
| `app/db/repositories/track/{core,filtering,library,external_ids,stats}.py` | `app/repositories/track.py` (merge) |
| `app/db/repositories/playlist.py` | `app/repositories/playlist.py` |
| `app/db/repositories/set.py` | `app/repositories/set.py` |
| `app/db/repositories/feature.py` | `app/repositories/track_features.py` |
| `app/db/repositories/audio.py` | `app/repositories/audio_file.py` |
| `app/db/repositories/transition.py` | `app/repositories/transition.py` |
| `app/db/repositories/transition_history.py` | `app/repositories/transition_history.py` |
| `app/db/repositories/track_feedback.py` | `app/repositories/track_feedback.py` |
| `app/db/repositories/track_affinity.py` | `app/repositories/track_affinity.py` |
| `app/db/repositories/metadata.py` | `app/repositories/provider_metadata.py` |
| `app/db/repositories/ingestion.py` | `app/repositories/provider_metadata.py` (merge) |
| `app/db/repositories/export.py` | **DELETE** |
| `app/db/repositories/embedding.py` | **DELETE** |
| `app/db/repositories/candidate.py` | **DELETE** (logic moves to query helper in `app/repositories/track.py`) |

### 14.3 Services (39 → 0 files; logic redistributes)

| Current service | New home |
|---|---|
| `app/services/track_service.py` | deleted — CRUD via `entity_*` tools |
| `app/services/playlist_service.py` | deleted — CRUD via `entity_*` tools |
| `app/services/set/facade.py` | deleted — split into `entity_*` + `set_version` handler |
| `app/services/set/builder.py` | `app/handlers/set_version_build.py` + `app/domain/optimization/` |
| `app/services/set/scoring.py` | `app/tools/compute/score_pool.py` + `app/domain/transition/` |
| `app/services/set/cheatsheet.py` | `app/resources/set.py` (cheatsheet resource logic) |
| `app/services/set/crud.py` | deleted — covered by `entity_*` |
| `app/services/set_narrative.py` | `app/resources/set.py` (narrative resource logic) |
| `app/services/audio_service.py` | `app/handlers/track_features_analyze.py` |
| `app/services/tiered_pipeline.py` | folded into `app/handlers/track_features_analyze.py` |
| `app/services/delivery_service.py` | `app/handlers/set_deliver.py` (new) + `app/domain/audit/` |
| `app/services/discovery_service.py` | `app/handlers/track_import.py` + `app/prompts/expand_playlist_workflow.py` |
| `app/services/import_service.py` | `app/handlers/track_import.py` + `app/handlers/audio_file_download.py` |
| `app/services/sync_service.py` | `app/tools/sync/playlist_sync.py` |
| `app/services/candidate_service.py` | query helper in `app/repositories/track.py` |
| `app/services/reasoning_service.py` | `app/resources/track.py` (suggest_next/suggest_replacement resources) |
| `app/services/search_service.py` | covered by `entity_list(search=..., filters=...)` |
| `app/services/mix_point_service.py` | `app/handlers/set_version_build.py` (invoked during build) |
| `app/services/metadata_service.py` | `app/handlers/track_import.py` |
| `app/services/embedding_service.py` | **DELETE** (embeddings table dropped) |
| `app/services/prefetch_service.py` | retained as `app/server/prefetch.py` (invoked by suggest_next resource) |
| `app/services/adaptive_arc.py` | `app/resources/session.py` (energy_trend + suggest_direction) |
| `app/services/track_affinity.py` | `app/handlers/track_affinity_refresh.py` |
| `app/services/track_service.py` (misc queries) | query helpers in `app/repositories/track.py` |
| `app/services/transition_cache.py` | `app/server/middleware/response_caching.py` (cache per-tool) |
| `app/services/transition_history.py` | CRUD via `entity_*`; best_pairs via `resource` |
| `app/services/curation/*.py` | `app/handlers/track_features_classify.py`, `app/domain/audit/rules.py`, `app/handlers/playlist_distribute.py` |
| `app/services/workflows/*` | `app/prompts/*_workflow.py` |

### 14.4 Controllers (tools + resources + prompts)

| Current | Target |
|---|---|
| `app/controllers/tools/*.py` (46 files, 88 tools) | `app/tools/{entity,provider,compute,sync,admin}/*.py` (13 files, 13 tools) |
| `app/controllers/resources/*.py` (12 files, 9 resources) | `app/resources/*.py` (8 files, ~26 resources) |
| `app/controllers/prompts/workflows/*.py` (8 files, 6 prompts) | `app/prompts/*.py` (6 files, 6 prompts) |
| `app/controllers/dependencies/*.py` | `app/server/di.py` (single file) |
| `app/controllers/middleware.py` | `app/server/middleware/*.py` (1 file per concern) |
| `app/controllers/elicitation.py` | `app/shared/elicitation.py` |

### 14.5 Domain & external

| Current | Target |
|---|---|
| `app/transition/*` (20 files) | `app/domain/transition/*` (one-to-one move) |
| `app/optimization/*` (6 files) | `app/domain/optimization/*` (one-to-one move) |
| `app/camelot/*` | `app/domain/camelot/*` |
| `app/templates/*` | `app/domain/template/*` |
| `app/audit/*` | `app/domain/audit/*` |
| `app/entities/*` (5 files) | merged into `app/domain/transition/features.py` (TrackFeatures) + deleted rest |
| `app/audio/*` (36 files) | `app/audio/*` (retain; internal reorganization permitted in Phase 5) |
| `app/ym/*` | **DELETE** — replaced by `app/providers/yandex/*` |
| `app/clients/*` (empty) | **DELETE** |
| `app/providers/*` (current re-exports) | rewrite: `protocol.py`, `registry.py` moves to `app/registry/provider.py` |

### 14.6 Bootstrap + REST + config

| Current | Target |
|---|---|
| `app/bootstrap/*` (8 files) | `app/server/*` (8 files, re-homed) |
| `app/api/*` | `app/rest/*` (minimized — drop `services/ym_audio_proxy.py`, `tool_registry.py`, `signed_url_cache.py`) |
| `app/config.py` (single file) | `app/config/*.py` (split into 8 files) |
| `app/core/*` (9 files) | `app/shared/*` (6 files — simplified) |
| `app/schemas/*` (11 files) | `app/schemas/*.py` (12 files, 4 DTOs per entity: View/Filter/Create/Update) |
| `app/db/migrations/` | `app/db/migrations/` (unchanged path) |
| `app/db/session.py`, `app/db/seed.py` | `app/db/session.py`, `app/db/seed.py` (retained) |

---

## 15. Phased Rollout Plan

Seven implementation phases, each with its own spec + plan + PR merged into `dev`. Each phase has clear entry/exit criteria. Running BFS/L5 campaigns on VM **must continue working at every phase boundary**.

### Phase 0 — Architecture Blueprint (this document)

- **Deliverable:** this spec, committed and approved.
- **PR:** `refactor/phase-0-blueprint` → `dev`.
- **Exit:** user has read and approved the blueprint.

### Phase 1 — Foundation (parallel skeleton)

- **Goal:** create `app/v2/` shell with new structure; no behavior change.
- **Deliverables:**
  - Directory layout per §3.
  - `app/v2/shared/errors.py`, `ids.py`, `time.py`, `pagination.py`, `filters.py`.
  - `app/v2/config/` split.
  - `app/v2/registry/entity.py` (`EntityConfig` + `EntityRegistry`).
  - `app/v2/registry/provider.py` (`Provider` protocol + `ProviderRegistry`).
  - `app/v2/repositories/base.py` (`BaseRepository[M]` + Django filter parser).
  - `app/v2/repositories/unit_of_work.py`.
  - `app/v2/server/` — minimal `app.py`, `lifespan.py`, `di.py`.
  - `app/v2/` can import from `app/` (not vice versa).
- **Tests:** unit tests for `BaseRepository.filter()` with Django lookups; UoW transaction lifecycle; EntityRegistry registration.
- **Exit:** `uv run pytest tests/v2/` green. `app/` untouched, production still runs from `app/`.

### Phase 2 — Persistence

- **Goal:** models + repos migrated; Alembic migration drops dead tables.
- **Deliverables:**
  - All 13 `app/v2/models/*.py` (one per aggregate).
  - All 13 `app/v2/repositories/*.py` (thin subclass pattern).
  - All 12 `app/v2/schemas/*.py` (4 DTOs each).
  - Alembic migration: drop 15 dead tables + orphan columns.
  - `app/v2/db/session.py`, `seed.py`.
- **Tests:** model constraint tests; repo batch methods; migration forward/backward (SQLite test DB + Supabase staging).
- **Exit:** Phase-1 tests + Phase-2 repo tests green. Staging DB migrated.

### Phase 3 — Tools (entity + provider + compute)

- **Goal:** all 13 tools implemented + handlers; old tools kept running in parallel.
- **Deliverables:**
  - `app/v2/tools/entity/{list,get,create,update,delete,aggregate}.py`.
  - `app/v2/tools/provider/{read,write,search}.py`.
  - `app/v2/tools/compute/{score_pool,sequence_optimize}.py`.
  - `app/v2/tools/sync/playlist_sync.py`.
  - `app/v2/tools/admin/unlock_namespace.py`.
  - `app/v2/handlers/*.py` (6 handlers per §5.2).
  - `app/v2/providers/yandex/` (adapter + client ported from `app/ym/`).
  - 11 entity registrations in `app/v2/registry/entity.py:register_default_entities()`.
  - Provider registration in `app/v2/server/lifespan.py`.
- **Tests:**
  - Contract tests per tool (metadata, annotations, tags).
  - Client integration tests for each operation × each entity.
  - Handler unit tests with mocked provider.
  - Migration-path tests: invoke `entity_create(entity="track", data={...})` and verify it produces same result as old `import_tracks` tool for the same input.
- **Exit:** 100% tool surface coverage; side-by-side comparison of old vs new on representative inputs passes.

### Phase 4 — Resources + Prompts

- **Goal:** migrate read-only reads to resources; consolidate prompts.
- **Deliverables:**
  - All 18 resources per §8.
  - All 6 prompts per §9 (migrated to `Message` + `PromptResult`).
  - `schema://entities/{entity}` resource wired to `EntityRegistry` introspection.
  - `reference://*` blobs from `app/domain/camelot/`, `app/domain/template/`, `app/domain/audit/`.
- **Tests:**
  - Resource URI template matching.
  - Prompt output typing (`PromptResult`).
  - Parity checks for each migrated tool-to-resource conversion.
- **Exit:** Phase-3 tests + Phase-4 resource/prompt tests green.

### Phase 5 — Server composition, middleware, transforms

- **Goal:** v2 server fully composable and runnable.
- **Deliverables:**
  - `app/v2/server/app.py` — `build_mcp_server()` with full pipeline.
  - All 15 middleware in `app/v2/server/middleware/` (post-PR1 count; 16 at original Phase 5 landing).
  - `app/v2/server/transforms.py` — `BM25SearchTransform` + `PromptsAsTools` + `ResourcesAsTools` (+ optional `CodeMode`).
  - `app/v2/server/visibility.py` — namespace activation + global disable defaults.
  - `app/v2/server/sampling.py`, `observability.py`.
  - `app/v2/rest/` minimal FastAPI wrapper.
  - `app/v2/server.py` — entrypoint.
- **Tests:**
  - Middleware pipeline ordering (unit tests per middleware).
  - End-to-end tool call through full pipeline.
  - Tool Search discovery.
  - Namespace activation per-session.
- **Exit:** `fastmcp run app/v2/server.py` runs, all tools/resources/prompts discoverable.

### Phase 6 — Domain + audio port

- **Goal:** move pure domain modules + audio pipeline into `app/v2/`.
- **Deliverables:**
  - `app/v2/domain/` populated (one-to-one moves from `app/transition/`, `app/optimization/`, `app/camelot/`, `app/templates/`, `app/audit/`).
  - `app/v2/audio/` — reorganize internally if helpful (not a hard requirement).
  - Import-linter contracts enforcing `domain` purity (§16).
- **Tests:** re-run existing domain tests against v2 paths; import-linter gate green.
- **Exit:** `uv run lint-imports` clean; domain tests green.

### Phase 7 — Cutover

- **Goal:** atomic swap `app/` → `app/v1/` (legacy stash), `app/v2/` → `app/`.
- **Deliverables:**
  - Delete entries per §13.1 (`app/engines/`, `app/ym/`, `app/infrastructure/`, etc.).
  - Move `app/` → `app/v1_legacy/` (stash for 1 release cycle).
  - Move `app/v2/` → `app/`.
  - Update `pyproject.toml`, `alembic.ini`, `start.sh`, scripts, panel `.env.local` references.
  - Update `CLAUDE.md`, `docs/architecture.md`, `docs/tool-catalog.md`, `docs/structure.md` — full rewrite.
  - Update `.claude/rules/` — rewrite per new structure.
- **Campaign compatibility:** before cutover, verify BFS expander + L5 analyzer scripts migrate to new tool names (or wrap with shims in `scripts/` for one release).
- **Tests:** full `make check` green. Smoke test on VM with one track analyze.
- **Exit:** all tests pass on new tree; `dev` branch merged to `main`; tag `v1.0.0` — "The Blueprint".
- **Post-cutover (+1 release):** delete `app/v1_legacy/`.

---

## 16. Import-Linter Contracts

Replace current `.importlinter` with this tighter set. Applied from Phase 1 (against `app/v2/`), promoted to `app/` at Phase 7.

```ini
[importlinter]
root_packages = app
include_external_packages = True

# ── Domain is pure ──────────────────────────────────
[importlinter:contract:domain-pure]
name = Domain must not touch DB / HTTP / FastMCP / SQLAlchemy
type = forbidden
source_modules =
    app.domain
forbidden_modules =
    app.models
    app.repositories
    app.tools
    app.resources
    app.prompts
    app.handlers
    app.providers
    app.server
    app.rest
    app.db
    app.audio
    fastmcp
    sqlalchemy
    httpx

# ── Shared is leaf ──────────────────────────────────
[importlinter:contract:shared-leaf]
name = Shared must not import app domain code
type = forbidden
source_modules =
    app.shared
forbidden_modules =
    app.models
    app.repositories
    app.tools
    app.resources
    app.prompts
    app.handlers
    app.providers
    app.server
    app.rest
    app.db
    app.audio
    app.domain

# ── Repos flush only (no commits outside UoW) ───────
[importlinter:contract:repos-no-transport]
name = Repositories must not import FastMCP or tools
type = forbidden
source_modules =
    app.repositories
forbidden_modules =
    fastmcp
    app.tools
    app.resources
    app.prompts
    app.server
    app.rest

# ── Handlers are application layer ──────────────────
[importlinter:contract:handlers-no-tools]
name = Handlers must not import tools (prevents circular)
type = forbidden
source_modules =
    app.handlers
forbidden_modules =
    app.tools
    app.resources
    app.prompts

# ── Tools thin ──────────────────────────────────────
[importlinter:contract:tools-thin]
name = Tools only call handlers + repos + domain, not services (which don't exist)
type = forbidden
source_modules =
    app.tools
forbidden_modules =
    sqlalchemy
    httpx
    app.audio
    app.providers.yandex

# ── Audio internal ──────────────────────────────────
[importlinter:contract:audio-internal]
name = Audio pipeline isolated from MCP / REST
type = forbidden
source_modules =
    app.audio
forbidden_modules =
    fastmcp
    app.tools
    app.resources
    app.prompts
    app.rest
    app.repositories

# ── REST thin ───────────────────────────────────────
[importlinter:contract:rest-thin]
name = REST must not import DB models / repositories
type = forbidden
source_modules =
    app.rest
forbidden_modules =
    app.models
    app.repositories

# ── Providers isolated ──────────────────────────────
[importlinter:contract:providers-no-persistence]
name = Providers must not touch DB directly (handlers bridge)
type = forbidden
source_modules =
    app.providers
forbidden_modules =
    app.models
    app.repositories
    app.handlers
    app.tools

# ── Registry independent ────────────────────────────
[importlinter:contract:registry-indep]
name = Registry modules must not depend on tools or handlers
type = forbidden
source_modules =
    app.registry
forbidden_modules =
    app.tools
    app.resources
    app.prompts
    app.handlers
```

Total: **9 contracts** (up from 6). Enforced in CI via `uv run lint-imports`.

---

## 17. Testing Strategy

### 17.1 Parallel refactor implications

From Phase 1-6, new code lives at `app/v2/` and legacy at `app/`. Test suites also live in parallel:

- `tests/` — existing tests, run against `app/`.
- `tests/v2/` — new tests, run against `app/v2/`.

Both run in CI. No cross-importing.

### 17.2 Target coverage per layer

| Layer | Test type | Target |
|---|---|---|
| Models | Constraint validation | 100% aggregate roots |
| Repositories | Unit tests with in-memory SQLite | 100% non-trivial methods |
| Handlers | Unit + integration (mocked provider) | 100% |
| Tools (entity_*) | Metadata + integration | 100% tools |
| Resources | URI template matching + response format | 100% resources |
| Prompts | Return-type validation (`PromptResult`) | 100% prompts |
| Domain | Property tests + synthetic fixtures | 100% public API |
| Middleware | Unit tests per middleware | 100% new middleware |

### 17.3 Migration-parity tests (Phase 3-4)

For each old tool being replaced, add a **parity test** that:
1. Calls old tool against a snapshot DB state.
2. Calls new tool/handler/resource against the same state.
3. Asserts semantic equivalence (structural, not byte-exact — timestamps differ).

This catches regressions without requiring full re-test of downstream workflows.

### 17.4 Snapshot tests for prompts

Since prompts are LLM-facing text, use `inline-snapshot` for each prompt's `Message` content. Accept updates only on explicit `--snapshot-update`.

### 17.5 Campaign smoke test

At Phase 7 cutover, run:
1. `scripts/vm_import_and_analyze.py --limit 5` (5-track smoke test)
2. `build_set` equivalent flow via new tools on 1 playlist
3. `deliver_set` equivalent flow
4. `sync_playlist pull`

All must succeed before merging cutover PR.

---

## 18. Risks & Open Questions

### 18.1 Risks

| Risk | Mitigation |
|---|---|
| BFS/L5 campaign breaks during parallel phase | Keep `app/` functional; `app/v2/` imports FROM `app/` during transition (one-way); cutover only at Phase 7 |
| EntityRegistry init order (circular imports) | Registration in `app/v2/server/lifespan.py` startup hook, not at module import |
| Custom handlers prove too opaque to debug | `AuditLogMiddleware` logs entity + handler name; Sentry tags include handler key |
| Migration-parity test misses a subtle case | Run scripts/`smoke_test_all_tools.py` on staging before each phase merge |
| FastMCP v3 types (Message, PromptResult, ResourceResult) break something we don't anticipate | Phase 4 is dedicated to prompts + resources; we catch issues early |
| Alembic migration breaks staging DB | Test forward + backward on a branch-scoped DB (Supabase branch) before applying to staging |
| Panel breaks despite "out of scope" (panel reads MCP tool names) | Panel `lib/queries/*.ts` mostly reads Supabase directly — only `actions/*.ts` calls MCP. Audit those files at start of Phase 3 and map old tool names → new. |
| 15 tables dropped but columns referenced somewhere | Full grep for table names + `CREATE TYPE` names across `app/` and `panel/` at Phase 2 start |
| Performance regression from generic CRUD | Benchmark suite in Phase 3: compare old `list_tracks` (specific) vs new `entity_list(entity="track")` over same input; require ≤10% regression |

### 18.2 Open questions (non-blocking, resolve per-phase)

1. **Relation operations for playlist (`add_tracks`, `remove_tracks`, `reorder`)** — resolve in Phase 3. Candidates: (a) `entity_update(entity="playlist", data={items: [...]})` with smart diff in handler; (b) keep as atomic tools `playlist_add_tracks` etc. Default: option (b) — atomic tools, until we hit real demand for (a).
2. **Large projection `include_relations` performance** — if including `track_features` + `sections` makes a list call >100ms, need index review. Assess in Phase 3 benchmark.
3. **`track_sections` table (1.68M rows)** — do we keep it in this refactor? Decision: keep. Partitioning/pruning is a future ops concern, not blueprint scope.
4. **CodeMode experimental gate** — enable for specific prompts (e.g., `full_pipeline`) or server-wide? Resolve in Phase 5.
5. **Do we adopt `task_meta` for long analysis jobs?** — defer. Current VM scripts handle background work outside MCP.

### 18.3 What this spec deliberately does NOT address

- Panel refactor (D2 — out of scope)
- pg_graphql for Panel reads (future Panel project)
- Authentication (single-user, no multi-tenancy yet)
- Scheduling / cron (existing `scripts/` + systemd units continue)
- DJ engine simulator (engines/ deleted, no revival planned)
- Audit logging storage backend (AuditLogMiddleware writes to structured log; dedicated `audit_log` table postponed until needed)
- Schema versioning beyond Alembic (no semver on DB schema)

---

## 19. Post-blueprint actions

After user approval of this spec:

1. User merges this branch (`worktree-phase-0-blueprint-spec` → `dev`).
2. Blueprint is canonical reference — every Phase spec cites section numbers from here.
3. Begin Phase 1 spec (a separate document): concrete plan for `app/v2/` shell.
4. Update `.claude/rules/` to reference this blueprint when conflicting with individual rule files.
5. Consider archiving prior specs (`2026-04-16-fastmcp-deep-refactor-design.md`, `2026-04-16-phase{1,2,3}-*-design.md`, `2026-04-16-declarative-mcp-design.md`, `2026-04-16-provider-agnostic-refactoring-prompt.md`) into `docs/superpowers/specs/archive/` — this blueprint supersedes them.

---

## Appendix A — Related reading

**FastMCP v3+ required reading (load before implementation of each phase):**

- `docs/servers/tools.mdx` — tool design basics
- `docs/servers/resources.mdx` — resource templates, return types
- `docs/servers/prompts.mdx` — Message / PromptResult
- `docs/servers/transforms/tool-search.mdx` — BM25 + Regex strategies
- `docs/servers/transforms/tool-transformation.mdx` — ArgTransform, hide/default
- `docs/servers/transforms/resources-as-tools.mdx` — tool-only client compat
- `docs/servers/transforms/prompts-as-tools.mdx` — same for prompts
- `docs/servers/transforms/namespace.mdx` — mounted server prefixing
- `docs/servers/transforms/code-mode.mdx` — experimental, Phase 5
- `docs/servers/visibility.mdx` — enable/disable, tags, sessions
- `docs/servers/middleware.mdx` — hooks, ordering
- `docs/servers/dependency-injection.mdx` — Depends(), CurrentContext()
- `docs/servers/lifespan.mdx` — composition, `|` operator
- `docs/servers/elicitation.mdx` — ctx.elicit() for mid-execution input
- `docs/servers/progress.mdx` — ctx.report_progress()
- `docs/servers/testing.mdx` — Client fixture pattern
- `docs/servers/versioning.mdx` — multi-version tools
- `docs/servers/pagination.mdx` — list_page_size
- `docs/servers/composition.mdx` — mount with namespace
- `v3-notes/resource-internal-types.md` — ResourceResult strict typing
- `v3-notes/prompt-internal-types.md` — Message / PromptResult
- `v3-notes/provider-architecture.md` — FastMCPProvider + TransformingProvider
- `v3-notes/visibility.md` — VisibilityFilter hierarchy
- `v3-notes/get-methods-consolidation.md` — list_* API rename
- `v3-notes/task-meta-parameter.md` — explicit background tasks
- `v3-notes/provider-test-pattern.md` — direct server calls in tests

**Example servers to mimic:**

- `examples/filesystem-provider/` — layout pattern
- `examples/namespace_activation/` — per-session unlock
- `examples/search/server_bm25.py` — Tool Search setup
- `examples/code_mode/server.py` — CodeMode setup
- `examples/prompts_as_tools/`, `examples/resources_as_tools/` — transforms

---

## Appendix B — Sign-off checklist

Before implementing Phase 1, verify:

- [ ] User has read this spec end-to-end
- [ ] All `Open Questions` in §18.2 either resolved or explicitly deferred to a phase
- [ ] Migration-map spot-check on 3 representative files matches expectations
- [ ] Phase 1 deliverable scope is small enough for one PR
- [ ] Existing campaigns (BFS expander, L5 analyzer) continue running on VM unmodified

Sign-off: `___________________________________________`

Date: `______________`
