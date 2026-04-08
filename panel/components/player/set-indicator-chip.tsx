// panel/components/player/set-indicator-chip.tsx
'use client'

import { IconSparkles } from '@tabler/icons-react'
import { cn } from '@/lib/utils'
import { usePlayer } from './player-provider'

function formatMmSs(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function SetIndicatorChip({ onOpen }: { onOpen: () => void }) {
  const { set } = usePlayer()
  if (!set.active || !set.template) return null

  const totalSec = set.template.durationMin * 60
  const isSearching = set.upcoming.length === 0

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/15 px-2.5 py-1',
        'text-[11px] text-primary hover:bg-primary/25 transition-colors',
      )}
      aria-label="Open set planner"
      title={`Set: ${set.template.name}`}
    >
      <IconSparkles className="size-3" />
      <span className="font-medium">{set.template.name}</span>
      <span className="tabular-nums">
        {formatMmSs(set.elapsedSec)}/{formatMmSs(totalSec)}
      </span>
      {isSearching && (
        <span className="size-1.5 animate-pulse rounded-full bg-primary" />
      )}
    </button>
  )
}
