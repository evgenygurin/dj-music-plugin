'use client'

import { type ColumnDef } from '@tanstack/react-table'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'
import { useCallback, useState } from 'react'

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

const columns: ColumnDef<TrackRow>[] = [
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
]

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

  const handleSearch = () => {
    router.push(`${pathname}?${createQueryString({ search: searchInput, page: '1' })}`)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch()
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const handlePrev = () => {
    if (currentPage > 1) {
      router.push(`${pathname}?${createQueryString({ page: String(currentPage - 1) })}`)
    }
  }

  const handleNext = () => {
    if (currentPage < totalPages) {
      router.push(`${pathname}?${createQueryString({ page: String(currentPage + 1) })}`)
    }
  }

  const handleRowClick = (row: TrackRow) => {
    router.push(`/library/${row.id}`)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search tracks..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-64"
          />
          <Button variant="outline" size="sm" onClick={handleSearch}>
            Search
          </Button>
        </div>
        <span className="text-sm text-muted-foreground">
          {total.toLocaleString()} tracks
        </span>
      </div>

      <DataTable columns={columns} data={initialTracks} onRowClick={handleRowClick} />

      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          Page {currentPage} of {totalPages}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handlePrev} disabled={currentPage <= 1}>
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleNext}
            disabled={currentPage >= totalPages}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
