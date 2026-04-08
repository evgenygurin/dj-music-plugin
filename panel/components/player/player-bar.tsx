'use client'

import {
  Blend,
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
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
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
 * Persistent player bar — Spotify/Apple Music layout.
 *
 * Layout (from top to bottom):
 *   1. Edge-to-edge seek slider (h-1, full width, hover thumb)
 *   2. Three-column body:
 *      - Left:    cover + title + meta line
 *      - Center:  prev / play-pause / next / stop  ·  0:23 / 5:24
 *      - Right:   Mix popover · Set mode · Volume slider
 *
 * Always visible at the bottom of the viewport regardless of page or
 * track state. Uses shadcn primitives only (Slider, Switch, Popover,
 * Button) and lucide icons. Safe to render with no current track.
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
      {/* ─── Seek slider — edge to edge, sits on top edge of the bar ─────────── */}
      <div className="group relative h-1.5 px-3 -mt-px">
        <Slider
          value={[progressPct]}
          min={0}
          max={100}
          step={0.1}
          disabled={!hasTrack}
          onValueChange={(v) => {
            if (hasTrack && duration > 0) audio.seek((v[0] / 100) * duration)
          }}
          className={cn(
            'absolute inset-x-3 top-0',
            // Slim default + bigger thumb on hover
            '[&_[data-slot=slider-track]]:h-1 [&_[data-slot=slider-thumb]]:size-3 [&_[data-slot=slider-thumb]]:opacity-0 group-hover:[&_[data-slot=slider-thumb]]:opacity-100 transition',
          )}
          aria-label="Seek"
        />
      </div>

      {/* ─── Body row ──────────────────────────────────────────────────────── */}
      <div className="mx-auto grid max-w-screen-2xl grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-6 px-4 py-3 lg:px-6">
        {/* Left: cover + meta */}
        <div className="flex min-w-0 items-center gap-3">
          <div
            className={cn(
              'relative grid size-14 shrink-0 place-items-center overflow-hidden rounded-md border border-border/60 bg-muted/40',
              hasTrack && 'bg-gradient-to-br from-muted/60 to-muted/20',
            )}
          >
            <Music className={cn('size-6', hasTrack ? 'text-primary/70' : 'text-muted-foreground')} />
          </div>
          <div className="min-w-0 flex-1">
            {hasTrack ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold leading-tight">
                    {current.title}
                  </span>
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
              <div>
                <div className="text-sm font-medium text-muted-foreground">Ничего не играет</div>
                <div className="text-xs text-muted-foreground/70">Нажмите ▶ на треке в библиотеке</div>
              </div>
            )}
          </div>
        </div>

        {/* Center: transport + time */}
        <div className="flex items-center gap-3">
          <Button
            size="icon"
            variant="ghost"
            className="h-9 w-9 text-muted-foreground hover:text-foreground"
            onClick={() => audio.prev()}
            disabled={!hasTrack || !audio.hasPrev}
            aria-label="Previous track"
          >
            <SkipBack className="size-4" />
          </Button>
          <Button
            size="icon"
            className="size-11 rounded-full shadow-sm"
            onClick={() => audio.toggle()}
            disabled={!hasTrack && !isLoading}
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isLoading ? (
              <Loader2 className="size-5 animate-spin" />
            ) : isPlaying ? (
              <Pause className="size-5 fill-current" />
            ) : (
              <Play className="size-5 translate-x-[1px] fill-current" />
            )}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-9 w-9 text-muted-foreground hover:text-foreground"
            onClick={() => audio.next()}
            disabled={!hasTrack || !audio.hasNext}
            aria-label="Next track"
          >
            <SkipForward className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-9 w-9 text-muted-foreground hover:text-foreground"
            onClick={() => audio.stop()}
            disabled={!hasTrack}
            aria-label="Stop"
          >
            <Square className="size-3.5" />
          </Button>
          <div className="hidden min-w-[88px] items-center gap-1 pl-2 text-[11px] tabular-nums text-muted-foreground sm:flex">
            <span>{formatTime(position)}</span>
            <span className="text-muted-foreground/40">/</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        {/* Right: mix + set + volume */}
        <div className="flex min-w-0 items-center justify-end gap-2">
          <MixButton />
          {set.active ? (
            <Button
              size="sm"
              variant="default"
              className="h-8 gap-1.5 rounded-full px-3 text-[11px]"
              onClick={onOpenSetPlanner}
              aria-label="Open set planner"
              title={`${set.template?.name} — click to open planner`}
            >
              <Sparkles className="size-3.5" />
              <span className="font-medium">{set.template?.name}</span>
              <span className="tabular-nums opacity-80">{formatTime(set.elapsedSec)}</span>
            </Button>
          ) : (
            <Button
              size="icon"
              variant="ghost"
              className="h-9 w-9 text-muted-foreground hover:text-foreground"
              onClick={onOpenControlPanel}
              aria-label="Set modes"
              title="Choose set mode"
            >
              <Sparkles className="size-4" />
            </Button>
          )}

          <div className="hidden items-center gap-1.5 md:flex">
            <Button
              size="icon"
              variant="ghost"
              className="h-9 w-9 text-muted-foreground hover:text-foreground"
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
              className="w-24"
              aria-label="Volume"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Mix toggle + length selector. Default ON / 32 bars / auto.
 *
 * - Off  → next-track switches snap instantly (no crossfade)
 * - Auto → crossfades use the configured bar length, scaled to BPM
 */
function MixButton() {
  const player = usePlayer()
  const { audio } = player
  const enabled = audio.mixEnabled
  const bars = audio.crossfadeBars
  const seconds = audio.crossfadeSeconds

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
          <span className="hidden sm:inline">{enabled ? `${bars} bars` : 'Off'}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" sideOffset={12} className="w-72 p-4">
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-0.5">
              <div className="text-sm font-semibold leading-none">Crossfade mix</div>
              <div className="text-[11px] text-muted-foreground">
                {enabled
                  ? `Auto · ~${Math.round(seconds)}s @ current BPM`
                  : 'Snap transitions — no crossfade'}
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
        </div>
      </PopoverContent>
    </Popover>
  )
}
