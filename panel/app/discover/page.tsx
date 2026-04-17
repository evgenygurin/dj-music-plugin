import { PageShell, PageHeader } from '@/components/page-shell'
import { fetchToolSchema } from '@/lib/mcp-client'
import { YmSearch } from './ym-search'
import { DiscoverActions } from './discover-actions'

export const dynamic = 'force-dynamic'

export default async function DiscoverPage() {
  const [importSchema, downloadSchema, similarSchema, expandSchema] = await Promise.all([
    fetchToolSchema('import_tracks'),
    fetchToolSchema('download_tracks'),
    fetchToolSchema('find_similar_tracks'),
    fetchToolSchema('expand_playlist_ym'),
  ])

  return (
    <PageShell title="Discover">
      <PageHeader
        title="Discover"
        description="Search Yandex Music, import tracks, find similar artists, and expand playlists."
      />

      <YmSearch />

      <DiscoverActions
        importSchema={importSchema ?? {}}
        downloadSchema={downloadSchema ?? {}}
        similarSchema={similarSchema ?? {}}
        expandSchema={expandSchema ?? {}}
      />
    </PageShell>
  )
}
