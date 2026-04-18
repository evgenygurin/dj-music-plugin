# DJ Music Panel — Design Specification

> Full-stack dashboard for DJ techno library management, set building, and Yandex Music integration.
> Frontend: Next.js 16 + shadcn/ui v4 + Tailwind v4. Backend: FastMCP 3.2 HTTP + Supabase PostgreSQL.

## 1. Overview

### Purpose

Control panel for a single DJ user to:
- Visualize library health, BPM/key/mood distributions, analysis coverage
- Browse and filter 2,800+ tracks with audio features
- Manage DJ sets: view energy arcs, transition scores, rebuild/deliver
- Search and import tracks from Yandex Music
- Manage playlists and subgenre distribution

### Architecture Decision

**Hybrid data access** — read-only queries go directly to Supabase PostgreSQL via Server Components (fast, works without MCP server). Write operations (build_set, classify_mood, deliver_set, etc.) go through FastMCP 3.2 HTTP endpoint to reuse existing business logic without duplication.

### Non-Goals

- No user authentication (single-user panel, protected by Vercel deployment settings)
- No real-time updates (ISR revalidation is sufficient for DJ workflow)
- No mobile-first design (desktop-primary, responsive as bonus)
- No REST API layer (Supabase SDK + MCP HTTP are the only data sources)

## 2. Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Framework | Next.js | 16.2+ | App Router, Turbopack, React 19 Server Components |
| React | React | 19 | Server Components, Server Actions |
| Language | TypeScript | 5.7+ | Strict typing |
| UI | shadcn/ui | v4 (CLI: shadcn@3.5) | Component library |
| CSS | Tailwind CSS | v4 | CSS-first configuration |
| Charts | Recharts | 2.x | Via shadcn `chart` component |
| Theme | next-themes | latest | Dark mode |
| Icons | @tabler/icons-react | latest | Dashboard-01 block convention |
| Data Table | @tanstack/react-table | latest | Sort, filter, pagination, column visibility |
| Validation | zod | latest | Schema validation for table data |
| DB Read | @supabase/ssr | latest | createServerClient for Server Components |
| DB Client | @supabase/supabase-js | 2.x | Supabase JS client |
| MCP Client | @modelcontextprotocol/sdk | latest | StreamableHTTPClientTransport for MCP calls |
| MCP Server | FastMCP | 3.2+ | http_app() + FastAPI ASGI mount |
| ASGI | FastAPI | latest | Host for MCP HTTP endpoint |
| ASGI Server | Uvicorn | latest | Production ASGI server |
| Database | PostgreSQL | 17 | Supabase cloud (eu-central-1) |
| Deploy | Vercel | latest | Auto-deploy Next.js 16, @vercel/analytics |

## 3. Architecture

```sql
┌────────────────────────────────────────────────────────┐
│                  Vercel (Next.js 16)                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Server Components (read)                         │  │
│  │  @supabase/ssr → createServerClient()             │  │
│  │  → SELECT from 40 tables (tracks, features, sets) │  │
│  │  → ISR caching (revalidate: 30-60s)               │  │
│  │  → Works WITHOUT MCP server running               │  │
│  │                                                    │  │
│  │  Server Actions (write)                            │  │
│  │  → @modelcontextprotocol/sdk                      │  │
│  │  → StreamableHTTPClientTransport                  │  │
│  │  → Client.callTool('build_set', {...})            │  │
│  │  → revalidateTag() after mutations                │  │
│  └──────────────────────────────────────────────────┘  │
└────────────┬──────────────────────┬────────────────────┘
             │ read                 │ write (HTTP)
             ▼                     ▼
┌──────────────────┐    ┌──────────────────────────────┐
│ Supabase         │    │ FastAPI + FastMCP 3.2         │
│ PostgreSQL 17    │    │                              │
│ (cloud)          │◄───│ mcp_app = mcp.http_app("/")  │
│                  │    │ api = FastAPI(lifespan=...)   │
│ 40 tables        │    │ api.mount("/mcp", mcp_app)   │
│ Shared by both   │    │                              │
│ read and write   │    │ /api/health — healthcheck    │
│                  │    │ /mcp — streamable-http       │
└──────────────────┘    │                              │
                        │ uvicorn serve_http:api       │
                        │ --host 0.0.0.0 --port 8000   │
                        └──────────────────────────────┘
```

