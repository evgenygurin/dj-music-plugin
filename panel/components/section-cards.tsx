import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { LibraryStats } from '@/lib/queries/dashboard'

function MetricCard({
  label,
  value,
  sub,
  tone,
  progress,
}: {
  label: string
  value: string | number
  sub?: string
  tone: string
  progress?: number
}) {
  return (
    <Card className="overflow-hidden border-border/70 bg-card/80 shadow-none backdrop-blur-sm">
      <CardContent className="relative flex h-full flex-col gap-3 p-4">
        <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${tone}`} />
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
            {label}
          </p>
          <p className="text-3xl font-semibold leading-none tabular-nums">{value}</p>
        </div>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
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
    <div className="grid grid-cols-1 gap-3 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
      <MetricCard
        label="Tracks Ready"
        value={stats.totalTracks.toLocaleString()}
        sub="Indexed in the crate & ready for exploration."
        tone="from-cyan-400/90 via-cyan-300/40 to-transparent"
      />
      <MetricCard
        label="Analysis Coverage"
        value={stats.analyzedTracks.toLocaleString()}
        sub={`${coveragePct}% of the library has usable audio features.`}
        tone="from-sky-400/90 via-sky-300/40 to-transparent"
        progress={coveragePct}
      />
      <MetricCard
        label="Sets Built"
        value={stats.totalSets.toLocaleString()}
        sub="Saved sequences with optimized transitions."
        tone="from-fuchsia-400/90 via-fuchsia-300/40 to-transparent"
      />
      <MetricCard
        label="Average Quality"
        value={stats.avgSetQuality != null ? stats.avgSetQuality.toFixed(2) : '—'}
        sub="Mean transition score across saved set versions."
        tone="from-amber-300/90 via-amber-200/40 to-transparent"
      />
    </div>
  )
}
