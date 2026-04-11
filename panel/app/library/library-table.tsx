'use client'

import { type ColumnDef, type OnChangeFn, type SortingState } from '@tanstack/react-table'
import { Activity, Compass, Gauge, Search, Zap } from 'lucide-react'
import { IconLoader2, IconPlayerPauseFilled, IconPlayerPlayFilled } from '@tabler/icons-react'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'
import { startTransition, useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react'

import { loadDjQueue, loadMoreTracks } from '@/actions/library-actions'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import { DataTable } from '@/components/data-table'
import { MoodBadge } from '@/components/mood-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupText,
} from '@/components/ui/input-group'
import { Separator } from '@/components/ui/separator'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import type { TrackRow } from '@/lib/queries/tracks'
import { cn } from '@/lib/utils'
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

type SortBy = 'title' | 'bpm' | 'integrated_lufs' | 'energy_mean' | 'duration_ms' | 'mood_confidence'
type SortDir = 'asc' | 'desc'

const SORT_BY_OPTIONS: ReadonlyArray<{ value: SortBy; label: string }> = [
  { value: 'title', label: 'Title' },
  { value: 'bpm', label: 'BPM' },
  { value: 'energy_mean', label: 'Energy' },
  { value: 'integrated_lufs', label: 'LUFS' },
  { value: 'duration_ms', label: 'Duration' },
]

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
            className={cn('size-8 rounded-full', active && 'shadow-md shadow-foreground/15')}
            onClick={(e) => {
              e.stopPropagation()
              onToggle(row.original)
            }}
            aria-label={showPause ? 'Pause' : 'Play'}
          >
            {showSpinner ? (
              <IconLoader2 className="animate-spin" />
            ) : showPause ? (
              <IconPlayerPauseFilled />
            ) : (
              <IconPlayerPlayFilled />
            )}
          </Button>
        )
      },
      enableSorting: false,
    },
    {
      accessorKey: 'title',
      header: 'Title',
      cell: ({ row }) => {
        const active = currentId === row.original.id
        return (
          <div className={cn('max-w-[240px] truncate font-medium', active && 'text-foreground')}>
            {row.original.title}
          </div>
        )
      },
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
      cell: ({ row }) => <span className="dj-data text-sm text-foreground/80">{formatBpm(row.original.bpm)}</span>,
    },
    {
      accessorKey: 'camelot',
      header: 'Key',
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground/80">{row.original.camelot ?? '—'}</span>,
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
      cell: ({ row }) => <span className="dj-data text-sm text-muted-foreground">{formatLufs(row.original.integrated_lufs)}</span>,
    },
    {
      accessorKey: 'energy_mean',
      header: 'Energy',
      cell: ({ row }) => {
        const val = row.original.energy_mean
        if (val === null) return <span className="text-sm text-muted-foreground/40">—</span>
        const pct = Math.min(100, val * 100)
        return (
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-12 overflow-hidden rounded-full bg-muted/30">
              <div className="h-full rounded-full bg-foreground/40" style={{ width: `${pct}%` }} />
            </div>
            <span className="dj-data text-[11px] text-muted-foreground">{val.toFixed(2)}</span>
          </div>
        )
      },
    },
    {
      accessorKey: 'duration_ms',
      header: 'Dur',
      cell: ({ row }) => (
        <span className="dj-data text-sm text-muted-foreground">
          {row.original.duration_ms !== null ? formatDuration(row.original.duration_ms) : '—'}
        </span>
      ),
    },
    {
      accessorKey: 'analysis_level',
      header: 'LVL',
      cell: ({ row }) => {
        const level = row.original.analysis_level
        const label = level !== null ? (ANALYSIS_LEVELS[level] ?? `L${level}`) : '—'
        return <span className="dj-data text-[11px] text-muted-foreground/60">{label}</span>
      },
      enableSorting: false,
    },
  ]
}

const PAGE_SIZE = 50
const ENERGY_ARC_STOPS = 20

function formatStyle(style: string | null): string {
  if (!style) return 'pending'
  return style.replaceAll('_', ' ')
}