### Read Path (Server Components → Supabase)

```typescript
// panel/lib/supabase/server.ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  )
}
```

Supabase foreign keys enable nested selects:
- `tracks` ← `track_audio_features_computed` (track_id → tracks.id)
- `dj_set_items` → `transitions` (transition_id → transitions.id)
- `dj_set_items` → `tracks` (track_id → tracks.id)
- `dj_set_items` → `dj_set_versions` (version_id → dj_set_versions.id)
- `track_audio_features_computed` → `keys` (key_code → keys.key_code)

### Write Path (Server Actions → MCP HTTP)

```typescript
// panel/lib/mcp-client.ts
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'

const MCP_URL = process.env.MCP_HTTP_URL ?? 'http://localhost:8000/mcp'

export async function mcpCall(tool: string, args: Record<string, unknown>) {
  const client = new Client({ name: 'dj-panel', version: '1.0.0' })
  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL))
  await client.connect(transport)
  try {
    const result = await client.callTool({ name: tool, arguments: args })
    return result
  } finally {
    await client.close()
  }
}
```

```typescript
// panel/actions/set-actions.ts
'use server'
import { revalidateTag } from 'next/cache'
import { mcpCall } from '@/lib/mcp-client'

export async function buildSet(playlistId: number, template: string) {
  const result = await mcpCall('build_set', {
    playlist_id: playlistId,
    template,
    algorithm: 'ga',
  })
  revalidateTag('sets')
  return result
}
```

### MCP HTTP Server (new file)

```python
# serve_http.py (project root)
from fastapi import FastAPI
from app.server import mcp

mcp_app = mcp.http_app(path="/")
api = FastAPI(title="DJ Music MCP API", lifespan=mcp_app.lifespan)

@api.get("/api/health")
def health():
    return {"status": "ok", "tools": 50}

api.mount("/mcp", mcp_app)

# Run: uvicorn serve_http:api --host 0.0.0.0 --port 8000
```

## 4. Database Schema (40 tables)

### Tables Used by Panel

**Core Library (read frequently):**
- `tracks` (id, title, sort_title, duration_ms, status) — 2,847 rows
- `artists` (id, name, sort_name) — linked via `track_artists` (track_id, artist_id, role)
- `genres` / `track_genres`, `labels` / `track_labels`, `releases` / `track_releases`

**Audio Features (read frequently, 63 columns):**
- `track_audio_features_computed` — primary data source for dashboard
  - Tempo: bpm, bpm_confidence, bpm_stability, variable_tempo
  - Loudness (7): integrated_lufs, short_term_lufs_mean, momentary_max, rms_dbfs, true_peak_db, crest_factor_db, loudness_range_lu
  - Energy (16): mean, max, std, slope + 7 bands (sub, low, lowmid, mid, highmid, high) + 6 ratios
  - Spectral (8): centroid_hz, rolloff_85, rolloff_95, flatness, flux_mean, flux_std, slope, contrast
  - Key (5): key_code, key_confidence, atonality, hnr_db, chroma_entropy
  - Rhythm (5): hp_ratio, onset_rate, pulse_clarity, kick_prominence, mfcc_vector (varchar JSON)
  - P1/P2 essentia (9): danceability, dynamic_complexity, dissonance_mean, tonnetz_vector, tempogram_ratio_vector, beat_loudness_band_ratio, spectral_complexity_mean, pitch_salience_mean, bpm_histogram_first_peak_weight, bpm_histogram_second_peak_bpm, bpm_histogram_second_peak_weight, phrase_boundaries_ms, dominant_phrase_bars
  - Classification: mood (varchar), mood_confidence (float), analysis_level (int: 0/2/3)
- `track_sections` (track_id, section_type, start_ms, end_ms, energy, confidence)
- `feature_extraction_runs` (track_id, pipeline_name, pipeline_version, status)

**DJ Library (read on track detail):**
- `dj_library_items` (track_id, file_path, file_hash, file_size, bitrate, sample_rate, channels)
- `dj_beatgrids` (library_item_id, bpm, first_downbeat_ms, confidence, variable_tempo, canonical)
- `dj_beatgrid_change_points` (beatgrid_id, position_ms, bpm)
- `dj_cue_points` (library_item_id, position_ms, kind, hotcue_index, label, color)
- `dj_saved_loops` (library_item_id, in_position_ms, out_position_ms, label, color)

