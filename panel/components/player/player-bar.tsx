'use client'

import {
  Loader2,
  Music,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  SlidersHorizontal,
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

import { usePlayer } from './player-provider'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

interface PlayerBarProps {
  onOpenControlPanel: () => void
  onOpenSetPlanner: () => void
}

/**
 * Single persistent player bar — Spotify/Apple Music style.
 *
 * Always visible at the bottom of the viewport regardless of page or
 * track state. Uses lucide icons (shadcn convention). When no track
 * is loaded, shows a placeholder with disabled controls so users
 * always know where playback lives.
 */
export function PlayerBar({ onOpenControlPanel, onOpenSetPlanner }: PlayerBarProps) {
  const player = usePlayer()
  const { audio, set } = player
  const {
    current,
    isPlaying,
    isLoading,
    position,
    duration,
    volume,
    muted,
  } = audio

  const hasTrack = current !== null
  const progressPct = hasTrack && duration > 0 ? (position / duration) * 100 : 0
  const VolumeIcon = muted ? VolumeX : volume > 0.5 ? Volume2 : Volume1

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40',
        'border-t border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85',
      )}
      role="region"
      aria-label="Audio player"
    >
      <div className="mx-auto grid max-w-screen-2xl grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 py-3 lg:px-6">
        {/* Left: cover + track meta */}
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid size-12 shrink-0 place-items-center rounded-md border border-border/60 bg-muted/40">
            <Music className="size-5 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            {hasTrack ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{current.title}</span>
                  {current.mood && <MoodBadge mood={current.mood} />}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="truncate">{current.artists || '—'}</span>
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
              </>
            ) : (
              <div className="text-sm italic text-muted-foreground">Ничего не играет</div>
            )}
          </div>
        </div>

        {/* Center: transport + seek */}
        <div className="flex min-w-[360px] flex-col items-center gap-1.5">
          <div className="flex items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              onClick={() => audio.prev()}
              disabled={!hasTrack || !audio.hasPrev}
              aria-label="Previous track"
            >
              <SkipBack className="size-3.5" />
            </Button>
            <Button
              size="icon"
              className="h-10 w-10 rounded-full"
              onClick={() => audio.toggle()}
              disabled={!hasTrack && !isLoading}
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : isPlaying ? (
                <Pause className="size-4" />
              ) : (
                <Play className="size-4 translate-x-[1px]" />
              )}
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              onClick={() => audio.next()}
              disabled={!hasTrack || !audio.hasNext}
              aria-label="Next track"
            >
              <SkipForward className="size-3.5" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              onClick={() => audio.stop()}
              disabled={!hasTrack}
              aria-label="Stop"
            >
              <Square className="size-3.5" />
            </Button>
          </div>
          <div className="flex w-full items-center gap-2">
            <span className="w-10 text-right text-[10px] tabular-nums text-muted-foreground">
              {formatTime(position)}
            </span>
            <Slider
              value={[progressPct]}
              min={0}
              max={100}
              step={0.1}
              onValueChange={(v) => {
                if (hasTrack && duration > 0) audio.seek((v[0] / 100) * duration)
              }}
              disabled={!hasTrack}
              className="flex-1"
              aria-label="Seek"
            />
            <span className="w-10 text-[10px] tabular-nums text-muted-foreground">
              {formatTime(duration)}
            </span>
          </div>
        </div>

        {/* Right: set mode + volume */}
        <div className="flex min-w-0 items-center justify-end gap-2">
          {set.active ? (
            <Button
              size="sm"
              variant="default"
              className="h-8 gap-1.5 rounded-full px-3 text-[11px]"
              onClick={onOpenSetPlanner}
              aria-label="Open set planner"
              title={`${set.template?.name} — click to open planner`}
            >
              <Sparkles className="size-3" />
              <span className="font-medium">{set.template?.name}</span>
              <span className="tabular-nums opacity-80">
                {formatTime(set.elapsedSec)}
              </span>
            </Button>
          ) : (
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              onClick={onOpenControlPanel}
              aria-label="Set modes"
              title="Choose set mode"
            >
              <Sparkles className="size-4" />
            </Button>
          )}

          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={onOpenControlPanel}
            aria-label="Player settings"
            title="Settings"
          >
            <SlidersHorizontal className="size-4" />
          </Button>

          <div className="hidden items-center gap-1 md:flex">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
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

      {/* Ambient progress strip at the very bottom */}
      <div
        className="absolute bottom-0 left-0 h-0.5 bg-primary/70 transition-[width] duration-100"
        style={{ width: `${progressPct}%` }}
      />
    </div>
  )
}
