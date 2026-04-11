'use client'

import { useCallback, useRef } from 'react'
import {
  IconLoader2,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipForwardFilled,
} from '@tabler/icons-react'

import { loadDjQueue } from '@/actions/library-actions'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import type { PlayerTrackMeta } from '@/components/audio-player/audio-player-types'
import { TransitionVisualizer } from '@/components/player/transition-visualizer'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/* ── Fake waveform bars (visual only, deterministic heights) ── */
const BAR_HEIGHTS = [52,78,34,91,45,67,83,29,61,94,38,72,55,87,41,63,76,33,58,89,44,71,82,36,65,93,47,74,51,85,39,68,57,92,43,77,54,88,31,64,79,35,69,95,42,73,56,81]

function WaveformBars({ active, progress }: { active: boolean; progress: number }) {
  return (
    <div className="flex items-center gap-[1.5px] h-10 w-full">
      {BAR_HEIGHTS.map((h, i) => {
        const filled = active && i / BAR_HEIGHTS.length < progress
        return (
          <div
            key={i}
            className="flex-1 rounded-full transition-colors duration-75"
            style={{
              height: `${h}%`,
              backgroundColor: filled
                ? 'oklch(0.9 0 0 / 0.7)'
                : active
                  ? 'oklch(0.9 0 0 / 0.15)'
                  : 'oklch(0.5 0 0 / 0.08)',
            }}
          />
        )
      })}
    </div>
  )
}

/* ── Single deck strip ── */
function DeckStrip({
  label,
  track,
  active,
  progress,
  time,
  side,
}: {
  label: string
  track: PlayerTrackMeta | null
  active: boolean
  progress: number
  time: string
  side: 'left' | 'right'
}) {
  return (
    <div className="flex-1 min-w-0 px-3 py-2">
      {/* Label */}
      <div className={`flex items-baseline gap-2 mb-1 ${side === 'right' ? 'flex-row-reverse' : ''}`}>
        <span className="dj-data text-[9px] uppercase tracking-[0.2em] text-muted-foreground/30">
          {label}
        </span>
        {track && (
          <span className="dj-data text-[10px] text-muted-foreground/40">{time}</span>
        )}
      </div>

      {/* Waveform */}
      <WaveformBars active={active} progress={progress} />

      {/* Track info */}
      <div className={`mt-1.5 ${side === 'right' ? 'text-right' : ''}`}>
        {track ? (
          <>
            <p className="text-xs font-medium truncate leading-tight">{track.title}</p>
            <div className={`flex items-center gap-1.5 mt-0.5 ${side === 'right' ? 'justify-end' : ''}`}>
              {track.bpm && (
                <span className="dj-data text-[10px] text-foreground/50">{track.bpm.toFixed(0)}</span>
              )}
              {track.camelot && (
                <span className="dj-data text-[10px] text-muted-foreground/30">{track.camelot}</span>
              )}
            </div>
          </>
        ) : (
          <p className="text-[10px] text-muted-foreground/20 italic">empty</p>
        )}
      </div>
    </div>
  )
}

