'use client'

import { type ColumnDef, type OnChangeFn, type SortingState } from '@tanstack/react-table'
import { Search } from 'lucide-react'
import { IconLoader2, IconPlayerPauseFilled, IconPlayerPlayFilled } from '@tabler/icons-react'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'
import { startTransition, useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react'

import { loadDjQueue, loadMoreTracks } from '@/actions/library-actions'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import { DataTable } from '@/components/data-table'
import { MoodBadge } from '@/components/mood-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { TrackRow } from '@/lib/queries/tracks'
import { cn, formatBpm, formatDuration, formatLufs } from '@/lib/utils'
import { ANALYSIS_LEVELS } from '@/lib/constants'

interface LibraryTableProps {
  initialTracks: TrackRow[]
  total: number
  currentSearch: string
  currentSortBy: string
  currentSortDir: string
  currentBpmMin?: number
  currentBpmMax?: number
  currentMood?: string
}

const PAGE_SIZE = 50

/* ── Track card (mobile) ── */
function TrackCard({ track, active, playing, loading, onPlay, onOpen }: {
  track: TrackRow; active: boolean; playing: boolean; loading: boolean
  onPlay: () => void; onOpen: () => void
}) {
  return (
    <div
      role="button" tabIndex={0}
      className={cn('flex items-center gap-3 rounded-lg p-2 transition-colors',
        active ? 'bg-foreground/[0.06]' : 'hover:bg-foreground/[0.03]')}
      onClick={onOpen}
      onKeyDown={e => { if (e.key === 'Enter') onOpen() }}
    >
      <Button variant={active ? 'default' : 'ghost'} size="icon"
        className="size-9 shrink-0 rounded-full"
        onClick={e => { e.stopPropagation(); onPlay() }}
        aria-label={active && playing ? 'Pause' : 'Play'}>
        {active && loading ? <IconLoader2 className="size-4 animate-spin" />
          : active && playing ? <IconPlayerPauseFilled className="size-3.5" />
          : <IconPlayerPlayFilled className="size-3.5" />}
      </Button>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{track.title}</p>
        <p className="truncate text-[11px] text-muted-foreground/40">{track.artists || '—'}</p>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        {track.bpm != null && <span className="dj-data text-[11px] text-foreground/50">{track.bpm.toFixed(0)}</span>}
        {track.camelot && <span className="dj-data text-[10px] text-muted-foreground/30">{track.camelot}</span>}
        {track.mood && <MoodBadge mood={track.mood} />}
      </div>
    </div>
  )
}

/* ── Desktop columns ── */
function buildColumns(currentId: number | null, isPlaying: boolean, isLoading: boolean, onToggle: (r: TrackRow) => void): ColumnDef<TrackRow>[] {
  return [
    { id: 'play', header: '', enableSorting: false,
      cell: ({ row }) => {
        const active = currentId === row.original.id
        return (
          <Button variant={active ? 'default' : 'ghost'} size="icon"
            className={cn('size-8 rounded-full', active && 'shadow-md shadow-foreground/10')}
            onClick={e => { e.stopPropagation(); onToggle(row.original) }}
            aria-label={active && isPlaying ? 'Pause' : 'Play'}>
            {active && isLoading ? <IconLoader2 className="size-4 animate-spin" />
              : active && isPlaying ? <IconPlayerPauseFilled className="size-3.5" />
              : <IconPlayerPlayFilled className="size-3.5" />}
          </Button>
        )
      },
    },
    { accessorKey: 'title', header: 'Title',
      cell: ({ row }) => <div className={cn('max-w-[240px] truncate font-medium', currentId === row.original.id && 'text-foreground')}>{row.original.title}</div>,
    },
    { accessorKey: 'artists', header: 'Artists', enableSorting: false,
      cell: ({ row }) => <div className="max-w-[180px] truncate text-sm text-muted-foreground">{row.original.artists || '—'}</div>,
    },
    { accessorKey: 'bpm', header: 'BPM',
      cell: ({ row }) => <span className="dj-data text-sm text-foreground/70">{formatBpm(row.original.bpm)}</span>,
    },
    { accessorKey: 'camelot', header: 'Key', enableSorting: false,
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground/60">{row.original.camelot ?? '—'}</span>,
    },
    { accessorKey: 'mood', header: 'Mood', enableSorting: false,
      cell: ({ row }) => <MoodBadge mood={row.original.mood} />,
    },
    { accessorKey: 'integrated_lufs', header: 'LUFS',
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground">{formatLufs(row.original.integrated_lufs)}</span>,
    },
    { accessorKey: 'energy_mean', header: 'Energy',
      cell: ({ row }) => {
        const v = row.original.energy_mean
        if (v === null) return <span className="text-muted-foreground/20">—</span>
        return (
          <div className="flex items-center gap-1.5">
            <div className="h-1 w-10 rounded-full bg-muted/20 overflow-hidden">
              <div className="h-full bg-foreground/30 rounded-full" style={{ width: `${Math.min(100, v * 100)}%` }} />
            </div>
            <span className="dj-data text-[10px] text-muted-foreground/40">{v.toFixed(2)}</span>
          </div>
        )
      },
    },
    { accessorKey: 'duration_ms', header: 'Dur',
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground">{row.original.duration_ms ? formatDuration(row.original.duration_ms) : '—'}</span>,
    },
  ]
}

/* ── Main component ── */
export function LibraryTable({ initialTracks, total, currentSearch, currentSortBy, currentSortDir, currentBpmMin, currentBpmMax, currentMood }: LibraryTableProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [searchInput, setSearchInput] = useState(currentSearch)
  const [isPending, startNavigation] = useTransition()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [tracks, setTracks] = useState<TrackRow[]>(initialTracks)
  const [nextPage, setNextPage] = useState(2)
  const [hasMore, setHasMore] = useState(initialTracks.length < total)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const sorting = useMemo<SortingState>(() => [{ id: currentSortBy, desc: currentSortDir === 'desc' }], [currentSortBy, currentSortDir])

  useEffect(() => { setTracks(initialTracks); setNextPage(2); setHasMore(initialTracks.length < total) }, [initialTracks, total])
  useEffect(() => { setSearchInput(currentSearch) }, [currentSearch])

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return
    setIsLoadingMore(true)
    try {
      const r = await loadMoreTracks({ page: nextPage, pageSize: PAGE_SIZE, search: currentSearch || undefined,
        sortBy: currentSortBy as any, sortDir: currentSortDir as any, bpmMin: currentBpmMin, bpmMax: currentBpmMax, mood: currentMood })
      setTracks(prev => { const seen = new Set(prev.map(t => t.id)); return [...prev, ...r.tracks.filter(t => !seen.has(t.id))] })
      setNextPage(p => p + 1); setHasMore(r.hasMore)
    } finally { setIsLoadingMore(false) }
  }, [currentBpmMax, currentBpmMin, currentMood, currentSearch, currentSortBy, currentSortDir, hasMore, isLoadingMore, nextPage])

  useEffect(() => {
    const node = sentinelRef.current; if (!node) return
    const io = new IntersectionObserver(entries => { if (entries[0]?.isIntersecting) loadMore() }, { rootMargin: '600px' })
    io.observe(node); return () => io.disconnect()
  }, [loadMore])

  const player = useAudioPlayer()
  const activeId = player.current?.id ?? null

  const handleToggle = useCallback((row: TrackRow) => {
    const meta = { id: row.id, title: row.title, artists: row.artists, durationMs: row.duration_ms, bpm: row.bpm, camelot: row.camelot, mood: row.mood }
    const queue = tracks.map(t => ({ id: t.id, title: t.title, artists: t.artists, durationMs: t.duration_ms, bpm: t.bpm, camelot: t.camelot, mood: t.mood }))
    player.toggle(meta, queue)
    if (row.bpm) {
      void loadDjQueue(row.bpm).then(dj => {
        if (dj.length > 0) {
          const expanded = dj.map(t => ({ id: t.id, title: t.title, artists: t.artists, durationMs: t.duration_ms, bpm: t.bpm, camelot: t.camelot, mood: t.mood }))
          const ids = new Set(queue.map(t => t.id))
          player.setQueue([...queue, ...expanded.filter(t => !ids.has(t.id))])
        }
      })
    }
  }, [player, tracks])

  const columns = buildColumns(activeId, player.isPlaying, player.isLoading, handleToggle)

  const createQS = useCallback((updates: Record<string, string | undefined>) => {
    const p = new URLSearchParams(searchParams.toString())
    for (const [k, v] of Object.entries(updates)) { v === undefined || v === '' ? p.delete(k) : p.set(k, v) }
    return p.toString()
  }, [searchParams])

  const nav = useCallback((updates: Record<string, string | undefined>) => {
    startNavigation(() => { router.push(`${pathname}?${createQS({ ...updates, page: '1' })}`) })
  }, [createQS, pathname, router, startNavigation])

  useEffect(() => {
    if (searchInput === currentSearch) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => nav({ search: searchInput }), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [currentSearch, nav, searchInput])

  const handleSort = useCallback<OnChangeFn<SortingState>>(updater => {
    const next = typeof updater === 'function' ? updater(sorting) : updater
    const primary = next[0]; nav({ sortBy: primary?.id ?? 'title', sortDir: primary?.desc ? 'desc' : 'asc' })
  }, [nav, sorting])

  const handleRowClick = (row: TrackRow) => { startTransition(() => { router.push(`/library/${row.id}`) }) }

  return (
    <div className="flex flex-col gap-3">
      {/* Search bar */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground/30" />
          {isPending && <IconLoader2 className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin text-foreground/30" />}
          <Input placeholder="Search..." value={searchInput} onChange={e => setSearchInput(e.target.value)}
            className="h-9 rounded-lg bg-foreground/[0.03] border-foreground/5 pl-9 pr-9 text-sm placeholder:text-muted-foreground/20" />
        </div>
        <span className="dj-data text-[10px] text-muted-foreground/25 shrink-0">
          {tracks.length}<span className="text-muted-foreground/10"> / </span>{total.toLocaleString()}
        </span>
      </div>

      {/* Mobile track list */}
      <div className="flex flex-col gap-0.5 md:hidden">
        {tracks.map(track => (
          <TrackCard key={track.id} track={track} active={activeId === track.id}
            playing={player.isPlaying} loading={player.isLoading}
            onPlay={() => handleToggle(track)} onOpen={() => handleRowClick(track)} />
        ))}
      </div>

      {/* Desktop table */}
      <div className="hidden md:block rounded-lg border border-foreground/5 overflow-hidden">
        <DataTable columns={columns} data={tracks} onRowClick={handleRowClick}
          sorting={sorting} onSortingChange={handleSort} manualSorting />
      </div>

      {/* Load more */}
      <div ref={sentinelRef} className="flex items-center justify-center py-6">
        {isLoadingMore && <IconLoader2 className="size-4 animate-spin text-foreground/20" />}
        {!hasMore && tracks.length > 0 && (
          <span className="dj-data text-[9px] uppercase tracking-wider text-muted-foreground/15">
            {total.toLocaleString()} tracks
          </span>
        )}
      </div>
    </div>
  )
}
