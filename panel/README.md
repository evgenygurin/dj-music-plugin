# DJ Music Plugin — Monitoring Panel

Next.js dashboard для инспекции треков, плейлистов, сетов и транзиций библиотеки DJ Music Plugin (v1.0.1). Панель — **монитор**, не генератор: чтение идёт напрямую из Supabase, мутации — через REST-обёртку над MCP.

## Стек

| Слой | Тех |
|---|---|
| Framework | Next.js 16 (App Router, RSC by default) |
| Runtime | Bun |
| UI | shadcn/ui (Base UI + Tailwind v4 через CSS-first `@theme`) |
| Icons | `@tabler/icons-react` |
| Charts | Recharts (cyberpunk magenta/cyan) |
| Theme | `next-themes`, class-based dark; Geist sans+mono локально в `app/fonts/` |
| Reads | Supabase PostgreSQL **direct** (`lib/supabase/server.ts`) |
| Mutations | Server actions → `lib/mcp-client.ts` → REST `/api/tools/{name}/call` |

## Быстрый старт

```bash
cd panel
bun install
# Seed ../.claude/dj-music.local.md from the tracked template if it's not yet present.
# The .local.md file is gitignored; never overwrite it unconditionally.
[ -f ../.claude/dj-music.local.md ] || cp ../.claude/dj-music.local.md.example ../.claude/dj-music.local.md
# Fill panel/.env.local via the /panel-setup slash-command, or copy
# NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY and MCP_HTTP_URL by hand.
bun dev                            # http://localhost:3000
```

REST API должен быть поднят:

```bash
uv run --extra http uvicorn app.rest.app:api --host 0.0.0.0 --port 8000 --reload
```

## Data flow

```text
READ:   Server component (page.tsx) → lib/queries/*.ts → Supabase SQL → typed result
WRITE:  User action → actions/*.ts (server action) → mcpCall('<tool>', args)
        → POST http://localhost:8000/api/tools/<tool>/call → FastMCP
STREAM: GET /api/audio/[trackId] → route.ts → REST_BASE/api/audio/stream/<ym_id>
        → app/rest/app.py streams MP3 with Range headers
```

## Структура

| Путь | Назначение |
|---|---|
| `panel/app/` | Pages: `/`, `/library`, `/library/[id]`, `/playlists`, `/playlists/[id]`, `/sets`, `/sets/[id]`, `/discover` |
| `panel/lib/queries/` | Supabase read-queries (dashboard, tracks, playlists, sets, mix-meta) |
| `panel/lib/supabase/` | SSR-compatible Supabase client |
| `panel/lib/mcp-client.ts` | HTTP wrapper для MCP tool calls |
| `panel/lib/constants.ts` | Subgenre colors + labels |
| `panel/actions/` | Server actions (analysis, discovery, set, sync, library, mix-meta, set-templates) |
| `panel/components/charts/` | 5 Recharts визуализаций (BPM, LUFS, mood pie, Camelot wheel, energy arc) |
| `panel/components/ui/` | shadcn компоненты (добавляются через `bunx shadcn@latest add`) |
| `panel/components/` | Domain: data-table, mood-badge, track-features, sections-timeline, transition-table, app-sidebar, audio-player |

## v1 MCP dispatcher интеграция

Server actions зовут polymorphic dispatcher'ы v1:

| Action | Вызывает |
|---|---|
| `analysis-actions.ts` | `entity_create(entity="track_features", level=2)` (включает mood classification) |
| `discovery-actions.ts` | `provider_search(provider="yandex", ...)`, `entity_create(entity="track")` |
| `set-actions.ts` | `entity_create(entity="set_version", ...)`, `transition_score_pool`, resource reads |
| `sync-actions.ts` | `playlist_sync(direction=pull\|push\|diff)` (требует `unlock_namespace(namespace="sync")`) |

> **Дрифт**: часть action'ов ещё держит старые tool-имена из v0.8 (Blueprint D2 оставил Panel refactor вне scope v1). Если встречаешь `build_set` / `analyze_track` / `ym_search` / `sync_playlist` — сверься с `docs/tool-catalog.md` и маппингом в `.claude/agents/panel-doctor.md`.

## Env vars

| Var | Default | Назначение |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | — | Supabase endpoint |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | — | Supabase anon JWT (RLS **disabled** на большинстве таблиц) |
| `MCP_HTTP_URL` | `http://localhost:8000` | REST API base |

Подробная конфигурация через `.claude/dj-music.local.md` — см. `docs/plugin-settings.md`.

## Troubleshooting

- Hydration mismatch, ECONNREFUSED, Supabase пустой результат, server action падает, Tailwind v4 класс не применяется → используй агента `panel-doctor` (`.claude/agents/panel-doctor.md`).
- Проблемы с YM API (429, diff format, revision mismatch) → `ym-api-specialist`.
- BG-процессы (BFS, L5 sweep) → `bg-jobs-watcher`.

## Дополнительно

- `panel/AGENTS.md` — Next.js 16 breaking-changes cheat-sheet для Claude Code.
- `docs/panel-guide.md` — архитектура, data flow, компоненты на уровне проекта.
