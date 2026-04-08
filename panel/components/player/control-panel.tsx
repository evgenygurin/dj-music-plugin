// panel/components/player/control-panel.tsx
'use client'

import { IconX } from '@tabler/icons-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'
import type { SetTemplate } from '@/lib/set-narrative/types'

const COMPATIBILITY_MODE_NAME = '__compatibility__'

const MODE_ICONS: Record<string, string> = {
  warm_up_30: '☀',
  classic_60: '✨',
  peak_hour_60: '🔥',
  roller_90: '🌊',
  progressive_120: '📈',
  wave_120: '🌊',
  closing_60: '🌙',
  full_library: '∞',
}

function SparklineArc({ template }: { template: SetTemplate }) {
  // Tiny 80×16 svg showing energy_lufs across slots
  const values = template.slots.map((s) => s.energyLufs)
  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const range = Math.max(1, maxV - minV)
  const points = template.slots
    .map((s, i) => {
      const x = (i / Math.max(1, template.slots.length - 1)) * 76 + 2
      const y = 14 - ((s.energyLufs - minV) / range) * 12
      return `${x},${y}`
    })
    .join(' ')
  return (
    <svg width={80} height={16} className="opacity-70">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.5} />
    </svg>
  )
}

export function ControlPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const player = usePlayer()
  const { set, audio } = player

  if (!open) return null

  const activeName = set.active && set.template ? set.template.name : COMPATIBILITY_MODE_NAME

  const selectMode = (name: string) => {
    if (name === COMPATIBILITY_MODE_NAME) {
      set.stopSet()
      onClose()
      return
    }
    set.startTemplate(name)
    onClose()
  }

  return (
    <div className="fixed bottom-[80px] left-0 right-0 z-50 pointer-events-none">
      <div className="mx-auto w-full max-w-screen-2xl px-4 lg:px-6 pointer-events-auto">
        <div className="rounded-lg border border-border/60 bg-background shadow-xl">
          <div className="flex items-center justify-between border-b border-border/60 px-4 py-2">
            <span className="text-sm font-medium">Set mode</span>
            <button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1 hover:bg-muted/40">
              <IconX className="size-4" />
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto p-2">
            <button
              type="button"
              onClick={() => selectMode(COMPATIBILITY_MODE_NAME)}
              className={cn(
                'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted/40',
                activeName === COMPATIBILITY_MODE_NAME && 'bg-primary/10 border border-primary/40',
              )}
            >
              <span className="text-base">∞</span>
              <div className="flex-1">
                <div className="font-medium">Compatibility</div>
                <div className="text-xs text-muted-foreground">Endless · next compatible track</div>
              </div>
            </button>

            {set.templates.map((tpl) => (
              <button
                key={tpl.name}
                type="button"
                onClick={() => selectMode(tpl.name)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted/40',
                  activeName === tpl.name && 'bg-primary/10 border border-primary/40',
                )}
              >
                <span className="text-base">{MODE_ICONS[tpl.name] ?? '✨'}</span>
                <div className="flex-1">
                  <div className="font-medium">{humanName(tpl)}</div>
                  <div className="text-xs text-muted-foreground">{tpl.description}</div>
                </div>
                <SparklineArc template={tpl} />
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
            <span>Mix length:</span>
            {[4, 8, 16, 32, 64].map((b) => (
              <Button
                key={b}
                size="sm"
                variant={audio.crossfadeBars === b ? 'default' : 'outline'}
                className="h-6 px-2 text-[10px]"
                onClick={() => audio.setCrossfadeBars?.(b)}
              >
                {b}
              </Button>
            ))}
            <span className="ml-2 tabular-nums">
              ~{Math.round(audio.crossfadeSeconds)}s
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function humanName(tpl: SetTemplate): string {
  const parts = tpl.name.split('_')
  const last = parts[parts.length - 1]
  if (/^\d+$/.test(last)) {
    const rest = parts.slice(0, -1).join(' ')
    return `${capitalise(rest)} ${last}`
  }
  return capitalise(tpl.name.replaceAll('_', ' '))
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}