function EnergyArcStrip({
  points,
  activeValue,
}: {
  points: number[]
  activeValue: number | null
}) {
  if (points.length < 2) {
    return (
      <div className="rounded-xl border border-border/40 bg-muted/20 px-3 py-2">
        <p className="text-xs text-muted-foreground">Energy arc appears after more tracks are loaded.</p>
      </div>
    )
  }

  const width = 100
  const height = 28
  const minY = 4
  const maxY = height - 4
  const toY = (value: number) => {
    const clamped = Math.max(0, Math.min(1, value))
    return maxY - clamped * (maxY - minY)
  }

  const curve = points
    .map((value, index) => {
      const x = (index / (points.length - 1)) * width
      return `${x},${toY(value)}`
    })
    .join(' ')

  const activeY = activeValue !== null ? toY(activeValue) : null

  return (
    <div className="rounded-2xl border border-border/40 bg-muted/20 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="dj-data text-[10px] uppercase tracking-[0.24em] text-muted-foreground/70">Energy Arc</span>
        <span className="dj-data text-[11px] text-foreground/70">
          Live {activeValue !== null ? activeValue.toFixed(2) : '—'}
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-11 w-full">
        <defs>
          <linearGradient id="library-energy" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.18" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.65" />
          </linearGradient>
        </defs>
        <polyline fill="none" stroke="url(#library-energy)" strokeWidth="2.2" strokeLinecap="round" points={curve} />
        {activeY !== null ? <circle cx={width - 2} cy={activeY} r="2.1" fill="currentColor" opacity="0.9" /> : null}
      </svg>
    </div>
  )
}

