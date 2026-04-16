# App Router Rules (Next.js 16)

## Page Structure

Every route follows this pattern:
```text
panel/app/<route>/
├── page.tsx        # Server component — async, fetches data directly from Supabase
├── loading.tsx     # Skeleton placeholder (Suspense boundary)
├── error.tsx       # Error boundary — must be 'use client'
```

- `page.tsx` — default server component, `async function`, no `'use client'`
- `loading.tsx` — import `*Skeleton` from `@/components/skeletons`
- `error.tsx` — `'use client'`, use `PageError` from `@/components/page-error`

## Server vs Client Components

- **Default: server component** — async, no `'use client'`
- **Client component** (`'use client'`): required for state, effects, event handlers, `useAudioPlayer`
- Do NOT make a component client just because it uses shadcn — shadcn works server-side

## Data Fetching Pattern

```typescript
// page.tsx (server component)
import { getTracks } from '@/lib/queries/tracks'

export default async function TracksPage() {
  const tracks = await getTracks()
  return <TracksTable tracks={tracks} />
}
```

Data fetching always in server component. Never fetch in client components.

## Server Actions (Mutations)

```typescript
// actions/my-action.ts
'use server'
import { mcpCall } from '@/lib/mcp-client'

export async function myAction(args: Record<string, unknown>) {
  return mcpCall('tool_name', args)
}
```

All mutations → `mcpCall()` → REST API → MCP server → DB. Never write to Supabase directly from panel.

## Fonts (4 variables from root layout)

- `--font-geist-sans` — body (local Geist)
- `--font-geist-mono` — monospace (local Geist Mono)
- `--font-instrument-serif` — display headings (Google Instrument Serif)
- `--font-jetbrains-mono` — DJ data (BPM, time, counters)

Use `className="dj-data"` for DJ numeric data (applies JetBrains Mono + tight tracking).

## Navigation

- `<Link href="/path">` for navigation (never `<a>`)
- Active state: `usePathname()` from `next/navigation` (client component only)

## Global Layout Providers (from `layout.tsx`)

- `PlayerProvider` — Web Audio engine context, wraps everything
- `SidebarProvider` + `AppSidebar` — desktop sidebar (`hidden md:contents`)
- `BottomNav` — mobile bottom navigation
- `CommandPalette` — Cmd+K search

## Gotchas

- `SidebarInset` has bottom padding `pb-[calc(8.5rem+env(safe-area-inset-bottom,0px))]` — don't add your own bottom padding to pages
- `<html>` has `className="dark"` and `suppressHydrationWarning` — don't remove either
- `safe-top` / `safe-bottom` utilities: use on mobile full-screen pages for notch/home bar insets
- `Metadata` export only in server components or `layout.tsx` — not in client components
- Theme is dark-only: `defaultTheme="dark" enableSystem={false}` in root layout — no light mode variants

<claude-mem-context>
# Recent Activity

### Apr 6, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #467 | 10:21 PM | 🔄 | Updated root layout with shadcn sidebar CSS variables | ~357 |
| #466 | 10:20 PM | 🔄 | Restructured dashboard page layout with container queries | ~387 |
</claude-mem-context>
