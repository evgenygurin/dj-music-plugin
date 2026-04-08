'use client'

import { Sparkles } from 'lucide-react'

import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/**
 * Small reusable Set chip — shown above the bar whenever a set is
 * active. Click opens the SetPlannerDrawer (Layer 4).
 */
export function SetIndicatorChip({ onOpen }: { onOpen: () => void }) {
  const { set } = usePlayer()
  if (!set.active || !set.template) return null

  const isSearching = set.upcoming.length === 0

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/15 px-2.5 py-1',
        'text-[11px] text-primary transition-colors hover:bg-primary/25',
      )}
      aria-label="Open set planner"
      title={`Set: ${set.template.name}`}
    >
      <Sparkles className="size-3" />
      <span className="font-medium">{set.template.name}</span>
      <span className="tabular-nums">{formatTime(set.elapsedSec)}</span>
      {isSearching && <span className="size-1.5 animate-pulse rounded-full bg-primary" />}
    </button>
  )
}
