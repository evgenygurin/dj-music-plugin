---
description: REST API wrapper patterns (app/api/server.py)
globs: app/api/server.py
---

# REST API (FastAPI Wrapper)

- `app/api/server.py` is a thin wrapper exposing MCP tools over HTTP — **never duplicate business logic here**
- All business logic lives in MCP tools/services. REST API only proxies `mcp.call_tool()`
- Run: `uv run --extra http uvicorn app.api.server:api --host 0.0.0.0 --port 8000 --reload`

## Endpoints

- `GET /api/health` — server status + tool count + MCP readiness
- `GET /api/tools` — list all tools with inputSchema (filter: `?tag=core`)
- `GET /api/tools/{name}` — single tool metadata
- `GET /api/tools/{name}/schema` — JSON Schema for form generation
- `POST /api/tools/{name}/call` — execute tool with `{"arguments": {...}}`
- `POST /mcp` — native MCP StreamableHTTP transport

## Patterns

- Tool discovery is static (at import time via FileSystemProvider) — no DB needed for Swagger
- MCP lifespan failure is graceful: discovery works, execution returns 503
- CORS allows `localhost:3000` (panel dev) and `*.vercel.app` (production)
- Pydantic models: `ToolCallRequest`, `ToolCallResponse`, `ToolInfo`, `ToolListResponse`
