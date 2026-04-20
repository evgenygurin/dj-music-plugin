# FastMCP v3 Polish — Design Spec

**Date:** 2026-04-20
**Scope:** Code-level alignment of `dj-music-plugin` with canonical FastMCP v3.0
surface. Deduplicates custom middleware against built-ins, migrates per-tool
timeout from middleware to the native `@tool(timeout=N)` decorator parameter,
extends the existing `fastmcp.json`, fixes CORS headers for browser MCP clients.
**Status:** Design — awaiting implementation.
**Target release:** `v1.0.3` (patch, no MCP surface changes).
**Successor spec:** `fastmcp-tasks-migration` (adds `@tool(task=True)` + Docket +
Redis + REST `/mcp` mount — out of scope here).

---

## 1. Purpose

After a thorough read of FastMCP v3 `docs/`, `examples/`, and `v3-notes/`, an
audit of `app/` revealed that ~90% of the v1 blueprint surface is already
canonical. Six middleware duplicate FastMCP built-ins, one uses the wrong
paradigm (middleware reading `tool.meta["timeout_s"]` instead of the native
`@tool(timeout=N)` parameter), CORS lacks MCP-protocol headers required for
browser clients, and `fastmcp.json` exists but is missing `environment` and
`deployment.env` sections.

This spec closes those gaps in three sequential PRs against `dev`. Total
deliverable: **~600 LOC removed, ~200 added, ~2 days calendar, ~6-8 hours work**.

## 2. Scope

**In scope (10 changes, 3 PRs):**

**PR1 `refactor/middleware-dedupe`** (pp. 1-7):
1. Delete `app/server/middleware/otel_tracing.py` — FastMCP v3 ships native
   OTEL instrumentation with MCP semantic conventions.
2. Replace `DetailedTimingMiddleware` with
   `fastmcp.server.middleware.timing.DetailedTimingMiddleware`.
3. Replace `StructuredLoggingMiddleware` with
   `fastmcp.server.middleware.logging.StructuredLoggingMiddleware`.
4. Replace `ResponseLimitingMiddleware` with
   `fastmcp.server.middleware.response_limiting.ResponseLimitingMiddleware`.
5. Replace `ResponseCachingMiddleware` with
   `fastmcp.server.middleware.caching.ResponseCachingMiddleware` + explicit
   `CallToolSettings(included_tools=<read-only list>)`.
6. Replace `RetryMiddleware` with
   `fastmcp.server.middleware.error_handling.RetryMiddleware` with
   `retry_exceptions=(TransientError,)`. Move `TransientError` to
   `app/shared/errors.py`.
7. Rename `ErrorHandlingMiddleware` → `DomainErrorMiddleware` to avoid name
   collision with FastMCP's built-in `ErrorHandlingMiddleware`.

**PR2 `refactor/tool-timeout-migration`** (p. 8):
8. Delete `app/server/middleware/tool_timeout.py` and
   `ToolCallTimeoutMiddleware` from `ALL_MIDDLEWARE`. Add `timeout=N` to each of
   the 14 `@tool(...)` decorators per the category table in §4.2. Drop
   `settings.mcp.default_tool_timeout_s` from `app/config/mcp.py` (not used
   elsewhere).

**PR3 `feat/fastmcp-json-and-cors`** (pp. 10, 12):
9. Extend `fastmcp.json` with `environment` (uv / python 3.12 / project) and
   `deployment.env` with `${VAR}` interpolation for DJ_* env vars.
10. Fix CORS in `app/rest/app.py`: explicit `allow_headers` including
    `mcp-protocol-version`, `mcp-session-id`, `Authorization`, `Content-Type`;
    `expose_headers=["mcp-session-id"]`; narrow `allow_methods` from `["*"]` to
    explicit `["GET", "POST", "DELETE", "OPTIONS"]`.

**Non-goals (deferred to separate specs):**

- `@tool(task=True)` + Docket + Redis — requires infrastructure, own spec.
- REST API `api.mount("/mcp", mcp.http_app())` — coupled to Docket lifecycle.
- Docstring-based parameter descriptions for all 47 functions — DX polish
  without behavioral change; own minor spec when we want a clean-code day.
