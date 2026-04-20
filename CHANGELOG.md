# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.4] — 2026-04-20

**FastMCP v3 polish — middleware dedupe, per-tool timeouts, fastmcp.json + CORS.**

### Changed
- Replaced 5 custom middleware with canonical FastMCP v3 built-ins: `DetailedTimingMiddleware`, `RetryMiddleware`, `ResponseLimitingMiddleware`, `ResponseCachingMiddleware`, `StructuredLoggingMiddleware`. Behaviour equivalent, covered by FastMCP core tests.
- Renamed `ErrorHandlingMiddleware` → `DomainErrorMiddleware` to avoid collision with FastMCP's built-in `ErrorHandlingMiddleware`. File renamed from `app/server/middleware/error_handling.py` to `app/server/middleware/domain_error.py`.
- Moved `TransientError` from `app/server/middleware/retry.py` to `app/shared/errors.py`.
- `DomainErrorMiddleware` now re-raises `McpError` unchanged, preserving native MCP protocol error codes (e.g. FastMCP timeout `-32000`) instead of wrapping them as `ToolError("internal error")`.
- `ResponseCachingMiddleware`: bounded `MemoryStore(max_entries_per_collection=settings.mcp.response_cache_max)` and explicit `included_tools` allowlist for 13 `readOnlyHint=True` tools (dispatchers + UI).
- `RetryMiddleware`: preserve the pre-migration 0.5s `base_delay` (FastMCP default 1.0s would double every retry wait).
- Per-tool timeouts now carry **both** the forward-looking `@tool(timeout=N)` kwarg and `meta={"timeout_s": N}` on 19 tools (14 dispatchers + 5 read-only UI). The kwarg is documentation/future-proof until FastMCP's `FileSystemProvider` learns to forward it; `ToolCallTimeoutMiddleware` reads `meta["timeout_s"]` as the effective cap today. `tool_invoke` opts out (proxy/fallback — delegated tool enforces its own timeout).
- CORS: explicit allowlist via `DJ_MCP_CORS_ALLOW_ORIGINS` (CSV or JSON array, read directly from env to avoid eager Settings load). Default remains `["http://localhost:3000"]`. Narrowed `allow_methods` to `["GET", "POST", "DELETE", "OPTIONS"]`, `allow_headers` to `["mcp-protocol-version", "mcp-session-id", "Authorization", "Content-Type"]`, added `expose_headers=["mcp-session-id"]` so browser MCP clients can read the session ID.
- `.claude-plugin/plugin.json`: the `mcp` server command now runs `if [ -f .env ]; then source .env; fi` before `exec`, so `fastmcp.json` env interpolation finds the DJ_* vars without hard-failing when the file is absent.

### Added
- `fastmcp.json` `environment` section (uv / python ≥ 3.12 / project root) for declarative env management.
- `fastmcp.json` `deployment.env` with `${VAR}` interpolation for string-valued DJ_* secrets (`DJ_DB_URL`, `DJ_YM_TOKEN`, `DJ_YM_LIBRARY_PATH`, `DJ_SENTRY_DSN`, `DJ_MCP_CODE_MODE` with default `0`).

### Removed
- `OTELTracingMiddleware` — FastMCP v3 ships native OpenTelemetry instrumentation with MCP semantic conventions (`tools/call {name}`, `gen_ai.tool.name`).

### Breaking (internal to codebase only — MCP surface unchanged)
- Import: `from app.server.middleware.error_handling import ErrorHandlingMiddleware` → `from app.server.middleware.domain_error import DomainErrorMiddleware`.
- Import: `from app.server.middleware.retry import TransientError` → `from app.shared.errors import TransientError`.
- `app/server/middleware/otel_tracing.py` deleted.

## [1.0.2] — 2026-04-20

### Changed
- **FastMCP pin:** `fastmcp[tasks]>=3.1.0` → `fastmcp[tasks]>=3.2.4,<4`. Picks up fakeredis-regression fix (v3.2.3) and background-tasks auth-scoping + security hardening (v3.2.4). The v3.2.0 deprecations (`PromptToolMiddleware`, `ResourceToolMiddleware`) do not affect this project — we use `PromptsAsTools` / `ResourcesAsTools` (different classes). No code changes required.

