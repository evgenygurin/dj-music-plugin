import Link from 'next/link'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { MoodBadge } from '@/components/mood-badge'
import { formatBpm } from '@/lib/utils'

/**
 * Minimum shape required to render a track row in an ordered listing.
 * Both `PlaylistTrack` (lib/queries/playlists.ts) and `SetVersionTrack`
 * (lib/queries/sets.ts) satisfy this contract.
 */
export interface TrackOrderRow {
  sort_index: number
  track: {
    id: number
    title: string
    artists: string
    bpm: number | null
    camelot: string | null
    mood: string | null
  }
}

interface TrackOrderTableProps<T extends TrackOrderRow> {
  tracks: T[]
  /** Optional empty-state message when `tracks` is empty. */
  emptyMessage?: string
}

/**
 * Server-rendered, ordered track table used by playlist and set detail pages.
 * Replaces hand-rolled `<Table>` markup that previously lived inline on both
 * pages — guarantees both stay in sync visually.
 */
export function TrackOrderTable<T extends TrackOrderRow>({
  tracks,
  emptyMessage = 'No tracks.',
}: TrackOrderTableProps<T>) {
  if (tracks.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">{emptyMessage}</p>
  }

  return (
    <div className="overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">#</TableHead>
            <TableHead>Title</TableHead>
            <TableHead>Artists</TableHead>
            <TableHead className="w-16">BPM</TableHead>
            <TableHead className="w-14">Key</TableHead>
            <TableHead className="w-32">Mood</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tracks.map((item) => (
            <TableRow key={item.sort_index}>
              <TableCell className="text-muted-foreground text-xs tabular-nums">
                {item.sort_index + 1}
              </TableCell>
              <TableCell>
                <Link
                  href={`/library/${item.track.id}`}
                  className="hover:underline font-medium text-sm line-clamp-1 max-w-[220px] block"
                >
                  {item.track.title}
                </Link>
              </TableCell>
              <TableCell>
                <span className="text-sm text-muted-foreground max-w-[160px] truncate block">
                  {item.track.artists || '—'}
                </span>
              </TableCell>
              <TableCell>
                <span className="font-mono text-xs tabular-nums">
                  {formatBpm(item.track.bpm)}
                </span>
              </TableCell>
              <TableCell>
                <span className="font-mono text-xs">{item.track.camelot ?? '—'}</span>
              </TableCell>
              <TableCell>
                <MoodBadge mood={item.track.mood} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
