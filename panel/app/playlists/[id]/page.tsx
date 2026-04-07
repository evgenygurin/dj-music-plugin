import { notFound } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageShell, PageHeader } from '@/components/page-shell'
import { MoodDistributionChart } from '@/components/charts/mood-distribution'
import { PlaylistActionsBar } from '@/components/playlist-actions-bar'
import { TrackOrderTable } from '@/components/track-order-table'
import { getPlaylistDetail } from '@/lib/queries/playlists'

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
    <PageShell title={playlist.name} parent={{ label: 'Playlists', href: '/playlists' }}>
      <PageHeader
        title={playlist.name}
        badge={
          <div className="flex flex-wrap items-center gap-2">
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
        }
        actions={<PlaylistActionsBar playlistId={playlistId} />}
      />

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

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Tracks</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <TrackOrderTable
            tracks={playlist.tracks}
            emptyMessage="This playlist is empty."
          />
        </CardContent>
      </Card>
    </PageShell>
  )
}
