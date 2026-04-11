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
import { Badge } from '@/components/ui/badge'
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
    <div>
      <div className="flex flex-col gap-2 p-3 md:hidden">
        {tracks.map((item) => (
          <Link
            key={item.sort_index}
            href={`/library/${item.track.id}`}
            className="rounded-xl border border-border/30 bg-card/70 px-3 py-2"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="line-clamp-1 text-sm font-medium">{item.track.title}</p>
                <p className="line-clamp-1 text-xs text-muted-foreground">
                  {item.track.artists || '—'}
                </p>
              </div>
              <Badge variant="outline" className="dj-data text-[10px]">
                #{item.sort_index + 1}
              </Badge>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary" className="dj-data text-[10px]">
                {formatBpm(item.track.bpm)} BPM
              </Badge>
              <Badge variant="outline" className="dj-data text-[10px]">
                {item.track.camelot ?? '—'}
              </Badge>
              <MoodBadge mood={item.track.mood} />
            </div>
          </Link>
        ))}
      </div>

      <div className="hidden overflow-auto md:block">
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
                    className="block max-w-[220px] line-clamp-1 text-sm font-medium hover:underline"
                  >
                    {item.track.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <span className="block max-w-[160px] truncate text-sm text-muted-foreground">
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
    </div>
  )
}