- `ctx.transport` branching, `dereference_schemas=False`, tool/resource icons —
  minor features, individually trivial.
- `EntityRegistry` → `Provider` subclass refactor — large architectural change
  with no forcing function.
- Phase 7 cutover `app/v1_legacy` cleanup — own blueprint phase.

## 3. Release Positioning

- **Version:** `v1.0.3`. Pure patch — MCP-facing surface (13 tools + 27
  resources + 6 prompts, their names, schemas, annotations) is unchanged.
- **Breaking changes (internal to codebase only):**
  - Import path: `from app.server.middleware.error_handling import
    ErrorHandlingMiddleware` → `from app.server.middleware.domain_error import
    DomainErrorMiddleware`.
  - Import path: `from app.server.middleware.retry import TransientError` →
    `from app.shared.errors import TransientError`. Re-export shim kept in
    `app/server/middleware/retry.py` for one release; deletable in `v1.0.4`.
  - `tool.meta["timeout_s"]` convention dropped (was unused — no production
    tool set it). If any test or script did set it, they must migrate.
- **Error-message changes:** timeout violations now surface as native MCP
  error code `-32000` with text `"Tool '<name>' exceeded timeout of <N>s"`
  rather than `ToolError("tool '<name>' timed out after <N>s")`. No MCP client
  parses this text; structurally both are `CallToolResult(isError=True)`.
- **Changelog entry:**
  - `Changed:` replaced 5 custom middleware with canonical FastMCP v3 built-ins;
    renamed `ErrorHandlingMiddleware` → `DomainErrorMiddleware`; moved
    per-tool timeout from custom middleware to native `@tool(timeout=N)`.
  - `Added:` `fastmcp.json` environment/env sections for declarative runtime
    config; CORS headers for browser MCP clients (`mcp-protocol-version`,
    `mcp-session-id` across `allow_headers` + `expose_headers`).
  - `Removed:` `OTELTracingMiddleware` (FastMCP ships native OTEL tracing);
    `ToolCallTimeoutMiddleware` (replaced by decorator parameter);
    `settings.mcp.default_tool_timeout_s`.

## 4. Technical Design

### 4.1 Middleware pipeline (post-PR1+PR2)

Count drops from **16 → 14** (two removed — `OTELTracingMiddleware` and
`ToolCallTimeoutMiddleware`; one renamed — `ErrorHandlingMiddleware` →
`DomainErrorMiddleware`; five replaced with imports of built-ins — timing,
retry, response-caching, response-limit, structured-logging).

```python
# app/server/middleware/__init__.py (post-PR1+PR2 shape)

from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ListPromptsSettings,
    ListResourcesSettings,
    ListToolsSettings,
    ReadResourceSettings,
    ResponseCachingMiddleware,
)
from fastmcp.server.middleware.error_handling import RetryMiddleware
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import DetailedTimingMiddleware

from app.config import Settings
from app.server.middleware.audit_log import AuditLogMiddleware
from app.server.middleware.cost_tracking import CostTrackingMiddleware
from app.server.middleware.db_session import DbSessionMiddleware
from app.server.middleware.deprecation_warning import DeprecationWarningMiddleware
from app.server.middleware.domain_error import DomainErrorMiddleware
from app.server.middleware.progress_throttle import ProgressThrottleMiddleware
from app.server.middleware.provider_rate_limit import ProviderRateLimitMiddleware
from app.server.middleware.sampling_budget import SamplingBudgetMiddleware
from app.server.middleware.sentry_context import SentryContextMiddleware
from app.shared.errors import TransientError

_READ_ONLY_TOOLS: tuple[str, ...] = (
    "entity_list",
    "entity_get",
    "entity_aggregate",
    "provider_read",
    "provider_search",
    "transition_score_pool",
)

def build_middleware_list(settings: Settings) -> list:
    """Construct the 10-middleware pipeline in canonical order (outer→inner)."""
    return [
        # 1 outermost — domain-error → ToolError translation
        DomainErrorMiddleware(mask_details=not settings.mcp.debug),
        # 2 — sentry breadcrumb context
        SentryContextMiddleware(),
        # (OTEL middleware removed — FastMCP v3 native tracing)
        # 3 — per-tool timing (built-in)
        DetailedTimingMiddleware(),
        # 4 — audit-log of mutations
        AuditLogMiddleware(),
        # 5 — retry transient errors (built-in)
        RetryMiddleware(max_retries=2, retry_exceptions=(TransientError,)),
        # 6 — cap response size (built-in)
        ResponseLimitingMiddleware(max_size=settings.mcp.response_max_bytes),
        # 7 — cache read-only tool calls (built-in, explicit opt-in per tool)
        ResponseCachingMiddleware(
            call_tool_settings=CallToolSettings(
                ttl=settings.mcp.response_cache_ttl,
                included_tools=list(_READ_ONLY_TOOLS),
            ),
            list_tools_settings=ListToolsSettings(enabled=False),
            list_resources_settings=ListResourcesSettings(enabled=False),
            list_prompts_settings=ListPromptsSettings(enabled=False),
            read_resource_settings=ReadResourceSettings(enabled=False),
        ),
        # 8 — warn on deprecated tool version calls
        DeprecationWarningMiddleware(),
        # 9 — provider/LLM cost accounting
        CostTrackingMiddleware(),
        # 10 — LLM sampling budget per session
        SamplingBudgetMiddleware(),
        # 11 — throttle progress events to 1/sec
        ProgressThrottleMiddleware(),
        # (ToolCallTimeoutMiddleware removed — @tool(timeout=N))
        # 12 — Yandex Music rate limit
        ProviderRateLimitMiddleware(),
        # 13 — open UoW, commit/rollback
        DbSessionMiddleware(),
        # 14 innermost — structured log at tool boundary (built-in)
        StructuredLoggingMiddleware(include_payloads=False, max_payload_length=500),
    ]
```

