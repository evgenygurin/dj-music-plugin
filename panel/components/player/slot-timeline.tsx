// panel/components/player/slot-timeline.tsx
'use client'

import { Check, Play } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { CurrentSlot, SetTemplate } from '@/lib/set-narrative/types'

interface Props {
  template: SetTemplate
  current: CurrentSlot
}

export function SlotTimeline({ template, current }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {template.slots.map((slot, i) => {
        const status =
          i < current.index ? 'played' : i === current.index ? 'playing' : 'pending'
        return (
          <div
            key={i}
            className={cn(
              'min-w-[88px] rounded-md border px-3 py-2 text-xs',
              status === 'played' && 'border-muted-foreground/30 bg-muted/20 opacity-60',
              status === 'playing' && 'border-primary/60 bg-primary/10',
              status === 'pending' && 'border-border/60',
            )}
            title={`${slot.targetMood ?? ''} · ${slot.bpmMin}-${slot.bpmMax} BPM · ${slot.energyLufs} LUFS`}
          >
            <div className="font-mono">{i + 1}</div>
            <div className="truncate font-medium">{slot.targetMood ?? '—'}</div>
            <div className="text-[10px] text-muted-foreground">
              {Math.round((slot.durationMs / 1000 / 60) * 10) / 10} min
            </div>
            {status === 'playing' && (
              <div className="mt-1 flex items-center gap-1 text-[10px] text-primary">
                <Play className="size-2.5 fill-primary" />
                playing
              </div>
            )}
            {status === 'played' && (
              <Check className="mt-1 size-2.5 text-muted-foreground" />
            )}
          </div>
        )
      })}
    </div>
  )
}
