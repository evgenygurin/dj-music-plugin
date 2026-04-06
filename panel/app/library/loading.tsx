import { Skeleton } from '@/components/ui/skeleton'

export default function LibraryLoading() {
  return (
    <>
      <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4 lg:px-6">
        <Skeleton className="h-7 w-7 rounded-md" />
        <Skeleton className="mx-2 h-4 w-px" />
        <Skeleton className="h-4 w-16" />
      </header>
      <div className="flex flex-1 flex-col">
        <div className="flex flex-col gap-4 px-4 py-4 md:gap-6 md:py-6 lg:px-6">
          {/* Search bar */}
          <div className="flex items-center gap-2">
            <Skeleton className="h-9 w-64" />
            <Skeleton className="h-9 w-20" />
          </div>

          {/* Table header */}
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>

          {/* Pagination */}
          <div className="flex justify-between">
            <Skeleton className="h-4 w-24" />
            <div className="flex gap-2">
              <Skeleton className="h-9 w-20" />
              <Skeleton className="h-9 w-16" />
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
