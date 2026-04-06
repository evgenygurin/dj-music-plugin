import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SiteHeader } from '@/components/site-header'
import { getSetList } from '@/lib/queries/sets'
import { formatDuration } from '@/lib/utils'

export const revalidate = 30

export default async function SetsPage() {
  const sets = await getSetList()

  return (
    <>
      <SiteHeader title="DJ Sets" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {sets.length === 0 ? (
          <p className="text-muted-foreground">No DJ sets found.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sets.map((set) => (
              <Link key={set.id} href={`/sets/${set.id}`}>
                <Card className="h-full transition-colors hover:bg-muted/50 cursor-pointer">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base line-clamp-1">{set.name}</CardTitle>
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
                        <span className="font-medium">{set.trackCount}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground block text-xs">Versions</span>
                        <span className="font-medium">{set.versionCount}</span>
                      </div>
                      {set.target_duration_ms !== null && (
                        <div>
                          <span className="text-muted-foreground block text-xs">Duration</span>
                          <span className="font-medium font-mono">
                            {formatDuration(set.target_duration_ms)}
                          </span>
                        </div>
                      )}
                      {set.latestVersion?.quality_score !== null &&
                        set.latestVersion?.quality_score !== undefined && (
                          <div>
                            <span className="text-muted-foreground block text-xs">Quality</span>
                            <span className="font-medium">
                              {set.latestVersion.quality_score.toFixed(2)}
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
      </div>
    </>
  )
}
