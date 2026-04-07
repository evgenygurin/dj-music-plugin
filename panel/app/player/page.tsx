import { SiteHeader } from '@/components/site-header'
import { getTrackDetail, getTrackList } from '@/lib/queries/tracks'
import { DjPlayer } from '@/components/dj-player'

export const revalidate = 0

interface PlayerPageProps {
  searchParams: Promise<{
    deck1?: string
    deck2?: string
    search?: string
    page?: string
  }>
}

export default async function PlayerPage({ searchParams }: PlayerPageProps) {
  const params = await searchParams
  const deck1Id = params.deck1 ? parseInt(params.deck1) : null
  const deck2Id = params.deck2 ? parseInt(params.deck2) : null

  const [deck1Track, deck2Track, libraryResult] = await Promise.all([
    deck1Id ? getTrackDetail(deck1Id) : Promise.resolve(null),
    deck2Id ? getTrackDetail(deck2Id) : Promise.resolve(null),
    getTrackList({
      page: params.page ? parseInt(params.page) : 1,
      search: params.search,
      pageSize: 50,
    }),
  ])

  return (
    <>
      <SiteHeader title="DJ Player" />
      <DjPlayer
        deck1={deck1Track}
        deck2={deck2Track}
        library={libraryResult.tracks}
        libraryTotal={libraryResult.total}
        currentPage={params.page ? parseInt(params.page) : 1}
        currentSearch={params.search ?? ''}
      />
    </>
  )
}
