import Link from 'next/link'
import { IconMusic } from '@tabler/icons-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { PageShell, PageHeader } from '@/components/page-shell'
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from '@/components/ui/empty'
import { getPlaylistList } from '@/lib/queries/playlists'
import type { PlaylistListItem } from '@/lib/queries/playlists'

export const revalidate = 60

function PlaylistCard({ playlist, indent }: { playlist: PlaylistListItem; indent: number }) {
  const sourceBadge = playlist.source_of_truth ?? playlist.source_app

  return (
    <div style={{ marginLeft: `${indent * 20}px` }}>
      <Link href={`/playlists/${playlist.id}`}>
        <Card className="mb-2 transition-colors hover:bg-muted/50 cursor-pointer">
          <CardHeader className="py-3 px-4">
            <div className="flex items-center justify-between gap-2 min-w-0">
              <div className="flex items-center gap-2 min-w-0">
                {indent > 0 && (
                  <div className="h-px w-3 bg-border flex-shrink-0" />
                )}
                <CardTitle className="text-sm font-medium line-clamp-1">
                  {playlist.name}
                </CardTitle>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <Badge variant="secondary" className="text-xs tabular-nums">
                  {playlist.trackCount} tracks
                </Badge>
                {sourceBadge && (
                  <Badge variant="outline" className="text-xs capitalize">
                    {sourceBadge}
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
    <PageShell title="Playlists">
      <PageHeader
        title="Playlists"
        badge={
          playlists.length > 0 && (
            <Badge variant="secondary" className="tabular-nums">
              {playlists.length}
            </Badge>
          )
        }
      />

      {playlists.length === 0 ? (
        <Empty className="border min-h-[200px]">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconMusic />
            </EmptyMedia>
            <EmptyTitle>No playlists yet</EmptyTitle>
            <EmptyDescription>
              Import tracks and create playlists to get started.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div>{renderTree(roots, 0)}</div>
      )}
    </PageShell>
  )
}
