# Panel Guide

Next.js dashboard for monitoring and analytics of the DJ music library.

## Stack

| Tech | Version | Purpose |
|------|---------|---------|
| Next.js | 16 | App router, SSR, server actions |
| Bun | — | Package manager and runtime |
| shadcn/ui | — | Component library (Base UI + Tailwind v4) |
| Supabase | — | PostgreSQL queries (direct, no ORM) |
| Recharts | — | Chart visualizations |
| TanStack Table | — | Client-side table sorting/filtering |
| @tabler/icons-react | — | Icon library |

## Pages

| Route | Page | Data Source |
|-------|------|-------------|
| `/` | Dashboard | `queries/dashboard.ts` — stats, BPM/LUFS/mood/key distributions, analysis coverage |
| `/library` | Track list | `queries/tracks.ts` — paginated, filterable, sortable table |
| `/library/[id]` | Track detail | `queries/tracks.ts` — full track with artists, features, sections, cue points, YM metadata |
| `/playlists` | Playlist list | `queries/playlists.ts` — with track counts |
| `/playlists/[id]` | Playlist detail | Playlist tracks with features |
| `/sets` | Set list | `queries/sets.ts` — with version info |
| `/sets/[id]` | Set detail | Set tracks, transitions, energy arc |
| `/discover` | YM Search | `discovery-actions.ts` (legacy `ym_search`) |
| `/curation` | Curation workflows | playlist audit / classify / distribute |
| `/delivery` | Set delivery | `set-actions.ts` |
| `/audio` | Audio / analysis UI | `analysis-actions.ts` |
| `/admin` | Admin / system | — |
| `/dj` | DJ live workspace | — |
| `/player` | Player | — |
| `/tools`, `/tools/[name]` | Tool catalog / ad-hoc tool call | `tool-actions.ts` |

## Data Flow

```text
READ path (dashboard, listings):
  Page (server component) → lib/queries/*.ts → Supabase PostgreSQL

WRITE path (mutations):
  User action → Server action (actions/*.ts) → lib/mcp-client.ts
    → HTTP POST /api/tools/{name}/call → app/rest/app.py → MCP Server → DB
```

## Server Actions (current code, April 2026)

Panel has 17 action files under `panel/actions/`, all calling
`callTool(name, args)` from `lib/mcp-client.ts`. As of April 2026 the
actions still use **legacy pre-v1 tool names** — they have not been
migrated onto the 13 v1 dispatchers. Panel refactor is intentionally
out of scope per Blueprint D2.

| File | Tool calls (as in code) |
|------|------------------------|
| `analysis-actions.ts` | `classify_mood`, `analyze_track` |
| `default-first-picker-actions.ts` | (Supabase queries) |
| `discovery-actions.ts` | `ym_search`, `import_tracks` |
| `feedback-actions.ts` | (calls via `tool-actions`) |
| `library-actions.ts` | `audit_playlist`, `sync_playlist` |
| `mix-meta-actions.ts` | — |
| `mixer-actions.ts` | `set_eq`, `kill_eq`, `reset_eq`, `set_filter`, `mixer_state`, `mixer_crossfader` |
| `playlist-actions.ts` | (Supabase queries) |
| `set-actions.ts` | `build_set`, `rebuild_set`, `deliver_set`, `score_transitions`, `get_set_cheat_sheet`, `export_set` |
| `set-picker-actions.ts` | `score_transitions` |
| `set-templates-actions.ts` | `get_set_templates` |
| `sync-actions.ts` | `sync_playlist`, `distribute_to_subgenres`, `push_set_to_ym` |
| `tool-actions.ts` | arbitrary `callTool(name, args)` pass-through |
| `track-actions.ts` | `analyze_track`, `classify_mood`, `manage_tracks` |
| `track-feedback-actions.ts` | `like_track`, `ban_track`, `rate_track` |
| `transition-actions.ts` | `score_transitions` |
| `transition-log-actions.ts` | `log_transition`, `update_reaction` |

These tool names are NOT in the v1 MCP surface. When the REST wrapper
relays a call for one of them to a v1 server, it will 404 / raise
unless a shim is in place. Mapping old → new tool names lives in
`.claude/agents/panel-doctor.md` (follow-up task).

## Components

### Charts (`components/charts/`)

| Component | Visualization | Data |
|-----------|--------------|------|
| BpmDistribution | Histogram (bar) | BPM buckets from tracks |
| LufsRange | Histogram (bar) | LUFS level distribution |
| MoodDistribution | Pie/donut | Subgenre classification counts |
| CamelotWheel | Radial | Key distribution across 24 keys |
| EnergyArc | Line | Energy curve across set tracks |

All use Recharts with cyberpunk neon gradient styling.

### Domain Components

| Component | Purpose |
|-----------|---------|
| `data-table.tsx` | TanStack React Table wrapper with sorting, filtering, pagination |
| `mood-badge.tsx` | Colored badge per subgenre (colors from `lib/constants.ts`) |
| `track-features.tsx` | Tabbed display of audio features (tempo, loudness, energy, spectral, rhythm) |
| `section-cards.tsx` | Track structure sections (intro, drop, breakdown, etc.) |
| `sections-timeline.tsx` | Visual timeline of track sections |
| `transition-table.tsx` | Set transitions with scores, pins, conflict indicators |
| `app-sidebar.tsx` | Navigation sidebar with vinyl logo, tooltips, version footer |

### UI Components (`components/ui/`)

25+ shadcn components. Do not modify these directly — use `bunx shadcn@latest add <component>` to add new ones.

## Theme

- Dark mode default (class-based via `next-themes`)
- Cyberpunk aesthetic: magenta primary, cyan/green/amber accents
- Custom CSS variables in `globals.css` for chart colors
- Geist fonts (sans + mono) loaded locally from `app/fonts/`

## Dev Setup

```bash
cd panel
cp .env.example .env.local    # Set Supabase URL + key + MCP URL
bun install
bun dev                        # http://localhost:3000
```

Requires running backend: `uv run --extra http uvicorn app.rest.app:api --port 8000`

`MCP_HTTP_URL` may point at `http://localhost:8000` or
`http://localhost:8000/mcp`; `lib/mcp-client.ts` strips a trailing
`/mcp` so the panel always hits the FastAPI REST root (the native
`/mcp` StreamableHTTP mount is not implemented yet — see
`.claude/rules/rest-api.md`).
