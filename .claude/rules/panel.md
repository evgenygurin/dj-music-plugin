---
description: Next.js panel conventions and patterns
globs: panel/**/*
---

# Panel (Next.js)

- **Framework**: Next.js 16 with app router, server components by default
- **Package manager**: bun (not npm/yarn). Run `bun install`, `bun dev`, `bun build`
- **UI library**: shadcn/ui (Base UI + Tailwind v4). Config in `panel/components.json`
- **Icons**: @tabler/icons-react (not lucide for custom icons)
- **Charts**: Recharts with cyberpunk neon theme (magenta/cyan gradients)
- **Theme**: Dark mode default via next-themes (class-based). Cyberpunk aesthetic with `--primary` magenta and `--chart-*` neon colors
- **Fonts**: Local Geist (sans + mono) from `app/fonts/`, not Google Fonts

## Directory Structure

- `app/` — Pages (dashboard, library, playlists, sets, discover). App router with `page.tsx` + `layout.tsx`
- `actions/` — Server actions for MCP mutations (analysis, discovery, set-building, sync). Each calls MCP via `mcpCall()` from `lib/mcp-client.ts`
- `components/` — Shared UI: `charts/` (5 Recharts visualizations), `ui/` (25+ shadcn components), domain components (data-table, mood-badge, track-features, transition-table)
- `lib/queries/` — Supabase read queries (dashboard stats, tracks, playlists, sets). Direct SQL via Supabase client, not ORM
- `lib/supabase/` — SSR-compatible Supabase client (`createClient()` with Next.js cookies)
- `lib/mcp-client.ts` — HTTP wrapper for MCP tool calls via REST API (`MCP_HTTP_URL`)
- `lib/constants.ts` — Subgenre colors and labels

## Data Flow

- **Reads**: Page server components → `lib/queries/*.ts` → Supabase PostgreSQL (direct)
- **Writes/Mutations**: Server actions → `lib/mcp-client.ts` → REST API (app/api/server.py) → MCP Server → DB

## Env Vars

- `NEXT_PUBLIC_SUPABASE_URL` — Supabase endpoint
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase anon JWT
- `MCP_HTTP_URL` — MCP REST API (default: http://localhost:8000)

## Порты (КРИТИЧНО!)

- REST API fallback в TS-коде: **всегда `http://localhost:8000`** (не 8001, не другой)
- Читай из `process.env.MCP_HTTP_URL`, fallback `'http://localhost:8000'`
- Порт 8001 — только для `.claude/launch.json` preview, НЕ для panel кода