**Playlists (read/write):**
- `dj_playlists` (id, name, parent_id, source_of_truth, platform_ids, source_app)
- `dj_playlist_items` (playlist_id, track_id, sort_index, added_at)

**DJ Sets (read/write):**
- `dj_sets` (id, name, description, target_duration_ms, target_bpm_min/max, target_energy_arc, template_name, source_playlist_id, ym_playlist_id)
- `dj_set_versions` (set_id, label, generator_run_meta, quality_score)
- `dj_set_items` (version_id, track_id, sort_index, transition_id, pinned, planned_eq, notes, mix_in_point_ms, mix_out_point_ms)
- `dj_set_constraints` (set_id, constraint_type, constraint_value)
- `dj_set_feedback` (version_id, set_item_id, rating, feedback_type, notes)

**Transitions (read on set detail):**
- `transitions` (from_track_id, to_track_id, 8 scores: bpm_score, energy_score, harmonic_score, spectral_score, groove_score, key_distance_weighted, low_conflict_score, overall_quality)
- `transition_candidates` (from_track_id, to_track_id, bpm_distance, key_distance, energy_delta, fully_scored)

**Platform Metadata (read on track detail):**
- `yandex_metadata` (track_id, yandex_track_id, album_id, album_title, cover_uri, explicit)
- `spotify_metadata` + `spotify_audio_features` + `spotify_album_metadata` + `spotify_artist_metadata` + `spotify_playlist_metadata`
- `soundcloud_metadata` (playback_count, favoritings_count, streamable, permalink_url)
- `beatport_metadata` (bpm, key, genre, subgenre, preview_url)

**Reference (static, read once):**
- `keys` (key_code, pitch_class, mode, name, camelot) — 24 rows
- `key_edges` (from_key_code, to_key_code, distance, weight, rule_name)
- `providers` (id, name) — 4 rows

**Other (read rarely):**
- `track_external_ids`, `raw_provider_responses`, `app_exports`
- `embeddings`, `timeseries_references`

## 5. Pages and Components

### 5.1 Layout (all pages)

**shadcn blocks:** `sidebar-01` (AppSidebar + Breadcrumb + SidebarInset) + `dashboard-01` (SidebarProvider pattern)

```text
┌─────────────────────────────────────────────────┐
│ SidebarProvider                                  │
│ ┌──────────┬──────────────────────────────────┐ │
│ │ AppSidebar│ SidebarInset                     │ │
│ │          │ ┌──────────────────────────────┐ │ │
│ │ Dashboard│ │ SiteHeader + Breadcrumb      │ │ │
│ │ Library  │ ├──────────────────────────────┤ │ │
│ │ Playlists│ │                              │ │ │
│ │ Sets     │ │   Page Content               │ │ │
│ │ Discover │ │                              │ │ │
│ │          │ │                              │ │ │
│ └──────────┘ └──────────────────────────────┘ │ │
└─────────────────────────────────────────────────┘
```

- **ThemeProvider** (next-themes): `defaultTheme="dark"`, `attribute="class"`
- **SidebarProvider**: sidebar width `calc(var(--spacing) * 72)`
- 5 nav items: Dashboard, Library, Playlists, Sets, Discover
- Dark theme CSS variables for sidebar from shadcn docs

### 5.2 Dashboard (`/`)

**Data sources:** 5 aggregate queries on `tracks`, `track_audio_features_computed`, `dj_sets`, `dj_set_versions`, `dj_library_items`

**Vercel pattern:** `export const revalidate = 30`

