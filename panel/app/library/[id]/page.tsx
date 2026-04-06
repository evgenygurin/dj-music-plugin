import { notFound } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SiteHeader } from '@/components/site-header'
import { MoodBadge } from '@/components/mood-badge'
import { TrackFeatures } from '@/components/track-features'
import { SectionsTimeline } from '@/components/sections-timeline'
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from '@/components/ui/empty'
import { getTrackDetail } from '@/lib/queries/tracks'
import { formatDuration, formatBpm, formatLufs, camelotNotation } from '@/lib/utils'
import { TrackActionsMenu } from './track-actions-menu'

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

function MetricItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )
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
      <SiteHeader title={track.title} parent={{ label: 'Library', href: '/library' }} />
      <div className="flex flex-1 flex-col">
        <div className="@container/main flex flex-1 flex-col gap-2">
          <div className="flex flex-col gap-4 px-4 py-4 md:gap-6 md:py-6 lg:px-6">

            {/* Hero header */}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h1 className="text-2xl font-semibold truncate">{track.title}</h1>
                {artistNames && (
                  <p className="text-muted-foreground mt-0.5">{artistNames}</p>
                )}
                <div className="flex flex-wrap items-center gap-2 mt-3">
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
              </div>
              <div className="shrink-0">
                <TrackActionsMenu trackId={trackId} />
              </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="overview">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="features">Audio Features</TabsTrigger>
                <TabsTrigger value="sections">Sections</TabsTrigger>
                <TabsTrigger value="file">File Info</TabsTrigger>
                {track.ymMetadata && <TabsTrigger value="ym">YM</TabsTrigger>}
              </TabsList>

              {/* Overview */}
              <TabsContent value="overview" className="mt-4">
                <div className="grid gap-4">
                  {f ? (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm font-medium">Key Metrics</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
                          <MetricItem label="BPM" value={formatBpm(f.bpm)} />
                          <MetricItem label="Key" value={camelotNotation(f.key_code)} />
                          <MetricItem label="Loudness" value={formatLufs(f.integrated_lufs)} />
                          <MetricItem
                            label="Energy"
                            value={f.energy_mean !== null ? f.energy_mean.toFixed(3) : '—'}
                          />
                          <MetricItem
                            label="Onset Rate"
                            value={f.onset_rate !== null ? f.onset_rate.toFixed(2) : '—'}
                          />
                          <MetricItem
                            label="Kick Prominence"
                            value={f.kick_prominence !== null ? f.kick_prominence.toFixed(3) : '—'}
                          />
                          <MetricItem
                            label="HP Ratio"
                            value={f.hp_ratio !== null ? f.hp_ratio.toFixed(2) : '—'}
                          />
                          <MetricItem
                            label="Spectral Centroid"
                            value={
                              f.spectral_centroid_hz !== null
                                ? `${f.spectral_centroid_hz.toFixed(0)} Hz`
                                : '—'
                            }
                          />
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    <Empty>
                      <EmptyHeader>
                        <EmptyMedia variant="icon">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
                        </EmptyMedia>
                        <EmptyTitle>No audio features</EmptyTitle>
                        <EmptyDescription>
                          Run analysis to extract BPM, key, energy, and other audio features.
                        </EmptyDescription>
                      </EmptyHeader>
                      <EmptyContent>
                        <TrackActionsMenu trackId={trackId} />
                      </EmptyContent>
                    </Empty>
                  )}

                  {f?.mood && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm font-medium">Mood Classification</CardTitle>
                      </CardHeader>
                      <CardContent className="flex items-center gap-3">
                        <MoodBadge mood={f.mood} />
                        {f.mood_confidence !== null && (
                          <span className="text-sm text-muted-foreground">
                            {Math.round((f.mood_confidence as number) * 100)}% confidence
                          </span>
                        )}
                      </CardContent>
                    </Card>
                  )}
                </div>
              </TabsContent>

              {/* Audio Features */}
              <TabsContent value="features" className="mt-4">
                <Card>
                  <CardContent className="pt-6">
                    <TrackFeatures features={featuresRecord} />
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Sections */}
              <TabsContent value="sections" className="mt-4">
                {track.sections.length > 0 ? (
                  <Card>
                    <CardContent className="pt-6">
                      <SectionsTimeline sections={track.sections} />
                    </CardContent>
                  </Card>
                ) : (
                  <Empty>
                    <EmptyHeader>
                      <EmptyTitle>No sections detected</EmptyTitle>
                      <EmptyDescription>
                        Sections (intro, drop, breakdown, outro) are detected during L4 analysis.
                      </EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                )}
              </TabsContent>

              {/* File Info */}
              <TabsContent value="file" className="mt-4">
                <div className="grid gap-4">
                  {track.libraryItem ? (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm font-medium">File</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                          <div className="col-span-2 sm:col-span-3">
                            <span className="text-xs text-muted-foreground block mb-1">Path</span>
                            <span className="font-mono text-xs break-all text-foreground/80">
                              {track.libraryItem.file_path}
                            </span>
                          </div>
                          {track.libraryItem.file_size !== null && (
                            <MetricItem
                              label="Size"
                              value={`${(track.libraryItem.file_size / 1024 / 1024).toFixed(1)} MB`}
                            />
                          )}
                          {track.libraryItem.bitrate !== null && (
                            <MetricItem label="Bitrate" value={`${track.libraryItem.bitrate} kbps`} />
                          )}
                          {track.libraryItem.sample_rate !== null && (
                            <MetricItem
                              label="Sample Rate"
                              value={`${track.libraryItem.sample_rate} Hz`}
                            />
                          )}
                          {track.libraryItem.channels !== null && (
                            <MetricItem
                              label="Channels"
                              value={track.libraryItem.channels === 2 ? 'Stereo' : String(track.libraryItem.channels)}
                            />
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    <Empty>
                      <EmptyHeader>
                        <EmptyTitle>No file info</EmptyTitle>
                        <EmptyDescription>No local library item linked to this track.</EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  )}

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
                </div>
              </TabsContent>

              {/* YM Metadata */}
              {track.ymMetadata && (
                <TabsContent value="ym" className="mt-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm font-medium">Yandex Music</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                        {track.ymMetadata.yandex_track_id && (
                          <MetricItem
                            label="Track ID"
                            value={
                              <span className="font-mono">{track.ymMetadata.yandex_track_id}</span>
                            }
                          />
                        )}
                        {track.ymMetadata.album_title && (
                          <MetricItem label="Album" value={track.ymMetadata.album_title} />
                        )}
                        {track.ymMetadata.explicit !== null && (
                          <MetricItem
                            label="Explicit"
                            value={track.ymMetadata.explicit ? 'Yes' : 'No'}
                          />
                        )}
                        {track.ymMetadata.album_id !== null && (
                          <MetricItem
                            label="Album ID"
                            value={<span className="font-mono">{track.ymMetadata.album_id}</span>}
                          />
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              )}
            </Tabs>

          </div>
        </div>
      </div>
    </>
  )
}
