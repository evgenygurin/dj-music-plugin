import { notFound } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageShell } from '@/components/page-shell'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { TransitionTable } from '@/components/transition-table'
import { EnergyArcChart, prepareEnergyArcData } from '@/components/charts/energy-arc'
import { SetActionsPanel } from '@/components/set-actions-panel'
import { CheatSheetTab } from '@/components/cheat-sheet-tab'
import { TrackOrderTable } from '@/components/track-order-table'
import { getSetDetail, getSetVersionTracks } from '@/lib/queries/sets'
import { formatDuration, formatBpm, scoreColor } from '@/lib/utils'

export const revalidate = 60

interface SetDetailPageProps {
  params: Promise<{ id: string }>
}

export default async function SetDetailPage({ params }: SetDetailPageProps) {
  const { id } = await params
  const setId = parseInt(id, 10)

  if (isNaN(setId)) notFound()

  const set = await getSetDetail(setId)
  if (!set) notFound()

  const latestVersion = set.versions[0] ?? null
  const versionTracks = latestVersion ? await getSetVersionTracks(latestVersion.id) : []

  // Prepare energy arc data
  const arcInputData = versionTracks
    .filter((t) => t.track.integrated_lufs !== null)
    .map((t) => ({
      position: t.sort_index + 1,
      title: t.track.title,
      lufs: t.track.integrated_lufs!,
    }))
  const energyArcData = prepareEnergyArcData(arcInputData)

  const qualityScore = latestVersion?.quality_score ?? null

  return (
    <PageShell title={set.name} parent={{ label: 'DJ Sets', href: '/sets' }}>
      {/* Header */}
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-lg font-semibold">{set.name}</h1>
                {set.template_name && (
                  <Badge variant="secondary">{set.template_name}</Badge>
                )}
                {qualityScore !== null && (
                  <Badge
                    variant="outline"
                    className={`font-mono ${scoreColor(qualityScore)}`}
                  >
                    {qualityScore.toFixed(2)}
                  </Badge>
                )}
                {set.target_bpm_min !== null && set.target_bpm_max !== null && (
                  <Badge variant="outline" className="font-mono">
                    {formatBpm(set.target_bpm_min)}–{formatBpm(set.target_bpm_max)} BPM
                  </Badge>
                )}
                {set.target_duration_ms !== null && (
                  <Badge variant="outline">{formatDuration(set.target_duration_ms)}</Badge>
                )}
                <Badge variant="outline" className="text-muted-foreground">
                  {set.versions.length} version{set.versions.length !== 1 ? 's' : ''}
                </Badge>
              </div>
              {set.description && (
                <p className="text-sm text-muted-foreground">{set.description}</p>
              )}
            </div>

            {/* Energy arc */}
            {energyArcData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Energy Arc</CardTitle>
                </CardHeader>
                <CardContent>
                  <EnergyArcChart data={energyArcData} />
                </CardContent>
              </Card>
            )}

            {/* Tabs */}
            <Tabs defaultValue="tracks">
              <TabsList>
                <TabsTrigger value="tracks">
                  Tracks
                  {versionTracks.length > 0 && (
                    <span className="ml-1 text-muted-foreground">({versionTracks.length})</span>
                  )}
                </TabsTrigger>
                <TabsTrigger value="transitions">Transitions</TabsTrigger>
                <TabsTrigger value="cheatsheet">Cheat Sheet</TabsTrigger>
                <TabsTrigger value="actions">Actions</TabsTrigger>
              </TabsList>

              {/* Tracks tab */}
              <TabsContent value="tracks">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">
                      Track Order
                      {latestVersion?.label && (
                        <span className="ml-2 text-muted-foreground font-normal text-xs">
                          ({latestVersion.label})
                        </span>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <TrackOrderTable
                      tracks={versionTracks}
                      emptyMessage="No tracks in this version."
                    />
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Transitions tab */}
              <TabsContent value="transitions">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">Transition Scores</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <TransitionTable tracks={versionTracks} />
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Cheat Sheet tab */}
              <TabsContent value="cheatsheet">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">DJ Cheat Sheet</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CheatSheetTab setId={setId} />
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Actions tab */}
              <TabsContent value="actions">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">Set Actions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <SetActionsPanel
                      setId={setId}
                      sourcePlaylistId={set.source_playlist_id}
                      setName={set.name}
                      templateName={set.template_name}
                    />
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            {/* Constraints */}
            {set.constraints.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Constraints</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {set.constraints.map((c) => (
                      <div key={c.id} className="flex items-center gap-2 text-sm">
                        <Badge variant="outline" className="text-xs">{c.constraint_type}</Badge>
                        <span className="text-muted-foreground font-mono text-xs">
                          {JSON.stringify(c.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
    </PageShell>
  )
}
