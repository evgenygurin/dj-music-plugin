# DJ Music Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack dashboard for DJ techno library management — Next.js 16 frontend on Vercel reading from Supabase PostgreSQL, with write operations proxied through FastMCP 3.2 HTTP endpoint.

**Architecture:** Hybrid data access — Server Components query Supabase directly for reads (fast, works without MCP server). Server Actions call FastMCP HTTP endpoint for writes (build_set, classify_mood, etc.) to reuse existing business logic. ISR caching with tag-based invalidation after mutations.

**Tech Stack:** Next.js 16.2+ (App Router, React 19 SC), shadcn/ui v4, Tailwind v4, Recharts, @tanstack/react-table, @supabase/ssr, @modelcontextprotocol/sdk, FastAPI + FastMCP 3.2 http_app()

**Spec:** `docs/superpowers/specs/2026-04-06-shadcn-vercel-panel-design.md`

---

## File Structure

```text
# NEW files (panel/ is entirely new Next.js project)
serve_http.py                          # FastAPI + MCP HTTP mount (Python, project root)

panel/                                 # Next.js 16 project
  package.json
  tsconfig.json
  next.config.ts
  .env.local                           # Supabase + MCP URLs (gitignored)
  app/
    layout.tsx                         # Root: ThemeProvider + SidebarProvider + fonts
    page.tsx                           # Dashboard: stats cards + 5 charts
    library/
      page.tsx                         # Track DataTable + filter bar
      [id]/page.tsx                    # Track detail: features tabs + sections + metadata
    sets/
      page.tsx                         # Set cards grid
      [id]/page.tsx                    # Set detail: energy arc + transition table + actions
    playlists/
      page.tsx                         # Playlist tree + stats
      [id]/page.tsx                    # Playlist detail: track table + subgenre chart
    discover/
      page.tsx                         # YM search + import + download
  components/
    ui/                                # shadcn/ui v4 components (auto-generated)
    app-sidebar.tsx                    # Sidebar nav (based on sidebar-01 block)
    site-header.tsx                    # Breadcrumb + sidebar trigger
    section-cards.tsx                  # Dashboard stat cards
    data-table.tsx                     # Reusable DataTable (based on dashboard-01)
    data-table-toolbar.tsx             # Filters bar for DataTable
    track-features.tsx                 # 7-tab audio feature display
    sections-timeline.tsx              # Track sections colored bar
    transition-table.tsx               # Set transition scores table
    mood-badge.tsx                     # Colored badge per subgenre
    charts/
      bpm-distribution.tsx             # Bar chart: BPM bins
      mood-distribution.tsx            # Horizontal bar: mood counts
      camelot-wheel.tsx                # Radar chart: 24 keys
      lufs-range.tsx                   # Area chart: LUFS distribution
      energy-arc.tsx                   # Bar chart: set energy flow
  lib/
    supabase/
      server.ts                        # createServerClient factory
    mcp-client.ts                      # StreamableHTTPClientTransport wrapper
    queries/
      dashboard.ts                     # Aggregate stats + distribution queries
      tracks.ts                        # Track list + detail + features
      sets.ts                          # Set list + detail + transitions
      playlists.ts                     # Playlist tree + items
    utils.ts                           # Formatting helpers (duration, camelot, etc.)
    constants.ts                       # Subgenre colors, column definitions
  actions/
    set-actions.ts                     # build_set, rebuild_set, deliver_set, score_transitions
    analysis-actions.ts                # classify_mood, analyze_track
    sync-actions.ts                    # sync_playlist, distribute_to_subgenres, push_set_to_ym
    discovery-actions.ts               # ym_search, import_tracks, download_tracks
  tailwind.css                         # Tailwind v4 CSS-first config + dark theme
```

---

## Phase 1: MCP HTTP Server + Next.js Foundation

### Task 1: Create FastAPI HTTP server for MCP

**Files:**
- Create: `serve_http.py`

This file mounts the existing FastMCP server as an HTTP endpoint using FastAPI, enabling the Next.js frontend to call MCP tools over HTTP.

- [ ] **Step 1: Create serve_http.py**

```python
# serve_http.py
"""FastAPI wrapper exposing FastMCP server over HTTP.

Usage:
    uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.server import mcp

mcp_app = mcp.http_app(path="/")

api = FastAPI(title="DJ Music MCP API", lifespan=mcp_app.lifespan)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/api/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "tools": 50}

api.mount("/mcp", mcp_app)
```

- [ ] **Step 2: Verify server starts**

Run: `cd /Users/laptop/dev/dj-music-plugin && uv run uvicorn serve_http:api --host 0.0.0.0 --port 8000`

Expected: Server starts, `http://localhost:8000/api/health` returns `{"status": "ok", "tools": 50}`

- [ ] **Step 3: Verify MCP endpoint**

Run: `curl -sf http://localhost:8000/api/health | python3 -m json.tool`

Expected: JSON with status ok. Stop the server after verification.

- [ ] **Step 4: Commit**

```bash
git add serve_http.py
git commit -m "feat(panel): add FastAPI HTTP wrapper for MCP server

Mounts existing FastMCP server at /mcp via http_app().
Enables Next.js frontend to call MCP tools over HTTP.
Includes CORS for localhost:3000 and Vercel deployments."
```

---

### Task 2: Initialize Next.js 16 project

**Files:**
- Create: `panel/` (entire Next.js project via create-next-app)

- [ ] **Step 1: Create Next.js project**

```bash
cd /Users/laptop/dev/dj-music-plugin
npx create-next-app@latest panel \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src=false \
  --turbopack \
  --import-alias "@/*"
```

Answer prompts: Yes to all defaults. This creates `panel/` with App Router, TypeScript, Tailwind v4, ESLint.

- [ ] **Step 2: Verify it runs**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm run dev
```

Expected: Dev server at `http://localhost:3000` with Next.js default page.

Stop the server after verification.

- [ ] **Step 3: Commit**

```bash
git add panel/
git commit -m "chore(panel): initialize Next.js 16 project

create-next-app with TypeScript, Tailwind v4, App Router, Turbopack."
```

---

### Task 3: Install dependencies and shadcn/ui

**Files:**
- Modify: `panel/package.json`

- [ ] **Step 1: Initialize shadcn/ui**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel
npx shadcn@latest init -d
```

This sets up shadcn/ui v4 with default config (New York style, CSS variables, dark mode).

- [ ] **Step 2: Install shadcn components**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel
npx shadcn@latest add sidebar chart table card badge tabs dialog \
  select combobox slider sonner skeleton progress button \
  dropdown-menu drawer collapsible breadcrumb separator \
  toggle-group command checkbox scroll-area popover tooltip
```

- [ ] **Step 3: Install additional dependencies**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel
npm install @supabase/supabase-js @supabase/ssr \
  @modelcontextprotocol/sdk \
  @tanstack/react-table zod \
  @tabler/icons-react next-themes \
  @vercel/analytics
```

- [ ] **Step 4: Verify dependencies installed**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm ls --depth=0
```

Expected: All packages listed without errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/
git commit -m "chore(panel): install shadcn/ui v4 components and dependencies

Components: sidebar, chart, table, card, badge, tabs, dialog, select,
combobox, slider, sonner, skeleton, progress, button, dropdown-menu,
drawer, collapsible, breadcrumb, separator, toggle-group, command,
checkbox, scroll-area, popover, tooltip.
Deps: supabase, mcp sdk, tanstack-table, tabler-icons, next-themes."
```

---

### Task 4: Create environment config

**Files:**
- Create: `panel/.env.local`
- Create: `panel/.env.example`

- [ ] **Step 1: Create .env.example**

```bash
# panel/.env.example
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
MCP_HTTP_URL=http://localhost:8000/mcp
```

- [ ] **Step 2: Create .env.local with real values**

```bash
# panel/.env.local
NEXT_PUBLIC_SUPABASE_URL=https://bowosphlnghhgaulcyfm.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<get from Supabase dashboard → Settings → API → anon key>
MCP_HTTP_URL=http://localhost:8000/mcp
```

The anon key is safe for client-side use — it's a public key with Row Level Security. Since this is a single-user panel with no RLS policies, the anon key gives full read access to all tables (which is what we want).

To get the anon key: Supabase Dashboard → Project Settings → API → Project API keys → `anon` `public`.

- [ ] **Step 3: Ensure .env.local is gitignored**

Check that `panel/.gitignore` (created by create-next-app) includes `.env*.local`. It should by default.

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/.env.example
git commit -m "chore(panel): add environment variable template

Supabase URL/key for reads, MCP HTTP URL for writes."
```

---

### Task 5: Supabase server client

**Files:**
- Create: `panel/lib/supabase/server.ts`

- [ ] **Step 1: Create Supabase server client factory**

```typescript
// panel/lib/supabase/server.ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // setAll called from Server Component — ignore
          }
        },
      },
    }
  )
}
```

- [ ] **Step 2: Verify file created**

```bash
cat panel/lib/supabase/server.ts
```

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/lib/supabase/server.ts
git commit -m "feat(panel): add Supabase server client factory

@supabase/ssr createServerClient for Server Components.
Cookie-based session for potential future auth."
```

---

### Task 6: MCP client wrapper

**Files:**
- Create: `panel/lib/mcp-client.ts`

- [ ] **Step 1: Create MCP client**

```typescript
// panel/lib/mcp-client.ts
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'

const MCP_URL = process.env.MCP_HTTP_URL ?? 'http://localhost:8000/mcp'

