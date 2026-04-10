'use client'

import { type ColumnDef, type OnChangeFn, type SortingState } from '@tanstack/react-table'
import { IconLoader2, IconPlayerPauseFilled, IconPlayerPlayFilled } from '@tabler/icons-react'
import { Search } from 'lucide-react'
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
import { formatBpm, formatDuration, formatLufs } from '@/lib/utils'
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

function buildColumns(
  currentId: number | null,
  isPlaying: boolean,
  isLoading: boolean,
  onToggle: (row: TrackRow) => void,
): ColumnDef<TrackRow>[] {
  return [
  {
    id: 'play',
    header: '',
    cell: ({ row }) => {
      const id = row.original.id
      const active = currentId === id
      const showSpinner = active && isLoading
      const showPause = active && isPlaying && !isLoading
      return (
        <Button
          variant={active ? 'default' : 'ghost'}
          size="icon"
          className="h-7 w-7 rounded-full"
          onClick={(e) => {
            e.stopPropagation()
            onToggle(row.original)
          }}
          aria-label={showPause ? 'Pause' : 'Play'}
        >
          {showSpinner ? (
            <IconLoader2 className="h-4 w-4 animate-spin" />
          ) : showPause ? (
            <IconPlayerPauseFilled className="h-3.5 w-3.5" />
          ) : (
            <IconPlayerPlayFilled className="h-3.5 w-3.5" />
          )}
        </Button>
      )
    },
    enableSorting: false,
  },
  {
    accessorKey: 'id',
    header: '#',
    cell: ({ row }) => <span className="text-muted-foreground text-xs">{row.original.id}</span>,
    enableSorting: false,
  },
  {
    accessorKey: 'title',
    header: 'Title',
    cell: ({ row }) => (
      <div className="max-w-[240px] truncate font-medium">{row.original.title}</div>
    ),
  },
  {
    accessorKey: 'artists',
    header: 'Artists',
    cell: ({ row }) => (
      <div className="max-w-[180px] truncate text-sm text-muted-foreground">
        {row.original.artists || '—'}
      </div>
    ),
    enableSorting: false,
  },
  {
    accessorKey: 'bpm',
    header: 'BPM',
    cell: ({ row }) => (
      <span className="tabular-nums text-sm">{formatBpm(row.original.bpm)}</span>
    ),
  },
  {
    accessorKey: 'camelot',
    header: 'Key',
    cell: ({ row }) => (
      <span className="text-sm font-mono">{row.original.camelot ?? '—'}</span>
    ),
    enableSorting: false,
  },
  {
    accessorKey: 'mood',
    header: 'Mood',
    cell: ({ row }) => <MoodBadge mood={row.original.mood} />,
    enableSorting: false,
  },
  {
    accessorKey: 'integrated_lufs',
    header: 'LUFS',
    cell: ({ row }) => (
      <span className="tabular-nums text-sm">{formatLufs(row.original.integrated_lufs)}</span>
    ),
  },
  {
    accessorKey: 'energy_mean',
    header: 'Energy',
    cell: ({ row }) => (
      <span className="tabular-nums text-sm">
        {row.original.energy_mean !== null ? row.original.energy_mean.toFixed(3) : '—'}
      </span>
    ),
  },
  {
    accessorKey: 'duration_ms',
    header: 'Duration',
    cell: ({ row }) => (
      <span className="tabular-nums text-sm">
        {row.original.duration_ms !== null ? formatDuration(row.original.duration_ms) : '—'}
      </span>
    ),
  },
  {
    accessorKey: 'analysis_level',
    header: 'Analysis',
    cell: ({ row }) => {
      const level = row.original.analysis_level
      const label = level !== null ? (ANALYSIS_LEVELS[level] ?? `L${level}`) : 'None'
      return <Badge variant="secondary" className="text-xs">{label}</Badge>
    },
    enableSorting: false,
  },
  {
    accessorKey: 'mood_confidence',
    header: 'Conf',
    cell: ({ row }) => (
      <span className="tabular-nums text-sm text-muted-foreground">
        {row.original.mood_confidence !== null
          ? `${(row.original.mood_confidence * 100).toFixed(0)}%`
          : '—'}
      </span>
    ),
  },
  ]
}

const PAGE_SIZE = 50

