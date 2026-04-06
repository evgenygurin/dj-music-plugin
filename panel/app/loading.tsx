import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

export default function DashboardLoading() {
  return (
    <>
      <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4 lg:px-6">
        <Skeleton className="h-7 w-7 rounded-md" />
        <Skeleton className="mx-2 h-4 w-px" />
        <Skeleton className="h-4 w-24" />
      </header>
      <div className="flex flex-1 flex-col">
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
          {/* Section cards skeleton */}
          <div className="grid grid-cols-1 gap-4 px-4 lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-8 w-16" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-4 w-32" />
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Charts skeleton */}
          <div className="grid gap-4 px-4 md:grid-cols-2 lg:px-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardHeader>
                  <Skeleton className="h-5 w-32" />
                  <Skeleton className="h-4 w-48" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-[220px] w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
