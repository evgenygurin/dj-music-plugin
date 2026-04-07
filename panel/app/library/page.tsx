import { PageShell } from '@/components/page-shell'
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
    <PageShell title="Library">
      <LibraryTable
        initialTracks={result.tracks}
        total={result.total}
        currentPage={page}
        currentSearch={search ?? ''}
        currentSortBy={sortBy}
        currentSortDir={sortDir}
      />
    </PageShell>
  )
}