| Widget | shadcn Component | SQL Source |
|--------|-----------------|------------|
| Stats cards (5) | `Card` + `CardAction` + `Badge` (SectionCards pattern) | `COUNT(*)` on tracks, features, sets, library_items; `AVG(quality_score)` on versions |
| BPM distribution | `ChartContainer` + Recharts `BarChart` | `SELECT FLOOR(bpm/5)*5 as bin, COUNT(*) FROM track_audio_features_computed GROUP BY 1` |
| Mood distribution | `ChartContainer` + Recharts horizontal `BarChart` | `SELECT mood, COUNT(*) FROM track_audio_features_computed WHERE mood IS NOT NULL GROUP BY 1 ORDER BY 2 DESC` |
| Camelot wheel | `ChartContainer` + Recharts `RadarChart` (PolarAngleAxis 24 keys) | `SELECT k.camelot, COUNT(*) FROM track_audio_features_computed f JOIN keys k ON f.key_code = k.key_code GROUP BY 1` |
| LUFS range | `ChartContainer` + Recharts `AreaChart` (ChartAreaInteractive pattern) | `SELECT ROUND(integrated_lufs), COUNT(*) FROM track_audio_features_computed GROUP BY 1` |
| Analysis coverage | `Progress` bar + `Badge` per level | `SELECT analysis_level, COUNT(*) FROM track_audio_features_computed GROUP BY 1` |

### 5.3 Library (`/library`)

**Data source:** `tracks` JOIN `track_artists` JOIN `artists` JOIN `track_audio_features_computed` JOIN `keys`

**Vercel pattern:** Server Component initial load + URL `searchParams` for server-side filtering

| Element | shadcn Component | Details |
|---------|-----------------|---------|
| DataTable | `@tanstack/react-table` + shadcn `Table` | ColumnDef with: id, title, artists, bpm, camelot (from keys), mood, integrated_lufs, energy_mean, analysis_level, duration_ms. Sort, pagination (50/page), column visibility toggle |
| Filters bar | `Select` (key, mood), `Slider` (bpm range, lufs range, energy), `Combobox` (artist search), `Badge` (active filters) | WHERE clauses on features columns. URL searchParams → server query |
| Row actions | `DropdownMenu` | MCP tools: analyze_track, classify_mood, download_tracks, find_similar_tracks |
| Mood badge | `Badge` with color per subgenre | 15 subgenre colors |

### 5.4 Track Detail (`/library/[id]`)

**Data sources:** 7 tables for single track

| Section | shadcn Component | DB Tables |
|---------|-----------------|-----------|
| Header | `Card` with title, artists, label, release | `tracks` + `track_artists` + `artists` + `track_releases` + `releases` + `labels` |
| Audio features | `Tabs` (7 tabs: Tempo, Loudness, Energy, Spectral, Key, Rhythm, P1/P2) + `Card` per tab | `track_audio_features_computed` — all 63 columns grouped by category |
| Sections timeline | Custom colored bars + `Tooltip` on hover | `track_sections` (section_type, start_ms, end_ms, energy) |
| Cue points | `Badge` (colored by kind) + position display | `dj_cue_points` (position_ms, kind, hotcue_index, label, color) |
| Saved loops | `Badge` + in/out position | `dj_saved_loops` (in_position_ms, out_position_ms, label) |
| Beatgrid | Inline display: BPM, first downbeat, confidence | `dj_beatgrids` + `dj_beatgrid_change_points` |
| File info | `Card` with bitrate, sample_rate, channels, size | `dj_library_items` |
| Platform metadata | `Tabs` (YM / Spotify / SC / Beatport) + `Card` per platform | `yandex_metadata`, `spotify_metadata`, `soundcloud_metadata`, `beatport_metadata` |
| Pipeline status | `Badge` (status) + pipeline info | `feature_extraction_runs` |

### 5.5 Sets List (`/sets`)

**Data source:** `dj_sets` JOIN `dj_set_versions` (latest by created_at)

| Element | shadcn Component |
|---------|-----------------|
| Set cards | `Card` with name, template, quality_score, track count, version count |
| Quick actions | `Button` → MCP: build_set, rebuild_set |

### 5.6 Set Detail (`/sets/[id]`)

**Data sources:** `dj_sets` + `dj_set_versions` + `dj_set_items` JOIN `tracks` JOIN `track_audio_features_computed` JOIN `transitions`

