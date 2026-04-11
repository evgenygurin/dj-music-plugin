'use client'

import { Blend } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

/**
 * Direct-access Mix popover. Shown in MediumPlayerBar (Layer 2) so the
 * user can flip crossfade on/off and change bar length without diving
 * into the ControlPanel.
 *
 * Default: ON / 32 bars / auto duration from current BPM.
 */
export function MixButton() {
  const { audio } = usePlayer()
  const enabled = audio.mixEnabled
  const bars = audio.crossfadeBars
  const seconds = audio.crossfadeSeconds
  const masterTempo = audio.masterTempoBpm

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="sm"
          variant={enabled ? 'default' : 'outline'}
          className="h-8 gap-1.5 rounded-full px-3 text-[11px] font-medium"
          aria-label="Mix settings"
          title={enabled ? `Mix: ${bars} bars (~${Math.round(seconds)}s)` : 'Mix: off'}
        >
          <Blend className="size-3.5" />
          <span>{enabled ? `${bars} bars` : 'Off'}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" sideOffset={12} className="w-72 p-4">
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-0.5">
              <div className="text-sm font-semibold leading-none">Crossfade mix</div>
              <div className="text-[11px] text-muted-foreground">
                {enabled
                  ? `Auto · ~${Math.round(seconds)}s @ ${masterTempo?.toFixed(1) ?? 'track'} BPM`
                  : 'Snap transitions'}
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={enabled}
              aria-label="Toggle mixing"
              onClick={() => audio.toggleMixEnabled()}
              className={cn(
                'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors',
                enabled ? 'bg-primary' : 'bg-muted',
              )}
            >
              <span
                className={cn(
                  'inline-block size-4 transform rounded-full bg-background shadow transition-transform',
                  enabled ? 'translate-x-[18px]' : 'translate-x-0.5',
                )}
              />
            </button>
          </div>

          <div>
            <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
              Length
            </div>
            <div className="grid grid-cols-5 gap-1.5">
              {[4, 8, 16, 32, 64].map((b) => (
                <Button
                  key={b}
                  size="sm"
                  variant={bars === b ? 'default' : 'outline'}
                  className="h-8 px-0 text-xs"
                  disabled={!enabled}
                  onClick={() => audio.setCrossfadeBars(b)}
                >
                  {b}
                </Button>
              ))}
            </div>
            <div className="mt-1.5 text-[10px] text-muted-foreground">1 bar = 4 beats</div>
          </div>

          <div>
            <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
              Master Tempo
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-2.5 text-xs"
                onClick={() => audio.nudgeMasterTempoBpm(-0.5)}
                disabled={masterTempo === null}
              >
                -0.5
              </Button>
              <div className="flex-1 rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-center">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  Session
                </div>
                <div className="font-mono text-sm tabular-nums">
                  {masterTempo !== null ? `${masterTempo.toFixed(1)} BPM` : '—'}
                </div>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-2.5 text-xs"
                onClick={() => audio.nudgeMasterTempoBpm(0.5)}
                disabled={masterTempo === null}
              >
                +0.5
              </Button>
            </div>
            <div className="mt-1.5 flex gap-1.5">
              <Button
                size="sm"
                variant="outline"
                className="h-8 flex-1 text-xs"
                onClick={() => audio.resetMasterTempoToCurrentTrack()}
                disabled={audio.current?.bpm == null}
              >
                From current track
              </Button>
            </div>
            <div className="mt-1.5 text-[10px] text-muted-foreground">
              Locked session tempo. Incoming tracks follow this BPM instead of dragging the mix.
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