export default function PlayerPage() {
  const audio = useAudioPlayer()
  const queueLoadedRef = useRef(false)

  const {
    current,
    isPlaying,
    isLoading,
    position,
    duration,
    masterTempoBpm,
    nextUp,
    outgoing,
    isCrossfading,
    lastResolvedStyle,
    recommendedStyle,
  } = audio

  const progress = current && duration > 0 ? position / duration : 0
  const activeStyle = lastResolvedStyle ?? recommendedStyle

  const handleStart = useCallback(async () => {
    if (queueLoadedRef.current && current) {
      audio.toggle()
      return
    }
    const tracks = await loadDjQueue(128)
    if (tracks.length === 0) return
    const queue: PlayerTrackMeta[] = tracks.map((t) => ({
      id: t.id, title: t.title, artists: t.artists,
      durationMs: t.duration_ms, bpm: t.bpm,
      camelot: t.camelot, mood: t.mood,
    }))
    if (!audio.autoDj) audio.toggleAutoDj()
    if (!audio.mixEnabled) audio.toggleMixEnabled()
    audio.play(queue[0], queue)
    queueLoadedRef.current = true
  }, [audio, current])

  const handleNext = useCallback(() => {
    void audio.playRecommendedNext()
  }, [audio])

  // Deck assignments: current = Deck 1, outgoing (during crossfade) = Deck 2,
  // nextUp = Deck 3, Deck 4 = future/empty
  const deck1 = current
  const deck2 = isCrossfading && outgoing ? outgoing : null
  const deck3 = nextUp
  const deck4: PlayerTrackMeta | null = null

  return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none">

      {/* Master BPM — top */}
      {masterTempoBpm && (
        <div className="flex items-center justify-center gap-2 pt-4 pb-2">
          <span className="dj-data text-3xl text-foreground">{Math.round(masterTempoBpm)}</span>
          <span className="dj-data text-[9px] uppercase tracking-[0.2em] text-muted-foreground/25">BPM</span>
        </div>
      )}

      {/* ── TOP ROW: Deck 1 + Deck 2 ── */}
      <div className="flex items-stretch border-y border-foreground/5">
        <DeckStrip
          label="Deck 1"
          track={deck1}
          active={!!deck1 && isPlaying}
          progress={progress}
          time={formatTime(position)}
          side="left"
        />
        <div className="w-px bg-foreground/5" />
        <DeckStrip
          label="Deck 2"
          track={deck2}
          active={!!deck2 && isCrossfading}
          progress={isCrossfading ? 0.5 : 0}
          time=""
          side="right"
        />
      </div>

      {/* ── CENTER: Play button hub ── */}
      <div className="flex-1 flex flex-col items-center justify-center relative">

        {/* Horizontal line through center */}
        <div className="absolute left-0 right-0 top-1/2 h-px bg-foreground/5" />

        {/* Transition style label */}
        {isCrossfading && activeStyle && (
          <p className="absolute top-4 dj-data text-[9px] uppercase tracking-[0.3em] text-muted-foreground/25">
            {activeStyle.replace(/_/g, ' ')}
          </p>
        )}

        {/* Current track title */}
        {current && (
          <p className="absolute top-10 display-heading text-lg text-foreground/60 truncate max-w-[80%] text-center">
            {current.title}
          </p>
        )}

        {/* PLAY / PAUSE — the hub */}
        <div className="relative z-10 flex items-center gap-6">
          <button
            type="button"
            onClick={current ? () => audio.toggle() : handleStart}
            disabled={isLoading}
            className="size-24 rounded-full bg-foreground text-background flex items-center justify-center hover:bg-foreground/90 active:scale-95 transition-transform shadow-2xl ring-4 ring-foreground/5"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isLoading ? (
              <IconLoader2 className="size-10 animate-spin" />
            ) : isPlaying ? (
              <IconPlayerPauseFilled className="size-10" />
            ) : (
              <IconPlayerPlayFilled className="size-10 translate-x-[3px]" />
            )}
          </button>

          {/* Next button — right of play */}
          {current && (
            <button
              type="button"
              onClick={handleNext}
              className="size-14 rounded-full border border-foreground/10 text-foreground/50 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all"
              aria-label="Next track"
            >
              <IconPlayerSkipForwardFilled className="size-5" />
            </button>
          )}
        </div>

        {/* Artists below play */}
        {current?.artists && (
          <p className="absolute bottom-10 text-xs text-muted-foreground/30 truncate max-w-[70%]">
            {current.artists}
          </p>
        )}

        {/* Idle state text */}
        {!current && !isLoading && (
          <p className="mt-6 display-heading text-4xl text-foreground/80">Mix</p>
        )}
      </div>

      {/* ── BOTTOM ROW: Deck 3 + Deck 4 ── */}
      <div className="flex items-stretch border-y border-foreground/5">
        <DeckStrip
          label="Deck 3"
          track={deck3}
          active={false}
          progress={0}
          time=""
          side="left"
        />
        <div className="w-px bg-foreground/5" />
        <DeckStrip
          label="Deck 4"
          track={deck4}
          active={false}
          progress={0}
          time=""
          side="right"
        />
      </div>

      {/* Bottom info */}
      {nextUp && (
        <div className="flex items-center justify-center gap-2 py-3">
          <span className="dj-data text-[9px] uppercase tracking-[0.2em] text-muted-foreground/20">next</span>
          <span className="text-xs text-muted-foreground/40 truncate max-w-[60%]">{nextUp.title}</span>
          {nextUp.bpm && <span className="dj-data text-[10px] text-muted-foreground/20">{nextUp.bpm.toFixed(0)}</span>}
        </div>
      )}

      <TransitionVisualizer />
    </div>
  )
}