Changes to `app/server/app.py`:

```python
def register_middleware(mcp: FastMCP, settings: Settings) -> None:
    for mw in build_middleware_list(settings):
        mcp.add_middleware(mw)

def build_mcp_server() -> FastMCP:
    bootstrap_observability()
    settings = get_settings()
    root = _v2_root()
    mcp = FastMCP(
        name="dj-music-v2",
        providers=[
            FileSystemProvider(root=root / "tools"),
            FileSystemProvider(root=root / "resources"),
            FileSystemProvider(root=root / "prompts"),
        ],
        transforms=build_pre_constructor_transforms(),
        lifespan=build_server_lifespan(),
        sampling_handler=build_sampling_handler(),
    )
    register_post_constructor_transforms(mcp)
    register_middleware(mcp, settings)  # now needs settings
    apply_visibility_policy(mcp)
    return mcp
```

Files to delete in PR1:
- `app/server/middleware/otel_tracing.py`
- `app/server/middleware/timing.py`
- `app/server/middleware/retry.py` (becomes a re-export shim → `app/shared/errors.py`)
- `app/server/middleware/response_caching.py`
- `app/server/middleware/response_limit.py`
- `app/server/middleware/structured_logging.py`

File to create in PR1:
- `app/server/middleware/domain_error.py` — renamed from `error_handling.py`,
  same implementation (maps `NotFoundError`/`ValidationError`/`ConflictError`/
  `NotAllowedError`/`DJMusicError` → `ToolError`).

File to delete at end of PR1:
- `app/server/middleware/error_handling.py`

Import-linter contract `tools-thin` (blueprint §16): unchanged — middleware
still forbidden from importing `app.tools`.

### 4.2 Timeout migration (PR2)

**Current state:** `ToolCallTimeoutMiddleware` wraps every tool call in
`asyncio.wait_for(call_next(context), timeout=T)` where `T` is read from
`tool.meta["timeout_s"]` or `settings.mcp.default_tool_timeout_s = 300.0`. **No
tool in `app/tools/**/*.py` sets `meta["timeout_s"]`** — all use the 300s
fallback.

**Target state:** FastMCP's native `@tool(timeout=N)` parameter. The server
itself wraps the handler via `asyncio.wait_for` and raises MCP error `-32000`
on expiry. No middleware needed.

**Per-tool timeout values (new):**

