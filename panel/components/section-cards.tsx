import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import type { LibraryStats } from '@/lib/queries/dashboard'

export function SectionCards({ stats }: { stats: LibraryStats }) {
  const cards = [
    { title: 'Total Tracks', value: stats.totalTracks.toLocaleString(), description: 'in library' },
    {
      title: 'Analyzed',
      value: stats.analyzedTracks.toLocaleString(),
      description: `${stats.totalTracks > 0 ? Math.round((stats.analyzedTracks / stats.totalTracks) * 100) : 0}% coverage`,
    },
    { title: 'DJ Sets', value: stats.totalSets.toLocaleString(), description: 'created' },
    { title: 'Library Files', value: stats.libraryItems.toLocaleString(), description: 'downloaded' },
    {
      title: 'Avg Set Quality',
      value: stats.avgSetQuality?.toFixed(2) ?? '—',
      description: stats.avgSetQuality ? 'score' : 'no sets scored',
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{card.value}</div>
            <p className="text-xs text-muted-foreground">{card.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
