import { Skeleton } from '@/components/ui/skeleton'

export default function PlaylistsLoading() {
  return (
    <>
      <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4 lg:px-6">
        <Skeleton className="h-7 w-7 rounded-md" />
        <Skeleton className="mx-2 h-4 w-px" />
        <Skeleton className="h-4 w-20" />
      </header>
      <div className="flex flex-1 flex-col">
        <div className="flex flex-col gap-4 px-4 py-4 md:gap-6 md:py-6 lg:px-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      </div>
    </>
  )
}
