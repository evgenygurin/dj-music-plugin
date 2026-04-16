---
description: Bootstrap composition root — server assembly, middleware, transforms, lifespans, FileSystemProvider
globs:
  - app/bootstrap/**/*.py
  - app/server.py
---

# Bootstrap

The bootstrap layer wires all server components together. Never add business logic here.

## `server_builder.py` — composition root

Call order is fixed:

```python
mcp = FastMCP(
    providers=[FileSystemProvider(mcp_dir)],      # auto-discovers controllers/
    transforms=build_pre_constructor_transforms(), # ToolTransform before first load
    lifespan=build_server_lifespan(),
    sampling_handler=sampling_handler,
)
register_post_constructor_transforms(mcp)  # PromptsAsTools, ResourcesAsTools
register_middleware(mcp, ...)              # after transforms
apply_visibility_policy(mcp)              # mcp.disable(tags=...) — always last
```

**Order is critical.** Violating it causes invisible bugs (transforms on wrong tool set, visibility ignoring middleware, etc.).

## Lifespans (`lifespans.py`)

Decorator: `@lifespan` from `fastmcp.server.lifespan`.
Composition: `|` operator — enter left→right, exit right→left, dicts merged.

```python
return db_lifespan | provider_lifespan | analyzer_lifespan | cache_lifespan
```

| Lifespan | Keys yielded |
|----------|-------------|
| `db_lifespan` | `db_engine`, `db_session_factory` |
| `provider_lifespan` | `provider_registry`, `ym_client` |
| `analyzer_lifespan` | `analyzer_registry` |
| `cache_lifespan` | `transition_cache` |

Access in tools via DI helpers, not `ctx.lifespan_context` directly.

**Adding a lifespan**: decorate with `@lifespan`, yield a dict, append `| new_lifespan` in `build_server_lifespan()`. Always `try/finally` for cleanup.

## Middleware Pipeline (ordered, `middleware.py`)

| # | Middleware | Purpose |
|---|-----------|---------|
| 1 | `ToolCallTimeoutMiddleware` | per-tool timeouts (build_set=120s, analyze_batch=600s) |
| 2 | `StructuredLoggingMiddleware` | JSON structured logs |
| 3 | `DetailedTimingMiddleware` | latency tracking |
| 4 | `ResponseLimitingMiddleware(max_size=50_000)` | truncate giant responses |
| 5 | `ResponseCachingMiddleware` | **currently disabled** (both call_tool + read_resource) |
| 6 | `YMRateLimitMiddleware` | rate-limit YM API calls |
| 7 | `ErrorHandlingMiddleware` | structured errors + Sentry callback |
| 8 | `RetryMiddleware(max_retries=2)` | retry transient errors |

To add a new middleware: `mcp.add_middleware(MyMiddleware(...))` in `register_middleware()`. First added = outermost layer.

## ToolTransform (`transforms.py`)

**`build_pre_constructor_transforms()`** — passed to `FastMCP(transforms=...)`:
- One `ToolTransform({name: ToolTransformConfig(...)})` dict with all transformed tools
- Rewrite `description` for action-dispatched tools (enumerate all `action` values)
- Hide internal params: `ArgTransformConfig(hide=True, default=10)` for `top_n`, `batch_size`
- Rewrite `data` param descriptions (enumerate payload shape per action)

**`register_post_constructor_transforms()`** — after `mcp` is created:
- `ResourcesAsTools(mcp)` — exposes resources as callable tools
- `PromptsAsTools(mcp)` — exposes prompts as callable tools
- Both wrapped in `try/except ImportError`

## Visibility Policy (`visibility.py`)

```python
_DISABLED_AT_STARTUP = frozenset({"delivery","discovery","curation","sync","ym","audio","memory"})
apply_visibility_policy(mcp)  # calls mcp.disable(tags=_DISABLED_AT_STARTUP)
```

Server-level (all sessions). Users unlock per-session via `unlock_tools(action="unlock", category="...")` which calls `ctx.enable_components(tags={cat})`.

**Adding a hidden category**: add tag to `_DISABLED_AT_STARTUP`, tag your tools, update `unlock_tools` help text in `admin.py`.

## Sampling (`sampling.py`)

- Set `DJ_ANTHROPIC_API_KEY` to enable server-side Anthropic fallback
- Without it: LLM client passes `search_queries=[...]` as tool parameters directly
- `behavior="fallback"` — sampling only used if client doesn't provide queries

## FileSystemProvider Auto-Discovery

Recursively scans `app/controllers/` for `@tool`, `@resource`, `@prompt` decorators.
- Tools/resources: **no `__init__.py` needed**
- Prompts: must be in `app/controllers/prompts/workflows/__init__.py` `__all__`

## Gotchas

- `apply_visibility_policy` must run AFTER `register_middleware` — order matters
- Do NOT add transforms after `apply_visibility_policy` — disabled tools won't be transformed
- Lifespan key collisions: later lifespan overwrites earlier. Reserved keys: `db_engine`, `db_session_factory`, `provider_registry`, `ym_client`, `analyzer_registry`, `transition_cache`
- `build_db_session_factory()` adds `statement_cache_size=0` for PostgreSQL only (pgbouncer workaround)
- `on_duplicate="warn"` in FastMCP constructor — duplicate tool names log a warning, not error
- `FileSystemProvider` scans at construction time — adding a new `@tool` file requires server restart
