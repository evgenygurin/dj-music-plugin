import Link from 'next/link'
import { IconPlaylist } from '@tabler/icons-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageShell, PageHeader } from '@/components/page-shell'
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from '@/components/ui/empty'
import { getSetList } from '@/lib/queries/sets'
import { formatDuration, scoreColor } from '@/lib/utils'

export const revalidate = 30

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default async function SetsPage() {
  const sets = await getSetList()

  return (
    <PageShell title="DJ Sets">
      <PageHeader
        title="DJ Sets"
        badge={
          sets.length > 0 && (
            <Badge variant="secondary" className="tabular-nums">
              {sets.length}
            </Badge>
          )
        }
      />

      {sets.length === 0 ? (
        <Empty className="border min-h-[200px]">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconPlaylist />
            </EmptyMedia>
            <EmptyTitle>No DJ sets yet</EmptyTitle>
            <EmptyDescription>
              Build a set from a playlist to get started.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sets.map((set) => (
            <Link key={set.id} href={`/sets/${set.id}`}>
              <Card className="h-full transition-colors hover:bg-muted/50 cursor-pointer">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base line-clamp-1">{set.name}</CardTitle>
                    {set.latestVersion?.quality_score !== null &&
                      set.latestVersion?.quality_score !== undefined && (
                        <span
                          className={`text-sm font-mono font-semibold flex-shrink-0 ${scoreColor(set.latestVersion.quality_score)}`}
                        >
                          {set.latestVersion.quality_score.toFixed(2)}
                        </span>
                      )}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {set.template_name && (
                      <Badge variant="secondary" className="text-xs">
                        {set.template_name}
                      </Badge>
                    )}
                    {set.target_bpm_min !== null && set.target_bpm_max !== null && (
                      <Badge variant="outline" className="text-xs font-mono">
                        {set.target_bpm_min}–{set.target_bpm_max} BPM
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground block text-xs">Tracks</span>
                      <span className="font-medium tabular-nums">{set.trackCount}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block text-xs">Versions</span>
                      <span className="font-medium tabular-nums">{set.versionCount}</span>
                    </div>
                    {set.target_duration_ms !== null && (
                      <div>
                        <span className="text-muted-foreground block text-xs">Duration</span>
                        <span className="font-medium font-mono">
                          {formatDuration(set.target_duration_ms)}
                        </span>
                      </div>
                    )}
                    {set.created_at && (
                      <div>
                        <span className="text-muted-foreground block text-xs">Created</span>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(set.created_at)}
                        </span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  )
}
