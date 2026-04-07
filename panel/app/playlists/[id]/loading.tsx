import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { PageShellSkeleton, RowsSkeleton } from '@/components/skeletons'

export default function PlaylistDetailLoading() {
  return (
    <PageShellSkeleton withBreadcrumb>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Skeleton className="h-6 w-24 rounded-full" />
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-16" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full mb-3" />
          <RowsSkeleton count={6} />
        </CardContent>
      </Card>
    </PageShellSkeleton>
  )
}