function MobileTrackCard({
  track,
  isActive,
  isLoading,
  isPlaying,
  onToggle,
  onOpen,
}: {
  track: TrackRow
  isActive: boolean
  isLoading: boolean
  isPlaying: boolean
  onToggle: (row: TrackRow) => void
  onOpen: (row: TrackRow) => void
}) {
  const showSpinner = isActive && isLoading
  const showPause = isActive && isPlaying && !isLoading

  return (
    <div
      role="button"
      tabIndex={0}
      className={cn(
        'rounded-xl border p-2.5 transition-colors',
        isActive
          ? 'border-foreground/30 bg-card'
          : 'border-border/40 bg-card/70 hover:border-border hover:bg-card',
      )}
      onClick={() => onOpen(track)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(track)
        }
      }}
      aria-label={`Open ${track.title}`}
    >
      <div className="flex items-start gap-3">
        <Button
          variant={isActive ? 'default' : 'outline'}
          size="icon"
          className="size-10 rounded-full"
          onClick={(event) => {
            event.stopPropagation()
            onToggle(track)
          }}
          aria-label={showPause ? 'Pause' : 'Play'}
        >
          {showSpinner ? (
            <IconLoader2 className="animate-spin" />
          ) : showPause ? (
            <IconPlayerPauseFilled />
          ) : (
            <IconPlayerPlayFilled />
          )}
        </Button>
        <div className="min-w-0 flex-1">
          <p className={cn('truncate text-sm font-medium', isActive && 'text-foreground')}>{track.title}</p>
          <p className="truncate text-xs text-muted-foreground">{track.artists || '—'}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <Badge variant="secondary" className="dj-data text-[10px]">
              {formatBpm(track.bpm)} BPM
            </Badge>
            <Badge variant="outline" className="dj-data text-[10px]">
              {track.camelot ?? '—'}
            </Badge>
            <Badge variant="outline" className="dj-data text-[10px]">
              {formatLufs(track.integrated_lufs)}
            </Badge>
            <Badge variant="outline" className="dj-data text-[10px]">
              {track.duration_ms !== null ? formatDuration(track.duration_ms) : '—'}
            </Badge>
            {track.mood ? <MoodBadge mood={track.mood} /> : null}
          </div>
        </div>
      </div>
    </div>
  )
}

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

  const [tracks, setTracks] = useState<TrackRow[]>(initialTracks)
  const [nextPage, setNextPage] = useState(2)
  const [hasMore, setHasMore] = useState(initialTracks.length < total)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const sorting = useMemo<SortingState>(
    () => [{ id: currentSortBy, desc: currentSortDir === 'desc' }],
    [currentSortBy, currentSortDir]
  )

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
  const activeTrackId = player.current?.id ?? null
  const activeTransitionStyle = player.lastResolvedStyle ?? player.recommendedStyle
  const activeTrackEnergy = useMemo(
    () => tracks.find((track) => track.id === activeTrackId)?.energy_mean ?? null,
    [activeTrackId, tracks],
  )
  const energyPoints = useMemo(
    () =>
      tracks
        .filter((track) => track.energy_mean !== null)
        .slice(0, ENERGY_ARC_STOPS)
        .map((track) => Number(track.energy_mean ?? 0)),
    [tracks],
  )

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
      const visibleQueue = tracks.map((t) => ({
        id: t.id, title: t.title, artists: t.artists,
        durationMs: t.duration_ms, bpm: t.bpm,
        camelot: t.camelot, mood: t.mood,
      }))
      player.toggle(meta, visibleQueue)

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
    activeTrackId,
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

  const navigateWithParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      startNavigation(() => {
        router.push(`${pathname}?${createQueryString({ ...updates, page: '1' })}`)
      })
    },
    [createQueryString, pathname, router, startNavigation],
  )

  useEffect(() => {
    if (searchInput === currentSearch) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigateWithParams({ search: searchInput })
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [currentSearch, navigateWithParams, searchInput])

  const handleSortingChange = useCallback<OnChangeFn<SortingState>>(
    (updater) => {
      const nextSorting = typeof updater === 'function' ? updater(sorting) : updater
      const primary = nextSorting[0]
      const sortBy = primary?.id ?? 'title'
      const sortDir = primary?.desc ? 'desc' : 'asc'

      startTransition(() => {
        navigateWithParams({
          sortBy,
          sortDir,
        })
      })
    },
    [navigateWithParams, sorting]
  )

  const handleRowClick = (row: TrackRow) => {
    startTransition(() => {
      router.push(`/library/${row.id}`)
    })
  }

  const handleSortByChange = useCallback(
    (values: string[]) => {
      const value = values[0]
      if (!value) return
      navigateWithParams({ sortBy: value })
    },
    [navigateWithParams],
  )

  const handleSortDirChange = useCallback(
    (values: string[]) => {
      const value = values[0]
      if (!value) return
      navigateWithParams({ sortDir: value })
    },
    [navigateWithParams],
  )

  return (
    <div className="flex flex-col gap-4">
      <Card className="relative overflow-hidden border-border/40 bg-card/85 py-0">
        <div className="pointer-events-none absolute inset-0 text-foreground/70 [background:radial-gradient(circle_at_top,currentColor,transparent_60%)] opacity-10" />
        <CardHeader className="relative border-b border-border/30 pb-4">
          <CardTitle className="display-heading text-2xl tracking-tight">Library Deck</CardTitle>
          <CardDescription className="dj-data text-[10px] uppercase tracking-[0.26em] text-muted-foreground/80">
            Luxury Techno Control Surface
          </CardDescription>
        </CardHeader>
        <CardContent className="relative flex flex-col gap-4 pb-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-border/40 bg-muted/20 p-3">
              <p className="dj-data text-[10px] uppercase tracking-[0.24em] text-muted-foreground/70">Now Playing</p>
              {player.current ? (
                <div className="mt-2 flex flex-col gap-2">
                  <p className="truncate text-base font-medium">{player.current.title}</p>
                  <p className="truncate text-xs text-muted-foreground">{player.current.artists || 'Unknown artist'}</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant="secondary" className="dj-data text-[10px]">
                      {formatBpm(player.current.bpm ?? null)} BPM
                    </Badge>
                    <Badge variant="outline" className="dj-data text-[10px]">
                      {player.current.camelot ?? '—'}
                    </Badge>
                    {player.current.mood ? <MoodBadge mood={player.current.mood} /> : null}
                  </div>
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  Select a track to open the full-width waveform deck.
                </p>
              )}
            </div>

            <div className="rounded-2xl border border-border/40 bg-muted/20 p-3">
              <p className="dj-data text-[10px] uppercase tracking-[0.24em] text-muted-foreground/70">Session State</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-border/30 bg-card/80 px-2 py-1.5">
                  <p className="text-[10px] text-muted-foreground">Master tempo</p>
                  <p className="dj-data text-sm">
                    {player.masterTempoBpm !== null ? `${player.masterTempoBpm.toFixed(1)} BPM` : 'Unlocked'}
                  </p>
                </div>
                <div className="rounded-lg border border-border/30 bg-card/80 px-2 py-1.5">
                  <p className="text-[10px] text-muted-foreground">Transition</p>
                  <p className="dj-data text-sm capitalize">{formatStyle(activeTransitionStyle)}</p>
                </div>
                <div className="rounded-lg border border-border/30 bg-card/80 px-2 py-1.5">
                  <p className="text-[10px] text-muted-foreground">Crossfade</p>
                  <p className="dj-data text-sm">{player.crossfadeBars} bars</p>
                </div>
                <div className="rounded-lg border border-border/30 bg-card/80 px-2 py-1.5">
                  <p className="text-[10px] text-muted-foreground">Next up</p>
                  <p className="truncate text-xs">{player.nextUp?.title ?? 'Auto select'}</p>
                </div>
              </div>
            </div>
          </div>

          <EnergyArcStrip points={energyPoints} activeValue={activeTrackEnergy} />
        </CardContent>
      </Card>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
        <InputGroup className="h-11 rounded-2xl border-border/40 bg-card/80">
          <InputGroupAddon>
            <InputGroupText>
              <Search />
            </InputGroupText>
          </InputGroupAddon>
          <InputGroupInput
            aria-label="Search tracks"
            autoComplete="off"
            name="track-search"
            placeholder="Search tracks, artists, moods..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <InputGroupAddon align="inline-end">
            {isPending ? (
              <InputGroupText>
                <IconLoader2 className="animate-spin" />
              </InputGroupText>
            ) : null}
          </InputGroupAddon>
        </InputGroup>

        <div className="flex items-center gap-2 rounded-2xl border border-border/40 bg-card/80 px-3">
          <Gauge className="text-muted-foreground" />
          <span className="dj-data text-xs text-foreground/80">
            {tracks.length.toLocaleString()}
            <span className="text-muted-foreground/40"> / </span>
            {total.toLocaleString()}
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span className="text-xs text-muted-foreground">{player.isCrossfading ? 'Crossfading' : 'Ready'}</span>
        </div>
      </div>

      <Card size="sm" className="border-border/40 bg-card/75">
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Compass className="text-muted-foreground" />
            <span className="dj-data text-[10px] uppercase tracking-[0.24em] text-muted-foreground/75">Navigation</span>
            {currentBpmMin != null && currentBpmMax != null ? (
              <Badge variant="outline" className="dj-data text-[10px]">
                {currentBpmMin}–{currentBpmMax} BPM
              </Badge>
            ) : null}
            {currentMood ? <MoodBadge mood={currentMood} /> : null}
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-xs text-muted-foreground">Sort by</span>
            <ToggleGroup
              multiple={false}
              value={[currentSortBy as SortBy]}
              onValueChange={handleSortByChange}
              variant="outline"
              size="sm"
              spacing={1}
              className="w-full flex-wrap"
            >
              {SORT_BY_OPTIONS.map((option) => (
                <ToggleGroupItem key={option.value} value={option.value}>
                  {option.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          <div className="flex items-center gap-2">
            <Activity className="text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Direction</span>
            <ToggleGroup
              multiple={false}
              value={[currentSortDir as SortDir]}
              onValueChange={handleSortDirChange}
              variant="outline"
              size="sm"
              spacing={1}
            >
              <ToggleGroupItem value="asc">Ascending</ToggleGroupItem>
              <ToggleGroupItem value="desc">Descending</ToggleGroupItem>
            </ToggleGroup>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-2 md:hidden">
        {tracks.map((track) => (
          <MobileTrackCard
            key={track.id}
            track={track}
            isActive={activeTrackId === track.id}
            isLoading={player.isLoading}
            isPlaying={player.isPlaying}
            onToggle={handleTogglePlay}
            onOpen={handleRowClick}
          />
        ))}
      </div>

      <div className="hidden md:block">
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-card/80">
          <DataTable
            columns={columns}
            data={tracks}
            onRowClick={handleRowClick}
            sorting={sorting}
            onSortingChange={handleSortingChange}
            manualSorting
          />
        </div>
      </div>

      <div ref={sentinelRef} className="flex items-center justify-center py-8">
        {isLoadingMore && (
          <div className="flex items-center gap-2">
            <IconLoader2 className="animate-spin text-foreground/40" />
            <span className="text-sm text-muted-foreground/60">Loading…</span>
          </div>
        )}
        {!hasMore && tracks.length > 0 && (
          <span className="dj-data text-xs uppercase tracking-wider text-muted-foreground/40">
            Full library · {total.toLocaleString()} tracks
          </span>
        )}
        {hasMore && !isLoadingMore && (
          <Button variant="outline" size="sm" onClick={() => loadMore()} className="gap-2 rounded-full border-border/30">
            <Zap data-icon="inline-start" />
            Load More
          </Button>
        )}
      </div>
    </div>
  )
}