| Tool | Category | `timeout=` |
|---|---|---|
| `entity_list` | fast read | `30.0` |
| `entity_get` | fast read | `30.0` |
| `entity_aggregate` | fast read | `30.0` |
| `provider_read` | fast read (YM is network-bound but quick) | `30.0` |
| `provider_search` | fast read | `30.0` |
| `unlock_namespace` | admin, instant | `30.0` |
| `tool_invoke` | admin proxy | `30.0` |
| `entity_create` | write, may trigger handler (import/download/analyze) | `120.0` |
| `entity_update` | write, may trigger reanalyze | `120.0` |
| `entity_delete` | write | `120.0` |
| `provider_write` | YM mutation (add/remove tracks, create playlist) | `120.0` |
| `transition_score_pool` | compute, N×N pairwise scoring on full pool | `300.0` |
| `sequence_optimize` | compute, GA over pool | `300.0` |
| `playlist_sync` | paginated YM pull/push | `180.0` |

Pattern per file:

```python
@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    timeout=30.0,  # <-- new
    description=...,
)
async def entity_list(...) -> EntityListResult:
    ...
```

**Files changed:** 14 tool files in `app/tools/**/*.py`.

**Files deleted:** `app/server/middleware/tool_timeout.py`.

**Config cleanup:** remove `default_tool_timeout_s` field from
`app/config/mcp.py`.

**Verification grep:** `rg 'timeout_s|default_tool_timeout|ToolCallTimeoutMiddleware' app/ tests/`
→ only result allowed is `app/providers/yandex/client.py:timeout_s` (HTTP
client timeout, unrelated).

### 4.3 fastmcp.json extension (PR3, part 1)

Current file (12 lines) declares only `source` and minimal `deployment`. Plan
adds `environment` (so `fastmcp run` / `fastmcp dev inspector` can create a
uv-managed environment declaratively) and `deployment.env` with `${VAR}`
interpolation so secrets stay in `.env` rather than duplicated across shell
profiles.

```json
{
  "$schema": "https://gofastmcp.com/public/schemas/fastmcp.json/v1.json",
  "source": {
    "type": "filesystem",
    "path": "server.py",
    "entrypoint": "mcp"
  },
  "environment": {
    "type": "uv",
    "python": ">=3.12",
    "project": "."
  },
  "deployment": {
    "transport": "stdio",
    "log_level": "INFO",
    "env": {
      "DJ_DB_URL": "${DJ_DB_URL}",
      "DJ_YM_TOKEN": "${DJ_YM_TOKEN}",
      "DJ_YM_USER_ID": "${DJ_YM_USER_ID}",
      "DJ_YM_LIBRARY_PATH": "${DJ_YM_LIBRARY_PATH}",
      "DJ_SENTRY_DSN": "${DJ_SENTRY_DSN}",
      "DJ_MCP_CODE_MODE": "${DJ_MCP_CODE_MODE:-0}"
    }
  }
}
```

`plugin.json` already invokes `fastmcp run fastmcp.json --no-banner` — no
change needed.

**Not creating** `dev.fastmcp.json` / `prod.fastmcp.json` — `.env` + the
`DJ_PLUGIN_DEV_PATH` escape hatch from `CLAUDE.md` already handle the dev/prod
split.

### 4.4 CORS headers (PR3, part 2)

Change `app/rest/app.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],  # was ["*"]
    allow_headers=[                                       # was ["*"]
        "mcp-protocol-version",
        "mcp-session-id",
        "Authorization",
        "Content-Type",
    ],
    expose_headers=["mcp-session-id"],                    # new
)
```

**Why this matters:** MCP Inspector and any future browser-resident MCP client
set `mcp-protocol-version` and `mcp-session-id` headers on requests, and read
`mcp-session-id` from responses for session tracking. With `allow_origins !=
"*"` and `allow_credentials=True`, the browser CORS preflight requires
explicit `allow_headers` rather than `"*"`, and session tracking requires
explicit `expose_headers`.

## 5. Testing Strategy

**Principle:** trust FastMCP core tests for built-in middleware. Our
responsibility is verifying the pipeline composes correctly and our custom
middleware still interact well with the built-ins.

### Per-PR verification