## [1.0.1] — 2026-04-18

### Added
- **Yandex Music:** `set_playlist_description` endpoint in YandexClient + YandexAdapter (`POST /users/{owner}/playlists/{kind}/description`). Exposed via `provider_write(provider="yandex", entity="playlist", operation="set_description", params={playlist_id, description})`.
- **Developer ergonomics:** PostToolUse hook (`hooks/reload-mcp.sh` + `hooks/hooks.json`) that auto-kills the fastmcp stdio process on plugin edits so Claude Code respawns it with fresh code — no manual `/mcp` reconnect. Slash command `/reload-plugin` for manual cache purge + restart.

### Fixed
- **MCP entrypoint:** `fastmcp.json` now points at root `server.py` (self-referential `from app.server.X` imports broke when FastMCP loaded `app/server.py` as synthetic module).

## [1.0.0] — 2026-04-17

**Major release — global refactor to v1 bounded-contexts architecture.**

### Added
- **EntityRegistry** — polymorphic CRUD over 13 entity types (tracks, playlists, sets, transitions, ...)
- **ProviderRegistry** — pluggable music-platform providers (Yandex, stubs for Spotify/Beatport/SoundCloud)
- **UnitOfWork** — single-session-per-tool transaction boundary
- **16 middlewares** composed into `build_mcp_server()`: error_handling, sentry_context, otel_tracing, timing, audit_log, retry, response_limit, response_caching, deprecation_warning, cost_tracking, sampling_budget, progress_throttle, tool_timeout, provider_rate_limit, db_session, structured_logging
- **Domain layer**: pure `app/domain/{transition,optimization,camelot,template,audit}/` — scorer parity at 1e-9 vs legacy
- **Audio layer**: ported 18 analyzers to `app/audio/` with SharedMemory transport + per-worker AnalysisContext cache
- **Resources layer**: ~27 URI resources (entity-scoped, session-scoped, schema introspection, 4 static reference blobs)
- **Prompts layer**: 6 workflow recipes (dj_expert_session, build_set_workflow, deliver_set_workflow, expand_playlist_workflow, full_pipeline, quick_mix_check)
- **REST API**: thin FastAPI wrapper under `app/rest/` (extra `[http]`)
- **Observability**: Sentry + OpenTelemetry bootstrap under `[observability]` extra
- **AuditSettings**: 22 techno-audit thresholds accessible via `settings.audit.*`
- **Smoke test script**: `scripts/smoke_test_all_tools.py` verifying tool/resource/prompt registration end-to-end through `Client(mcp)`

### Changed
- **88 narrow tools → 13 generic dispatchers**: `entity_create/get/update/delete/list/aggregate`, `provider_search/resolve/download`, `sequence_optimize`, `transition_score_pool`, `playlist_sync`, `unlock_namespace`
- **Package layout**: flat `app/{tools,resources,prompts,handlers,repositories,registry,providers,domain,audio,schemas,server,rest,shared,config,models,db}/` — no more `app/controllers/`, `app/services/`, `app/entities/`, `app/engines/`
- **Settings**: split into 8 per-domain Pydantic settings classes (`audio`, `audit`, `database`, `delivery`, `discovery`, `mcp`, `optimization`, `transition`, `yandex`) aggregated via `get_settings()`
- **FastMCP composition**: explicit `FastMCP(providers=[FileSystemProvider(...)], transforms=[PromptsAsTools, ResourcesAsTools, BM25SearchTransform], lifespan=..., sampling_handler=...)`
- **Import-linter contracts**: reduced to 5 v1-scoped architectural gates

### Removed
- ~53,454 LOC of legacy sources: `app/engines/`, `app/infrastructure/`, `app/ym/`, `app/services/` (39 files), `app/controllers/`, `app/bootstrap/`, `app/api/`, `app/schemas/`, `app/transition/`, `app/optimization/`, `app/camelot/`, `app/templates/`, `app/audit/`, `app/entities/`, `app/audio/`, `app/core/`, `app/db/`, `app/config.py`, `app/server.py`, `app/telemetry.py`, `app/_version.py`
- 15 dead DB tables (drop migration `p2_drop_dead_tables`)

### Migration notes

