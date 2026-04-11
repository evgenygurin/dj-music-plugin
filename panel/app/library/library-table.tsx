'use client'

import { type ColumnDef, type OnChangeFn, type SortingState } from '@tanstack/react-table'
import { Search } from 'lucide-react'
import { IconLoader2, IconPlayerPauseFilled, IconPlayerPlayFilled, IconPlayerSkipForwardFilled } from '@tabler/icons-react'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'
import { startTransition, useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react'

import { loadDjQueue, loadMoreTracks } from '@/actions/library-actions'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import { DataTable } from '@/components/data-table'
import { MoodBadge } from '@/components/mood-badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { TrackRow } from '@/lib/queries/tracks'
import { cn, formatBpm, formatDuration, formatLufs } from '@/lib/utils'

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
const SORTS = [
  { key: 'title', label: 'Title' },
  { key: 'bpm', label: 'BPM' },
  { key: 'energy_mean', label: 'Energy' },
  { key: 'integrated_lufs', label: 'LUFS' },
] as const

function fmt(ms: number | null) { return ms ? formatDuration(ms) : '—' }

/* ── Now Playing sticky card ── */
function NowPlaying({ player }: { player: ReturnType<typeof useAudioPlayer> }) {
  const t = player.current
  if (!t) return null
  const pos = player.position
  const dur = player.duration
  const pct = dur > 0 ? (pos / dur) * 100 : 0

  return (
    <div className="sticky top-0 z-10 -mx-3 px-3 py-2 bg-black/90 backdrop-blur-md border-b border-foreground/5">
      <div className="flex items-center gap-3">
        <Button variant="default" size="icon" className="size-9 shrink-0 rounded-full"
          onClick={() => player.toggle()} aria-label={player.isPlaying ? 'Pause' : 'Play'}>
          {player.isLoading ? <IconLoader2 className="size-4 animate-spin" />
            : player.isPlaying ? <IconPlayerPauseFilled className="size-3.5" />
            : <IconPlayerPlayFilled className="size-3.5" />}
        </Button>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{t.title}</p>
          <div className="flex items-center gap-2 mt-0.5">
            {t.bpm != null && <span className="dj-data text-xs text-foreground/60">{t.bpm.toFixed(0)}</span>}
            {t.camelot && <span className="dj-data text-[10px] text-muted-foreground/30">{t.camelot}</span>}
            {t.mood && <span className="text-[9px] text-muted-foreground/20">{t.mood.replace(/_/g, ' ')}</span>}
          </div>
        </div>

        <Button variant="ghost" size="icon" className="size-8 shrink-0 rounded-full text-foreground/30"
          onClick={() => void player.playRecommendedNext()} aria-label="Next">
          <IconPlayerSkipForwardFilled className="size-3.5" />
        </Button>
      </div>
      {/* Progress */}
      <div className="h-[2px] mt-1.5 bg-foreground/5 rounded-full overflow-hidden">
        <div className="h-full bg-foreground/25" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

/* ── Track card (mobile) ── */
function TrackCard({ track, active, playing, loading, onPlay, onOpen }: {
  track: TrackRow; active: boolean; playing: boolean; loading: boolean
  onPlay: () => void; onOpen: () => void
}) {
  return (
    <div role="button" tabIndex={0}
      className={cn('flex items-center gap-2.5 py-2 px-1 rounded-lg transition-colors',
        active ? 'bg-foreground/[0.06]' : 'active:bg-foreground/[0.03]')}
      onClick={onOpen}
      onKeyDown={e => { if (e.key === 'Enter') onOpen() }}>
      <Button variant={active ? 'default' : 'ghost'} size="icon"
        className="size-9 shrink-0 rounded-full"
        onClick={e => { e.stopPropagation(); onPlay() }}
        aria-label={active && playing ? 'Pause' : 'Play'}>
        {active && loading ? <IconLoader2 className="size-4 animate-spin" />
          : active && playing ? <IconPlayerPauseFilled className="size-3.5" />
          : <IconPlayerPlayFilled className="size-3.5" />}
      </Button>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium leading-tight">{track.title}</p>
        <p className="truncate text-[11px] text-muted-foreground/30">{track.artists || '—'}</p>
      </div>

      {/* BPM big + Key + Mood */}
      <div className="flex items-center gap-1.5 shrink-0">
        {track.bpm != null && <span className="dj-data text-sm text-foreground/60">{track.bpm.toFixed(0)}</span>}
        {track.camelot && <span className="dj-data text-[11px] text-muted-foreground/25">{track.camelot}</span>}
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
        const a = currentId === row.original.id
        return (
          <Button variant={a ? 'default' : 'ghost'} size="icon" className="size-8 rounded-full"
            onClick={e => { e.stopPropagation(); onToggle(row.original) }}>
            {a && isLoading ? <IconLoader2 className="size-4 animate-spin" />
              : a && isPlaying ? <IconPlayerPauseFilled className="size-3.5" />
              : <IconPlayerPlayFilled className="size-3.5" />}
          </Button>
        )
      },
    },
    { accessorKey: 'title', header: 'Title',
      cell: ({ row }) => <div className={cn('max-w-[240px] truncate font-medium', currentId === row.original.id && 'text-foreground')}>{row.original.title}</div>,
    },
    { accessorKey: 'artists', header: 'Artists', enableSorting: false,
      cell: ({ row }) => <div className="max-w-[160px] truncate text-sm text-muted-foreground/50">{row.original.artists || '—'}</div>,
    },
    { accessorKey: 'bpm', header: 'BPM',
      cell: ({ row }) => <span className="dj-data text-sm text-foreground/60">{formatBpm(row.original.bpm)}</span>,
    },
    { accessorKey: 'camelot', header: 'Key', enableSorting: false,
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground/40">{row.original.camelot ?? '—'}</span>,
    },
    { accessorKey: 'mood', header: 'Mood', enableSorting: false,
      cell: ({ row }) => <MoodBadge mood={row.original.mood} />,
    },
    { accessorKey: 'integrated_lufs', header: 'LUFS',
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground/40">{formatLufs(row.original.integrated_lufs)}</span>,
    },
    { accessorKey: 'energy_mean', header: 'Energy',
      cell: ({ row }) => {
        const v = row.original.energy_mean
        if (v === null) return <span className="text-muted-foreground/15">—</span>
        return (
          <div className="flex items-center gap-1.5">
            <div className="h-1 w-10 rounded-full bg-foreground/5 overflow-hidden">
              <div className="h-full bg-foreground/25 rounded-full" style={{ width: `${Math.min(100, v * 100)}%` }} />
            </div>
            <span className="dj-data text-[10px] text-muted-foreground/30">{v.toFixed(2)}</span>
          </div>
        )
      },
    },
    { accessorKey: 'duration_ms', header: 'Dur',
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground/40">{fmt(row.original.duration_ms)}</span>,
    },
  ]
}

/* ── Main ── */
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
    const p = next[0]; nav({ sortBy: p?.id ?? 'title', sortDir: p?.desc ? 'desc' : 'asc' })
  }, [nav, sorting])

  const handleRowClick = (row: TrackRow) => { startTransition(() => { router.push(`/library/${row.id}`) }) }

  return (
    <div className="flex flex-col gap-2">
      {/* Search + count */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground/20" />
          {isPending && <IconLoader2 className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin text-foreground/20" />}
          <Input placeholder="Search..." value={searchInput} onChange={e => setSearchInput(e.target.value)}
            className="h-9 rounded-lg bg-foreground/[0.03] border-foreground/5 pl-9 pr-9 text-sm placeholder:text-muted-foreground/15" />
        </div>
        <span className="dj-data text-[10px] text-muted-foreground/20 shrink-0">{total.toLocaleString()}</span>
      </div>

      {/* Sort chips */}
      <div className="flex items-center gap-1 overflow-x-auto -mx-1 px-1">
        {SORTS.map(s => {
          const active = currentSortBy === s.key
          const desc = active && currentSortDir === 'desc'
          return (
            <button key={s.key} type="button"
              onClick={() => nav({ sortBy: s.key, sortDir: active && !desc ? 'desc' : 'asc' })}
              className={cn('shrink-0 rounded-full px-2.5 py-1 dj-data text-[10px] transition-colors',
                active ? 'bg-foreground/10 text-foreground/70' : 'text-muted-foreground/25 hover:text-muted-foreground/40')}>
              {s.label}{active ? (desc ? ' ↓' : ' ↑') : ''}
            </button>
          )
        })}
        {currentBpmMin != null && currentBpmMax != null && (
          <span className="shrink-0 rounded-full bg-foreground/5 px-2.5 py-1 dj-data text-[10px] text-foreground/40">
            {currentBpmMin}–{currentBpmMax}
          </span>
        )}
        {currentMood && <MoodBadge mood={currentMood} />}
      </div>

      {/* Now Playing sticky (mobile) */}
      <div className="md:hidden">
        <NowPlaying player={player} />
      </div>

      {/* Mobile track list */}
      <div className="flex flex-col md:hidden">
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
      <div ref={sentinelRef} className="flex items-center justify-center py-4">
        {isLoadingMore && <IconLoader2 className="size-4 animate-spin text-foreground/15" />}
        {!hasMore && tracks.length > 0 && (
          <span className="dj-data text-[8px] uppercase tracking-wider text-muted-foreground/10">{total.toLocaleString()} tracks</span>
        )}
      </div>
    </div>
  )
}