export async function mcpCall(
  tool: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const client = new Client({ name: 'dj-panel', version: '1.0.0' })
  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL))
  await client.connect(transport)
  try {
    const result = await client.callTool({ name: tool, arguments: args })
    if (result.isError) {
      throw new Error(
        `MCP tool ${tool} failed: ${JSON.stringify(result.content)}`
      )
    }
    // Extract structured content or text
    const structured = result.structuredContent
    if (structured) return structured
    // Fallback to text content
    const textParts = (result.content as Array<{ type: string; text?: string }>)
      ?.filter((c) => c.type === 'text')
      .map((c) => c.text)
      .join('')
    return textParts ? JSON.parse(textParts) : result.content
  } finally {
    await client.close()
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/lib/mcp-client.ts
git commit -m "feat(panel): add MCP HTTP client wrapper

StreamableHTTPClientTransport for calling MCP tools from Server Actions.
Extracts structuredContent or parses text content."
```

---

### Task 7: Utility helpers and constants

**Files:**
- Create: `panel/lib/utils.ts` (extend existing if shadcn created one)
- Create: `panel/lib/constants.ts`

- [ ] **Step 1: Check if utils.ts already exists**

shadcn init creates `panel/lib/utils.ts` with the `cn()` helper. We'll extend it.

```bash
cat panel/lib/utils.ts
```

- [ ] **Step 2: Add formatting helpers to utils.ts**

Append to the existing `panel/lib/utils.ts`:

```typescript
// panel/lib/utils.ts — append after existing cn() function

/** Format milliseconds as "M:SS" */
export function formatDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

/** Map key_code (0-23) to Camelot notation */
const CAMELOT_MAP: Record<number, string> = {
  0: '5A', 1: '12A', 2: '7A', 3: '2A', 4: '9A', 5: '4A',
  6: '11A', 7: '6A', 8: '1A', 9: '8A', 10: '3A', 11: '10A',
  12: '5B', 13: '12B', 14: '7B', 15: '2B', 16: '9B', 17: '4B',
  18: '11B', 19: '6B', 20: '1B', 21: '8B', 22: '3B', 23: '10B',
}

export function camelotNotation(keyCode: number | null): string {
  if (keyCode === null || keyCode === undefined) return '—'
  return CAMELOT_MAP[keyCode] ?? '—'
}

/** Format LUFS value with unit */
export function formatLufs(lufs: number | null): string {
  if (lufs === null || lufs === undefined) return '—'
  return `${lufs.toFixed(1)} LUFS`
}

/** Format BPM with one decimal */
export function formatBpm(bpm: number | null): string {
  if (bpm === null || bpm === undefined) return '—'
  return bpm.toFixed(1)
}

/** Transition score color class */
export function scoreColor(score: number | null): string {
  if (score === null || score === undefined) return 'text-muted-foreground'
  if (score === 0) return 'text-red-500 font-bold'
  if (score < 0.4) return 'text-red-400'
  if (score < 0.7) return 'text-yellow-400'
  return 'text-green-400'
}
```

- [ ] **Step 3: Create constants file**

```typescript
// panel/lib/constants.ts

/** 15 techno subgenres ordered by energy (low → high), with display colors */
export const SUBGENRE_COLORS: Record<string, string> = {
  ambient_dub: '#6366f1',      // indigo
  dub_techno: '#818cf8',       // indigo lighter
  minimal: '#a5b4fc',          // indigo lightest
  detroit: '#60a5fa',          // blue
  melodic_deep: '#38bdf8',     // sky
  progressive: '#2dd4bf',      // teal
  hypnotic: '#34d399',         // emerald
  driving: '#a3e635',          // lime
  tribal: '#facc15',           // yellow
  breakbeat: '#fb923c',        // orange
  peak_time: '#f97316',        // orange darker
  acid: '#f43f5e',             // rose
  raw: '#e11d48',              // rose darker
  industrial: '#dc2626',       // red
  hard_techno: '#991b1b',      // red darkest
}

/** Subgenre display names */
export const SUBGENRE_LABELS: Record<string, string> = {
  ambient_dub: 'Ambient Dub',
  dub_techno: 'Dub Techno',
  minimal: 'Minimal',
  detroit: 'Detroit',
  melodic_deep: 'Melodic Deep',
  progressive: 'Progressive',
  hypnotic: 'Hypnotic',
  driving: 'Driving',
  tribal: 'Tribal',
  breakbeat: 'Breakbeat',
  peak_time: 'Peak Time',
  acid: 'Acid',
  raw: 'Raw',
  industrial: 'Industrial',
  hard_techno: 'Hard Techno',
}

/** Analysis level labels */
export const ANALYSIS_LEVELS: Record<number, string> = {
  0: 'None',
  2: 'Triage (L1+L2)',
  3: 'Scoring (L3)',
}

/** Nav items for sidebar */
export const NAV_ITEMS = [
  { title: 'Dashboard', url: '/', icon: 'IconDashboard' },
  { title: 'Library', url: '/library', icon: 'IconDatabase' },
  { title: 'Sets', url: '/sets', icon: 'IconListDetails' },
  { title: 'Playlists', url: '/playlists', icon: 'IconFolder' },
  { title: 'Discover', url: '/discover', icon: 'IconSearch' },
] as const
```

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/lib/utils.ts panel/lib/constants.ts
git commit -m "feat(panel): add utility helpers and constants

Duration/BPM/LUFS formatters, Camelot notation mapping,
score coloring, 15 subgenre colors, nav items."
```

---

### Task 8: App layout with sidebar and dark theme

**Files:**
- Modify: `panel/app/layout.tsx`
- Modify: `panel/tailwind.css` (Tailwind v4 CSS config)
- Create: `panel/components/app-sidebar.tsx`
- Create: `panel/components/site-header.tsx`

- [ ] **Step 1: Update tailwind.css for dark theme**

Replace the contents of `panel/tailwind.css` (or `panel/app/globals.css`, whichever exists) — keep the existing `@import` lines from shadcn init, and add dark theme overrides. The file should look like:

```css
@import "tailwindcss";
@import "tw-animate-css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
  /* shadcn theme variables are auto-set by shadcn init */
}
```

Note: shadcn init may have already set this up. Only modify if needed — preserve what shadcn created.

- [ ] **Step 2: Create app-sidebar.tsx**

```tsx
// panel/components/app-sidebar.tsx
'use client'

import * as React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  IconDashboard,
  IconDatabase,
  IconListDetails,
  IconFolder,
  IconSearch,
} from '@tabler/icons-react'

import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
} from '@/components/ui/sidebar'

const navItems = [
  { title: 'Dashboard', url: '/', icon: IconDashboard },
  { title: 'Library', url: '/library', icon: IconDatabase },
  { title: 'Sets', url: '/sets', icon: IconListDetails },
  { title: 'Playlists', url: '/playlists', icon: IconFolder },
  { title: 'Discover', url: '/discover', icon: IconSearch },
]

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()

  return (
    <Sidebar {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/">
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-semibold">DJ Music Panel</span>
                  <span className="text-xs text-muted-foreground">
                    Techno Library
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    asChild
                    isActive={
                      item.url === '/'
                        ? pathname === '/'
                        : pathname.startsWith(item.url)
                    }
                  >
                    <Link href={item.url}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
```

- [ ] **Step 3: Create site-header.tsx**

```tsx
// panel/components/site-header.tsx
import { Separator } from '@/components/ui/separator'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from '@/components/ui/breadcrumb'
import { SidebarTrigger } from '@/components/ui/sidebar'

export function SiteHeader({ title }: { title: string }) {
  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage>{title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </header>
  )
}
```

- [ ] **Step 4: Update root layout.tsx**

Replace `panel/app/layout.tsx`:

```tsx
// panel/app/layout.tsx
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { ThemeProvider } from 'next-themes'
import { Analytics } from '@vercel/analytics/next'
import { Toaster } from '@/components/ui/sonner'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { AppSidebar } from '@/components/app-sidebar'
import './globals.css'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'DJ Music Panel',
  description: 'Techno library management dashboard',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <SidebarProvider>
            <AppSidebar />
            <SidebarInset>{children}</SidebarInset>
          </SidebarProvider>
          <Toaster />
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
```

- [ ] **Step 5: Create placeholder page.tsx**

Replace `panel/app/page.tsx`:

```tsx
// panel/app/page.tsx
import { SiteHeader } from '@/components/site-header'

export default function DashboardPage() {
  return (
    <>
      <SiteHeader title="Dashboard" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <p className="text-muted-foreground">Dashboard coming soon...</p>
      </div>
    </>
  )
}
```

- [ ] **Step 6: Verify layout renders**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm run dev
```

Expected: Dark-themed page with sidebar (DJ Music Panel, 5 nav items) and "Dashboard coming soon..." content. Stop server.

- [ ] **Step 7: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/app/layout.tsx panel/app/page.tsx panel/app/globals.css \
  panel/components/app-sidebar.tsx panel/components/site-header.tsx \
  panel/tailwind.css
git commit -m "feat(panel): add layout with sidebar and dark theme

SidebarProvider + AppSidebar with 5 nav items.
ThemeProvider (next-themes) defaulting to dark.
SiteHeader with breadcrumb. Sonner toasts. Vercel analytics."
```

---

## Phase 2: Data Layer (Queries)

### Task 9: Dashboard queries

**Files:**
- Create: `panel/lib/queries/dashboard.ts`

- [ ] **Step 1: Create dashboard queries**

```typescript
// panel/lib/queries/dashboard.ts
import { createClient } from '@/lib/supabase/server'

export interface LibraryStats {
  totalTracks: number
  analyzedTracks: number
  totalSets: number
  libraryItems: number
  avgSetQuality: number | null
}

export async function getLibraryStats(): Promise<LibraryStats> {
  const supabase = await createClient()

  const [tracks, features, sets, library, quality] = await Promise.all([
    supabase.from('tracks').select('*', { count: 'exact', head: true }),
    supabase
      .from('track_audio_features_computed')
      .select('*', { count: 'exact', head: true })
      .gt('analysis_level', 0),
    supabase.from('dj_sets').select('*', { count: 'exact', head: true }),
    supabase
      .from('dj_library_items')
      .select('*', { count: 'exact', head: true }),
    supabase
      .from('dj_set_versions')
      .select('quality_score')
      .not('quality_score', 'is', null),
  ])

  const scores = quality.data ?? []
  const avgQuality =
    scores.length > 0
      ? scores.reduce((sum, v) => sum + (v.quality_score ?? 0), 0) /
        scores.length
      : null

  return {
    totalTracks: tracks.count ?? 0,
    analyzedTracks: features.count ?? 0,
    totalSets: sets.count ?? 0,
    libraryItems: library.count ?? 0,
    avgSetQuality: avgQuality,
  }
}

export interface BpmBin {
  bin: number
  count: number
}

export async function getBpmDistribution(): Promise<BpmBin[]> {
  const supabase = await createClient()
  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('bpm')
    .not('bpm', 'is', null)

  if (!data) return []

  // Group into 5-BPM bins
  const bins = new Map<number, number>()
  for (const row of data) {
    const bin = Math.floor(row.bpm / 5) * 5
    bins.set(bin, (bins.get(bin) ?? 0) + 1)
  }

  return Array.from(bins.entries())
    .map(([bin, count]) => ({ bin, count }))
    .sort((a, b) => a.bin - b.bin)
}

export interface MoodCount {
  mood: string
  count: number
}

export async function getMoodDistribution(): Promise<MoodCount[]> {
  const supabase = await createClient()
  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('mood')
    .not('mood', 'is', null)

  if (!data) return []

  const counts = new Map<string, number>()
  for (const row of data) {
    counts.set(row.mood, (counts.get(row.mood) ?? 0) + 1)
  }

  return Array.from(counts.entries())
    .map(([mood, count]) => ({ mood, count }))
    .sort((a, b) => b.count - a.count)
}

export interface KeyCount {
  camelot: string
  count: number
}

export async function getKeyDistribution(): Promise<KeyCount[]> {
  const supabase = await createClient()

  // Get features with key_code, then join with keys table
  const { data: features } = await supabase
    .from('track_audio_features_computed')
    .select('key_code')
    .not('key_code', 'is', null)

  const { data: keys } = await supabase.from('keys').select('key_code, camelot')

  if (!features || !keys) return []

  const keyMap = new Map(keys.map((k) => [k.key_code, k.camelot]))

  const counts = new Map<string, number>()
  for (const row of features) {
    const camelot = keyMap.get(row.key_code) ?? '?'
    counts.set(camelot, (counts.get(camelot) ?? 0) + 1)
  }

  // Sort by Camelot number (1A, 1B, 2A, 2B, ...)
  return Array.from(counts.entries())
    .map(([camelot, count]) => ({ camelot, count }))
    .sort((a, b) => {
      const numA = parseInt(a.camelot)
      const numB = parseInt(b.camelot)
      if (numA !== numB) return numA - numB
      return a.camelot.localeCompare(b.camelot)
    })
}

export interface LufsBin {
  lufs: number
  count: number
}

export async function getLufsDistribution(): Promise<LufsBin[]> {
  const supabase = await createClient()
  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('integrated_lufs')
    .not('integrated_lufs', 'is', null)

  if (!data) return []

  const bins = new Map<number, number>()
  for (const row of data) {
    const bin = Math.round(row.integrated_lufs)
    bins.set(bin, (bins.get(bin) ?? 0) + 1)
  }

  return Array.from(bins.entries())
    .map(([lufs, count]) => ({ lufs, count }))
    .sort((a, b) => a.lufs - b.lufs)
}

export interface AnalysisLevelCount {
  level: number
  count: number
}

export async function getAnalysisCoverage(): Promise<AnalysisLevelCount[]> {
  const supabase = await createClient()
  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('analysis_level')

  if (!data) return []

  const counts = new Map<number, number>()
  for (const row of data) {
    const level = row.analysis_level ?? 0
    counts.set(level, (counts.get(level) ?? 0) + 1)
  }

  return Array.from(counts.entries())
    .map(([level, count]) => ({ level, count }))
    .sort((a, b) => a.level - b.level)
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/lib/queries/dashboard.ts
git commit -m "feat(panel): add dashboard Supabase queries

Stats, BPM/mood/key/LUFS distributions, analysis coverage.
All via @supabase/ssr Server Component queries."
```

---

### Task 10: Track queries

**Files:**
- Create: `panel/lib/queries/tracks.ts`

- [ ] **Step 1: Create track queries**

```typescript
// panel/lib/queries/tracks.ts
import { createClient } from '@/lib/supabase/server'

export interface TrackRow {
  id: number
  title: string
  duration_ms: number | null
  status: number
  artists: string
  bpm: number | null
  key_code: number | null
  camelot: string | null
  mood: string | null
  integrated_lufs: number | null
  energy_mean: number | null
  analysis_level: number | null
}

export interface TrackListParams {
  page?: number
  pageSize?: number
  sortBy?: string
  sortDir?: 'asc' | 'desc'
  bpmMin?: number
  bpmMax?: number
  mood?: string
  keyCode?: number
  search?: string
}

export interface TrackListResult {
  tracks: TrackRow[]
  total: number
}

export async function getTrackList(
  params: TrackListParams = {}
): Promise<TrackListResult> {
  const {
    page = 1,
    pageSize = 50,
    sortBy = 'title',
    sortDir = 'asc',
    bpmMin,
    bpmMax,
    mood,
    keyCode,
    search,
  } = params

  const supabase = await createClient()
  const offset = (page - 1) * pageSize

  // Get tracks with features in a single query
  let query = supabase
    .from('tracks')
    .select(
      `
      id, title, duration_ms, status,
      track_audio_features_computed!left(
        bpm, key_code, mood, integrated_lufs, energy_mean, analysis_level
      )
    `,
      { count: 'exact' }
    )
    .eq('status', 0) // active tracks only

  // Search filter
  if (search) {
    query = query.ilike('title', `%${search}%`)
  }

  // Audio feature filters — applied via inner join conditions
  if (bpmMin !== undefined) {
    query = query.gte('track_audio_features_computed.bpm', bpmMin)
  }
  if (bpmMax !== undefined) {
    query = query.lte('track_audio_features_computed.bpm', bpmMax)
  }
  if (mood) {
    query = query.eq('track_audio_features_computed.mood', mood)
  }
  if (keyCode !== undefined) {
    query = query.eq('track_audio_features_computed.key_code', keyCode)
  }

  // Sort
  const featureColumns = [
    'bpm',
    'key_code',
    'mood',
    'integrated_lufs',
    'energy_mean',
    'analysis_level',
  ]
  if (featureColumns.includes(sortBy)) {
    query = query.order(sortBy, {
      ascending: sortDir === 'asc',
      referencedTable: 'track_audio_features_computed',
    })
  } else {
    query = query.order(sortBy, { ascending: sortDir === 'asc' })
  }

  query = query.range(offset, offset + pageSize - 1)

  const { data, count } = await query

  if (!data) return { tracks: [], total: 0 }

  // Get artist names for these tracks
  const trackIds = data.map((t) => t.id)
  const { data: artists } = await supabase
    .from('track_artists')
    .select('track_id, artists(name)')
    .in('track_id', trackIds)
    .eq('role', 'primary')

  const artistMap = new Map<number, string>()
  if (artists) {
    for (const a of artists) {
      const existing = artistMap.get(a.track_id)
      const name =
        (a.artists as unknown as { name: string })?.name ?? 'Unknown'
      artistMap.set(a.track_id, existing ? `${existing}, ${name}` : name)
    }
  }

  // Get camelot for key_codes
  const { data: keys } = await supabase.from('keys').select('key_code, camelot')
  const keyMap = new Map(keys?.map((k) => [k.key_code, k.camelot]) ?? [])

  const tracks: TrackRow[] = data.map((t) => {
    const feat = Array.isArray(t.track_audio_features_computed)
      ? t.track_audio_features_computed[0]
      : t.track_audio_features_computed
    return {
      id: t.id,
      title: t.title,
      duration_ms: t.duration_ms,
      status: t.status,
      artists: artistMap.get(t.id) ?? '',
      bpm: feat?.bpm ?? null,
      key_code: feat?.key_code ?? null,
      camelot: feat?.key_code != null ? keyMap.get(feat.key_code) ?? null : null,
      mood: feat?.mood ?? null,
      integrated_lufs: feat?.integrated_lufs ?? null,
      energy_mean: feat?.energy_mean ?? null,
      analysis_level: feat?.analysis_level ?? null,
    }
  })

  return { tracks, total: count ?? 0 }
}

export interface TrackDetail {
  id: number
  title: string
  sort_title: string | null
  duration_ms: number | null
  status: number
  created_at: string
  updated_at: string
  artists: Array<{ name: string; role: string }>
  features: Record<string, unknown> | null
  sections: Array<{
    section_type: number
    start_ms: number
    end_ms: number
    energy: number | null
    confidence: number | null
  }>
  cuePoints: Array<{
    position_ms: number
    kind: number
    hotcue_index: number | null
    label: string | null
    color: string | null
  }>
  loops: Array<{
    in_position_ms: number
    out_position_ms: number
    label: string | null
    color: string | null
  }>
  libraryItem: {
    file_path: string | null
    bitrate: number | null
    sample_rate: number | null
    channels: number | null
    file_size: number | null
  } | null
  ymMetadata: Record<string, unknown> | null
}

export async function getTrackDetail(
  id: number
): Promise<TrackDetail | null> {
  const supabase = await createClient()

  // Parallel queries for all track data
  const [trackRes, featRes, sectionsRes, artistsRes, cueRes, loopRes, libRes, ymRes] =
    await Promise.all([
      supabase.from('tracks').select('*').eq('id', id).single(),
      supabase
        .from('track_audio_features_computed')
        .select('*')
        .eq('track_id', id)
        .maybeSingle(),
      supabase
        .from('track_sections')
        .select('section_type, start_ms, end_ms, energy, confidence')
        .eq('track_id', id)
        .order('start_ms'),
      supabase
        .from('track_artists')
        .select('role, artists(name)')
        .eq('track_id', id),
      supabase
        .from('dj_cue_points')
        .select('position_ms, kind, hotcue_index, label, color')
        .eq('library_item_id', id), // Note: may need to join via library_item
      supabase
        .from('dj_saved_loops')
        .select('in_position_ms, out_position_ms, label, color')
        .eq('library_item_id', id),
      supabase
        .from('dj_library_items')
        .select('file_path, bitrate, sample_rate, channels, file_size')
        .eq('track_id', id)
        .maybeSingle(),
      supabase
        .from('yandex_metadata')
        .select('*')
        .eq('track_id', id)
        .maybeSingle(),
    ])

  if (!trackRes.data) return null

  const track = trackRes.data

  // Cue points and loops are linked via library_item, re-query if needed
  let cuePoints = cueRes.data ?? []
  let loops = loopRes.data ?? []
  if (libRes.data && cuePoints.length === 0) {
    // Try via library item ID
    const libItemRes = await supabase
      .from('dj_library_items')
      .select('id')
      .eq('track_id', id)
      .maybeSingle()
    if (libItemRes.data) {
      const [cue2, loop2] = await Promise.all([
        supabase
          .from('dj_cue_points')
          .select('position_ms, kind, hotcue_index, label, color')
          .eq('library_item_id', libItemRes.data.id),
        supabase
          .from('dj_saved_loops')
          .select('in_position_ms, out_position_ms, label, color')
          .eq('library_item_id', libItemRes.data.id),
      ])
      cuePoints = cue2.data ?? []
      loops = loop2.data ?? []
    }
  }

  return {
    id: track.id,
    title: track.title,
    sort_title: track.sort_title,
    duration_ms: track.duration_ms,
    status: track.status,
    created_at: track.created_at,
    updated_at: track.updated_at,
    artists: (artistsRes.data ?? []).map((a) => ({
      name: (a.artists as unknown as { name: string })?.name ?? 'Unknown',
      role: a.role,
    })),
    features: featRes.data,
    sections: sectionsRes.data ?? [],
    cuePoints,
    loops,
    libraryItem: libRes.data,
    ymMetadata: ymRes.data,
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/lib/queries/tracks.ts
git commit -m "feat(panel): add track list and detail Supabase queries

Track list with joins to features/artists/keys, server-side filtering.
Track detail with parallel queries for features, sections, cue points,
loops, library items, and YM metadata."
```

---

### Task 11: Set queries

**Files:**
- Create: `panel/lib/queries/sets.ts`

- [ ] **Step 1: Create set queries**

```typescript
// panel/lib/queries/sets.ts
import { createClient } from '@/lib/supabase/server'

export interface SetListItem {
  id: number
  name: string
  template_name: string | null
  target_duration_ms: number | null
  target_bpm_min: number | null
  target_bpm_max: number | null
  created_at: string
  latestVersion: {
    id: number
    label: string | null
    quality_score: number | null
  } | null
  trackCount: number
  versionCount: number
}

export async function getSetList(): Promise<SetListItem[]> {
  const supabase = await createClient()

  const { data: sets } = await supabase
    .from('dj_sets')
    .select('*')
    .order('created_at', { ascending: false })

  if (!sets) return []

  // Get version info for all sets
  const setIds = sets.map((s) => s.id)
  const { data: versions } = await supabase
    .from('dj_set_versions')
    .select('id, set_id, label, quality_score, created_at')
    .in('set_id', setIds)
    .order('created_at', { ascending: false })

  // Get track counts per version
  const versionIds = versions?.map((v) => v.id) ?? []
  const { data: items } = await supabase
    .from('dj_set_items')
    .select('version_id')
    .in('version_id', versionIds)

  // Build maps
  const latestVersion = new Map<number, (typeof versions extends (infer T)[] | null ? T : never)>()
  const versionCounts = new Map<number, number>()
  for (const v of versions ?? []) {
    if (!latestVersion.has(v.set_id)) latestVersion.set(v.set_id, v)
    versionCounts.set(v.set_id, (versionCounts.get(v.set_id) ?? 0) + 1)
  }

  const itemCounts = new Map<number, number>()
  for (const item of items ?? []) {
    itemCounts.set(item.version_id, (itemCounts.get(item.version_id) ?? 0) + 1)
  }

  return sets.map((s) => {
    const latest = latestVersion.get(s.id)
    return {
      id: s.id,
      name: s.name,
      template_name: s.template_name,
      target_duration_ms: s.target_duration_ms,
      target_bpm_min: s.target_bpm_min,
      target_bpm_max: s.target_bpm_max,
      created_at: s.created_at,
      latestVersion: latest
        ? {
            id: latest.id,
            label: latest.label,
            quality_score: latest.quality_score,
          }
        : null,
      trackCount: latest ? (itemCounts.get(latest.id) ?? 0) : 0,
      versionCount: versionCounts.get(s.id) ?? 0,
    }
  })
}

export interface SetDetail {
  id: number
  name: string
  description: string | null
  template_name: string | null
  target_duration_ms: number | null
  target_bpm_min: number | null
  target_bpm_max: number | null
  target_energy_arc: unknown
  source_playlist_id: number | null
  versions: Array<{
    id: number
    label: string | null
    quality_score: number | null
    created_at: string
  }>
  constraints: Array<{
    constraint_type: string
    constraint_value: unknown
  }>
}

export async function getSetDetail(id: number): Promise<SetDetail | null> {
  const supabase = await createClient()

  const [setRes, versionsRes, constraintsRes] = await Promise.all([
    supabase.from('dj_sets').select('*').eq('id', id).single(),
    supabase
      .from('dj_set_versions')
      .select('id, label, quality_score, created_at')
      .eq('set_id', id)
      .order('created_at', { ascending: false }),
    supabase
      .from('dj_set_constraints')
      .select('constraint_type, constraint_value')
      .eq('set_id', id),
  ])

  if (!setRes.data) return null

  return {
    ...setRes.data,
    versions: versionsRes.data ?? [],
    constraints: constraintsRes.data ?? [],
  }
}

export interface SetVersionTrack {
  sort_index: number
  pinned: boolean
  notes: string | null
  mix_in_point_ms: number | null
  mix_out_point_ms: number | null
  track: {
    id: number
    title: string
    artists: string
    bpm: number | null
    key_code: number | null
    camelot: string | null
    mood: string | null
    integrated_lufs: number | null
    energy_mean: number | null
  }
  transition: {
    overall_quality: number | null
    bpm_score: number | null
    harmonic_score: number | null
    energy_score: number | null
    spectral_score: number | null
    groove_score: number | null
  } | null
}

export async function getSetVersionTracks(
  versionId: number
): Promise<SetVersionTrack[]> {
  const supabase = await createClient()

  const { data: items } = await supabase
    .from('dj_set_items')
    .select(
      `
      sort_index, pinned, notes, mix_in_point_ms, mix_out_point_ms,
      track_id, transition_id
    `
    )
    .eq('version_id', versionId)
    .order('sort_index')

  if (!items || items.length === 0) return []

  const trackIds = items.map((i) => i.track_id).filter(Boolean) as number[]
  const transitionIds = items
    .map((i) => i.transition_id)
    .filter(Boolean) as number[]

  // Parallel fetches
  const [tracksRes, featuresRes, artistsRes, transitionsRes, keysRes] =
    await Promise.all([
      supabase.from('tracks').select('id, title').in('id', trackIds),
      supabase
        .from('track_audio_features_computed')
        .select(
          'track_id, bpm, key_code, mood, integrated_lufs, energy_mean'
        )
        .in('track_id', trackIds),
      supabase
        .from('track_artists')
        .select('track_id, artists(name)')
        .in('track_id', trackIds)
        .eq('role', 'primary'),
      transitionIds.length > 0
        ? supabase
            .from('transitions')
            .select(
              'id, overall_quality, bpm_score, harmonic_score, energy_score, spectral_score, groove_score'
            )
            .in('id', transitionIds)
        : Promise.resolve({ data: [] }),
      supabase.from('keys').select('key_code, camelot'),
    ])

  const trackMap = new Map(tracksRes.data?.map((t) => [t.id, t]) ?? [])
  const featMap = new Map(
    featuresRes.data?.map((f) => [f.track_id, f]) ?? []
  )
  const keyMap = new Map(keysRes.data?.map((k) => [k.key_code, k.camelot]) ?? [])

  const artistMap = new Map<number, string>()
  for (const a of artistsRes.data ?? []) {
    const name =
      (a.artists as unknown as { name: string })?.name ?? 'Unknown'
    const existing = artistMap.get(a.track_id)
    artistMap.set(a.track_id, existing ? `${existing}, ${name}` : name)
  }

  const transMap = new Map(
    (transitionsRes.data ?? []).map((t) => [t.id, t])
  )

  return items.map((item) => {
    const track = trackMap.get(item.track_id!)
    const feat = featMap.get(item.track_id!)
    const trans = item.transition_id
      ? transMap.get(item.transition_id)
      : null

    return {
      sort_index: item.sort_index,
      pinned: item.pinned ?? false,
      notes: item.notes,
      mix_in_point_ms: item.mix_in_point_ms,
      mix_out_point_ms: item.mix_out_point_ms,
      track: {
        id: item.track_id!,
        title: track?.title ?? 'Unknown',
        artists: artistMap.get(item.track_id!) ?? '',
        bpm: feat?.bpm ?? null,
        key_code: feat?.key_code ?? null,
        camelot:
          feat?.key_code != null ? keyMap.get(feat.key_code) ?? null : null,
        mood: feat?.mood ?? null,
        integrated_lufs: feat?.integrated_lufs ?? null,
        energy_mean: feat?.energy_mean ?? null,
      },
      transition: trans
        ? {
            overall_quality: trans.overall_quality,
            bpm_score: trans.bpm_score,
            harmonic_score: trans.harmonic_score,
            energy_score: trans.energy_score,
            spectral_score: trans.spectral_score,
            groove_score: trans.groove_score,
          }
        : null,
    }
  })
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/lib/queries/sets.ts
git commit -m "feat(panel): add set list and detail Supabase queries

Set list with latest version, track/version counts.
Set detail with versions, constraints.
Version tracks with transitions, features, artists."
```

---

### Task 12: Playlist queries

**Files:**
- Create: `panel/lib/queries/playlists.ts`

- [ ] **Step 1: Create playlist queries**

```typescript
// panel/lib/queries/playlists.ts
import { createClient } from '@/lib/supabase/server'

export interface PlaylistListItem {
  id: number
  name: string
  parent_id: number | null
  source_of_truth: string | null
  source_app: string | null
  trackCount: number
}

export async function getPlaylistList(): Promise<PlaylistListItem[]> {
  const supabase = await createClient()

  const [playlistsRes, countsRes] = await Promise.all([
    supabase
      .from('dj_playlists')
      .select('id, name, parent_id, source_of_truth, source_app')
      .order('name'),
    supabase
      .from('dj_playlist_items')
      .select('playlist_id'),
  ])

  const countMap = new Map<number, number>()
  for (const item of countsRes.data ?? []) {
    countMap.set(
      item.playlist_id,
      (countMap.get(item.playlist_id) ?? 0) + 1
    )
  }

  return (playlistsRes.data ?? []).map((p) => ({
    ...p,
    trackCount: countMap.get(p.id) ?? 0,
  }))
}

export interface PlaylistDetail {
  id: number
  name: string
  parent_id: number | null
  source_of_truth: string | null
  platform_ids: unknown
  tracks: Array<{
    sort_index: number
    added_at: string | null
    track: {
      id: number
      title: string
      artists: string
      bpm: number | null
      camelot: string | null
      mood: string | null
      integrated_lufs: number | null
    }
  }>
  moodCounts: Array<{ mood: string; count: number }>
}

export async function getPlaylistDetail(
  id: number
): Promise<PlaylistDetail | null> {
  const supabase = await createClient()

  const [playlistRes, itemsRes] = await Promise.all([
    supabase.from('dj_playlists').select('*').eq('id', id).single(),
    supabase
      .from('dj_playlist_items')
      .select('sort_index, added_at, track_id')
      .eq('playlist_id', id)
      .order('sort_index'),
  ])

  if (!playlistRes.data) return null

  const trackIds = (itemsRes.data ?? [])
    .map((i) => i.track_id)
    .filter(Boolean) as number[]

  if (trackIds.length === 0) {
    return {
      ...playlistRes.data,
      tracks: [],
      moodCounts: [],
    }
  }

  const [tracksRes, featuresRes, artistsRes, keysRes] = await Promise.all([
    supabase.from('tracks').select('id, title').in('id', trackIds),
    supabase
      .from('track_audio_features_computed')
      .select('track_id, bpm, key_code, mood, integrated_lufs')
      .in('track_id', trackIds),
    supabase
      .from('track_artists')
      .select('track_id, artists(name)')
      .in('track_id', trackIds)
      .eq('role', 'primary'),
    supabase.from('keys').select('key_code, camelot'),
  ])

  const trackMap = new Map(tracksRes.data?.map((t) => [t.id, t]) ?? [])
  const featMap = new Map(
    featuresRes.data?.map((f) => [f.track_id, f]) ?? []
  )
  const keyMap = new Map(keysRes.data?.map((k) => [k.key_code, k.camelot]) ?? [])

  const artistMap = new Map<number, string>()
  for (const a of artistsRes.data ?? []) {
    const name =
      (a.artists as unknown as { name: string })?.name ?? 'Unknown'
    const existing = artistMap.get(a.track_id)
    artistMap.set(a.track_id, existing ? `${existing}, ${name}` : name)
  }

  // Mood distribution
  const moodCountMap = new Map<string, number>()
  for (const f of featuresRes.data ?? []) {
    if (f.mood) {
      moodCountMap.set(f.mood, (moodCountMap.get(f.mood) ?? 0) + 1)
    }
  }

  return {
    ...playlistRes.data,
    tracks: (itemsRes.data ?? []).map((item) => {
      const track = trackMap.get(item.track_id!)
      const feat = featMap.get(item.track_id!)
      return {
        sort_index: item.sort_index,
        added_at: item.added_at,
        track: {
          id: item.track_id!,
          title: track?.title ?? 'Unknown',
          artists: artistMap.get(item.track_id!) ?? '',
          bpm: feat?.bpm ?? null,
          camelot:
            feat?.key_code != null
              ? keyMap.get(feat.key_code) ?? null
              : null,
          mood: feat?.mood ?? null,
          integrated_lufs: feat?.integrated_lufs ?? null,
        },
      }
    }),
    moodCounts: Array.from(moodCountMap.entries())
      .map(([mood, count]) => ({ mood, count }))
      .sort((a, b) => b.count - a.count),
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/lib/queries/playlists.ts
git commit -m "feat(panel): add playlist list and detail Supabase queries

Playlist list with track counts, hierarchical parent_id.
Playlist detail with tracks, features, artists, mood distribution."
```

---

## Phase 3: Shared Components

### Task 13: Mood badge component

**Files:**
- Create: `panel/components/mood-badge.tsx`

- [ ] **Step 1: Create mood badge**

```tsx
// panel/components/mood-badge.tsx
import { Badge } from '@/components/ui/badge'
import { SUBGENRE_COLORS, SUBGENRE_LABELS } from '@/lib/constants'

export function MoodBadge({ mood }: { mood: string | null }) {
  if (!mood) return <span className="text-muted-foreground">—</span>

  const color = SUBGENRE_COLORS[mood] ?? '#888'
  const label = SUBGENRE_LABELS[mood] ?? mood

  return (
    <Badge
      variant="outline"
      style={{ borderColor: color, color }}
      className="text-xs"
    >
      {label}
    </Badge>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/components/mood-badge.tsx
git commit -m "feat(panel): add MoodBadge component

Colored badge for 15 techno subgenres with display names."
```

---

### Task 14: Section cards component (dashboard stats)

**Files:**
- Create: `panel/components/section-cards.tsx`

- [ ] **Step 1: Create section cards**

```tsx
// panel/components/section-cards.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { LibraryStats } from '@/lib/queries/dashboard'

export function SectionCards({ stats }: { stats: LibraryStats }) {
  const cards = [
    {
      title: 'Total Tracks',
      value: stats.totalTracks.toLocaleString(),
      description: 'in library',
    },
    {
      title: 'Analyzed',
      value: stats.analyzedTracks.toLocaleString(),
      description: `${stats.totalTracks > 0 ? Math.round((stats.analyzedTracks / stats.totalTracks) * 100) : 0}% coverage`,
    },
    {
      title: 'DJ Sets',
      value: stats.totalSets.toLocaleString(),
      description: 'created',
    },
    {
      title: 'Library Files',
      value: stats.libraryItems.toLocaleString(),
      description: 'downloaded',
    },
    {
      title: 'Avg Set Quality',
      value: stats.avgSetQuality?.toFixed(2) ?? '—',
      description: stats.avgSetQuality ? 'score' : 'no sets scored',
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {card.title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{card.value}</div>
            <p className="text-xs text-muted-foreground">
              {card.description}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/components/section-cards.tsx
git commit -m "feat(panel): add SectionCards dashboard stats component

5 stat cards: total tracks, analyzed, sets, library files, avg quality."
```

---

### Task 15: Dashboard chart components

**Files:**
- Create: `panel/components/charts/bpm-distribution.tsx`
- Create: `panel/components/charts/mood-distribution.tsx`
- Create: `panel/components/charts/camelot-wheel.tsx`
- Create: `panel/components/charts/lufs-range.tsx`
- Create: `panel/components/charts/energy-arc.tsx`

- [ ] **Step 1: Create BPM distribution chart**

```tsx
// panel/components/charts/bpm-distribution.tsx
'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Bar, BarChart, XAxis, YAxis } from 'recharts'
import type { BpmBin } from '@/lib/queries/dashboard'

const chartConfig = {
  count: { label: 'Tracks', color: 'hsl(var(--chart-1))' },
} satisfies ChartConfig

export function BpmDistributionChart({ data }: { data: BpmBin[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[250px] w-full">
      <BarChart data={data}>
        <XAxis dataKey="bin" tickLine={false} fontSize={12} />
        <YAxis tickLine={false} fontSize={12} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="count" fill="var(--color-count)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartContainer>
  )
}
```

- [ ] **Step 2: Create mood distribution chart**

```tsx
// panel/components/charts/mood-distribution.tsx
'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Bar, BarChart, XAxis, YAxis } from 'recharts'
import { SUBGENRE_COLORS, SUBGENRE_LABELS } from '@/lib/constants'
import type { MoodCount } from '@/lib/queries/dashboard'

const chartConfig = {
  count: { label: 'Tracks' },
} satisfies ChartConfig

export function MoodDistributionChart({ data }: { data: MoodCount[] }) {
  const chartData = data.map((d) => ({
    ...d,
    label: SUBGENRE_LABELS[d.mood] ?? d.mood,
    fill: SUBGENRE_COLORS[d.mood] ?? '#888',
  }))

  return (
    <ChartContainer config={chartConfig} className="h-[400px] w-full">
      <BarChart data={chartData} layout="vertical" margin={{ left: 100 }}>
        <XAxis type="number" tickLine={false} fontSize={12} />
        <YAxis
          type="category"
          dataKey="label"
          tickLine={false}
          fontSize={12}
          width={90}
        />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ChartContainer>
  )
}
```

- [ ] **Step 3: Create Camelot wheel chart**

```tsx
// panel/components/charts/camelot-wheel.tsx
'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import {
  Radar,
  RadarChart,
  PolarAngleAxis,
  PolarGrid,
} from 'recharts'
import type { KeyCount } from '@/lib/queries/dashboard'

const chartConfig = {
  count: { label: 'Tracks', color: 'hsl(var(--chart-2))' },
} satisfies ChartConfig

export function CamelotWheelChart({ data }: { data: KeyCount[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[350px] w-full">
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="80%">
        <PolarGrid />
        <PolarAngleAxis dataKey="camelot" fontSize={10} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Radar
          name="Tracks"
          dataKey="count"
          stroke="var(--color-count)"
          fill="var(--color-count)"
          fillOpacity={0.3}
        />
      </RadarChart>
    </ChartContainer>
  )
}
```

- [ ] **Step 4: Create LUFS range chart**

```tsx
// panel/components/charts/lufs-range.tsx
'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Area, AreaChart, XAxis, YAxis } from 'recharts'
import type { LufsBin } from '@/lib/queries/dashboard'

const chartConfig = {
  count: { label: 'Tracks', color: 'hsl(var(--chart-3))' },
} satisfies ChartConfig

export function LufsRangeChart({ data }: { data: LufsBin[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[250px] w-full">
      <AreaChart data={data}>
        <XAxis
          dataKey="lufs"
          tickLine={false}
          fontSize={12}
          tickFormatter={(v) => `${v}`}
        />
        <YAxis tickLine={false} fontSize={12} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Area
          dataKey="count"
          type="monotone"
          stroke="var(--color-count)"
          fill="var(--color-count)"
          fillOpacity={0.3}
        />
      </AreaChart>
    </ChartContainer>
  )
}
```

- [ ] **Step 5: Create energy arc chart (for set detail)**

```tsx
// panel/components/charts/energy-arc.tsx
'use client'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Bar, BarChart, XAxis, YAxis, Cell } from 'recharts'

const chartConfig = {
  lufs: { label: 'LUFS' },
} satisfies ChartConfig

interface EnergyArcData {
  position: number
  title: string
  lufs: number
}

function energyColor(lufs: number): string {
  // LUFS range typically -20 to -4 for techno
  // Map to green (low energy) → yellow → red (high energy)
  const normalized = Math.min(1, Math.max(0, (lufs + 20) / 16))
  if (normalized < 0.33) return 'hsl(142, 76%, 36%)' // green
  if (normalized < 0.66) return 'hsl(48, 96%, 53%)'  // yellow
  return 'hsl(0, 72%, 51%)'                           // red
}

export function EnergyArcChart({ data }: { data: EnergyArcData[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[200px] w-full">
      <BarChart data={data}>
        <XAxis dataKey="position" tickLine={false} fontSize={12} />
        <YAxis tickLine={false} fontSize={12} domain={[-20, -4]} />
        <ChartTooltip
          content={<ChartTooltipContent nameKey="title" />}
        />
        <Bar dataKey="lufs" radius={[4, 4, 0, 0]}>
          {data.map((entry, index) => (
            <Cell key={index} fill={energyColor(entry.lufs)} />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
```

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/components/charts/
git commit -m "feat(panel): add dashboard chart components

BPM distribution (bar), mood distribution (horizontal bar),
Camelot wheel (radar), LUFS range (area), energy arc (colored bar)."
```

---

## Phase 4: Pages

### Task 16: Dashboard page

**Files:**
- Modify: `panel/app/page.tsx`

- [ ] **Step 1: Implement dashboard page**

```tsx
// panel/app/page.tsx
import { SiteHeader } from '@/components/site-header'
import { SectionCards } from '@/components/section-cards'
import { BpmDistributionChart } from '@/components/charts/bpm-distribution'
import { MoodDistributionChart } from '@/components/charts/mood-distribution'
import { CamelotWheelChart } from '@/components/charts/camelot-wheel'
import { LufsRangeChart } from '@/components/charts/lufs-range'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { ANALYSIS_LEVELS } from '@/lib/constants'
import {
  getLibraryStats,
  getBpmDistribution,
  getMoodDistribution,
  getKeyDistribution,
  getLufsDistribution,
  getAnalysisCoverage,
} from '@/lib/queries/dashboard'

export const revalidate = 30

export default async function DashboardPage() {
  const [stats, bpmData, moodData, keyData, lufsData, coverage] =
    await Promise.all([
      getLibraryStats(),
      getBpmDistribution(),
      getMoodDistribution(),
      getKeyDistribution(),
      getLufsDistribution(),
      getAnalysisCoverage(),
    ])

  const totalAnalyzed = coverage.reduce((sum, c) => sum + c.count, 0)

  return (
    <>
      <SiteHeader title="Dashboard" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <SectionCards stats={stats} />

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>BPM Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <BpmDistributionChart data={bpmData} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>LUFS Range</CardTitle>
            </CardHeader>
            <CardContent>
              <LufsRangeChart data={lufsData} />
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Mood Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <MoodDistributionChart data={moodData} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Camelot Wheel</CardTitle>
            </CardHeader>
            <CardContent>
              <CamelotWheelChart data={keyData} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Analysis Coverage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {coverage.map((c) => (
              <div key={c.level} className="flex items-center gap-3">
                <Badge variant="outline" className="w-28 justify-center">
                  {ANALYSIS_LEVELS[c.level] ?? `L${c.level}`}
                </Badge>
                <Progress
                  value={totalAnalyzed > 0 ? (c.count / totalAnalyzed) * 100 : 0}
                  className="flex-1"
                />
                <span className="text-sm text-muted-foreground w-16 text-right">
                  {c.count} tracks
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
```

- [ ] **Step 2: Verify dashboard renders**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm run dev
```

Open `http://localhost:3000`. Expected: Stats cards + 4 charts + analysis coverage bar. If Supabase connection works, real data should appear.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/app/page.tsx
git commit -m "feat(panel): implement dashboard page

Stats cards, BPM/LUFS/mood/Camelot charts, analysis coverage.
ISR revalidate=30s. Server Component with parallel Supabase queries."
```

---

### Task 17: Library page with DataTable

**Files:**
- Create: `panel/components/data-table.tsx`
- Create: `panel/app/library/page.tsx`

- [ ] **Step 1: Create reusable DataTable component**

```tsx
// panel/components/data-table.tsx
'use client'

import * as React from 'react'
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { IconChevronUp, IconChevronDown } from '@tabler/icons-react'

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  onRowClick?: (row: TData) => void
}

export function DataTable<TData, TValue>({
  columns,
  data,
  onRowClick,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  })

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder ? null : header.column.getCanSort() ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="-ml-3 h-8"
                      onClick={() => header.column.toggleSorting()}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {header.column.getIsSorted() === 'asc' ? (
                        <IconChevronUp className="ml-1 h-4 w-4" />
                      ) : header.column.getIsSorted() === 'desc' ? (
                        <IconChevronDown className="ml-1 h-4 w-4" />
                      ) : null}
                    </Button>
                  ) : (
                    flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )
                  )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className={onRowClick ? 'cursor-pointer' : ''}
                onClick={() => onRowClick?.(row.original)}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="h-24 text-center"
              >
                No results.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 2: Create library page**

```tsx
// panel/app/library/page.tsx
import { SiteHeader } from '@/components/site-header'
import { LibraryTable } from './library-table'
import { getTrackList, type TrackListParams } from '@/lib/queries/tracks'

export const revalidate = 60

export default async function LibraryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  const params = await searchParams
  const queryParams: TrackListParams = {
    page: params.page ? parseInt(params.page) : 1,
    pageSize: 50,
    sortBy: params.sortBy ?? 'title',
    sortDir: (params.sortDir as 'asc' | 'desc') ?? 'asc',
    bpmMin: params.bpmMin ? parseFloat(params.bpmMin) : undefined,
    bpmMax: params.bpmMax ? parseFloat(params.bpmMax) : undefined,
    mood: params.mood ?? undefined,
    search: params.search ?? undefined,
  }

  const { tracks, total } = await getTrackList(queryParams)
  const totalPages = Math.ceil(total / 50)

  return (
    <>
      <SiteHeader title="Library" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <LibraryTable
          tracks={tracks}
          total={total}
          page={queryParams.page ?? 1}
          totalPages={totalPages}
        />
      </div>
    </>
  )
}
```

- [ ] **Step 3: Create library table client component**

```tsx
// panel/app/library/library-table.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type ColumnDef } from '@tanstack/react-table'
import { DataTable } from '@/components/data-table'
import { MoodBadge } from '@/components/mood-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatDuration, formatBpm, formatLufs } from '@/lib/utils'
import { ANALYSIS_LEVELS } from '@/lib/constants'
import type { TrackRow } from '@/lib/queries/tracks'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import * as React from 'react'

const columns: ColumnDef<TrackRow>[] = [
  { accessorKey: 'id', header: 'ID', size: 60 },
  { accessorKey: 'title', header: 'Title' },
  { accessorKey: 'artists', header: 'Artists' },
  {
    accessorKey: 'bpm',
    header: 'BPM',
    cell: ({ row }) => formatBpm(row.original.bpm),
  },
  { accessorKey: 'camelot', header: 'Key' },
  {
    accessorKey: 'mood',
    header: 'Mood',
    cell: ({ row }) => <MoodBadge mood={row.original.mood} />,
  },
  {
    accessorKey: 'integrated_lufs',
    header: 'LUFS',
    cell: ({ row }) => formatLufs(row.original.integrated_lufs),
  },
  {
    accessorKey: 'energy_mean',
    header: 'Energy',
    cell: ({ row }) =>
      row.original.energy_mean?.toFixed(3) ?? '—',
  },
  {
    accessorKey: 'duration_ms',
    header: 'Duration',
    cell: ({ row }) =>
      row.original.duration_ms
        ? formatDuration(row.original.duration_ms)
        : '—',
  },
  {
    accessorKey: 'analysis_level',
    header: 'Level',
    cell: ({ row }) => {
      const level = row.original.analysis_level
      return (
        <Badge variant="outline" className="text-xs">
          {level != null ? (ANALYSIS_LEVELS[level] ?? `L${level}`) : 'None'}
        </Badge>
      )
    },
  },
]

interface LibraryTableProps {
  tracks: TrackRow[]
  total: number
  page: number
  totalPages: number
}

export function LibraryTable({
  tracks,
  total,
  page,
  totalPages,
}: LibraryTableProps) {
  const router = useRouter()
  const [search, setSearch] = React.useState('')

  function navigate(newPage: number) {
    const params = new URLSearchParams(window.location.search)
    params.set('page', String(newPage))
    router.push(`/library?${params.toString()}`)
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const params = new URLSearchParams(window.location.search)
    if (search) params.set('search', search)
    else params.delete('search')
    params.set('page', '1')
    router.push(`/library?${params.toString()}`)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Search tracks..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
          />
          <Button type="submit" variant="secondary" size="sm">
            Search
          </Button>
        </form>
        <span className="text-sm text-muted-foreground ml-auto">
          {total} tracks
        </span>
      </div>

      <DataTable
        columns={columns}
        data={tracks}
        onRowClick={(row) => router.push(`/library/${row.id}`)}
      />

      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => navigate(page - 1)}
          >
            <IconChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => navigate(page + 1)}
          >
            <IconChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify library page**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm run dev
```

Navigate to `http://localhost:3000/library`. Expected: Table with tracks, search, pagination.

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/components/data-table.tsx panel/app/library/
git commit -m "feat(panel): implement library page with DataTable

Reusable DataTable component with @tanstack/react-table sorting.
Library page with server-side filtering via searchParams,
pagination, search. Columns: id, title, artists, BPM, key,
mood, LUFS, energy, duration, analysis level."
```

---

### Task 18: Track detail page

**Files:**
- Create: `panel/components/track-features.tsx`
- Create: `panel/components/sections-timeline.tsx`
- Create: `panel/app/library/[id]/page.tsx`

- [ ] **Step 1: Create track features component**

```tsx
// panel/components/track-features.tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface FeatureGroupProps {
  features: Record<string, unknown> | null
}

function FeatureRow({ label, value }: { label: string; value: unknown }) {
  let display: string
  if (value === null || value === undefined) display = '—'
  else if (typeof value === 'number') display = value.toFixed(4)
  else if (typeof value === 'boolean') display = value ? 'Yes' : 'No'
  else display = String(value)

  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono">{display}</span>
    </div>
  )
}

const FEATURE_GROUPS: Record<string, string[]> = {
  Tempo: ['bpm', 'bpm_confidence', 'bpm_stability', 'variable_tempo'],
  Loudness: [
    'integrated_lufs', 'short_term_lufs_mean', 'momentary_max',
    'rms_dbfs', 'true_peak_db', 'crest_factor_db', 'loudness_range_lu',
  ],
  Energy: [
    'energy_mean', 'energy_max', 'energy_std', 'energy_slope',
    'energy_sub', 'energy_low', 'energy_lowmid', 'energy_mid',
    'energy_highmid', 'energy_high',
  ],
  Spectral: [
    'spectral_centroid_hz', 'spectral_rolloff_85', 'spectral_rolloff_95',
    'spectral_flatness', 'spectral_flux_mean', 'spectral_flux_std',
    'spectral_slope', 'spectral_contrast',
  ],
  Key: [
    'key_code', 'key_confidence', 'atonality',
    'hnr_db', 'chroma_entropy',
  ],
  Rhythm: [
    'hp_ratio', 'onset_rate', 'pulse_clarity', 'kick_prominence',
  ],
  'P1/P2': [
    'danceability', 'dynamic_complexity', 'dissonance_mean',
    'spectral_complexity_mean', 'pitch_salience_mean',
    'bpm_histogram_first_peak_weight', 'bpm_histogram_second_peak_bpm',
  ],
}

export function TrackFeatures({ features }: FeatureGroupProps) {
  if (!features) {
    return (
      <Card>
        <CardContent className="py-6">
          <p className="text-muted-foreground">No audio features computed.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Tabs defaultValue="Tempo">
      <TabsList className="flex-wrap">
        {Object.keys(FEATURE_GROUPS).map((group) => (
          <TabsTrigger key={group} value={group}>
            {group}
          </TabsTrigger>
        ))}
      </TabsList>
      {Object.entries(FEATURE_GROUPS).map(([group, keys]) => (
        <TabsContent key={group} value={group}>
          <Card>
            <CardHeader>
              <CardTitle>{group}</CardTitle>
            </CardHeader>
            <CardContent className="divide-y">
              {keys.map((key) => (
                <FeatureRow
                  key={key}
                  label={key}
                  value={features[key] as unknown}
                />
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      ))}
    </Tabs>
  )
}
```

- [ ] **Step 2: Create sections timeline component**

```tsx
// panel/components/sections-timeline.tsx
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { formatDuration } from '@/lib/utils'

const SECTION_COLORS: Record<number, string> = {
  0: '#6366f1',  // intro
  1: '#ef4444',  // attack
  2: '#f97316',  // build
  3: '#eab308',  // pre-drop
  4: '#dc2626',  // drop
  5: '#b91c1c',  // peak
  6: '#3b82f6',  // breakdown
  7: '#8b5cf6',  // outro
  8: '#f59e0b',  // rise
  9: '#06b6d4',  // valley
  10: '#10b981', // sustain
}

const SECTION_NAMES: Record<number, string> = {
  0: 'Intro', 1: 'Attack', 2: 'Build', 3: 'Pre-Drop',
  4: 'Drop', 5: 'Peak', 6: 'Breakdown', 7: 'Outro',
  8: 'Rise', 9: 'Valley', 10: 'Sustain',
}

interface Section {
  section_type: number
  start_ms: number
  end_ms: number
  energy: number | null
  confidence: number | null
}

export function SectionsTimeline({ sections }: { sections: Section[] }) {
  if (sections.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No sections detected.</p>
    )
  }

  const totalDuration = Math.max(...sections.map((s) => s.end_ms))

  return (
    <TooltipProvider>
      <div className="flex h-10 w-full rounded-md overflow-hidden">
        {sections.map((section, i) => {
          const width =
            ((section.end_ms - section.start_ms) / totalDuration) * 100
          const color = SECTION_COLORS[section.section_type] ?? '#666'
          const name = SECTION_NAMES[section.section_type] ?? `Type ${section.section_type}`

          return (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <div
                  className="h-full transition-opacity hover:opacity-80"
                  style={{
                    width: `${width}%`,
                    backgroundColor: color,
                    minWidth: '2px',
                  }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-medium">{name}</p>
                <p className="text-xs">
                  {formatDuration(section.start_ms)} —{' '}
                  {formatDuration(section.end_ms)}
                </p>
                {section.energy != null && (
                  <p className="text-xs">Energy: {section.energy.toFixed(3)}</p>
                )}
              </TooltipContent>
            </Tooltip>
          )
        })}
      </div>
    </TooltipProvider>
  )
}
```

- [ ] **Step 3: Create track detail page**

```tsx
// panel/app/library/[id]/page.tsx
import { notFound } from 'next/navigation'
import { SiteHeader } from '@/components/site-header'
import { TrackFeatures } from '@/components/track-features'
import { SectionsTimeline } from '@/components/sections-timeline'
import { MoodBadge } from '@/components/mood-badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getTrackDetail } from '@/lib/queries/tracks'
import { formatDuration, camelotNotation, formatBpm, formatLufs } from '@/lib/utils'

export const revalidate = 120

export default async function TrackDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const track = await getTrackDetail(parseInt(id))

  if (!track) notFound()

  const artists = track.artists
    .filter((a) => a.role === 'primary')
    .map((a) => a.name)
    .join(', ')

  return (
    <>
      <SiteHeader title={track.title} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Header card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">{track.title}</CardTitle>
            <p className="text-muted-foreground">{artists || 'Unknown Artist'}</p>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {track.duration_ms && (
                <Badge variant="secondary">
                  {formatDuration(track.duration_ms)}
                </Badge>
              )}
              {track.features?.bpm != null && (
                <Badge variant="secondary">
                  {formatBpm(track.features.bpm as number)} BPM
                </Badge>
              )}
              {track.features?.key_code != null && (
                <Badge variant="secondary">
                  {camelotNotation(track.features.key_code as number)}
                </Badge>
              )}
              {track.features?.integrated_lufs != null && (
                <Badge variant="secondary">
                  {formatLufs(track.features.integrated_lufs as number)}
                </Badge>
              )}
              <MoodBadge mood={(track.features?.mood as string) ?? null} />
            </div>
          </CardContent>
        </Card>

        {/* Sections timeline */}
        {track.sections.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Sections</CardTitle>
            </CardHeader>
            <CardContent>
              <SectionsTimeline sections={track.sections} />
            </CardContent>
          </Card>
        )}

        {/* Audio features tabs */}
        <TrackFeatures features={track.features} />

        {/* Cue points */}
        {track.cuePoints.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Cue Points</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {track.cuePoints.map((cue, i) => (
                  <Badge
                    key={i}
                    variant="outline"
                    style={cue.color ? { borderColor: cue.color } : undefined}
                  >
                    {cue.label ?? `Cue ${cue.hotcue_index ?? i}`}:{' '}
                    {formatDuration(cue.position_ms)}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Loops */}
        {track.loops.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Saved Loops</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {track.loops.map((loop, i) => (
                  <Badge key={i} variant="outline">
                    {loop.label ?? `Loop ${i + 1}`}:{' '}
                    {formatDuration(loop.in_position_ms)} —{' '}
                    {formatDuration(loop.out_position_ms)}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* File info */}
        {track.libraryItem && (
          <Card>
            <CardHeader>
              <CardTitle>File Info</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-2 text-sm">
              <span className="text-muted-foreground">Bitrate</span>
              <span>{track.libraryItem.bitrate ?? '—'} kbps</span>
              <span className="text-muted-foreground">Sample Rate</span>
              <span>{track.libraryItem.sample_rate ?? '—'} Hz</span>
              <span className="text-muted-foreground">Channels</span>
              <span>{track.libraryItem.channels ?? '—'}</span>
              <span className="text-muted-foreground">Size</span>
              <span>
                {track.libraryItem.file_size
                  ? `${(track.libraryItem.file_size / 1024 / 1024).toFixed(1)} MB`
                  : '—'}
              </span>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
```

- [ ] **Step 4: Verify track detail**

Navigate to `http://localhost:3000/library/1`. Expected: Track header, sections timeline, feature tabs, cue points, loops, file info.

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/components/track-features.tsx panel/components/sections-timeline.tsx \
  panel/app/library/\[id\]/
git commit -m "feat(panel): implement track detail page

7-tab audio features display (63 columns grouped).
Sections timeline with colored bars and tooltips.
Cue points, loops, file info, header with badges."
```

---

### Task 19: Sets list page

**Files:**
- Create: `panel/app/sets/page.tsx`

- [ ] **Step 1: Create sets page**

```tsx
// panel/app/sets/page.tsx
import Link from 'next/link'
import { SiteHeader } from '@/components/site-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getSetList } from '@/lib/queries/sets'
import { formatDuration } from '@/lib/utils'

export const revalidate = 30

export default async function SetsPage() {
  const sets = await getSetList()

  return (
    <>
      <SiteHeader title="DJ Sets" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {sets.length === 0 ? (
          <p className="text-muted-foreground">No sets created yet.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sets.map((set) => (
              <Link key={set.id} href={`/sets/${set.id}`}>
                <Card className="hover:border-primary transition-colors cursor-pointer">
                  <CardHeader>
                    <CardTitle className="text-lg">{set.name}</CardTitle>
                    <div className="flex gap-2">
                      {set.template_name && (
                        <Badge variant="secondary">{set.template_name}</Badge>
                      )}
                      {set.target_bpm_min && set.target_bpm_max && (
                        <Badge variant="outline">
                          {set.target_bpm_min}–{set.target_bpm_max} BPM
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <span className="text-muted-foreground">Tracks</span>
                      <span>{set.trackCount}</span>
                      <span className="text-muted-foreground">Versions</span>
                      <span>{set.versionCount}</span>
                      {set.target_duration_ms && (
                        <>
                          <span className="text-muted-foreground">Duration</span>
                          <span>{formatDuration(set.target_duration_ms)}</span>
                        </>
                      )}
                      {set.latestVersion?.quality_score != null && (
                        <>
                          <span className="text-muted-foreground">Quality</span>
                          <span className="font-mono">
                            {set.latestVersion.quality_score.toFixed(3)}
                          </span>
                        </>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/app/sets/
git commit -m "feat(panel): implement sets list page

Set cards with template, BPM range, track count, quality score.
Links to set detail page."
```

---

### Task 20: Set detail page with transition table

**Files:**
- Create: `panel/components/transition-table.tsx`
- Create: `panel/app/sets/[id]/page.tsx`

- [ ] **Step 1: Create transition table component**

```tsx
// panel/components/transition-table.tsx
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { scoreColor, formatBpm, camelotNotation } from '@/lib/utils'
import { MoodBadge } from '@/components/mood-badge'
import type { SetVersionTrack } from '@/lib/queries/sets'
import { IconPin } from '@tabler/icons-react'

export function TransitionTable({ tracks }: { tracks: SetVersionTrack[] }) {
  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8">#</TableHead>
            <TableHead>Track</TableHead>
            <TableHead>BPM</TableHead>
            <TableHead>Key</TableHead>
            <TableHead>Mood</TableHead>
            <TableHead>LUFS</TableHead>
            <TableHead className="text-center">Overall</TableHead>
            <TableHead className="text-center">BPM</TableHead>
            <TableHead className="text-center">Harm</TableHead>
            <TableHead className="text-center">Energy</TableHead>
            <TableHead className="text-center">Spec</TableHead>
            <TableHead className="text-center">Groove</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tracks.map((item, i) => (
            <TableRow key={i}>
              <TableCell className="font-mono text-muted-foreground">
                <div className="flex items-center gap-1">
                  {item.sort_index + 1}
                  {item.pinned && (
                    <IconPin className="h-3 w-3 text-yellow-400" />
                  )}
                </div>
              </TableCell>
              <TableCell>
                <div>
                  <span className="font-medium">{item.track.title}</span>
                  {item.track.artists && (
                    <span className="text-sm text-muted-foreground ml-2">
                      {item.track.artists}
                    </span>
                  )}
                </div>
              </TableCell>
              <TableCell className="font-mono">
                {formatBpm(item.track.bpm)}
              </TableCell>
              <TableCell>{item.track.camelot ?? '—'}</TableCell>
              <TableCell>
                <MoodBadge mood={item.track.mood} />
              </TableCell>
              <TableCell className="font-mono">
                {item.track.integrated_lufs?.toFixed(1) ?? '—'}
              </TableCell>
              {/* Transition scores — shown on transition row (from previous track to this) */}
              <TableCell className="text-center">
                {item.transition ? (
                  <span className={scoreColor(item.transition.overall_quality)}>
                    {item.transition.overall_quality?.toFixed(3) ?? '—'}
                  </span>
                ) : i === 0 ? (
                  <span className="text-muted-foreground">—</span>
                ) : (
                  <Badge variant="outline" className="text-xs">
                    N/A
                  </Badge>
                )}
              </TableCell>
              {(['bpm_score', 'harmonic_score', 'energy_score', 'spectral_score', 'groove_score'] as const).map(
                (key) => (
                  <TableCell key={key} className="text-center font-mono text-xs">
                    {item.transition ? (
                      <span className={scoreColor(item.transition[key])}>
                        {item.transition[key]?.toFixed(2) ?? '—'}
                      </span>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                )
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 2: Create set detail page**

```tsx
// panel/app/sets/[id]/page.tsx
import { notFound } from 'next/navigation'
import { SiteHeader } from '@/components/site-header'
import { TransitionTable } from '@/components/transition-table'
import { EnergyArcChart } from '@/components/charts/energy-arc'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getSetDetail, getSetVersionTracks } from '@/lib/queries/sets'
import { formatDuration } from '@/lib/utils'

export const revalidate = 60

export default async function SetDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const set = await getSetDetail(parseInt(id))

  if (!set) notFound()

  // Load tracks for the latest version
  const latestVersion = set.versions[0]
  const tracks = latestVersion
    ? await getSetVersionTracks(latestVersion.id)
    : []

  // Energy arc data
  const energyArcData = tracks
    .filter((t) => t.track.integrated_lufs != null)
    .map((t) => ({
      position: t.sort_index + 1,
      title: t.track.title,
      lufs: t.track.integrated_lufs!,
    }))

  return (
    <>
      <SiteHeader title={set.name} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Header */}
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">{set.name}</CardTitle>
            {set.description && (
              <p className="text-muted-foreground">{set.description}</p>
            )}
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {set.template_name && (
                <Badge variant="secondary">{set.template_name}</Badge>
              )}
              {set.target_bpm_min && set.target_bpm_max && (
                <Badge variant="outline">
                  {set.target_bpm_min}–{set.target_bpm_max} BPM
                </Badge>
              )}
              {set.target_duration_ms && (
                <Badge variant="outline">
                  {formatDuration(set.target_duration_ms)}
                </Badge>
              )}
              {latestVersion?.quality_score != null && (
                <Badge variant="default">
                  Quality: {latestVersion.quality_score.toFixed(3)}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Version tabs */}
        {set.versions.length > 0 && (
          <Tabs defaultValue={String(latestVersion?.id)}>
            <TabsList>
              {set.versions.map((v) => (
                <TabsTrigger key={v.id} value={String(v.id)}>
                  {v.label ?? `v${v.id}`}
                  {v.quality_score != null && (
                    <span className="ml-1 text-xs text-muted-foreground">
                      ({v.quality_score.toFixed(2)})
                    </span>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value={String(latestVersion?.id)}>
              {/* Energy arc */}
              {energyArcData.length > 0 && (
                <Card className="mb-4">
                  <CardHeader>
                    <CardTitle>Energy Arc</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <EnergyArcChart data={energyArcData} />
                  </CardContent>
                </Card>
              )}

              {/* Transition table */}
              <Card>
                <CardHeader>
                  <CardTitle>
                    Tracks & Transitions ({tracks.length} tracks)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <TransitionTable tracks={tracks} />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        )}

        {/* Constraints */}
        {set.constraints.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Constraints</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {set.constraints.map((c, i) => (
                  <Badge key={i} variant="outline">
                    {c.constraint_type}: {JSON.stringify(c.constraint_value)}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
```

- [ ] **Step 3: Verify set detail**

Navigate to `http://localhost:3000/sets/1`. Expected: Set header, energy arc chart, transition table with color-coded scores.

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/components/transition-table.tsx panel/app/sets/\[id\]/
git commit -m "feat(panel): implement set detail page with transition table

Energy arc chart (colored bars by LUFS level).
Transition table with 6 scores, color-coded (green/yellow/red).
Version tabs, constraints display, pinned track indicators."
```

---

### Task 21: Playlists pages

**Files:**
- Create: `panel/app/playlists/page.tsx`
- Create: `panel/app/playlists/[id]/page.tsx`

- [ ] **Step 1: Create playlists list page**

```tsx
// panel/app/playlists/page.tsx
import Link from 'next/link'
import { SiteHeader } from '@/components/site-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getPlaylistList } from '@/lib/queries/playlists'

export const revalidate = 60

export default async function PlaylistsPage() {
  const playlists = await getPlaylistList()

  // Build tree structure
  const roots = playlists.filter((p) => p.parent_id === null)
  const childMap = new Map<number, typeof playlists>()
  for (const p of playlists) {
    if (p.parent_id !== null) {
      const children = childMap.get(p.parent_id) ?? []
      children.push(p)
      childMap.set(p.parent_id, children)
    }
  }

  return (
    <>
      <SiteHeader title="Playlists" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="space-y-2">
          {roots.map((playlist) => (
            <div key={playlist.id}>
              <PlaylistItem playlist={playlist} />
              {childMap.get(playlist.id)?.map((child) => (
                <div key={child.id} className="ml-6">
                  <PlaylistItem playlist={child} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

function PlaylistItem({
  playlist,
}: {
  playlist: { id: number; name: string; trackCount: number; source_of_truth: string | null }
}) {
  return (
    <Link href={`/playlists/${playlist.id}`}>
      <Card className="hover:border-primary transition-colors cursor-pointer">
        <CardContent className="flex items-center justify-between py-3">
          <span className="font-medium">{playlist.name}</span>
          <div className="flex gap-2">
            <Badge variant="outline">{playlist.trackCount} tracks</Badge>
            {playlist.source_of_truth && (
              <Badge variant="secondary">{playlist.source_of_truth}</Badge>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
```

- [ ] **Step 2: Create playlist detail page**

```tsx
// panel/app/playlists/[id]/page.tsx
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { SiteHeader } from '@/components/site-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { MoodBadge } from '@/components/mood-badge'
import { MoodDistributionChart } from '@/components/charts/mood-distribution'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { getPlaylistDetail } from '@/lib/queries/playlists'
import { formatBpm, formatLufs } from '@/lib/utils'

export const revalidate = 60

export default async function PlaylistDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const playlist = await getPlaylistDetail(parseInt(id))

  if (!playlist) notFound()

  return (
    <>
      <SiteHeader title={playlist.name} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Card>
          <CardHeader>
            <CardTitle>{playlist.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {playlist.tracks.length} tracks
              {playlist.source_of_truth &&
                ` · Source: ${playlist.source_of_truth}`}
            </p>
          </CardContent>
        </Card>

        {/* Mood distribution */}
        {playlist.moodCounts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Subgenre Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <MoodDistributionChart data={playlist.moodCounts} />
            </CardContent>
          </Card>
        )}

        {/* Track table */}
        <Card>
          <CardHeader>
            <CardTitle>Tracks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8">#</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Artists</TableHead>
                    <TableHead>BPM</TableHead>
                    <TableHead>Key</TableHead>
                    <TableHead>Mood</TableHead>
                    <TableHead>LUFS</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {playlist.tracks.map((item) => (
                    <TableRow key={item.sort_index}>
                      <TableCell className="text-muted-foreground">
                        {item.sort_index + 1}
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/library/${item.track.id}`}
                          className="hover:underline"
                        >
                          {item.track.title}
                        </Link>
                      </TableCell>
                      <TableCell>{item.track.artists}</TableCell>
                      <TableCell className="font-mono">
                        {formatBpm(item.track.bpm)}
                      </TableCell>
                      <TableCell>{item.track.camelot ?? '—'}</TableCell>
                      <TableCell>
                        <MoodBadge mood={item.track.mood} />
                      </TableCell>
                      <TableCell className="font-mono">
                        {formatLufs(item.track.integrated_lufs)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/app/playlists/
git commit -m "feat(panel): implement playlist pages

List page with hierarchical tree (parent_id nesting).
Detail page with subgenre distribution chart and track table."
```

---

### Task 22: Discover page

**Files:**
- Create: `panel/app/discover/page.tsx`
- Create: `panel/actions/discovery-actions.ts`

- [ ] **Step 1: Create discovery server actions**

```typescript
// panel/actions/discovery-actions.ts
'use server'

import { mcpCall } from '@/lib/mcp-client'
import { revalidateTag } from 'next/cache'

export async function ymSearch(query: string, type: string = 'tracks') {
  const result = await mcpCall('ym_search', { query, type, limit: 20 })
  return result
}

export async function importTracks(trackRefs: string[], playlistId?: number) {
  const result = await mcpCall('import_tracks', {
    track_refs: trackRefs,
    playlist_id: playlistId,
  })
  revalidateTag('tracks')
  revalidateTag('library-stats')
  return result
}

export async function downloadTracks(trackRefs: string[]) {
  const result = await mcpCall('download_tracks', {
    track_refs: trackRefs,
  })
  revalidateTag('tracks')
  revalidateTag('library-stats')
  return result
}
```

- [ ] **Step 2: Create discover page**

```tsx
// panel/app/discover/page.tsx
'use client'

import * as React from 'react'
import { SiteHeader } from '@/components/site-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { ymSearch, importTracks } from '@/actions/discovery-actions'
import { IconSearch, IconDownload } from '@tabler/icons-react'

interface SearchResult {
  id: string | number
  title: string
  artists?: string
  album?: string
  duration_ms?: number
}

export default function DiscoverPage() {
  const [query, setQuery] = React.useState('')
  const [results, setResults] = React.useState<SearchResult[]>([])
  const [loading, setLoading] = React.useState(false)
  const [importing, setImporting] = React.useState<Set<string>>(new Set())

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    try {
      const data = await ymSearch(query)
      // Extract tracks from MCP result
      const tracks =
        (data as { tracks?: SearchResult[] })?.tracks ??
        (Array.isArray(data) ? data : [])
      setResults(tracks)
    } catch (err) {
      toast.error('Search failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleImport(trackId: string) {
    setImporting((prev) => new Set(prev).add(trackId))
    try {
      await importTracks([trackId])
      toast.success('Track imported successfully')
    } catch (err) {
      toast.error('Import failed: ' + (err as Error).message)
    } finally {
      setImporting((prev) => {
        const next = new Set(prev)
        next.delete(trackId)
        return next
      })
    }
  }

  return (
    <>
      <SiteHeader title="Discover" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Card>
          <CardHeader>
            <CardTitle>Search Yandex Music</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSearch} className="flex gap-2">
              <Input
                placeholder="Search tracks, artists, albums..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1"
              />
              <Button type="submit" disabled={loading}>
                <IconSearch className="h-4 w-4 mr-2" />
                Search
              </Button>
            </form>
          </CardContent>
        </Card>

        {loading && (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {!loading && results.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Results ({results.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {results.map((track) => {
                const trackId = String(track.id)
                return (
                  <div
                    key={trackId}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div>
                      <p className="font-medium">{track.title}</p>
                      {track.artists && (
                        <p className="text-sm text-muted-foreground">
                          {track.artists}
                        </p>
                      )}
                      {track.album && (
                        <Badge variant="outline" className="mt-1 text-xs">
                          {track.album}
                        </Badge>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={importing.has(trackId)}
                      onClick={() => handleImport(trackId)}
                    >
                      <IconDownload className="h-4 w-4 mr-1" />
                      {importing.has(trackId) ? 'Importing...' : 'Import'}
                    </Button>
                  </div>
                )
              })}
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/app/discover/ panel/actions/discovery-actions.ts
git commit -m "feat(panel): implement discover page

YM search via MCP Server Action, import tracks with toast feedback.
Client component with loading skeletons and per-track import state."
```

---

## Phase 5: Server Actions (Write Operations)

### Task 23: Set and analysis server actions

**Files:**
- Create: `panel/actions/set-actions.ts`
- Create: `panel/actions/analysis-actions.ts`
- Create: `panel/actions/sync-actions.ts`

- [ ] **Step 1: Create set actions**

```typescript
// panel/actions/set-actions.ts
'use server'

import { revalidateTag } from 'next/cache'
import { mcpCall } from '@/lib/mcp-client'

export async function buildSet(
  playlistId: number,
  name: string,
  template?: string,
  algorithm: 'greedy' | 'ga' = 'ga'
) {
  const result = await mcpCall('build_set', {
    playlist_id: playlistId,
    name,
    template: template ?? undefined,
    algorithm,
  })
  revalidateTag('sets')
  return result
}

export async function rebuildSet(
  setId: number,
  options: {
    pin?: number[]
    unpin?: number[]
    exclude?: number[]
    algorithm?: 'greedy' | 'ga'
    version_label?: string
  } = {}
) {
  const result = await mcpCall('rebuild_set', {
    set_id: setId,
    ...options,
  })
  revalidateTag('sets')
  return result
}

export async function deliverSet(
  setId: number,
  options: {
    version?: number
    copy_files?: boolean
    sync_to_ym?: boolean
    dry_run?: boolean
  } = {}
) {
  const result = await mcpCall('deliver_set', {
    set_id: setId,
    ...options,
  })
  revalidateTag('sets')
  return result
}

export async function scoreTransitions(setId: number) {
  const result = await mcpCall('score_transitions', {
    mode: 'set',
    set_id: setId,
  })
  revalidateTag('sets')
  return result
}
```

- [ ] **Step 2: Create analysis actions**

```typescript
// panel/actions/analysis-actions.ts
'use server'

import { revalidateTag } from 'next/cache'
import { mcpCall } from '@/lib/mcp-client'

export async function classifyMood(trackIds: number[]) {
  const result = await mcpCall('classify_mood', {
    track_ids: trackIds,
  })
  revalidateTag('tracks')
  revalidateTag('library-stats')
  return result
}

export async function analyzeTrack(trackId: number) {
  const result = await mcpCall('analyze_track', {
    track_id: trackId,
  })
  revalidateTag('tracks')
  revalidateTag('library-stats')
  return result
}
```

- [ ] **Step 3: Create sync actions**

```typescript
// panel/actions/sync-actions.ts
'use server'

import { revalidateTag } from 'next/cache'
import { mcpCall } from '@/lib/mcp-client'

export async function syncPlaylist(
  playlistId: number,
  direction?: 'push' | 'pull'
) {
  const result = await mcpCall('sync_playlist', {
    playlist_id: playlistId,
    direction,
  })
  revalidateTag('playlists')
  return result
}

export async function distributeToSubgenres(
  sourcePlaylistId?: number,
  dryRun: boolean = false
) {
  const result = await mcpCall('distribute_to_subgenres', {
    source_playlist_id: sourcePlaylistId,
    dry_run: dryRun,
  })
  revalidateTag('playlists')
  revalidateTag('tracks')
  return result
}

export async function pushSetToYm(setId: number, playlistName?: string) {
  const result = await mcpCall('push_set_to_ym', {
    set_id: setId,
    ym_playlist_name: playlistName,
  })
  revalidateTag('sets')
  return result
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/actions/
git commit -m "feat(panel): add server actions for MCP write operations

Set actions: build, rebuild, deliver, score transitions.
Analysis actions: classify mood, analyze track.
Sync actions: sync playlist, distribute subgenres, push set to YM.
All use mcpCall() + revalidateTag() for cache invalidation."
```

---

## Phase 6: Build Verification and Deployment Config

### Task 24: Next.js config and build verification

**Files:**
- Modify: `panel/next.config.ts`

- [ ] **Step 1: Update next.config.ts**

```typescript
// panel/next.config.ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Server Actions call MCP server — allow external connection
  serverExternalPackages: ['@modelcontextprotocol/sdk'],
}

export default nextConfig
```

- [ ] **Step 2: Run production build**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm run build
```

Expected: Build succeeds. Some pages may show warnings about dynamic data — that's expected for ISR pages.

- [ ] **Step 3: Fix any build errors**

Address TypeScript errors, missing imports, or component issues found during build.

- [ ] **Step 4: Test production build locally**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm start
```

Open `http://localhost:3000`. Verify all pages render.

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add panel/next.config.ts
git commit -m "chore(panel): configure Next.js for production build

serverExternalPackages for MCP SDK compatibility."
```

---

### Task 25: Add panel to .gitignore and root config

**Files:**
- Modify: root `.gitignore` (if panel-specific entries needed)

- [ ] **Step 1: Verify panel .gitignore**

```bash
cat panel/.gitignore
```

Ensure it includes `.env*.local`, `.next/`, `node_modules/`, `out/`.

- [ ] **Step 2: Update root .gitignore if needed**

Add if not already present:

```text
# Panel
panel/.next/
panel/node_modules/
panel/out/
```

- [ ] **Step 3: Final commit**

```bash
cd /Users/laptop/dev/dj-music-plugin
git add .gitignore panel/.gitignore
git commit -m "chore: configure gitignore for panel build artifacts"
```

---

## Phase 7: Final Integration Test

### Task 26: End-to-end smoke test

- [ ] **Step 1: Start MCP HTTP server**

```bash
cd /Users/laptop/dev/dj-music-plugin
uv run uvicorn serve_http:api --host 0.0.0.0 --port 8000 &
```

- [ ] **Step 2: Start Next.js dev server**

```bash
cd /Users/laptop/dev/dj-music-plugin/panel && npm run dev &
```

- [ ] **Step 3: Verify all pages**

Open each page in browser and verify:

| Page | URL | Expected |
|------|-----|----------|
| Dashboard | `/` | Stats cards + 4 charts + coverage |
| Library | `/library` | Track table with data |
| Track detail | `/library/1` | Features tabs, sections |
| Sets | `/sets` | Set cards |
| Set detail | `/sets/1` | Energy arc + transition table |
| Playlists | `/playlists` | Playlist tree |
| Playlist detail | `/playlists/1` | Track table + mood chart |
| Discover | `/discover` | Search form (test search if MCP is running) |

- [ ] **Step 4: Verify MCP actions work**

On the Discover page, search for a track. If MCP server is running, results should appear.

- [ ] **Step 5: Stop servers and document any issues**

Stop both servers. Create issues for anything that didn't work as expected.

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1–8 | MCP HTTP server, Next.js init, deps, layout |
| 2 | 9–12 | Supabase query layer (dashboard, tracks, sets, playlists) |
| 3 | 13–15 | Shared components (badges, cards, charts) |
| 4 | 16–22 | All 8 pages (dashboard, library, track detail, sets, set detail, playlists, playlist detail, discover) |
| 5 | 23 | Server Actions for MCP write operations |
| 6 | 24–25 | Build config and verification |
| 7 | 26 | End-to-end smoke test |

**Total: 26 tasks, ~80 files created**
