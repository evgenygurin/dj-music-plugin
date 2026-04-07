import { Skeleton } from '@/components/ui/skeleton'
import { PageShellSkeleton } from '@/components/skeletons'

export default function PlaylistsLoading() {
  return (
    <PageShellSkeleton>
      <Skeleton className="h-8 w-32" />
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-lg" />
        ))}
      </div>
    </PageShellSkeleton>
  )
}
