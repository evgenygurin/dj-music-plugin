import { Badge } from '@/components/ui/badge'
import { SUBGENRE_COLORS, SUBGENRE_LABELS } from '@/lib/constants'

export function MoodBadge({ mood }: { mood: string | null }) {
  if (!mood) return <span className="text-muted-foreground">—</span>

  const color = SUBGENRE_COLORS[mood] ?? '#888'
  const label = SUBGENRE_LABELS[mood] ?? mood

  return (
    <Badge
      variant="outline"
      style={{ borderColor: color, color }}
      className="text-xs"
    >
      {label}
    </Badge>
  )
}
