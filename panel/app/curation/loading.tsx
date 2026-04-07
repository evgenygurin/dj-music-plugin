import { Skeleton } from '@/components/ui/skeleton'
import { PageShellSkeleton, CardGridSkeleton } from '@/components/skeletons'

export default function CurationLoading() {
  return (
    <PageShellSkeleton>
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-4 w-96" />
      <CardGridSkeleton cards={3} bodyHeight="h-20" />
      <CardGridSkeleton cards={1} bodyHeight="h-20" />
      <CardGridSkeleton cards={2} bodyHeight="h-20" />
    </PageShellSkeleton>
  )
}
