import { Skeleton } from '@/components/ui/skeleton'
import { PageShellSkeleton, CardGridSkeleton } from '@/components/skeletons'

export default function DiscoverLoading() {
  return (
    <PageShellSkeleton>
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-4 w-96" />
      <CardGridSkeleton cards={1} bodyHeight="h-32" />
      <CardGridSkeleton cards={1} bodyHeight="h-20" />
    </PageShellSkeleton>
  )
}