| PR | Command | Expected |
|---|---|---|
| PR1 | `make check` (ruff + format + mypy + lint-imports + pytest -q) | All green. Updated `tests/test_server/test_middleware/` only covers our remaining custom middleware. |
| PR1 | `uv run python -c "from app.server.app import build_mcp_server; mcp = build_mcp_server(); print(len(mcp._middleware))"` | `10` (was `16`). |
| PR1 | `opentelemetry-instrument uv run fastmcp run fastmcp.json` + exercise one tool + check traces | Native spans `tools/call entity_list` present with `gen_ai.tool.name` attribute. No parallel `mcp.tool.entity_list` spans. |
| PR2 | `rg "timeout_s\|default_tool_timeout\|ToolCallTimeoutMiddleware" app/ tests/` | Only `app/providers/yandex/client.py:timeout_s` remains. |
| PR2 | `uv run fastmcp inspect fastmcp.json --format fastmcp \| jq '.tools[] \| {name, timeout: .meta.fastmcp.timeout}'` | Each tool reports expected timeout from §4.2 table. |
| PR3 | `uv run fastmcp run fastmcp.json --no-banner` then connect Claude Code | Server starts, 13 tools + 27 resources + 6 prompts discoverable. |
| PR3 | `curl -i -X OPTIONS http://localhost:8000/api/tools/entity_list/call -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: mcp-session-id"` | `Access-Control-Allow-Headers: mcp-protocol-version, mcp-session-id, Authorization, Content-Type` + `Access-Control-Expose-Headers: mcp-session-id`. |

### Tests to remove in PR1

- `tests/test_server/test_middleware/test_otel_tracing.py` (middleware removed)
- `tests/test_server/test_middleware/test_retry.py` (replaced by built-in;
  FastMCP tests it)
- `tests/test_server/test_middleware/test_timing.py` (ditto)
- `tests/test_server/test_middleware/test_response_caching.py` (ditto)
- `tests/test_server/test_middleware/test_response_limit.py` (ditto)
- `tests/test_server/test_middleware/test_structured_logging.py` (ditto)
- `tests/test_server/test_middleware/test_tool_timeout.py` (removed in PR2)

Each removal PR must check that the test file actually exists before deleting
(some may already be absent in the current codebase).

### Tests to rename in PR1

- `tests/test_server/test_middleware/test_error_handling.py` →
  `test_domain_error.py`, updating imports to `DomainErrorMiddleware`.

### No new tests are added.

## 6. Rollout Plan

| PR | Branch | Base | Summary | Approx diff |
|---|---|---|---|---|
| PR1 | `refactor/middleware-dedupe` | `dev` | Remove 6 middleware, rename 1, update `ALL_MIDDLEWARE`, move `TransientError` | −600 / +150 |
| PR2 | `refactor/tool-timeout-migration` | `dev` (after PR1 merge) | Remove `ToolCallTimeoutMiddleware`, add `timeout=N` on 14 decorators, drop `default_tool_timeout_s` config field | −80 / +40 |
| PR3 | `feat/fastmcp-json-and-cors` | `dev` (after PR2 merge) | Extend `fastmcp.json`, tighten CORS | −5 / +20 |

**Merge strategy:** squash merge into `dev`. After all three land, one release
PR `dev` → `main` with tag `v1.0.3` and CHANGELOG entry from §3.

**Checkpoints:** after each PR merge, pause for maintainer review of the merged
diff before starting the next branch. If review surfaces issues, fix in the
same branch — do not cascade into the next PR.