| Section | shadcn Component | Details |
|---------|-----------------|---------|
| Header | `Card` with name, template_name, target_bpm range, target_duration | From `dj_sets` |
| Version selector | `Select` or `ToggleGroup` | `dj_set_versions` — label, quality_score. Client-side switch, data pre-loaded |
| Energy arc | `ChartContainer` + Recharts `BarChart` | `dj_set_items` ordered by sort_index → `track_audio_features_computed.integrated_lufs`. Color: green (low) → yellow (mid) → red (high) |
| Transition table | `Table` with conditional coloring | `dj_set_items` JOIN `transitions`: from_track, to_track, all 8 scores. Green (>0.7) / Yellow (0.4-0.7) / Red (<0.4 or 0.0 hard conflict). 📌 icon for pinned items |
| Constraints | `Badge` list | `dj_set_constraints` (constraint_type, constraint_value) |
| Feedback summary | Inline rating display | `dj_set_feedback` — avg rating, count |
| Actions | `Button` + `Dialog` confirmation | MCP: rebuild_set, score_transitions, deliver_set. `Sonner` toast for progress, `Progress` bar for long operations |

### 5.7 Playlists (`/playlists`, `/playlists/[id]`)

**Data source:** `dj_playlists` (hierarchical via parent_id) + `dj_playlist_items` + `tracks`

| Element | shadcn Component |
|---------|-----------------|
| Playlist tree | `Collapsible` nested items by parent_id, track count per playlist |
| Playlist detail | `Table` with tracks (sort_index order), same columns as library but scoped |
| Subgenre distribution | Horizontal `BarChart` — count of tracks per mood in playlist |
| Actions | MCP: sync_playlist, distribute_to_subgenres, audit_playlist, manage_playlist |

### 5.8 Discover (`/discover`)

| Element | shadcn Component | MCP Tool |
|---------|-----------------|----------|
| YM search | `Command` (combobox) + `Skeleton` loading + `Card` results | ym_search |
| Import | `Button` + `Dialog` confirmation | import_tracks |
| Download | `Button` + `Progress` | download_tracks |
| Find similar | `Button` on track row | find_similar_tracks |
| Expand playlist | `Button` + target count input | expand_playlist_ym |

## 6. Vercel Data Fetching Strategy

### Caching

| Page | Strategy | Revalidate |
|------|----------|-----------|
| Dashboard `/` | ISR | 30s |
| Library `/library` | ISR + searchParams | 60s |
| Track detail `/library/[id]` | ISR | 120s |
| Sets `/sets` | ISR | 30s |
| Set detail `/sets/[id]` | ISR | 60s |
| Playlists `/playlists` | ISR | 60s |
| Discover `/discover` | No cache (dynamic) | 0 |

### Cache Tags and Invalidation

```typescript
// After MCP mutations, bust relevant caches:
revalidateTag('tracks')        // after: classify_mood, analyze_track, import_tracks
revalidateTag('sets')          // after: build_set, rebuild_set, deliver_set
revalidateTag('playlists')     // after: sync_playlist, distribute_to_subgenres
revalidateTag('library-stats') // after: any mutation that changes counts
```

## 7. Project Structure

```text
dj-music-plugin/
├── app/                         ← Python MCP backend (existing)
│   ├── server.py                ← FastMCP server (stdio + FileSystemProvider)
│   └── ...                      ← models, services, repositories, mcp/tools
├── serve_http.py                ← NEW: FastAPI + mcp.http_app() mount
├── panel/                       ← NEW: Next.js 16 frontend
│   ├── app/
│   │   ├── layout.tsx           ← ThemeProvider + SidebarProvider
│   │   ├── page.tsx             ← Dashboard overview
│   │   ├── library/
│   │   │   ├── page.tsx         ← Track table + filters
│   │   │   └── [id]/page.tsx    ← Track detail + audio features
│   │   ├── playlists/
│   │   │   ├── page.tsx         ← Playlist list + tree
│   │   │   └── [id]/page.tsx    ← Playlist detail
│   │   ├── sets/
│   │   │   ├── page.tsx         ← Sets list
│   │   │   └── [id]/page.tsx    ← Set detail + transitions
│   │   └── discover/
│   │       └── page.tsx         ← YM search + import
│   ├── components/
│   │   ├── ui/                  ← shadcn/ui v4 (npx shadcn@latest add)
│   │   ├── charts/
│   │   │   ├── bpm-distribution.tsx
│   │   │   ├── mood-distribution.tsx
│   │   │   ├── camelot-wheel.tsx
│   │   │   ├── lufs-range.tsx
│   │   │   └── energy-arc.tsx
│   │   ├── app-sidebar.tsx      ← Based on sidebar-01 block
│   │   ├── data-table.tsx       ← Based on dashboard-01 DataTable
│   │   ├── section-cards.tsx    ← Based on dashboard-01 SectionCards
│   │   ├── track-features.tsx   ← 7-tab feature display
│   │   ├── sections-timeline.tsx← Track sections bar
│   │   └── transition-table.tsx ← Set transition scores
│   ├── lib/
│   │   ├── supabase/
│   │   │   └── server.ts        ← @supabase/ssr createServerClient
│   │   ├── mcp-client.ts        ← @modelcontextprotocol/sdk client
│   │   └── queries/
│   │       ├── tracks.ts        ← Track list + detail queries
│   │       ├── sets.ts          ← Set list + detail + transitions
│   │       ├── playlists.ts     ← Playlist tree + items
│   │       └── dashboard.ts     ← Aggregate stats + distributions
│   ├── actions/
│   │   ├── set-actions.ts       ← build_set, rebuild_set, deliver_set
│   │   ├── analysis-actions.ts  ← classify_mood, analyze_track
│   │   ├── sync-actions.ts      ← sync_playlist, push_set_to_ym
│   │   └── discovery-actions.ts ← ym_search, import_tracks, download_tracks
│   ├── tailwind.css             ← Tailwind v4 (CSS-first config)
│   ├── next.config.ts
│   ├── package.json
│   └── tsconfig.json
└── pyproject.toml               ← Python deps (existing)
```

