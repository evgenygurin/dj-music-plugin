# Component Patterns

## Directory Layout

```bash
panel/components/
├── ui/                        # shadcn/ui primitives — do NOT edit directly
├── charts/                    # Recharts visualizations (BpmDistribution, KeyDistribution, etc.)
├── audio-player/              # Web Audio engine — see audio-player/CLAUDE.md
├── player/                    # Player UI (TrackWaveform, TransitionVisualizer, etc.)
├── page-shell.tsx             # Standard page wrapper with title + optional action slot
├── page-error.tsx             # Error boundary UI (used in error.tsx files)
├── skeletons.tsx              # Loading skeletons for all pages
├── data-table.tsx             # TanStack Table v8 generic data table
├── mood-badge.tsx             # Colored badge for mood classification
├── track-features.tsx         # Feature display card
└── ...                        # Other domain components
```

## Page Composition Pattern

```tsx
// In page.tsx (server component)
import { PageShell } from '@/components/page-shell'

export default async function MyPage() {
  return (
    <PageShell title="Library" action={<ActionButton />}>
      <MyContent />
    </PageShell>
  )
}
```

## Error Boundary (`error.tsx`)

```tsx
'use client'
import { PageError } from '@/components/page-error'

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return <PageError error={error} onReset={reset} />
}
```

## Skeletons (`loading.tsx`)

```tsx
import { LibrarySkeleton } from '@/components/skeletons'
export default function Loading() { return <LibrarySkeleton /> }
```

Each page has a matching skeleton variant in `skeletons.tsx`.

## shadcn/ui

- **Install**: `bunx shadcn@latest add <component>` — adds to `components/ui/`
- **Never edit** `components/ui/` files — re-run `add` to update
- **Icons**: use `@tabler/icons-react` (NOT lucide) for custom icons
  - Exception: shadcn internal icons use lucide — leave them as-is

## Cyberpunk Theme Tokens

Dark mode only. Key CSS variables (defined in `globals.css`):
- `--primary` — magenta (`oklch(0.7 0.25 320)`)
- `--chart-1` through `--chart-5` — neon: magenta, cyan, green, yellow, purple

Charts use `fill="var(--chart-N)"` or Recharts `stroke="var(--chart-N)"`.

## `dj-data` CSS Class

Custom utility (JetBrains Mono + tight tracking). Use on all DJ numeric data:
```tsx
<span className="dj-data text-[12px] text-foreground/50">{bpm}</span>
```

Apply to: BPM values, LUFS meters, time displays, counters, status codes.

## Data Table

```tsx
import { DataTable } from '@/components/data-table'

<DataTable columns={columns} data={rows} />
```

Uses TanStack Table v8 (`useReactTable`). Always a client component.

## Charts (Recharts)

5 chart components in `components/charts/`:
- `BpmDistributionChart`, `KeyDistributionChart`, `EnergyHeatmap`, `SubgenreChart`, `MoodChart`
- All client components with `'use client'`
- Gradients defined via `<defs><linearGradient>` inside chart components

## Gotchas

- `audio-player-context.tsx` is ~2000 LOC with dual-deck Web Audio engine — read `audio-player/CLAUDE.md` before touching it
- `player-provider.tsx` wraps the context for React context injection — use `useAudioPlayer()` hook in components
- Fast Refresh: `audio-player-context.tsx` exports both components AND hooks — types must live in `audio-player-types.ts`
- `data-table.tsx` is generic — `columns` prop must match TanStack `ColumnDef<T>[]` type
- `app-sidebar.tsx` uses `offcanvas` collapsible behavior (not `icon` mode)
- `SectionCards` follows shadcn dashboard-01 pattern — use as reference for new dashboard cards

<claude-mem-context>
# Recent Activity

### Apr 6, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #468 | 10:21 PM | 🔄 | Finalized AppSidebar with offcanvas collapsible behavior | ~362 |
| #465 | 10:20 PM | 🔄 | Refactored SectionCards to shadcn dashboard-01 pattern | ~439 |
| #464 | 10:19 PM | 🔄 | Refactored SiteHeader to match shadcn/ui dashboard-01 pattern | ~348 |
</claude-mem-context>
