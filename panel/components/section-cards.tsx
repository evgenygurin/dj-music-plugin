import { Card, CardContent } from '@/components/ui/card'
import type { LibraryStats } from '@/lib/queries/dashboard'

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <Card className="shadow-none">
      <CardContent className="flex flex-col gap-1 p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tabular-nums leading-none">{value}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  )
}

export function SectionCards({ stats }: { stats: LibraryStats }) {
  const coveragePct =
    stats.totalTracks > 0
      ? Math.round((stats.analyzedTracks / stats.totalTracks) * 100)
      : 0

  return (
    <div className="grid grid-cols-2 gap-3 @xl/main:grid-cols-4">
      <MetricCard
        label="Tracks"
        value={stats.totalTracks.toLocaleString()}
        sub="in library"
      />
      <MetricCard
        label="Analyzed"
        value={stats.analyzedTracks.toLocaleString()}
        sub={`${coveragePct}% coverage`}
      />
      <MetricCard
        label="DJ Sets"
        value={stats.totalSets.toLocaleString()}
        sub="optimized orderings"
      />
      <MetricCard
        label="Set Quality"
        value={stats.avgSetQuality != null ? stats.avgSetQuality.toFixed(2) : '—'}
        sub="avg transition score"
      />
    </div>
  )
}
