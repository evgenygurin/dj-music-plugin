'use client'

import {
  ArrowRight,
  ChevronDown,
  Loader2,
  Music,
  Pause,
  Play,
  Scissors,
  Shuffle,
  SkipBack,
  SkipForward,
  Sparkles,
  Square,
  Volume1,
  Volume2,
  VolumeX,
  Wand2,
  Waves,
} from 'lucide-react'

import type { ManualTransitionStyle } from '@/components/audio-player/audio-player-types'
import { MoodBadge } from '@/components/mood-badge'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { cn } from '@/lib/utils'

import { MixButton } from './mix-button'
import { usePlayer } from './player-provider'
import { TrackWaveform } from './track-waveform'

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

const STYLE_OPTIONS: ReadonlyArray<{
  value: ManualTransitionStyle
  short: string
  label: string
  title: string
  Icon: typeof Sparkles | null
}> = [
  {
    value: 'auto',
    short: 'AUTO',
    label: 'Auto (backend scorer)',
    title: 'Auto — follow the backend scorer recommendation',
    Icon: Sparkles,
  },
  {
    value: 'cut',
    short: 'CUT',
    label: 'Cut',
    title: 'Cut — hard 50 ms cut on the downbeat, no overlap',
    Icon: Scissors,
  },
  {
    value: 'swap',
    short: 'SWAP',
    label: 'Swap',
    title: 'Swap — equal-power crossfade + LR4 kick kill',
    Icon: Shuffle,
  },
  {
    value: 'harmonic',
    short: 'HARM',
    label: 'Harmonic',
    title: 'Harmonic — equal-power blend, no bass kill',
    Icon: Music,
  },
  {
    value: 'fade',
    short: 'FADE',
    label: 'Fade',
    title: 'Fade — linear gain crossfade, no EQ tricks',
    Icon: Waves,
  },
]

function TransitionStyleChips({
  value,
  onChange,
}: {
  value: ManualTransitionStyle
  onChange: (s: ManualTransitionStyle) => void
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Transition style override"
      className="hidden items-center gap-0.5 rounded-full border border-border/40 bg-muted/20 p-0.5 xl:flex"
    >
      {STYLE_OPTIONS.map(({ value: v, short, label, title }) => {
        const selected = value === v
        return (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={`Transition style: ${label}`}
            title={title}
            onClick={() => onChange(v)}
            className={cn(
              'rounded-full px-2.5 py-1 dj-data text-[10px] tracking-wide transition-colors',
              selected
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
            )}
          >
            {short}
          </button>
        )
      })}
    </div>
  )
}

