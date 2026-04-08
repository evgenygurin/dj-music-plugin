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

/**
 * Layer 1 — minimal 48px-tall always-visible bar.
 *
 * Layout: [meta button | prev play next | time | expand] with a thin
 * 0.5h primary progress strip pinned to the very bottom.
 */
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
      className="fixed bottom-0 left-0 right-0 z-40 h-12 border-t border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85"
      role="region"
      aria-label="Mini player"
    >
      <div className="mx-auto flex h-full max-w-screen-2xl items-center gap-2 px-4">
        {/* Left: meta button → promote */}
        <button
          type="button"
          onClick={() => player.promoteLayer()}
          className={cn(
            'flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1 text-left hover:bg-muted/30',
            !hasTrack && 'cursor-default justify-center hover:bg-transparent',
          )}
          aria-label="Expand player"
        >
          {hasTrack ? (
            <>
              <Music className="size-3.5 shrink-0 text-primary/70" />
              <span className="truncate text-xs">
                <span className="font-medium">{current.title}</span>
                <span className="text-muted-foreground"> — {current.artists || '—'}</span>
              </span>
            </>
          ) : (
            <span className="text-xs italic text-muted-foreground">Ничего не играет</span>
          )}
        </button>

        {/* Center: transport */}
        <div className="flex items-center gap-1">
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
            aria-label="Next track (hard cut)"
            title="Next (hard cut)"
          >
            <SkipForward className="size-3.5" />
          </Button>
          {/* Recommended next — scorer pick, not random */}
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-primary/80 hover:bg-primary/10 hover:text-primary"
            onClick={() => {
              void audio.playRecommendedNext()
            }}
            disabled={!hasTrack}
            aria-label="Play recommended next track"
            title="Recommended next"
          >
            <Sparkles className="size-3.5" />
          </Button>
          {/* Mix now — immediate crossfade to next */}
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-primary/80 hover:bg-primary/10 hover:text-primary"
            onClick={() => audio.mixNow()}
            disabled={!hasTrack}
            aria-label="Mix now"
            title="Mix now"
          >
            <Waves className="size-3.5" />
          </Button>
          {/* Auto-Mix master switch (compact) */}
          <Button
            size="icon"
            variant={autoMixOn ? 'default' : 'ghost'}
            className="h-8 w-8"
            onClick={handleToggleAutoMix}
            aria-label={autoMixOn ? 'Turn Auto-Mix off' : 'Turn Auto-Mix on'}
            aria-pressed={autoMixOn}
            title={autoMixOn ? 'Auto-Mix ON' : 'Auto-Mix OFF'}
          >
            <Wand2 className="size-3.5" />
          </Button>
        </div>

        {/* Resolved style badge — visible only during active crossfade */}
        {isCrossfading && activeStyle && (
          <span
            className={cn(
              'hidden rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider md:inline',
              lastResolvedStyleWasManual
                ? 'border-amber-400/50 bg-amber-400/10 text-amber-300'
                : 'border-primary/40 bg-primary/10 text-primary',
            )}
            title={
              lastResolvedStyleWasManual
                ? 'Manual override — user picked this style'
                : 'Backend-recommended transition style'
            }
          >
            {activeStyle.replace(/_/g, ' ')}
            {lastResolvedStyleWasManual ? ' · manual' : ''}
          </span>
        )}

        {/* Right: time */}
        <span className="hidden tabular-nums text-[10px] text-muted-foreground sm:inline">
          {formatTime(position)} / {formatTime(duration)}
        </span>

        {/* Far right: expand */}
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

      {/* Progress strip */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-muted/30">
        <div
          className="h-full bg-primary transition-[width] duration-200"
          style={{ width: `${progressPct}%` }}
        />
      </div>
    </div>
  )
}
