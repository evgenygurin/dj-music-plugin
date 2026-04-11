import { notFound } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageShell } from '@/components/page-shell'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { TransitionTable } from '@/components/transition-table'
import { EnergyArcChart } from '@/components/charts/energy-arc'
import { prepareEnergyArcData } from '@/components/charts/energy-arc-data'
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
    <PageShell title={set.name} parent={{ label: 'Sets', href: '/sets' }}>
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="display-heading text-2xl md:text-3xl">{set.name}</h1>
        <div className="flex flex-wrap items-center gap-2">
          {set.template_name && (
            <Badge variant="secondary" className="dj-data text-[10px]">{set.template_name}</Badge>
          )}
          {qualityScore !== null && (
            <Badge
              variant="outline"
              className={`dj-data text-[11px] border-foreground/10 ${scoreColor(qualityScore)}`}
            >
              {qualityScore.toFixed(2)}
            </Badge>
          )}
          {set.target_bpm_min !== null && set.target_bpm_max !== null && (
            <Badge variant="outline" className="dj-data text-[11px] border-foreground/10">
              {formatBpm(set.target_bpm_min)}–{formatBpm(set.target_bpm_max)}
            </Badge>
          )}
          {set.target_duration_ms !== null && (
            <Badge variant="outline" className="dj-data text-[11px] border-foreground/10">{formatDuration(set.target_duration_ms)}</Badge>
          )}
          <Badge variant="outline" className="dj-data text-[10px] text-muted-foreground/50 border-foreground/10">
            {set.versions.length} ver{set.versions.length !== 1 ? 's' : ''}
          </Badge>
        </div>
        {set.description && (
          <p className="text-sm text-muted-foreground/70">{set.description}</p>
        )}
      </div>

      {/* Energy arc — full width */}
      {energyArcData.length > 0 && (
        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader>
            <CardTitle className="display-heading text-lg">Energy Arc</CardTitle>
          </CardHeader>
          <CardContent>
            <EnergyArcChart data={energyArcData} />
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="tracks">
        <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
          <TabsList>
            <TabsTrigger value="tracks">
              Tracks
              {versionTracks.length > 0 && (
                <span className="ml-1 text-muted-foreground/50 dj-data text-[10px]">({versionTracks.length})</span>
              )}
            </TabsTrigger>
            <TabsTrigger value="transitions">Transitions</TabsTrigger>
            <TabsTrigger value="cheatsheet">Cheat Sheet</TabsTrigger>
            <TabsTrigger value="actions">Actions</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="tracks">
          <Card className="shadow-none border-border/20 bg-card/50">
            <CardHeader>
              <CardTitle className="display-heading text-lg">
                Track Order
                {latestVersion?.label && (
                  <span className="ml-2 text-muted-foreground/40 font-sans text-xs font-normal">
                    {latestVersion.label}
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

        <TabsContent value="transitions">
          <Card className="shadow-none border-border/20 bg-card/50">
            <CardHeader>
              <CardTitle className="display-heading text-lg">Transitions</CardTitle>
            </CardHeader>
            <CardContent>
              <TransitionTable tracks={versionTracks} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cheatsheet">
          <Card className="shadow-none border-border/20 bg-card/50">
            <CardHeader>
              <CardTitle className="display-heading text-lg">Cheat Sheet</CardTitle>
            </CardHeader>
            <CardContent>
              <CheatSheetTab setId={setId} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="actions">
          <Card className="shadow-none border-border/20 bg-card/50">
            <CardHeader>
              <CardTitle className="display-heading text-lg">Actions</CardTitle>
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
        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader>
            <CardTitle className="display-heading text-lg">Constraints</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {set.constraints.map((c) => (
                <div key={c.id} className="flex items-center gap-2 text-sm">
                  <Badge variant="outline" className="dj-data text-[10px] border-foreground/10">{c.constraint_type}</Badge>
                  <span className="dj-data text-xs text-muted-foreground/50">
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
