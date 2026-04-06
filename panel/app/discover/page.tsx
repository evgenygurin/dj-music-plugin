import { SiteHeader } from '@/components/site-header'
import { fetchToolSchema } from '@/lib/mcp-client'
import { YmSearch } from './ym-search'
import { DiscoverActions } from './discover-actions'

export default async function DiscoverPage() {
  const [importSchema, downloadSchema, similarSchema, expandSchema] = await Promise.all([
    fetchToolSchema('import_tracks'),
    fetchToolSchema('download_tracks'),
    fetchToolSchema('find_similar_tracks'),
    fetchToolSchema('expand_playlist_ym'),
  ])

  return (
    <>
      <SiteHeader title="Discover" />
      <div className="flex flex-1 flex-col gap-6 py-6 px-4 lg:px-6">
        <div>
          <h1 className="text-lg font-semibold">Discover</h1>
          <p className="text-sm text-muted-foreground">
            Search Yandex Music, import tracks, find similar artists, and expand playlists.
          </p>
        </div>

        <YmSearch />

        <DiscoverActions
          importSchema={importSchema ?? {}}
          downloadSchema={downloadSchema ?? {}}
          similarSchema={similarSchema ?? {}}
          expandSchema={expandSchema ?? {}}
        />
      </div>
    </>
  )
}
