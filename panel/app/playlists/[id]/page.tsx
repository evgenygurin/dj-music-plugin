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
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary" className="dj-data text-[10px]">
              {playlist.tracks.length} tracks
            </Badge>
            {playlist.source_of_truth && (
              <Badge variant="outline" className="dj-data text-[10px] capitalize">
                {playlist.source_of_truth}
              </Badge>
            )}
            {playlist.platform_ids &&
              Object.entries(playlist.platform_ids).map(([platform, extId]) => (
                <Badge key={platform} variant="outline" className="dj-data max-w-[220px] truncate text-[10px] font-mono">
                  {platform}:{String(extId)}
                </Badge>
              ))}
          </div>
        }
        actions={<PlaylistActionsBar playlistId={playlistId} />}
      />

      {playlist.moodCounts.length > 0 && (
        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader>
            <CardTitle className="display-heading text-lg">Mood Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <MoodDistributionChart data={playlist.moodCounts} />
          </CardContent>
        </Card>
      )}

      <Card className="shadow-none border-border/20 bg-card/50">
        <CardHeader>
          <CardTitle className="display-heading text-lg">Tracks</CardTitle>
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