## 8. Environment Variables

### Vercel (panel)

```env
NEXT_PUBLIC_SUPABASE_URL=https://bowosphlnghhgaulcyfm.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
MCP_HTTP_URL=http://localhost:8000/mcp    # dev: localhost, prod: VPS URL
```

### MCP Server (serve_http.py)

Existing `.env` — no changes needed. The `serve_http.py` imports `app.server.mcp` which loads all settings from `app/config.py`.

## 9. shadcn/ui v4 Components to Install

```bash
cd panel
npx shadcn@latest add sidebar chart table card badge tabs dialog \
  select combobox slider sonner skeleton progress button \
  dropdown-menu drawer collapsible breadcrumb separator \
  toggle-group command checkbox scroll-area popover tooltip
```

## 10. MCP Tools Exposed via Panel

### Read-only (display in UI)

Via Supabase direct queries — no MCP needed.

### Write operations (via Server Actions → MCP HTTP)

| Action | MCP Tool | Trigger | Cache Invalidation |
|--------|----------|---------|-------------------|
| Build set | `build_set` | Sets page button | `sets` |
| Rebuild set | `rebuild_set` | Set detail button | `sets` |
| Deliver set | `deliver_set` | Set detail button | `sets` |
| Score transitions | `score_transitions` | Set detail button | `sets` |
| Classify mood | `classify_mood` | Library row action | `tracks`, `library-stats` |
| Analyze track | `analyze_track` | Library row action | `tracks`, `library-stats` |
| Download tracks | `download_tracks` | Discover button | `tracks`, `library-stats` |
| Import tracks | `import_tracks` | Discover button | `tracks`, `library-stats` |
| Find similar | `find_similar_tracks` | Library row action | — (read-only result) |
| Sync playlist | `sync_playlist` | Playlist button | `playlists` |
| Distribute subgenres | `distribute_to_subgenres` | Playlist button | `playlists`, `tracks` |
| Audit playlist | `audit_playlist` | Playlist button | — (read-only result) |
| YM search | `ym_search` | Discover search | — (read-only result) |
| Push set to YM | `push_set_to_ym` | Set detail button | `sets` |

## 11. Development Workflow

```bash
# Terminal 1: MCP HTTP server
uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Next.js dev server
cd panel && npm run dev

# Panel available at http://localhost:3000
# MCP endpoint at http://localhost:8000/mcp
# Health check at http://localhost:8000/api/health
```

## 12. Deployment

### Frontend (Vercel)

- Connect `panel/` directory to Vercel project
- Root directory: `panel`
- Framework: Next.js (auto-detected)
- Environment variables: set in Vercel dashboard

### MCP Backend

- Dev: `uvicorn serve_http:api` on localhost
- Prod: VPS/Railway with `uvicorn serve_http:api --host 0.0.0.0 --port 8000`
- Set `MCP_HTTP_URL` in Vercel env to point to production MCP endpoint
