'use client'

import {
  Activity,
  Disc3,
  Flame,
  Infinity as InfinityIcon,
  Moon,
  Sparkles,
  Sunrise,
  TrendingUp,
  Waves,
  X,
  type LucideIcon,
} from 'lucide-react'

import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'
import type { SetTemplate } from '@/lib/set-narrative/types'

const COMPATIBILITY_MODE_NAME = '__compatibility__'

const MODE_ICONS: Record<string, LucideIcon> = {
  warm_up_30: Sunrise,
  classic_60: Disc3,
  peak_hour_60: Flame,
  roller_90: Activity,
  progressive_120: TrendingUp,
  wave_120: Waves,
  closing_60: Moon,
  full_library: InfinityIcon,
}

function SparklineArc({ template }: { template: SetTemplate }) {
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

/**
 * Layer 3 — floating Set-mode picker. Opens above the bar at
 * fixed bottom-[88px] center. Click-outside detection via a
 * transparent full-viewport overlay sibling.
 */
export function ControlPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { set } = usePlayer()
  if (!open) return null

  const activeName = set.active && set.template ? set.template.name : COMPATIBILITY_MODE_NAME

  const selectMode = (name: string) => {
    if (name === COMPATIBILITY_MODE_NAME) {
      set.stopSet()
    } else {
      set.startTemplate(name)
    }
    onClose()
  }

  return (
    <>
      {/* Click-outside overlay */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className="fixed bottom-[88px] left-1/2 z-50 w-[480px] max-w-[calc(100vw-2rem)] -translate-x-1/2"
        role="dialog"
        aria-label="Set mode picker"
      >
        <div className="rounded-lg border border-border/60 bg-background shadow-xl">
          <div className="flex items-center justify-between border-b border-border/60 px-4 py-2">
            <span className="text-sm font-medium">Set mode</span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-md p-1 hover:bg-muted/40"
            >
              <X className="size-4" />
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto p-2">
            <button
              type="button"
              onClick={() => selectMode(COMPATIBILITY_MODE_NAME)}
              className={cn(
                'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted/40',
                activeName === COMPATIBILITY_MODE_NAME &&
                  'border border-primary/40 bg-primary/10',
              )}
            >
              <InfinityIcon className="size-4 shrink-0 text-muted-foreground" />
              <div className="flex-1">
                <div className="font-medium">Compatibility</div>
                <div className="text-xs text-muted-foreground">
                  Endless — next compatible track
                </div>
              </div>
            </button>

            {set.templates.map((tpl) => {
              const Icon = MODE_ICONS[tpl.name] ?? Sparkles
              return (
                <button
                  key={tpl.name}
                  type="button"
                  onClick={() => selectMode(tpl.name)}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted/40',
                    activeName === tpl.name && 'border border-primary/40 bg-primary/10',
                  )}
                >
                  <Icon className="size-4 shrink-0 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="font-medium">{humanName(tpl)}</div>
                    <div className="text-xs text-muted-foreground">{tpl.description}</div>
                  </div>
                  <SparklineArc template={tpl} />
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </>
  )
}
