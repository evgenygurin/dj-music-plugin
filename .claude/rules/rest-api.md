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

## Endpoints

- `GET /api/health` — server status + tool count + MCP readiness
- `GET /api/tools` — list all tools with inputSchema (filter: `?tag=...`)
- `GET /api/tools/{name}` — single tool metadata
- `GET /api/tools/{name}/schema` — JSON Schema for form generation
- `POST /api/tools/{name}/call` — execute tool with
  `{"arguments": {...}}`
- `POST /mcp` — native MCP StreamableHTTP transport

## Module Structure (`app/rest/`)

- `app.py` — app creation, CORS, router inclusion, `/mcp` mount. No
  route logic.
- `state.py` — `ApiRuntimeState` dataclass (tool cache, MCP readiness,
  provider clients, URL cache).
- `lifespan.py` — MCP startup, degraded-mode fallback.
- `schemas.py` — Pydantic request/response models.
- `routes/health.py`, `routes/discovery.py`, `routes/execution.py`,
  `routes/audio.py`.

## Patterns

- Tool discovery is static (at import time via FileSystemProvider) —
  no DB needed for Swagger.
- MCP lifespan failure is graceful: discovery works, execution returns
  503.
- CORS allows `localhost:3000` (panel dev) and `*.vercel.app` (prod).
- Route handlers access runtime via
  `request.app.state.runtime: ApiRuntimeState`.
- NEVER import `app.models` or `app.repositories` from `app.rest` —
  enforced by import-linter. REST talks to MCP, not the DB.
