// panel/components/player/set-planner-drawer.tsx
'use client'

import { IconX } from '@tabler/icons-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { EnergyArcGraph } from './energy-arc-graph'
import { SlotTimeline } from './slot-timeline'
import { usePlayer } from './player-provider'

export function SetPlannerDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const player = usePlayer()
  const { set } = player

  if (!open || !set.active || !set.template || !set.currentSlot) return null

  const totalMin = set.template.durationMin
  const elapsedMin = Math.floor(set.elapsedSec / 60)
  const elapsedSec = set.elapsedSec % 60
  const slotLabel = set.template.slots[set.currentSlot.index].targetMood ?? '—'

  return (
    <div
      role="dialog"
      aria-label="Set planner"
      className={cn(
        'fixed inset-x-0 bottom-0 z-50 max-h-[75vh] overflow-hidden',
        'border-t border-border/60 bg-background shadow-2xl',
        'flex flex-col',
      )}
    >
      <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <div>
          <div className="text-sm font-semibold">{set.template.name}</div>
          <div className="text-xs text-muted-foreground">
            {elapsedMin}:{String(elapsedSec).padStart(2, '0')} / {totalMin}:00 · slot{' '}
            {set.currentSlot.index + 1}/{set.template.slots.length} ({slotLabel})
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => set.stopSet()}>
            Stop set
          </Button>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1 hover:bg-muted/40">
            <IconX className="size-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
            Energy arc
          </h3>
          <EnergyArcGraph
            template={set.template}
            elapsedSec={set.elapsedSec}
            history={set.history}
          />
        </section>

        <section>
          <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">Slots</h3>
          <SlotTimeline template={set.template} current={set.currentSlot} />
        </section>

        <section>
          <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
            Upcoming candidates for slot {set.currentSlot.index + 1}
          </h3>
          {set.upcoming.length === 0 && (
            <p className="text-sm text-muted-foreground">Searching…</p>
          )}
          <ul className="space-y-1.5">
            {set.upcoming.slice(0, 5).map((c, i) => (
              <li
                key={c.trackId}
                className={cn(
                  'flex items-center justify-between rounded-md border border-border/40 px-3 py-2 text-sm hover:bg-muted/20 cursor-pointer',
                  i === 0 && 'border-primary/60 bg-primary/10',
                )}
                onClick={() =>
                  set.overridePick({
                    id: c.trackId,
                    title: c.title,
                    artists: c.artists,
                    durationMs: null,
                    bpm: c.bpm,
                    camelot: c.camelot,
                    mood: c.mood,
                  })
                }
                role="button"
                tabIndex={0}
              >
                <div className="flex-1 truncate">
                  <div className="flex items-center gap-2">
                    {i === 0 && <span>▶</span>}
                    <span className="font-medium truncate">{c.title}</span>
                    <span className="text-xs text-muted-foreground">
                      {c.bpm?.toFixed(1) ?? '—'} BPM · {c.camelot ?? '—'}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">{c.rationale}</div>
                </div>
                <div className="text-sm font-mono tabular-nums text-primary">
                  {c.combinedScore.toFixed(2)}
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void set.rebuildRemainder()}>
            Rebuild remainder
          </Button>
          <Button variant="outline" size="sm" onClick={() => set.skipSlot()}>
            Skip to next slot
          </Button>
        </section>
      </div>
    </div>
  )
}
