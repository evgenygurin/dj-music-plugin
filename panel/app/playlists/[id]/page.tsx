import Link from 'next/link'
import { notFound } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SiteHeader } from '@/components/site-header'
import { MoodBadge } from '@/components/mood-badge'
import { MoodDistributionChart } from '@/components/charts/mood-distribution'
import { PlaylistActionsBar } from '@/components/playlist-actions-bar'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from '@/components/ui/empty'
import { IconMusic } from '@tabler/icons-react'
import { getPlaylistDetail } from '@/lib/queries/playlists'
import { formatBpm } from '@/lib/utils'

export const revalidate = 60

interface PlaylistDetailPageProps {
  params: Promise<{ id: string }>
}

export default async function PlaylistDetailPage({ params }: PlaylistDetailPageProps) {
  const { id } = await params
  const playlistId = parseInt(id, 10)

  if (isNaN(playlistId)) notFound()

  const playlist = await getPlaylistDetail(playlistId)
  if (!playlist) notFound()

  return (
    <>
      <SiteHeader title={playlist.name} parent={{ label: 'Playlists', href: '/playlists' }} />
      <div className="flex flex-1 flex-col">
        <div className="@container/main flex flex-1 flex-col gap-2">
          <div className="flex flex-col gap-4 px-4 py-4 md:gap-6 md:py-6 lg:px-6">

            {/* Header */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-lg font-semibold">{playlist.name}</h1>
                <Badge variant="secondary" className="tabular-nums">
                  {playlist.tracks.length} tracks
                </Badge>
                {playlist.source_of_truth && (
                  <Badge variant="outline" className="capitalize">
                    {playlist.source_of_truth}
                  </Badge>
                )}
                {playlist.platform_ids &&
                  Object.entries(playlist.platform_ids).map(([platform, extId]) => (
                    <Badge key={platform} variant="outline" className="text-xs font-mono">
                      {platform}: {extId}
                    </Badge>
                  ))}
              </div>
              <PlaylistActionsBar playlistId={playlistId} />
            </div>

            {/* Mood distribution */}
            {playlist.moodCounts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Mood Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <MoodDistributionChart data={playlist.moodCounts} />
                </CardContent>
              </Card>
            )}

            {/* Track table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Tracks</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {playlist.tracks.length === 0 ? (
                  <div className="p-6">
                    <Empty>
                      <EmptyHeader>
                        <EmptyMedia variant="icon">
                          <IconMusic />
                        </EmptyMedia>
                        <EmptyTitle>No tracks</EmptyTitle>
                        <EmptyDescription>This playlist is empty.</EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  </div>
                ) : (
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
                        {playlist.tracks.map((item) => (
                          <TableRow key={item.sort_index}>
                            <TableCell className="text-muted-foreground text-xs tabular-nums">
                              {item.sort_index + 1}
                            </TableCell>
                            <TableCell>
                              <Link
                                href={`/library/${item.track.id}`}
                                className="hover:underline font-medium text-sm line-clamp-1 max-w-[200px] block"
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
                )}
              </CardContent>
            </Card>

          </div>
        </div>
      </div>
    </>
  )
}