**Timeline:** ~2 calendar days. ~6-8 hours work.

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Built-in middleware behavior drifts subtly from our custom versions (edge cases in caching keys, truncation boundaries, retry delays). | Each PR includes a smoke test on the dev `fastmcp run fastmcp.json` server exercising one read-only + one write + one compute tool. Documented as a PR description step. If divergence is found, retain our custom in that slot and document why. |
| Removing `OTELTracingMiddleware` breaks downstream Grafana/Jaeger dashboards keyed on `mcp.tool.X` span names. | Native OTEL uses `tools/call {name}`. Dashboard migration is a downstream concern, NOT in scope. If a dashboard owner flags this pre-merge, we keep the custom OTEL middleware (renaming spans to `legacy.mcp.tool.X`) until dashboards migrate — handled out-of-band. |
| Built-in `ResponseCachingMiddleware` default caches all tools, including mutating ones. Our custom only cached `readOnlyHint=True` tools. | Explicit `CallToolSettings(included_tools=_READ_ONLY_TOOLS)` with the six names from §4.1. All other operations (`list_*`, `read_resource`, `get_prompt`) have `enabled=False`. No accidental write caching. |
| `@tool(timeout=N)` returns native MCP error `-32000`; Panel actions may have expected the older `ToolError(...)` text format. | `panel/actions/*.ts` routes through `mcpCall()` → checks `result.is_error` boolean + generic message. Text not parsed. Verified by running `rg "timed out after" panel/` — should return no match. If it does, update the parsing. |
| `fastmcp.json` `${VAR}` interpolation requires vars in shell env at server start. Today we rely on `python-dotenv` inside `app.config`. | `plugin.json` already does `bash -c "cd ... && exec uv run fastmcp run fastmcp.json"` — bash does NOT source `.env` before `exec`. Interpolation may fail with empty strings. **Mitigation:** add `source .env 2>/dev/null ||` before `exec` in `plugin.json`. Alternatively, pass `--env-file .env` to `fastmcp run`. Verify with `uv run fastmcp run fastmcp.json --no-banner` in a clean shell. |
| `allow_credentials=True` with wildcard `allow_origins` is a CORS violation in browsers. | Current `allow_origins` is already an explicit list of two entries. We do NOT widen it. |
| `TransientError` import path changes; handlers may import it from the old location. | Pre-PR1 step: `rg "from app.server.middleware.retry import" app/` → fix any hits. Keep a re-export shim `app/server/middleware/retry.py` exporting `TransientError` for one release cycle; delete in `v1.0.4`. |
| `register_middleware(mcp, settings)` now takes `settings` — tests that call it without `settings` will break. | `build_mcp_app_for_tests(**overrides)` in `app/server/app.py` already calls `register_middleware`; update it to pass `get_settings()` (or a test override). Grep: `rg "register_middleware" app/ tests/`. |

## 8. Appendix — files touched summary

**PR1 (refactor/middleware-dedupe):**
- Delete: `app/server/middleware/{otel_tracing,timing,response_caching,response_limit,structured_logging}.py`.
- Rename: `app/server/middleware/error_handling.py` → `app/server/middleware/domain_error.py` (including class rename).
- Reduce to re-export shim: `app/server/middleware/retry.py` → re-exports `TransientError` from `app/shared/errors.py`.
- Modify: `app/server/middleware/__init__.py` (new imports + `build_middleware_list`).
- Modify: `app/server/app.py` (`register_middleware(mcp, settings)` signature).
- Modify: `app/shared/errors.py` (add `TransientError`).
- Test cleanup: delete 6 middleware-specific test files if present; rename `test_error_handling.py` → `test_domain_error.py`.
- Blueprint docs: update `docs/architecture.md` and `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §11 middleware table from 16 → 14.

**PR2 (refactor/tool-timeout-migration):**
- Delete: `app/server/middleware/tool_timeout.py`.
- Modify: `app/server/middleware/__init__.py` (remove from `ALL_MIDDLEWARE`).
- Modify: 14 files in `app/tools/**/*.py` (add `timeout=N`).
- Modify: `app/config/mcp.py` (drop `default_tool_timeout_s`).
- Test cleanup: delete `test_tool_timeout.py` if present.

**PR3 (feat/fastmcp-json-and-cors):**
- Modify: `fastmcp.json` (add `environment` + `deployment.env`).
- Modify: `app/rest/app.py` (CORS headers).
- Modify: `.claude-plugin/plugin.json` (add `source .env` before `exec` if
  interpolation verification requires it — see §7 risk).

## 9. Sign-off checklist

Before starting PR1:

- [ ] Spec reviewed and approved by maintainer.
- [ ] `rg "from app.server.middleware.retry import" app/` enumerates all
  `TransientError` importers; list attached to PR description.
- [ ] `rg "register_middleware" app/ tests/` enumerates all call sites;
  signature migration plan attached.
- [ ] `rg "tool.meta\[.timeout_s.\]|meta=\{.*timeout_s" app/ tests/ scripts/`
  confirms no production code sets per-tool timeout today.
- [ ] Clean shell test of `fastmcp run fastmcp.json` validates env
  interpolation path before PR3.

Sign-off: `___________________________________________`

Date: `______________`
