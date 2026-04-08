// panel/components/player/mini-player-bar.tsx
'use client'

import {
  IconChevronUp,
  IconLoader2,
  IconMusic,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
} from '@tabler/icons-react'

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
  const { audio, layer } = player

  // Persistent baseline bar: renders at layer 0 AND layer 1. Covers two
  // cases with one component:
  //   - layer 0 + no track  → hero shows instead (this bar is hidden)
  //   - layer 0 + has track → user clicked ▶ in a list; bar appears
  //                           without needing an explicit "promote"
  //   - layer 1             → same bar, regardless of track state
  // Higher layers (2+) take over via MediumPlayerBar.
  if (layer >= 2) return null
  if (layer === 0 && !audio.current) return null

  const { isPlaying, isLoading, current, position, duration } = audio
  const progressPct =
    current && duration > 0 ? Math.min(100, (position / duration) * 100) : 0

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40 h-12',
        'border-t border-border/60 bg-background/95 backdrop-blur',
      )}
      role="region"
      aria-label="Audio player"
    >
      <div className="mx-auto flex h-full max-w-screen-2xl items-center gap-3 px-4 lg:px-6">
        <button
          type="button"
          onClick={player.promoteLayer}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-label="Expand player"
        >
          <IconMusic className="size-4 shrink-0 text-muted-foreground" />
          {current ? (
            <>
              <span className="truncate text-sm font-medium">{current.title}</span>
              {current.artists && (
                <span className="truncate text-xs text-muted-foreground">
                  — {current.artists}
                </span>
              )}
            </>
          ) : (
            <span className="truncate text-sm text-muted-foreground italic">
              Ничего не играет
            </span>
          )}
        </button>

        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={() => audio.prev()}
            disabled={!audio.hasPrev}
            aria-label="Previous track"
          >
            <IconPlayerSkipBackFilled className="size-3.5" />
          </Button>
          <Button
            size="icon"
            className="h-9 w-9 rounded-full"
            onClick={() => audio.toggle()}
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isLoading ? (
              <IconLoader2 className="size-4 animate-spin" />
            ) : isPlaying ? (
              <IconPlayerPauseFilled className="size-4" />
            ) : (
              <IconPlayerPlayFilled className="size-4" />
            )}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={() => audio.next()}
            disabled={!audio.hasNext}
            aria-label="Next track"
          >
            <IconPlayerSkipForwardFilled className="size-3.5" />
          </Button>
        </div>

        <span className="hidden w-20 text-right text-[10px] tabular-nums text-muted-foreground sm:inline">
          {formatTime(position)} / {formatTime(duration)}
        </span>

        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={player.promoteLayer}
          aria-label="Expand player"
        >
          <IconChevronUp className="size-4" />
        </Button>
      </div>

      <div
        className="h-0.5 bg-primary transition-[width]"
        style={{ width: `${progressPct}%` }}
      />
    </div>
  )
}
