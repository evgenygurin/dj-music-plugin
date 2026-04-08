'use client'

import { Play } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'

import { EnergyArcGraph } from './energy-arc-graph'
import { SlotTimeline } from './slot-timeline'
import { usePlayer } from './player-provider'

interface Props {
  open: boolean
  onClose: () => void
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/**
 * Layer 4 — full Set planner drawer. Energy arc graph, slot timeline,
 * upcoming pick override list, and rebuild/skip actions.
 */
export function SetPlannerDrawer({ open, onClose }: Props) {
  const { set } = usePlayer()

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="bottom" className="flex h-[75vh] flex-col">
        {set.active && set.template && set.currentSlot ? (
          <>
            <SheetHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <SheetTitle>{set.template.name}</SheetTitle>
                  <div className="text-xs text-muted-foreground">
                    {formatTime(set.elapsedSec)} / {set.template.durationMin}:00 · slot{' '}
                    {set.currentSlot.index + 1}/{set.template.slots.length} (
                    {set.template.slots[set.currentSlot.index].targetMood ?? '—'})
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    set.stopSet()
                    onClose()
                  }}
                >
                  Stop set
                </Button>
              </div>
            </SheetHeader>

            <div className="flex-1 space-y-6 overflow-y-auto p-4">
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
                <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                  Slots
                </h3>
                <SlotTimeline template={set.template} current={set.currentSlot} />
              </section>

              <section>
                <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                  Upcoming
                </h3>
                {set.upcoming.length === 0 && (
                  <p className="text-sm text-muted-foreground">Searching…</p>
                )}
                <ul className="space-y-1.5">
                  {set.upcoming.slice(0, 5).map((c, i) => (
                    <li
                      key={c.trackId}
                      className={cn(
                        'flex cursor-pointer items-center justify-between rounded-md border border-border/40 px-3 py-2 text-sm hover:bg-muted/20',
                        i === 0 && 'border-primary/60 bg-primary/10',
                      )}
                      onClick={() =>
                        set.overridePick({
                          id: c.trackId,
                          title: c.title,
                          artists: c.artists,
                          bpm: c.bpm,
                          camelot: c.camelot,
                          mood: c.mood,
                          durationMs: null,
                        })
                      }
                      role="button"
                      tabIndex={0}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          {i === 0 && (
                            <Play className="size-3 shrink-0 fill-primary text-primary" />
                          )}
                          <span className="truncate font-medium">{c.title}</span>
                          <span className="text-xs text-muted-foreground">
                            {c.bpm?.toFixed(1) ?? '—'} BPM · {c.camelot ?? '—'}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground">{c.rationale}</div>
                      </div>
                      <div className="font-mono text-sm tabular-nums text-primary">
                        {c.combinedScore.toFixed(2)}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void set.rebuildRemainder()}
                >
                  Rebuild remainder
                </Button>
                <Button variant="outline" size="sm" onClick={() => set.skipSlot()}>
                  Skip to next slot
                </Button>
              </section>
            </div>
          </>
        ) : (
          <>
            <SheetHeader>
              <SheetTitle>Set planner</SheetTitle>
            </SheetHeader>
            <div className="flex flex-1 items-center justify-center p-8 text-sm text-muted-foreground">
              No active set — pick a mode from the player bar to begin.
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
