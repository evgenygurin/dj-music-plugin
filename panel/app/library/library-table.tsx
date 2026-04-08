'use client'

import { type ColumnDef } from '@tanstack/react-table'
import { IconLoader2, IconPlayerPauseFilled, IconPlayerPlayFilled } from '@tabler/icons-react'
import { Search } from 'lucide-react'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'

import { loadMoreTracks } from '@/actions/library-actions'
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
  currentPage: number
  currentSearch: string
  currentSortBy: string
  currentSortDir: string
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
  currentPage,
  currentSearch,
}: LibraryTableProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [searchInput, setSearchInput] = useState(currentSearch)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Infinite scroll state ─────────────────────────────────────
  const [tracks, setTracks] = useState<TrackRow[]>(initialTracks)
  const [nextPage, setNextPage] = useState(2)
  const [hasMore, setHasMore] = useState(initialTracks.length < total)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const sentinelRef = useRef<HTMLDivElement | null>(null)

  // Reset when the underlying server query changes (search/sort).
  useEffect(() => {
    setTracks(initialTracks)
    setNextPage(2)
    setHasMore(initialTracks.length < total)
  }, [initialTracks, total])

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return
    setIsLoadingMore(true)
    try {
      const result = await loadMoreTracks({
        page: nextPage,
        pageSize: PAGE_SIZE,
        search: currentSearch || undefined,
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
  }, [isLoadingMore, hasMore, nextPage, currentSearch])

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
      // Whole loaded list is the queue — auto-DJ and prev/next traverse it.
      const queue = tracks.map((t) => ({
        id: t.id,
        title: t.title,
        artists: t.artists,
        durationMs: t.duration_ms,
        bpm: t.bpm,
        camelot: t.camelot,
        mood: t.mood,
      }))
      const meta = queue.find((t) => t.id === row.id)!
      player.toggle(meta, queue)
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
      router.push(`${pathname}?${createQueryString({ search: searchInput, page: '1' })}`)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput, currentSearch])

  const handleRowClick = (row: TrackRow) => {
    router.push(`/library/${row.id}`)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            placeholder="Search tracks..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-9"
          />
        </div>
        <span className="text-sm text-muted-foreground shrink-0">
          {tracks.length.toLocaleString('en-US')} / {total.toLocaleString('en-US')} tracks
        </span>
      </div>

      <DataTable
        columns={columns}
        data={tracks}
        onRowClick={handleRowClick}
      />

      <div ref={sentinelRef} className="flex items-center justify-center py-6">
        {isLoadingMore && (
          <span className="text-sm text-muted-foreground">Загружаю ещё…</span>
        )}
        {!hasMore && tracks.length > 0 && (
          <span className="text-sm text-muted-foreground">
            Это все треки ({total.toLocaleString()})
          </span>
        )}
        {hasMore && !isLoadingMore && (
          <Button variant="outline" size="sm" onClick={() => loadMore()}>
            Загрузить ещё
          </Button>
        )}
      </div>
    </div>
  )
}
