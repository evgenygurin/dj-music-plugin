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

// ── Transition-style chip group ──────────────────────────────────
//
// Five mutually exclusive chips bound to `manualStyle`. `auto` is
// the default and means "follow the backend scorer's
// recommendation". The four concrete values force the dispatcher
// onto that runtime style regardless of what the scorer said.
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
      className="hidden items-center gap-0.5 rounded-full border border-border/60 bg-muted/30 p-0.5 xl:flex"
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
              'rounded-full px-2.5 py-1 text-[10px] font-medium tracking-wide transition-colors',
              selected
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
            )}
          >
            {short}
          </button>
        )
      })}
    </div>
  )
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
  // Auto-Mix master switch: treat autoDj + mixEnabled as one
  // user-facing concept. Toggling the AUTO button flips both so the
  // "ON" state is the obvious out-of-the-box default.
  const autoMixOn = autoDj && mixEnabled
  const handleToggleAutoMix = () => {
    if (autoMixOn) {
      audio.toggleAutoDj() // → autoDj=false; mix stays on
    } else {
      if (!autoDj) audio.toggleAutoDj()
      if (!mixEnabled) audio.toggleMixEnabled()
    }
  }

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
              aria-label="Next track (hard cut)"
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
          <div className="flex w-full items-center gap-2">
            <span className="tabular-nums text-[10px] text-muted-foreground">
              {formatTime(position)}
            </span>
            {hasTrack ? (
              <TrackWaveform
                trackId={current.id}
                position={position}
                duration={duration}
                onSeek={(s) => audio.seek(s)}
                className="flex-1"
                height={40}
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
            <span className="tabular-nums text-[10px] text-muted-foreground">
              {formatTime(duration)}
            </span>
          </div>
        </div>

        {/* Right: next-up peek + auto-mix + mix settings + set + collapse + volume */}
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
          {/* Next Up peek chip — shows what would play next */}
          {nextUp && (
            <div
              className="hidden min-w-0 max-w-[180px] items-center gap-1 rounded-full border border-border/60 bg-muted/30 px-2.5 py-1 text-[10px] text-muted-foreground md:flex"
              title={`Next: ${nextUp.title}${nextUp.artists ? ` — ${nextUp.artists}` : ''}`}
            >
              <ArrowRight className="size-3 shrink-0 text-primary/70" />
              <span className="truncate">
                <span className="font-medium text-foreground/90">{nextUp.title}</span>
                {nextUp.artists && (
                  <span className="text-muted-foreground"> — {nextUp.artists}</span>
                )}
              </span>
            </div>
          )}

          {/* Recommended Next — scorer pick, not shuffle. Explicit
              action kept in the mix-decisions cluster so the center
              transport stays a clean classical prev/play/next. */}
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-primary/80 hover:bg-primary/10 hover:text-primary"
            onClick={() => {
              void audio.playRecommendedNext()
            }}
            disabled={!hasTrack}
            aria-label="Play recommended next track"
            title="Recommended next (scorer)"
          >
            <Sparkles className="size-4" />
          </Button>

          {/* Mix Now — immediate smooth crossfade without waiting */}
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-primary/80 hover:bg-primary/10 hover:text-primary"
            onClick={() => audio.mixNow()}
            disabled={!hasTrack}
            aria-label="Mix now (smooth crossfade)"
            title="Mix now"
          >
            <Waves className="size-4" />
          </Button>

          {/* Auto-Mix master switch — toggles autoDj + mixEnabled together.
              ON means tracks recommend themselves and smoothly crossfade
              on end of track. Default ON out of the box. */}
          <Button
            size="sm"
            variant={autoMixOn ? 'default' : 'outline'}
            className="h-8 gap-1.5 rounded-full px-3 text-[11px] font-medium"
            onClick={handleToggleAutoMix}
            aria-label={autoMixOn ? 'Turn Auto-Mix off' : 'Turn Auto-Mix on'}
            aria-pressed={autoMixOn}
            title={
              autoMixOn
                ? 'Auto-Mix ON — tracks pick + crossfade automatically'
                : 'Auto-Mix OFF — manual transport'
            }
          >
            <Wand2 className="size-3.5" />
            <span>AUTO</span>
          </Button>

          {/* Manual transition-style override — 5 chips: auto / cut /
              swap / harmonic / fade. `auto` means follow the backend
              scorer's recommendation. The other four force the
              dispatcher onto a specific runtime style regardless of
              what the scorer said. Lets you audition the styles by
              ear and compare. */}
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
