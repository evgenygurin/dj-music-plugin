'use client'

import {
  ChevronUp,
  Loader2,
  Music,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Sparkles,
  Wand2,
  Waves,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function MiniPlayerBar() {
  const player = usePlayer()
  const { audio } = player
  if (player.layer !== 1) return null

  const {
    current,
    isPlaying,
    isLoading,
    position,
    duration,
    autoDj,
    mixEnabled,
    isCrossfading,
    lastResolvedStyle,
    lastResolvedStyleWasManual,
    recommendedStyle,
  } = audio
  const hasTrack = current !== null
  const activeStyle = lastResolvedStyle ?? recommendedStyle
  const progressPct = hasTrack && duration > 0 ? (position / duration) * 100 : 0
  const autoMixOn = autoDj && mixEnabled
  const handleToggleAutoMix = () => {
    if (autoMixOn) {
      audio.toggleAutoDj()
    } else {
      if (!autoDj) audio.toggleAutoDj()
      if (!mixEnabled) audio.toggleMixEnabled()
    }
  }

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-40 safe-bottom glass"
      role="region"
      aria-label="Mini player"
    >
      {/* Progress line */}
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-muted/20">
        <div
          className="h-full bg-primary transition-[width] duration-200"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      <div className="mx-auto flex h-12 max-w-screen-2xl items-center gap-1.5 px-2 md:h-16 md:gap-2 md:px-4">
        {/* Left: track info */}
        <button
          type="button"
          onClick={() => player.promoteLayer()}
          className={cn(
            'flex min-w-0 flex-1 items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-muted/20',
            !hasTrack && 'cursor-default justify-center hover:bg-transparent',
          )}
          aria-label="Expand player"
        >
          {hasTrack ? (
            <>
              {/* Album art placeholder */}
              <div className="grid size-8 shrink-0 place-items-center rounded-md bg-muted/30 border border-border/30 md:size-10 md:rounded-lg">
                <Music className="size-3.5 text-foreground/40" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium leading-tight">{current.title}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="truncate text-xs text-muted-foreground">{current.artists || '—'}</span>
                  {current.bpm && (
                    <span className="dj-data text-[10px] text-foreground/60">{Math.round(current.bpm)}</span>
                  )}
                  {current.camelot && (
                    <span className="dj-data text-[10px] text-muted-foreground/70">{current.camelot}</span>
                  )}
                </div>
              </div>
            </>
          ) : (
            <span className="text-sm text-muted-foreground">No track loaded</span>
          )}
        </button>

        {/* Center: transport */}
        <div className="flex items-center gap-0.5">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => audio.prev()}
            disabled={!hasTrack || !audio.hasPrev}
            aria-label="Previous track"
          >
            <SkipBack className="size-3.5" />
          </Button>
          <Button
            size="icon"
            className="h-10 w-10 rounded-full bg-primary text-primary-foreground hover:bg-primary/90"
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
            title="Next (hard cut)"
          >
            <SkipForward className="size-3.5" />
          </Button>
        </div>

        {/* Right cluster: quick actions */}
        <div className="flex items-center gap-0.5">
          <Button
            size="icon"
            variant="ghost"
            className="hidden h-8 w-8 text-foreground/60 hover:bg-primary/10 hover:text-primary sm:inline-flex"
            onClick={() => void audio.playRecommendedNext()}
            disabled={!hasTrack}
            aria-label="Play recommended next"
            title="Recommended next"
          >
            <Sparkles className="size-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="hidden h-8 w-8 text-foreground/60 hover:bg-primary/10 hover:text-primary sm:inline-flex"
            onClick={() => audio.mixNow()}
            disabled={!hasTrack}
            aria-label="Mix now"
            title="Mix now"
          >
            <Waves className="size-3.5" />
          </Button>
          <Button
            size="icon"
            variant={autoMixOn ? 'default' : 'ghost'}
            className="h-8 w-8"
            onClick={handleToggleAutoMix}
            aria-label={autoMixOn ? 'Auto-Mix off' : 'Auto-Mix on'}
            aria-pressed={autoMixOn}
            title={autoMixOn ? 'Auto-Mix ON' : 'Auto-Mix OFF'}
          >
            <Wand2 className="size-3.5" />
          </Button>

          {/* Crossfade style badge */}
          {isCrossfading && activeStyle && (
            <span
              className={cn(
                'hidden rounded-full border px-2 py-0.5 dj-data text-[9px] uppercase tracking-wider md:inline',
                lastResolvedStyleWasManual
                  ? 'border-foreground/20 bg-foreground/5 text-foreground'
                  : 'border-muted-foreground/30 bg-muted/30 text-muted-foreground',
              )}
            >
              {activeStyle.replace(/_/g, ' ')}
            </span>
          )}

          {/* Time */}
          <span className="hidden dj-data text-[10px] text-muted-foreground sm:inline ml-1">
            {formatTime(position)}<span className="text-muted-foreground/40"> / </span>{formatTime(duration)}
          </span>

          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => player.promoteLayer()}
            aria-label="Expand player"
          >
            <ChevronUp className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
