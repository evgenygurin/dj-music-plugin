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
| `/discover` | YM Search | Server action `ymSearch` → MCP `ym_search` |

## Data Flow

```text
READ path (dashboard, listings):
  Page (server component) → lib/queries/*.ts → Supabase PostgreSQL

WRITE path (mutations):
  User action → Server action (actions/*.ts) → lib/mcp-client.ts
    → HTTP POST /api/tools/{name}/call → serve_http.py → MCP Server → DB
```

## Server Actions

| File | Actions | MCP Tools Called |
|------|---------|-----------------|
| `analysis-actions.ts` | classifyMood, analyzeTrack | classify_mood, analyze_track |
| `discovery-actions.ts` | ymSearch, importTracks | ym_search, import_tracks |
| `set-actions.ts` | buildSet, rebuildSet, deliverSet, scoreTransitions | build_set, rebuild_set, deliver_set, score_transitions |
| `sync-actions.ts` | syncPlaylist | sync_playlist |

All actions use `mcpCall(toolName, args)` from `lib/mcp-client.ts` which POSTs to `MCP_HTTP_URL`.

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

Requires running backend: `uv run uvicorn serve_http:api --port 8000`
