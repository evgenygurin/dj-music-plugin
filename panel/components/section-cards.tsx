import {
  IconMusic,
  IconWaveSine,
  IconPlaylist,
  IconDownload,
  IconStar,
} from '@tabler/icons-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import type { LibraryStats } from '@/lib/queries/dashboard'

export function SectionCards({ stats }: { stats: LibraryStats }) {
  const coveragePct =
    stats.totalTracks > 0
      ? Math.round((stats.analyzedTracks / stats.totalTracks) * 100)
      : 0

  const cards = [
    {
      title: 'Total Tracks',
      value: stats.totalTracks.toLocaleString(),
      description: 'in library',
      icon: IconMusic,
      badge: null,
    },
    {
      title: 'Analyzed',
      value: stats.analyzedTracks.toLocaleString(),
      description: 'audio features',
      icon: IconWaveSine,
      badge: `${coveragePct}%`,
    },
    {
      title: 'DJ Sets',
      value: stats.totalSets.toLocaleString(),
      description: 'created',
      icon: IconPlaylist,
      badge: null,
    },
    {
      title: 'Library Files',
      value: stats.libraryItems.toLocaleString(),
      description: 'downloaded',
      icon: IconDownload,
      badge: null,
    },
    {
      title: 'Set Quality',
      value: stats.avgSetQuality?.toFixed(2) ?? '—',
      description: stats.avgSetQuality ? 'avg score' : 'no sets scored',
      icon: IconStar,
      badge: null,
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => (
        <Card
          key={card.title}
          className="relative overflow-hidden border-border/50 transition-colors hover:border-primary/30"
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
            <card.icon className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold tracking-tight">
                {card.value}
              </span>
              {card.badge && (
                <Badge
                  variant="secondary"
                  className="bg-primary/10 text-primary text-xs"
                >
                  {card.badge}
                </Badge>
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {card.description}
            </p>
          </CardContent>
          {/* Subtle glow accent on bottom border */}
          <div className="absolute bottom-0 left-0 h-[2px] w-full bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
        </Card>
      ))}
    </div>
  )
}
