import { SiteHeader } from '@/components/site-header'
import { getTrackList } from '@/lib/queries/tracks'
import { LibraryTable } from './library-table'

export const revalidate = 60

interface LibraryPageProps {
  searchParams: Promise<Record<string, string | undefined>>
}

export default async function LibraryPage({ searchParams }: LibraryPageProps) {
  const params = await searchParams

  const page = params.page ? parseInt(params.page, 10) : 1
  const sortBy = (params.sortBy as 'title' | 'bpm' | 'integrated_lufs' | 'energy_mean' | 'duration_ms') ?? 'title'
  const sortDir = (params.sortDir as 'asc' | 'desc') ?? 'asc'
  const bpmMin = params.bpmMin ? parseFloat(params.bpmMin) : undefined
  const bpmMax = params.bpmMax ? parseFloat(params.bpmMax) : undefined
  const mood = params.mood ?? undefined
  const search = params.search ?? undefined

  const result = await getTrackList({ page, sortBy, sortDir, bpmMin, bpmMax, mood, search })

  return (
    <>
      <SiteHeader title="Library" />
      <div className="flex flex-1 flex-col">
        <div className="@container/main flex flex-1 flex-col gap-2">
          <div className="flex flex-col gap-4 px-4 py-4 md:gap-6 md:py-6 lg:px-6">
            <LibraryTable
          initialTracks={result.tracks}
          total={result.total}
          currentPage={page}
          currentSearch={search ?? ''}
          currentSortBy={sortBy}
          currentSortDir={sortDir}
            />
          </div>
        </div>
      </div>
    </>
  )
}
