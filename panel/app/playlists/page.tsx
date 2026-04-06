import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SiteHeader } from '@/components/site-header'
import { getPlaylistList } from '@/lib/queries/playlists'
import type { PlaylistListItem } from '@/lib/queries/playlists'

export const revalidate = 60

function PlaylistCard({ playlist, indent }: { playlist: PlaylistListItem; indent: number }) {
  return (
    <div style={{ marginLeft: `${indent * 24}px` }}>
      <Link href={`/playlists/${playlist.id}`}>
        <Card className="mb-2 transition-colors hover:bg-muted/50 cursor-pointer">
          <CardHeader className="py-3 px-4">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-sm font-medium line-clamp-1">{playlist.name}</CardTitle>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Badge variant="secondary" className="text-xs tabular-nums">
                  {playlist.trackCount} tracks
                </Badge>
                {playlist.source_of_truth && (
                  <Badge variant="outline" className="text-xs">
                    {playlist.source_of_truth}
                  </Badge>
                )}
                {playlist.source_app && (
                  <Badge variant="outline" className="text-xs text-muted-foreground">
                    {playlist.source_app}
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>
        </Card>
      </Link>
    </div>
  )
}

export default async function PlaylistsPage() {
  const playlists = await getPlaylistList()

  // Build tree structure
  const roots = playlists.filter((p) => p.parent_id === null)
  const childrenByParent = new Map<number, PlaylistListItem[]>()
  for (const p of playlists) {
    if (p.parent_id !== null) {
      const children = childrenByParent.get(p.parent_id) ?? []
      children.push(p)
      childrenByParent.set(p.parent_id, children)
    }
  }

  function renderTree(items: PlaylistListItem[], depth: number): React.ReactNode[] {
    return items.flatMap((item) => {
      const children = childrenByParent.get(item.id) ?? []
      return [
        <PlaylistCard key={item.id} playlist={item} indent={depth} />,
        ...renderTree(children, depth + 1),
      ]
    })
  }

  return (
    <>
      <SiteHeader title="Playlists" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {playlists.length === 0 ? (
          <p className="text-muted-foreground">No playlists found.</p>
        ) : (
          <div>{renderTree(roots, 0)}</div>
        )}
      </div>
    </>
  )
}
