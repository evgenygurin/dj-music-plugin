import { notFound } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SiteHeader } from '@/components/site-header'
import { TransitionTable } from '@/components/transition-table'
import { EnergyArcChart, prepareEnergyArcData } from '@/components/charts/energy-arc'
import { getSetDetail, getSetVersionTracks } from '@/lib/queries/sets'
import { formatDuration, formatBpm } from '@/lib/utils'

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

  return (
    <>
      <SiteHeader title={set.name} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Header card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">{set.name}</CardTitle>
            {set.description && (
              <p className="text-muted-foreground text-sm">{set.description}</p>
            )}
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {set.template_name && (
                <Badge variant="secondary">{set.template_name}</Badge>
              )}
              {set.target_bpm_min !== null && set.target_bpm_max !== null && (
                <Badge variant="outline" className="font-mono">
                  {formatBpm(set.target_bpm_min)}–{formatBpm(set.target_bpm_max)} BPM
                </Badge>
              )}
              {set.target_duration_ms !== null && (
                <Badge variant="outline">{formatDuration(set.target_duration_ms)}</Badge>
              )}
              <Badge variant="outline">{set.versions.length} version{set.versions.length !== 1 ? 's' : ''}</Badge>
            </div>
          </CardContent>
        </Card>

        {/* Versions info */}
        {set.versions.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Versions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {set.versions.map((v) => (
                  <div
                    key={v.id}
                    className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm"
                  >
                    <span>{v.label ?? `v${v.id}`}</span>
                    {v.quality_score !== null && (
                      <Badge variant="secondary" className="text-xs">
                        {v.quality_score.toFixed(2)}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

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

        {/* Transition table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Track List
              {latestVersion?.label && (
                <span className="ml-2 text-muted-foreground font-normal text-xs">
                  ({latestVersion.label})
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TransitionTable tracks={versionTracks} />
          </CardContent>
        </Card>

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
      </div>
    </>
  )
}
