import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { LibraryStats } from '@/lib/queries/dashboard'

function MetricCard({
  label,
  value,
  sub,
  progress,
}: {
  label: string
  value: string | number
  sub?: string
  progress?: number
}) {
  return (
    <Card className="shadow-none border-border/20 bg-card/50">
      <CardContent className="flex h-full flex-col gap-2 p-3 md:gap-3 md:p-4">
        <div className="space-y-0.5">
          <p className="text-[9px] uppercase tracking-wider text-muted-foreground/50 md:text-[10px]">
            {label}
          </p>
          <p className="dj-data text-2xl leading-none md:text-3xl">{value}</p>
        </div>
        {sub && <p className="hidden text-xs text-muted-foreground md:block">{sub}</p>}
        {progress !== undefined ? <Progress value={progress} className="mt-auto h-1.5" /> : null}
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
    <div className="grid grid-cols-2 gap-3 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
      <MetricCard
        label="Tracks Ready"
        value={stats.totalTracks.toLocaleString()}
        sub="Indexed in the crate & ready for exploration."
      />
      <MetricCard
        label="Analysis Coverage"
        value={stats.analyzedTracks.toLocaleString()}
        sub={`${coveragePct}% of the library has usable audio features.`}
        progress={coveragePct}
      />
      <MetricCard
        label="Sets Built"
        value={stats.totalSets.toLocaleString()}
        sub="Saved sequences with optimized transitions."
      />
      <MetricCard
        label="Average Quality"
        value={stats.avgSetQuality != null ? stats.avgSetQuality.toFixed(2) : '—'}
        sub="Mean transition score across saved set versions."
      />
    </div>
  )
}
