---
description: REST API wrapper patterns
globs: app/api/**/*.py
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

## Module Structure

- `app/api/server.py` — app creation, CORS, router inclusion, `/mcp` mount. NEVER add route logic here
- `app/api/state.py` — `ApiRuntimeState` dataclass (tool cache, MCP readiness, YM client, URL cache)
- `app/api/lifespan.py` — MCP startup, degraded-mode fallback
- `app/api/schemas.py` — Pydantic request/response models
- `app/api/openapi.py` — OpenAPI tags, examples, version lookup
- `app/api/routes/health.py` — `/api/health`
- `app/api/routes/discovery.py` — `/api/tools`, `/api/tools/{name}`, `/api/tools/{name}/schema`
- `app/api/routes/execution.py` — `POST /api/tools/{name}/call`
- `app/api/routes/audio.py` — `GET /api/audio/stream/{ym_track_id}`
- `app/api/services/tool_registry.py` — `ToolRegistry` (static tool metadata cache)
- `app/api/services/signed_url_cache.py` — `SignedUrlCache` (YM download URL TTL cache)
- `app/api/services/ym_audio_proxy.py` — `YmAudioProxy` (stream YM audio)

## Patterns

- Tool discovery is static (at import time via FileSystemProvider) — no DB needed for Swagger
- MCP lifespan failure is graceful: discovery works, execution returns 503
- CORS allows `localhost:3000` (panel dev) and `*.vercel.app` (production)
- Route handlers access runtime via `request.app.state.runtime: ApiRuntimeState`
- NEVER import `app.db.models` or `app.db.repositories` from `app.api` — enforced by import-linter

## Порты (КРИТИЧНО — не менять!)

| Сервис | Порт | Назначение |
|--------|------|-----------|
| REST API (production/dev) | **8000** | `uvicorn app.api.server:api --port 8000` |
| REST API (preview) | **8001** | `.claude/launch.json` preview only |
| Panel (Next.js) | **3000** | `bun dev --port 3000` |

- **Panel `.env`**: `MCP_HTTP_URL=http://localhost:8000` — единственный source of truth
- **Все fallback'и в panel TS-коде** (`?? 'http://localhost:...'`) ДОЛЖНЫ использовать порт **8000**
- Порт 8001 используется ТОЛЬКО в `.claude/launch.json` для Claude Preview (чтобы не конфликтовать с основным сервером)
- **НЕ hardcode порты в panel коде** — всегда читай из `process.env.MCP_HTTP_URL`, fallback `8000`
- **Preview связка**: `scripts/preview-panel.sh` экспортирует `MCP_HTTP_URL=http://localhost:8001` → panel preview ходит на preview rest-api. Если меняешь порт в `launch.json` — меняй и в `preview-panel.sh`
