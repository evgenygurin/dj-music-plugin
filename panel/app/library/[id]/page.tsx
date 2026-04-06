import { notFound } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SiteHeader } from '@/components/site-header'
import { MoodBadge } from '@/components/mood-badge'
import { TrackFeatures } from '@/components/track-features'
import { SectionsTimeline } from '@/components/sections-timeline'
import { getTrackDetail } from '@/lib/queries/tracks'
import { formatDuration, formatBpm, formatLufs, camelotNotation } from '@/lib/utils'


export const revalidate = 120

interface TrackDetailPageProps {
  params: Promise<{ id: string }>
}

const CUE_KIND_NAMES: Record<number, string> = {
  0: 'Cue',
  1: 'Hot 1',
  2: 'Hot 2',
  3: 'Hot 3',
  4: 'Hot 4',
  5: 'Hot 5',
  6: 'Hot 6',
  7: 'Hot 7',
}

function formatMs(ms: number): string {
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export default async function TrackDetailPage({ params }: TrackDetailPageProps) {
  const { id } = await params
  const trackId = parseInt(id, 10)

  if (isNaN(trackId)) notFound()

  const track = await getTrackDetail(trackId)
  if (!track) notFound()

  const artistNames = track.artists.map((a) => a.name).join(', ')
  const f = track.features

  const featuresRecord: Record<string, unknown> | null = f
    ? (f as unknown as Record<string, unknown>)
    : null

  return (
    <>
      <SiteHeader title={track.title} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Header card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">{track.title}</CardTitle>
            {artistNames && (
              <p className="text-muted-foreground">{artistNames}</p>
            )}
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {track.duration_ms !== null && (
                <Badge variant="secondary">{formatDuration(track.duration_ms)}</Badge>
              )}
              {f?.bpm !== null && f?.bpm !== undefined && (
                <Badge variant="secondary">{formatBpm(f.bpm)} BPM</Badge>
              )}
              {f?.key_code !== null && f?.key_code !== undefined && (
                <Badge variant="secondary">{camelotNotation(f.key_code)}</Badge>
              )}
              {f?.integrated_lufs !== null && f?.integrated_lufs !== undefined && (
                <Badge variant="secondary">{formatLufs(f.integrated_lufs)}</Badge>
              )}
              {f?.mood && <MoodBadge mood={f.mood} />}
              {f?.mood_confidence !== null && f?.mood_confidence !== undefined && (
                <Badge variant="outline" className="text-xs">
                  {Math.round((f.mood_confidence as number) * 100)}% conf
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Sections timeline */}
        {track.sections.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Sections</CardTitle>
            </CardHeader>
            <CardContent>
              <SectionsTimeline sections={track.sections} />
            </CardContent>
          </Card>
        )}

        {/* Audio features */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Audio Features</CardTitle>
          </CardHeader>
          <CardContent>
            <TrackFeatures features={featuresRecord} />
          </CardContent>
        </Card>

        {/* Cue points */}
        {track.cuePoints.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Cue Points</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {track.cuePoints.map((cue) => (
                  <Badge key={cue.id} variant="outline" className="text-xs font-mono">
                    {CUE_KIND_NAMES[cue.kind] ?? `Kind ${cue.kind}`}{' '}
                    {formatMs(cue.position_ms)}
                    {cue.label ? ` (${cue.label})` : ''}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Loops */}
        {track.loops.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Saved Loops</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {track.loops.map((loop) => (
                  <Badge key={loop.id} variant="outline" className="text-xs font-mono">
                    {loop.label ?? 'Loop'} {formatMs(loop.in_position_ms)} →{' '}
                    {formatMs(loop.out_position_ms)}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* File info */}
        {track.libraryItem && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">File Info</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div>
                  <span className="text-muted-foreground block">Path</span>
                  <span className="font-mono text-xs break-all">{track.libraryItem.file_path}</span>
                </div>
                {track.libraryItem.file_size !== null && (
                  <div>
                    <span className="text-muted-foreground block">Size</span>
                    <span>{(track.libraryItem.file_size / 1024 / 1024).toFixed(1)} MB</span>
                  </div>
                )}
                {track.libraryItem.bitrate !== null && (
                  <div>
                    <span className="text-muted-foreground block">Bitrate</span>
                    <span>{track.libraryItem.bitrate} kbps</span>
                  </div>
                )}
                {track.libraryItem.sample_rate !== null && (
                  <div>
                    <span className="text-muted-foreground block">Sample Rate</span>
                    <span>{track.libraryItem.sample_rate} Hz</span>
                  </div>
                )}
                {track.libraryItem.channels !== null && (
                  <div>
                    <span className="text-muted-foreground block">Channels</span>
                    <span>{track.libraryItem.channels === 2 ? 'Stereo' : track.libraryItem.channels}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* YM metadata */}
        {track.ymMetadata && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Yandex Music</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                {track.ymMetadata.yandex_track_id && (
                  <div>
                    <span className="text-muted-foreground block">Track ID</span>
                    <span className="font-mono">{track.ymMetadata.yandex_track_id}</span>
                  </div>
                )}
                {track.ymMetadata.album_title && (
                  <div>
                    <span className="text-muted-foreground block">Album</span>
                    <span>{track.ymMetadata.album_title}</span>
                  </div>
                )}
                {track.ymMetadata.explicit !== null && (
                  <div>
                    <span className="text-muted-foreground block">Explicit</span>
                    <span>{track.ymMetadata.explicit ? 'Yes' : 'No'}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