- Panel (`panel/`) server actions call consolidated dispatchers — tool names and argument shapes changed; panel requires follow-up patch
- `scripts/vm_import_and_analyze.py` + `scripts/ym_bfs_expand.py` stubbed — require rewrite against `app.providers.yandex.*` + `app.handlers.*` (post-v1.0.0)
- Alembic `p2_drop_dead_tables` migration deferred to manual apply against Supabase after release

### Phase tags

Refactor executed in 7 phases, each tagged: `phase-1-foundation` → `phase-2-persistence` → `phase-3-tools` → `phase-6-domain-audio` → `phase-4-resources` → `phase-5-server` → v1.0.0 cutover.

## [0.8.0] — 2026-04-13

### Added
- **Smoke-test script** (`scripts/smoke_test_all_tools.py`) — calls all 88 MCP tools through FastMCP Client with in-memory DB, verifies registration + schema + execution
- Full MCP tool verification via Claude Code live client (91/91 tools responding correctly)

### Fixed
- `BestPairRead.avg_score` — was `float` (non-nullable), now `float | None` to handle entries with no score
- `ANNOTATIONS_READ_ONLY` test — updated to match current preset (`readOnlyHint` + `idempotentHint`)
- `test_unlock_tools_status` — removed stale `session_rules` assertion
- `test_fitness_template_intent` — fixed import `app.services.templates` → `app.templates`
- `audio_atomic` tools — use `FastMCPNotFoundError` instead of `ToolError` for missing entities
- MCP tool visibility — resolved FK errors and stale tests (#93)
- NOT NULL constraints in recent migration tables (#94)

### Changed
- `noqa B008` on `track_feedback` Depends() defaults (ruff compliance)
- Supabase added to sandbox network allowedDomains

## [0.7.1] — 2026-04-12

### Added
- `title` on all 88 `@tool()` decorators — Claude Code shows human-readable names instead of "Run Tool"
- 7 semantic annotation presets: `ANNOTATIONS_READ_ONLY`, `WRITE_IDEMPOTENT`, `WRITE_DESTRUCTIVE`, `WRITE_OPEN_WORLD`, `WRITE_DESTRUCTIVE_OPEN`, `READ_ONLY_OPEN_WORLD`, `WRITE`
- 16 SVG icon sets per tool category (tracks, sets, playlists, audio, ym, admin, etc.)
- `TOOL_META` / `RESOURCE_META` dicts on all tools and resources (`version`, `author`)
- `title`, `icons`, `meta` on all 9 `@resource()` decorators
- Neural Mix stem-aware scoring layer (cherry-picked from main #88)
- Speculative prefetch service for next-track preparation (#89)
- `PrefetchService` + DI factory + 3 test files
- `TransitionHistoryService` DI wiring via `Depends()` (was broken `= None`)
- GitHub Actions CI workflow (ruff + mypy + lint-imports + pytest)
- PR template (`.github/pull_request_template.md`)
- Branch strategy doc (`.github/BRANCH_STRATEGY.md`)
- Pre-push hook blocking direct pushes to main
- `.claude/rules/git.md` — project-specific git workflow rules

### Changed
- **Removed `BM25SearchTransform`** — was proxying all tool calls through `run_tool`, causing "Run Tool" display in Claude Code. Replaced with native `mcp.disable(tags=...)` tag-based visibility
- Visibility policy: extended categories (delivery, discovery, curation, sync, ym) disabled at startup, unlockable via `unlock_tools`
- Repo settings: squash-only merges (merge commits disabled), auto-delete branches enabled
- Main and dev branches synced (were 50 vs 14 commits diverged)

### Fixed
- `track_affinity.refresh_from_history()` — `func.cast(..., type_=None)` produced `NullType` DDL error, replaced with `func.count().filter()`
- Duplicate alembic revision `a1b2c3d4e5f6` — renamed `add_first_downbeat_ms` to `f4a1b2c3d5e6`
- Missing imports for `ICON_*`, `TOOL_META`, annotation constants in 34 tool/resource files

### Removed
- 4 backward-compatibility shims: `services/export.py`, `optimizer.py`, `templates.py`, `transition.py`
- `services/background_tasks.py` (dead code)
- Stale git branches (claude/keen-bardeen, docs/sync-markdown-with-project, fix/tool-title-display)

## [0.7.0] — 2026-04-11

### Added
- Transition Recipe Engine — 12 djay Pro AI transition types with stem-level instructions
- Beatgrid migration (23,755 tracks)
- Auto-DJ with smart track selection (BPM ±3, Camelot ≤2)
- Preload next track, echo-out LPF, click fix, transition logging
- Phase 1 — Transition History (model, repo, service, 4 MCP tools, migration)
- Phase 2 — Track Affinity Matrix (model, repo, service, 3 MCP tools)
- Phase 3 — Persistent Track Feedback (like/ban/rate, 6 MCP tools)
- Phase 4 — Adaptive Energy Arc (trend analysis, 3 MCP tools)
- Phase 5 — Set Narrative Engine (phase analysis + suggestions)
- Phase 6 — Personal Scoring Weights (profiles, 3 MCP tools)
- DJ Panel: 4-deck layout, waveforms, EQ faders, cue points, mixer, iOS PWA
- Mixer MCP tools: set_eq, kill_eq, reset_eq, set_filter
- Selectel VM deployment with systemd-run pattern

### Changed
- Scoring weights rebalanced: spectral 0.20 (was 0.15), groove 0.15 (was 0.10), harmonic 0.12 (was 0.20)
- Section-aware scoring with drum-only harmonic floor

## [0.6.0] — 2026-04-10

### Added
- Modular architecture: bootstrap/, api/, DI, workflows
- REST API wrapper (FastAPI) with Swagger docs
- Panel (Next.js) with Supabase direct reads + MCP mutations
- FileSystemProvider auto-discovery for tools/resources/prompts
- Visibility system with `unlock_tools` per-session toggle

### Changed
- Refactored from monolithic server to 5-band architecture
- Split controllers/dependencies into db, repos, services, audio, external, uow

## [0.5.0] — 2026-04-08

### Added
- Transition system redesign: 6-component scoring (+ timbral)
- Section-aware scoring with SectionContext
- Context-aware TransitionIntent with per-template phase tables
- Style recommendation + TransitionRecipeEngine design

## [0.4.0] — 2026-04-06

### Added
- P1 analyzers: danceability, tempogram, dissonance, dynamic_complexity, tonnetz, beats_loudness
- P2 analyzers: spectral_complexity, pitch_salience, bpm_histogram, phrase
- Two-phase pipeline: independent → dependent analyzers
- Audio core layer: AnalysisContext, AudioLoader, FrameParams
- Per-analyzer clip duration (60s stitched multi-window)
- Shared onset envelope cache

### Changed
- Audio module refactored to layered architecture: core/ → analyzers/ → classification/ → pipeline
- MoodClassifier refactored to Strategy pattern with SubgenreProfile dataclasses

## [0.3.0] — 2026-03-25

### Added
- Background tasks via FastMCP Docket for long-running tools
- Error masking + retry middleware for production safety
- Real MP3 download from Yandex Music API with iCloud stub detection
- BPM, Key, Beat, MFCC analyzers (librosa) + MP3 input support
- Transition scoring: compute + persist via TransitionScorer
- GA/Greedy optimizer wired to build_set tool
- Structured output: tracks tools return Pydantic models

### Changed
- Plugin bumped to v0.3.0 (51 tools: 47 visible + 4 atomic hidden)
- Server switched to FileSystemProvider

## [0.2.0] — 2026-03-24

### Added
- Hidden atomic tools layer + mood persist in DB
- Composable tools for playlist expansion and YM sync
- YM tools connected to real YandexMusicClient via DI

### Fixed
- Plugin spec alignment: .mcp.json, hooks format, marketplace.json

## [0.1.0] — 2026-03-24

### Added
- Project requirements specification (REQUIREMENTS.md)
- Architecture design specification
- Claude Code plugin with 5 DJ workflow skills
- 44 MCP tools across 10 categories
- 44 SQLAlchemy models
- Yandex Music async client with rate limiter
- Audio pipeline: 3 core analyzers (loudness, energy, spectral)
- MoodClassifier for 15 techno subgenres
- TransitionScorer: 5-component formula
- GA optimizer + greedy chain builder + 8 DJ set templates
- Export: M3U8, Rekordbox XML, JSON guide, cheat sheet
- FastMCP v3.1 server with db_lifespan, visibility system, DI
