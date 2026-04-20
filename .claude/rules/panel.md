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
- `actions/` — 17 server action files for MCP mutations (analysis, discovery, set-building, sync, mixer, feedback, tools). Each calls MCP via `callTool(name, args)` from `lib/mcp-client.ts`. Note: as of April 2026 actions still use legacy pre-v1 tool names (`build_set`, `analyze_track`, `ym_search`, …) — migration onto v1 dispatchers (`entity_*` / `provider_*`) is deferred per Blueprint D2.
- `components/` — Shared UI: `charts/` (5 Recharts visualizations), `ui/` (25+ shadcn components), domain components (data-table, mood-badge, track-features, transition-table)
- `lib/queries/` — Supabase read queries (dashboard stats, tracks, playlists, sets). Direct SQL via Supabase client, not ORM
- `lib/supabase/` — SSR-compatible Supabase client (`createClient()` with Next.js cookies)
- `lib/mcp-client.ts` — HTTP wrapper for MCP tool calls via REST API (`MCP_HTTP_URL`)
- `lib/constants.ts` — Subgenre colors and labels

## Data Flow

- **Reads**: Page server components → `lib/queries/*.ts` → Supabase PostgreSQL (direct)
- **Writes/Mutations**: Server actions → `lib/mcp-client.ts` → REST API (app/rest/app.py) → MCP Server → DB

## Env Vars

- `NEXT_PUBLIC_SUPABASE_URL` — Supabase endpoint
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase anon JWT
- `MCP_HTTP_URL` — MCP REST API (default: http://localhost:8000)
