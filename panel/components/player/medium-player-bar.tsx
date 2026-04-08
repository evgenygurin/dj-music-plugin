'use client'

import {
  ChevronDown,
  Loader2,
  Music,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Sparkles,
  Square,
  Volume1,
  Volume2,
  VolumeX,
} from 'lucide-react'

import { MoodBadge } from '@/components/mood-badge'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { cn } from '@/lib/utils'

import { MixButton } from './mix-button'
import { usePlayer } from './player-provider'

interface Props {
  onCollapse: () => void
  onOpenControlPanel: () => void
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/**
 * Layer 2 — full transport bar (~80px). Three flex columns:
 *   - meta (cover + title + mood + sub-line)
 *   - center (transport buttons + seek slider)
 *   - mix + set + collapse + volume
 */
export function MediumPlayerBar({ onCollapse, onOpenControlPanel }: Props) {
  const player = usePlayer()
  if (player.layer < 2) return null

  const { audio } = player
  const { current, isPlaying, isLoading, position, duration, volume, muted } = audio
  const hasTrack = current !== null
  const VolumeIcon = muted ? VolumeX : volume > 0.5 ? Volume2 : Volume1

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85"
      role="region"
      aria-label="Audio player"
    >
      <div className="mx-auto flex max-w-screen-2xl items-center gap-4 px-4 py-3">
        {/* Left meta */}
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div
            className={cn(
              'grid size-12 shrink-0 place-items-center overflow-hidden rounded-md border border-border/60 bg-muted/40',
              hasTrack && 'bg-gradient-to-br from-muted/60 to-muted/20',
            )}
          >
            <Music
              className={cn('size-5', hasTrack ? 'text-primary/70' : 'text-muted-foreground')}
            />
          </div>
          <div className="min-w-0">
            {hasTrack ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{current.title}</span>
                  {current.mood && <MoodBadge mood={current.mood} />}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="truncate">{current.artists || '—'}</span>
                  {current.bpm && (
                    <>
                      <span className="text-muted-foreground/40">·</span>
                      <span className="tabular-nums">{current.bpm.toFixed(1)} BPM</span>
                    </>
                  )}
                  {current.camelot && (
                    <>
                      <span className="text-muted-foreground/40">·</span>
                      <span className="font-mono">{current.camelot}</span>
                    </>
                  )}
                </div>
              </>
            ) : (
              <div className="text-sm italic text-muted-foreground">Ничего не играет</div>
            )}
          </div>
        </div>

        {/* Center transport + seek */}
        <div className="flex min-w-0 flex-[2] flex-col items-center gap-1">
          <div className="flex items-center gap-2">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => audio.prev()}
              disabled={!hasTrack || !audio.hasPrev}
              aria-label="Previous track"
            >
              <SkipBack className="size-4" />
            </Button>
            <Button
              size="icon"
              className="h-9 w-9 rounded-full"
              onClick={() => audio.toggle()}
              disabled={!hasTrack && !isLoading}
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : isPlaying ? (
                <Pause className="size-4 fill-current" />
              ) : (
                <Play className="size-4 translate-x-[1px] fill-current" />
              )}
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => audio.next()}
              disabled={!hasTrack || !audio.hasNext}
              aria-label="Next track"
            >
              <SkipForward className="size-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => audio.stop()}
              disabled={!hasTrack}
              aria-label="Stop"
            >
              <Square className="size-3.5" />
            </Button>
          </div>
          <div className="flex w-full items-center gap-2">
            <span className="tabular-nums text-[10px] text-muted-foreground">
              {formatTime(position)}
            </span>
            <Slider
              value={[hasTrack && duration > 0 ? (position / duration) * 100 : 0]}
              min={0}
              max={100}
              step={0.1}
              disabled={!hasTrack}
              onValueChange={(v) => {
                if (hasTrack && duration > 0) audio.seek((v[0] / 100) * duration)
              }}
              className="flex-1"
              aria-label="Seek"
            />
            <span className="tabular-nums text-[10px] text-muted-foreground">
              {formatTime(duration)}
            </span>
          </div>
        </div>

        {/* Right: mix + set + collapse + volume */}
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
          <MixButton />
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onOpenControlPanel}
            aria-label="Set modes"
            title="Choose set mode"
          >
            <Sparkles className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={onCollapse}
            aria-label="Collapse player"
          >
            <ChevronDown className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => audio.toggleMute()}
            aria-label={muted ? 'Unmute' : 'Mute'}
          >
            <VolumeIcon className="size-4" />
          </Button>
          <Slider
            value={[muted ? 0 : volume * 100]}
            min={0}
            max={100}
            step={1}
            onValueChange={(v) => audio.setVolume(v[0] / 100)}
            className="w-20"
            aria-label="Volume"
          />
        </div>
      </div>
    </div>
  )
}