export function LibraryTable({
  initialTracks,
  total,
  currentSearch,
  currentSortBy,
  currentSortDir,
  currentBpmMin,
  currentBpmMax,
  currentMood,
}: LibraryTableProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [searchInput, setSearchInput] = useState(currentSearch)
  const [isPending, startNavigation] = useTransition()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Infinite scroll state ─────────────────────────────────────
  const [tracks, setTracks] = useState<TrackRow[]>(initialTracks)
  const [nextPage, setNextPage] = useState(2)
  const [hasMore, setHasMore] = useState(initialTracks.length < total)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const sorting = useMemo<SortingState>(
    () => [{ id: currentSortBy, desc: currentSortDir === 'desc' }],
    [currentSortBy, currentSortDir]
  )

  // Reset when the underlying server query changes (search/sort).
  useEffect(() => {
    setTracks(initialTracks)
    setNextPage(2)
    setHasMore(initialTracks.length < total)
  }, [initialTracks, total])

  useEffect(() => {
    setSearchInput(currentSearch)
  }, [currentSearch])

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return
    setIsLoadingMore(true)
    try {
      const result = await loadMoreTracks({
        page: nextPage,
        pageSize: PAGE_SIZE,
        search: currentSearch || undefined,
        sortBy: currentSortBy as 'title' | 'bpm' | 'integrated_lufs' | 'energy_mean' | 'duration_ms' | 'mood_confidence',
        sortDir: currentSortDir as 'asc' | 'desc',
        bpmMin: currentBpmMin,
        bpmMax: currentBpmMax,
        mood: currentMood,
      })
      setTracks((prev) => {
        // Dedupe just in case the user toggled filters mid-flight.
        const seen = new Set(prev.map((t) => t.id))
        const merged = [...prev]
        for (const t of result.tracks) {
          if (!seen.has(t.id)) merged.push(t)
        }
        return merged
      })
      setNextPage((p) => p + 1)
      setHasMore(result.hasMore)
    } finally {
      setIsLoadingMore(false)
    }
  }, [
    currentBpmMax,
    currentBpmMin,
    currentMood,
    currentSearch,
    currentSortBy,
    currentSortDir,
    hasMore,
    isLoadingMore,
    nextPage,
  ])

  // IntersectionObserver-driven auto-load when sentinel scrolls into view.
  useEffect(() => {
    const node = sentinelRef.current
    if (!node) return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) loadMore()
      },
      { rootMargin: '600px' },
    )
    io.observe(node)
    return () => io.disconnect()
  }, [loadMore])

  const player = useAudioPlayer()

  const handleTogglePlay = useCallback(
    (row: TrackRow) => {
      const meta = {
        id: row.id,
        title: row.title,
        artists: row.artists,
        durationMs: row.duration_ms,
        bpm: row.bpm,
        camelot: row.camelot,
        mood: row.mood,
      }
      // Start with visible tracks as queue, then async-expand with
      // 500 BPM-compatible tracks for auto-DJ to pick from.
      const visibleQueue = tracks.map((t) => ({
        id: t.id, title: t.title, artists: t.artists,
        durationMs: t.duration_ms, bpm: t.bpm,
        camelot: t.camelot, mood: t.mood,
      }))
      player.toggle(meta, visibleQueue)

      // Background: load 500 tracks with ±5 BPM for better auto-DJ pool.
      // Uses setQueue to expand without restarting playback.
      if (row.bpm) {
        void loadDjQueue(row.bpm).then((djTracks) => {
          if (djTracks.length > 0) {
            const expanded = djTracks.map((t) => ({
              id: t.id, title: t.title, artists: t.artists,
              durationMs: t.duration_ms, bpm: t.bpm,
              camelot: t.camelot, mood: t.mood,
            }))
            const ids = new Set(visibleQueue.map((t) => t.id))
            const merged = [...visibleQueue, ...expanded.filter((t) => !ids.has(t.id))]
            player.setQueue(merged)
          }
        })
      }
    },
    [player, tracks],
  )

  const columns = buildColumns(
    player.current?.id ?? null,
    player.isPlaying,
    player.isLoading,
    handleTogglePlay,
  )

  const createQueryString = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString())
      for (const [key, value] of Object.entries(updates)) {
        if (value === undefined || value === '') {
          params.delete(key)
        } else {
          params.set(key, value)
        }
      }
      return params.toString()
    },
    [searchParams]
  )

  // Search edits trigger a fresh server-side query (resets scroll).
  useEffect(() => {
    if (searchInput === currentSearch) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      startNavigation(() => {
        router.push(`${pathname}?${createQueryString({ search: searchInput, page: '1' })}`)
      })
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [createQueryString, currentSearch, pathname, router, searchInput, startNavigation])

  const handleSortingChange = useCallback<OnChangeFn<SortingState>>(
    (updater) => {
      const nextSorting = typeof updater === 'function' ? updater(sorting) : updater
      const primary = nextSorting[0]
      const sortBy = primary?.id ?? 'title'
      const sortDir = primary?.desc ? 'desc' : 'asc'

      startTransition(() => {
        router.push(
          `${pathname}?${createQueryString({
            sortBy,
            sortDir,
            page: '1',
          })}`
        )
      })
    },
    [createQueryString, pathname, router, sorting]
  )

  const handleRowClick = (row: TrackRow) => {
    startTransition(() => {
      router.push(`/library/${row.id}`)
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          {isPending ? (
            <IconLoader2 className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
          ) : null}
          <Input
            aria-label="Search tracks"
            autoComplete="off"
            name="track-search"
            placeholder="Search Tracks…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-9 pr-9"
          />
        </div>
        <span className="text-sm text-muted-foreground shrink-0">
          {tracks.length.toLocaleString()} / {total.toLocaleString()} tracks
        </span>
      </div>

      <DataTable
        columns={columns}
        data={tracks}
        onRowClick={handleRowClick}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        manualSorting
      />

      <div ref={sentinelRef} className="flex items-center justify-center py-6">
        {isLoadingMore && (
          <span className="text-sm text-muted-foreground">Loading More…</span>
        )}
        {!hasMore && tracks.length > 0 && (
          <span className="text-sm text-muted-foreground">
            That’s the Full Library ({total.toLocaleString()})
          </span>
        )}
        {hasMore && !isLoadingMore && (
          <Button variant="outline" size="sm" onClick={() => loadMore()}>
            Load More
          </Button>
        )}
      </div>
    </div>
  )
}
