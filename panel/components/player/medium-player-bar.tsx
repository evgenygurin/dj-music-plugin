// panel/components/player/medium-player-bar.tsx
'use client'

import {
  IconAdjustmentsHorizontal,
  IconChevronDown,
  IconLoader2,
  IconMusic,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
  IconPlayerStopFilled,
  IconSparkles,
  IconVolume,
  IconVolume2,
  IconVolumeOff,
} from '@tabler/icons-react'

import { MoodBadge } from '@/components/mood-badge'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function MediumPlayerBar({ onOpenControlPanel }: { onOpenControlPanel: () => void }) {
  const player = usePlayer()
  const { audio, layer } = player

  if (layer !== 2) return null
  if (!audio.current) return null

  const { isPlaying, isLoading, current, position, duration, volume, muted } = audio
  const VolumeIcon = muted ? IconVolumeOff : volume > 0.5 ? IconVolume : IconVolume2

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40',
        'border-t border-border/60 bg-background/95 backdrop-blur',
      )}
      role="region"
      aria-label="Audio player"
    >
      <div className="mx-auto flex max-w-screen-2xl items-center gap-4 px-4 py-3 lg:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="grid size-12 shrink-0 place-items-center rounded-md border border-border/60 bg-muted/40">
            <IconMusic className="size-5 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">{current.title}</span>
              {current.mood && <MoodBadge mood={current.mood} />}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="truncate">{current.artists ?? '—'}</span>
              {current.bpm && (
                <>
                  <span>·</span>
                  <span className="tabular-nums">{current.bpm.toFixed(1)} BPM</span>
                </>
              )}
              {current.camelot && (
                <>
                  <span>·</span>
                  <span className="font-mono">{current.camelot}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex min-w-0 flex-[2] flex-col items-center gap-1.5">
          <div className="flex items-center gap-1">
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.prev()} disabled={!audio.hasPrev} aria-label="Previous track">
              <IconPlayerSkipBackFilled className="size-3.5" />
            </Button>
            <Button size="icon" className="h-9 w-9 rounded-full" onClick={() => audio.toggle()} aria-label={isPlaying ? 'Pause' : 'Play'}>
              {isLoading ? <IconLoader2 className="size-4 animate-spin" /> : isPlaying ? <IconPlayerPauseFilled className="size-4" /> : <IconPlayerPlayFilled className="size-4" />}
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.next()} disabled={!audio.hasNext} aria-label="Next track">
              <IconPlayerSkipForwardFilled className="size-3.5" />
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.stop()} aria-label="Stop">
              <IconPlayerStopFilled className="size-3.5" />
            </Button>
          </div>
          <div className="flex w-full items-center gap-2">
            <span className="w-10 text-right text-[10px] tabular-nums text-muted-foreground">{formatTime(position)}</span>
            <Slider
              value={[duration > 0 ? (position / duration) * 100 : 0]}
              min={0}
              max={100}
              step={0.1}
              onValueChange={(v) => {
                if (duration > 0) audio.seek((v[0] / 100) * duration)
              }}
              className="flex-1"
              aria-label="Seek"
            />
            <span className="w-10 text-[10px] tabular-nums text-muted-foreground">{formatTime(duration)}</span>
          </div>
        </div>

        <div className="hidden min-w-[180px] flex-1 items-center justify-end gap-2 md:flex">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={onOpenControlPanel}
            aria-label="Set modes"
            title="Click for set modes"
          >
            <IconSparkles className="size-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.toggleMute()} aria-label={muted ? 'Unmute' : 'Mute'}>
            <VolumeIcon className="size-4" />
          </Button>
          <Slider
            value={[muted ? 0 : volume * 100]}
            min={0}
            max={100}
            step={1}
            onValueChange={(v) => audio.setVolume(v[0] / 100)}
            className="w-24"
            aria-label="Volume"
          />
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onOpenControlPanel} aria-label="Open controls">
            <IconAdjustmentsHorizontal className="size-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={player.collapseLayer} aria-label="Collapse">
            <IconChevronDown className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
