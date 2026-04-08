import { Skeleton } from '@/components/ui/skeleton'
import { PageShellSkeleton, CardGridSkeleton } from '@/components/skeletons'

export default function ToolsLoading() {
  return (
    <PageShellSkeleton>
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-4 w-48" />
      <CardGridSkeleton cards={6} cols="sm:grid-cols-2 lg:grid-cols-3" bodyHeight="h-12" />
      <CardGridSkeleton cards={6} cols="sm:grid-cols-2 lg:grid-cols-3" bodyHeight="h-12" />
    </PageShellSkeleton>
  )
}
