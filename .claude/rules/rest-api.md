---
description: REST API wrapper patterns
globs: src/dj_music/api/**/*.py
---

# REST API (FastAPI Wrapper)

- `src/dj_music/api/server.py` is a thin wrapper exposing MCP tools over HTTP — **never duplicate business logic here**
- All business logic lives in MCP tools/services. REST API only proxies `mcp.call_tool()`
- Run: `uv run --extra http uvicorn dj_music.api.server:api --host 0.0.0.0 --port 8000 --reload`

## Endpoints

- `GET /api/health` — server status + tool count + MCP readiness
- `GET /api/tools` — list all tools with inputSchema (filter: `?tag=core`)
- `GET /api/tools/{name}` — single tool metadata
- `GET /api/tools/{name}/schema` — JSON Schema for form generation
- `POST /api/tools/{name}/call` — execute tool with `{"arguments": {...}}`
- `POST /mcp` — native MCP StreamableHTTP transport

## Module Structure

- `src/dj_music/api/server.py` — app creation, CORS, router inclusion, `/mcp` mount. NEVER add route logic here
- `src/dj_music/api/state.py` — `ApiRuntimeState` dataclass (tool cache, MCP readiness, YM client, URL cache)
- `src/dj_music/api/lifespan.py` — MCP startup, degraded-mode fallback
- `src/dj_music/api/schemas.py` — Pydantic request/response models
- `src/dj_music/api/openapi.py` — OpenAPI tags, examples, version lookup
- `src/dj_music/api/routes/health.py` — `/api/health`
- `src/dj_music/api/routes/discovery.py` — `/api/tools`, `/api/tools/{name}`, `/api/tools/{name}/schema`
- `src/dj_music/api/routes/execution.py` — `POST /api/tools/{name}/call`
- `src/dj_music/api/routes/audio.py` — `GET /api/audio/stream/{ym_track_id}`
- `src/dj_music/api/services/tool_registry.py` — `ToolRegistry` (static tool metadata cache)
- `src/dj_music/api/services/signed_url_cache.py` — `SignedUrlCache` (YM download URL TTL cache)
- `src/dj_music/api/services/ym_audio_proxy.py` — `YmAudioProxy` (stream YM audio)

## Patterns

- Tool discovery is static (at import time via FileSystemProvider) — no DB needed for Swagger
- MCP lifespan failure is graceful: discovery works, execution returns 503
- CORS allows `localhost:3000` (panel dev) and `*.vercel.app` (production)
- Route handlers access runtime via `request.app.state.runtime: ApiRuntimeState`
- NEVER import `dj_music.models` or `dj_music.repositories` from `dj_music.api` — enforced by import-linter