export function MediumPlayerBar({ onCollapse, onOpenControlPanel }: Props) {
  const player = usePlayer()
  if (player.layer < 2) return null

  const { audio } = player
  const {
    current,
    isPlaying,
    isLoading,
    position,
    duration,
    volume,
    muted,
    autoDj,
    mixEnabled,
    nextUp,
  } = audio
  const hasTrack = current !== null
  const VolumeIcon = muted ? VolumeX : volume > 0.5 ? Volume2 : Volume1
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
      className="fixed bottom-0 left-0 right-0 z-40 safe-bottom glass border-t border-foreground/5"
      role="region"
      aria-label="Audio player"
    >
      {/* Full-width waveform area */}
      <div className="px-3 pt-3 pb-1 md:px-4">
        <div className="flex items-center gap-2">
          <span className="dj-data text-[10px] text-muted-foreground/70 w-10 text-right">
            {formatTime(position)}
          </span>
          {hasTrack ? (
            <TrackWaveform
              trackId={current.id}
              position={position}
              duration={duration}
              onSeek={(s) => audio.seek(s)}
              className="flex-1"
              height={48}
            />
          ) : (
            <Slider
              value={[0]}
              min={0}
              max={100}
              step={1}
              disabled
              className="flex-1"
              aria-label="Seek"
            />
          )}
          <span className="dj-data text-[10px] text-muted-foreground/70 w-10">
            {formatTime(duration)}
          </span>
        </div>
      </div>

      <div className="mx-auto flex max-w-screen-2xl items-center gap-3 px-3 pb-2 md:px-4 md:gap-4">
        {/* Left: track meta */}
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div
            className={cn(
              'grid size-11 shrink-0 place-items-center overflow-hidden rounded-lg border border-border/30',
              hasTrack ? 'bg-gradient-to-br from-foreground/5 to-muted/10' : 'bg-muted/30',
            )}
          >
            <Music
              className={cn('size-5', hasTrack ? 'text-foreground/30' : 'text-muted-foreground/40')}
            />
          </div>
          <div className="min-w-0">
            {hasTrack ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{current.title}</span>
                  {current.mood && <MoodBadge mood={current.mood} />}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="truncate text-xs text-muted-foreground">{current.artists || '—'}</span>
                  {current.bpm && (
                    <span className="dj-data text-[11px] text-foreground/70 font-medium">
                      {current.bpm.toFixed(1)}
                    </span>
                  )}
                  {current.camelot && (
                    <span className="dj-data text-[11px] text-muted-foreground/60">
                      {current.camelot}
                    </span>
                  )}
                </div>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">No track loaded</div>
            )}
          </div>
        </div>

        {/* Center: transport */}
        <div className="flex items-center gap-1.5">
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
            className="h-11 w-11 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-foreground/10"
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
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => audio.next()}
            disabled={!hasTrack || !audio.hasNext}
            aria-label="Next track"
            title="Next (hard cut)"
          >
            <SkipForward className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="hidden h-8 w-8 text-muted-foreground hover:text-foreground lg:inline-flex"
            onClick={() => audio.stop()}
            disabled={!hasTrack}
            aria-label="Stop"
          >
            <Square className="size-3.5" />
          </Button>
        </div>

        {/* Right: mix controls + volume */}
        <div className="flex min-w-0 flex-1 items-center justify-end gap-1.5">
          {/* Next Up peek */}
          {nextUp && (
            <div
              className="hidden min-w-0 max-w-[160px] items-center gap-1 rounded-full border border-border/30 bg-muted/20 px-2.5 py-1 text-[10px] text-muted-foreground lg:flex"
              title={`Next: ${nextUp.title}${nextUp.artists ? ` — ${nextUp.artists}` : ''}`}
            >
              <ArrowRight className="size-3 shrink-0 text-foreground/30" />
              <span className="truncate font-medium text-foreground/80">{nextUp.title}</span>
            </div>
          )}

          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-foreground/50 hover:bg-foreground/5 hover:text-foreground"
            onClick={() => void audio.playRecommendedNext()}
            disabled={!hasTrack}
            aria-label="Recommended next"
            title="Recommended next (scorer)"
          >
            <Sparkles className="size-4" />
          </Button>

          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-foreground/50 hover:bg-foreground/5 hover:text-foreground"
            onClick={() => audio.mixNow()}
            disabled={!hasTrack}
            aria-label="Mix now"
            title="Mix now"
          >
            <Waves className="size-4" />
          </Button>

          <Button
            size="sm"
            variant={autoMixOn ? 'default' : 'outline'}
            className="h-8 gap-1.5 rounded-full px-3 dj-data text-[11px]"
            onClick={handleToggleAutoMix}
            aria-label={autoMixOn ? 'Auto-Mix off' : 'Auto-Mix on'}
            aria-pressed={autoMixOn}
          >
            <Wand2 className="size-3.5" />
            <span>AUTO</span>
          </Button>

          <TransitionStyleChips
            value={audio.manualStyle}
            onChange={audio.setManualStyle}
          />

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
            className="hidden h-8 w-8 text-muted-foreground hover:text-foreground md:inline-flex"
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
            className="hidden w-20 md:flex"
            aria-label="Volume"
          />
        </div>
      </div>
    </div>
  )
}
