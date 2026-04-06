import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

export default function TrackDetailLoading() {
  return (
    <>
      <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4 lg:px-6">
        <Skeleton className="h-7 w-7 rounded-md" />
        <Skeleton className="mx-2 h-4 w-px" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-3 w-3" />
        <Skeleton className="h-4 w-32" />
      </header>
      <div className="flex flex-1 flex-col">
        <div className="flex flex-col gap-4 px-4 py-4 md:gap-6 md:py-6 lg:px-6">
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-32" />
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-6 w-16 rounded-full" />
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-[200px] w-full" />
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
