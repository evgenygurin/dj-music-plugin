import { Skeleton } from '@/components/ui/skeleton'
import { PageShellSkeleton, RowsSkeleton } from '@/components/skeletons'

export default function LibraryLoading() {
  return (
    <PageShellSkeleton>
      <div className="flex items-center gap-2">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-9 w-20" />
      </div>
      <Skeleton className="h-10 w-full" />
      <RowsSkeleton count={8} />
      <div className="flex justify-between">
        <Skeleton className="h-4 w-24" />
        <div className="flex gap-2">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-9 w-16" />
        </div>
      </div>
    </PageShellSkeleton>
  )
}
