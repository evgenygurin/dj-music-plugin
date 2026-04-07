import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

/**
 * Mirrors `<SiteHeader>` so that suspense fallbacks reserve the right amount
 * of space and avoid layout shift when the real header mounts.
 */
export function SiteHeaderSkeleton({ withBreadcrumb = false }: { withBreadcrumb?: boolean }) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4 lg:px-6">
      <Skeleton className="h-7 w-7 rounded-md" />
      <Skeleton className="mx-2 h-4 w-px" />
      <Skeleton className="h-4 w-24" />
      {withBreadcrumb && (
        <>
          <Skeleton className="mx-1 h-3 w-3" />
          <Skeleton className="h-4 w-32" />
        </>
      )}
    </header>
  )
}

/**
 * Mirrors `<PageShell>` body for `loading.tsx` use. Combine with
 * `<SiteHeaderSkeleton>` for a complete page-level fallback.
 */
export function PageShellSkeleton({
  withBreadcrumb = false,
  children,
}: {
  withBreadcrumb?: boolean
  children: React.ReactNode
}) {
  return (
    <>
      <SiteHeaderSkeleton withBreadcrumb={withBreadcrumb} />
      <div className="flex flex-1 flex-col">
        <div className="@container/main flex flex-1 flex-col gap-2">
          <div className="flex flex-col gap-4 px-4 py-4 md:gap-6 md:py-6 lg:px-6">
            {children}
          </div>
        </div>
      </div>
    </>
  )
}

/** A row of N skeleton lines, useful for table-like loading states. */
export function RowsSkeleton({ count = 8, height = 'h-12' }: { count?: number; height?: string }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className={`w-full ${height}`} />
      ))}
    </div>
  )
}

/** A grid of card skeletons. */
export function CardGridSkeleton({
  cards = 4,
  cols = 'md:grid-cols-2',
  bodyHeight = 'h-[180px]',
}: {
  cards?: number
  cols?: string
  bodyHeight?: string
}) {
  return (
    <div className={`grid gap-4 ${cols}`}>
      {Array.from({ length: cards }).map((_, i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <Skeleton className={`w-full ${bodyHeight}`} />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
