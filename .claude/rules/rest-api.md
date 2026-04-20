---
description: REST API wrapper patterns (v1 layout)
globs: app/rest/**/*.py
---

# REST API (FastAPI Wrapper)

- `app/rest/app.py` is a thin wrapper exposing MCP tools over HTTP —
  **never duplicate business logic here**.
- All business logic lives in MCP tools / handlers / domain. REST API
  only proxies `mcp.call_tool()`.
- Run:
  `uv run --extra http uvicorn app.rest.app:api --host 0.0.0.0 --port 8000 --reload`.

## Endpoints (current, as of v1.0.3)

- `GET /api/health` — overall status + `mcp_ready` + tool count + `degraded_reason`
- `GET /api/tools?tag=...` — list tools (`ToolSummary`: name, description, tags)
- `GET /api/tools/{name}` — single tool metadata
- `POST /api/tools/{name}/call` — execute tool; body `{"arguments": {...}}`
  returns `{"result": ..., "is_error": bool, "error": str?}`

There is currently NO `/mcp` StreamableHTTP mount, NO
`/api/tools/{name}/schema` endpoint, and NO `audio` route. Earlier
designs referenced those; they are deferred.

## Module Structure (`app/rest/`)

- `app.py` — app factory (`build_rest_app()` → `api`), CORS, router
  inclusion. No route logic.
- `state.py` — `ApiRuntimeState` dataclass: `mcp`, `mcp_ready`,
  `degraded_reason`, `tool_cache`. (No provider client cache, no
  signed-URL cache.)
- `lifespan.py` — imports `build_mcp_server()` on startup; on failure
  the server stays up in degraded mode (`mcp_ready=False`).
- `schemas.py` — `HealthResponse`, `ToolSummary`, `ToolCallRequest`,
  `ToolCallResponse`.
- `routes/health.py`, `routes/discovery.py`, `routes/execution.py`.

## Patterns

- Tool discovery is async via `runtime.mcp.list_tools()` — relies on
  FileSystemProvider auto-discovery at MCP build time.
- MCP build failure is graceful: health reports `degraded`, execution
  returns 503, discovery returns 503 (`runtime.mcp is None`).
- CORS origin list comes from `DJ_MCP_CORS_ALLOW_ORIGINS` (CSV or JSON
  array). Default is `http://localhost:3000`. No wildcard
  `*.vercel.app` is trusted — deployers opt in explicitly.
- Allowed methods: `GET, POST, DELETE, OPTIONS`. Allowed headers
  include `mcp-protocol-version`, `mcp-session-id`, `Authorization`,
  `Content-Type`.
- Route handlers access runtime via `request.app.state.runtime`.
- NEVER import `app.models` or `app.repositories` from `app.rest` —
  enforced by import-linter. REST talks to MCP, not the DB.
