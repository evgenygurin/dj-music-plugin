'use client'

import { useCallback, useRef, useState } from 'react'
import {
  IconLoader2,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipForwardFilled,
  IconLayoutGrid,
  IconWaveSine,
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

/* ── Deterministic waveform bars ── */
const BARS_A = [52,78,34,91,45,67,83,29,61,94,38,72,55,87,41,63,76,33,58,89,44,71,82,36,65,93,47,74,51,85,39,68,57,92,43,77,54,88,31,64,79,35,69,95,42,73,56,81]
const BARS_B = [71,43,88,55,92,37,66,81,48,74,33,85,62,41,79,53,90,35,68,83,46,72,39,87,58,44,76,31,93,64,49,82,57,91,38,70,52,86,42,75,34,89,61,47,78,36,84,59]
const BARS_C = [63,89,41,77,52,84,35,71,93,46,68,38,82,57,44,91,33,76,61,88,49,73,36,85,54,42,79,65,94,37,72,58,83,45,69,31,87,56,43,78,34,92,67,51,86,39,75,48]
const BARS_D = [81,37,74,56,92,43,67,88,34,79,51,85,62,39,77,48,93,41,72,55,83,36,69,94,45,78,33,86,59,44,71,53,91,38,65,82,47,73,35,89,57,42,76,31,84,63,95,52]

function WaveformBars({ bars, active, progress, color }: { bars: number[]; active: boolean; progress: number; color: string }) {
  return (
    <div className="flex items-end gap-[1px] h-full w-full">
      {bars.map((h, i) => {
        const filled = active && i / bars.length < progress
        return (
          <div
            key={i}
            className="flex-1 rounded-sm transition-colors duration-100"
            style={{
              height: `${h}%`,
              backgroundColor: filled ? color : active ? 'oklch(0.9 0 0 / 0.12)' : 'oklch(0.5 0 0 / 0.06)',
            }}
          />
        )
      })}
    </div>
  )
}

/* ── EQ Knob (visual) ── */
function EqKnob({ label, value }: { label: string; value: number }) {
  const angle = -135 + value * 270
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="size-8 rounded-full border border-foreground/10 bg-foreground/3 relative">
        <div
          className="absolute top-1 left-1/2 w-px h-2.5 bg-foreground/60 origin-bottom"
          style={{ transform: `translateX(-50%) rotate(${angle}deg)` }}
        />
      </div>
      <span className="dj-data text-[7px] uppercase tracking-wider text-muted-foreground/30">{label}</span>
    </div>
  )
}

/* ── Single deck quadrant ── */
function DeckQuadrant({
  label,
  track,
  active,
  progress,
  time,
  bars,
  color,
}: {
  label: string
  track: PlayerTrackMeta | null
  active: boolean
  progress: number
  time: string
  bars: number[]
  color: string
}) {
  return (
    <div className="flex-1 flex flex-col p-2.5 min-w-0 min-h-0">
      {/* Header: label + time */}
      <div className="flex items-center justify-between mb-1.5">
        <span className="dj-data text-[8px] uppercase tracking-[0.2em] text-muted-foreground/25">{label}</span>
        <span className="dj-data text-[9px] text-muted-foreground/30">{time}</span>
      </div>

      {/* Waveform — fills available space */}
      <div className="flex-1 min-h-0">
        <WaveformBars bars={bars} active={active} progress={progress} color={color} />
      </div>

      {/* Track info */}
      <div className="mt-1.5">
        {track ? (
          <>
            <p className="text-[11px] font-medium truncate leading-tight">{track.title}</p>
            <div className="flex items-center gap-1.5 mt-0.5">
              {track.bpm && <span className="dj-data text-[9px] text-foreground/40">{track.bpm.toFixed(0)}</span>}
              {track.camelot && <span className="dj-data text-[9px] text-muted-foreground/25">{track.camelot}</span>}
              {track.mood && <span className="text-[8px] text-muted-foreground/20">{track.mood.replace(/_/g, ' ')}</span>}
            </div>
          </>
        ) : (
          <p className="text-[9px] text-muted-foreground/15 italic">—</p>
        )}
      </div>

      {/* EQ knobs */}
      <div className="flex items-center justify-center gap-3 mt-2">
        <EqKnob label="Hi" value={0.5} />
        <EqKnob label="Mid" value={0.5} />
        <EqKnob label="Lo" value={0.5} />
        <EqKnob label="Vol" value={active ? 0.75 : 0.5} />
      </div>
    </div>
  )
}

/* ── Master view — single full-screen waveform of the playing mix ── */
function MasterView({
  track,
  isPlaying,
  progress,
  position,
  duration,
  masterBpm,
  style,
  isCrossfading,
}: {
  track: PlayerTrackMeta | null
  isPlaying: boolean
  progress: number
  position: number
  duration: number
  masterBpm: number | null
  style: string | null
  isCrossfading: boolean
}) {
  return (
    <div className="flex-1 flex flex-col px-4">
      {/* Master BPM */}
      {masterBpm && (
        <div className="flex items-center justify-center gap-2 py-4">
          <span className="dj-data text-4xl text-foreground">{Math.round(masterBpm)}</span>
          <span className="dj-data text-[9px] uppercase tracking-[0.2em] text-muted-foreground/20">BPM</span>
        </div>
      )}

      {/* Track title */}
      {track && (
        <div className="text-center mb-4">
          <h1 className="display-heading text-2xl truncate">{track.title}</h1>
          <p className="text-xs text-muted-foreground/40 mt-1 truncate">{track.artists || ''}</p>
          <div className="flex items-center justify-center gap-3 mt-2">
            {track.bpm && <span className="dj-data text-sm text-foreground/50">{track.bpm.toFixed(1)}</span>}
            {track.camelot && <span className="dj-data text-sm text-muted-foreground/30">{track.camelot}</span>}
            {track.mood && <span className="text-xs text-muted-foreground/25">{track.mood.replace(/_/g, ' ')}</span>}
          </div>
        </div>
      )}

      {/* Big master waveform */}
      <div className="flex-1 min-h-0 flex items-center">
        <div className="w-full h-24">
          <WaveformBars bars={BARS_A} active={isPlaying} progress={progress} color="oklch(0.95 0 0 / 0.6)" />
        </div>
      </div>

      {/* Time bar */}
      <div className="flex items-center gap-3 py-2">
        <span className="dj-data text-xs text-muted-foreground/30 w-12 text-right">{formatTime(position)}</span>
        <div className="flex-1 h-px bg-foreground/5 relative">
          <div className="absolute inset-y-0 left-0 bg-foreground/20" style={{ width: `${progress * 100}%` }} />
        </div>
        <span className="dj-data text-xs text-muted-foreground/30 w-12">{formatTime(duration)}</span>
      </div>

      {/* Transition info */}
      {isCrossfading && style && (
        <p className="text-center dj-data text-[9px] uppercase tracking-[0.3em] text-muted-foreground/20 pb-2">
          {style.replace(/_/g, ' ')}
        </p>
      )}
    </div>
  )
}

/* ── Main page ── */
export default function PlayerPage() {
  const audio = useAudioPlayer()
  const queueLoadedRef = useRef(false)
  const [view, setView] = useState<'decks' | 'master'>('decks')

  const { current, isPlaying, isLoading, position, duration, masterTempoBpm, nextUp, outgoing, isCrossfading, lastResolvedStyle, recommendedStyle } = audio
  const progress = current && duration > 0 ? position / duration : 0
  const activeStyle = lastResolvedStyle ?? recommendedStyle

  const handleStart = useCallback(async () => {
    if (queueLoadedRef.current && current) { audio.toggle(); return }
    const tracks = await loadDjQueue(128)
    if (tracks.length === 0) return
    const queue: PlayerTrackMeta[] = tracks.map((t) => ({
      id: t.id, title: t.title, artists: t.artists, durationMs: t.duration_ms, bpm: t.bpm, camelot: t.camelot, mood: t.mood,
    }))
    if (!audio.autoDj) audio.toggleAutoDj()
    if (!audio.mixEnabled) audio.toggleMixEnabled()
    audio.play(queue[0], queue)
    queueLoadedRef.current = true
  }, [audio, current])

  const handleNext = useCallback(() => { void audio.playRecommendedNext() }, [audio])

  const deck1 = current
  const deck2 = isCrossfading && outgoing ? outgoing : null
  const deck3 = nextUp
  const deck4: PlayerTrackMeta | null = null

  return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none bg-black">

      {view === 'decks' ? (
        /* ══════ 4-DECK GRID VIEW ══════ */
        <>
          {/* Top row: Deck 1 | Deck 2 */}
          <div className="flex flex-1 min-h-0 border-b border-foreground/5">
            <DeckQuadrant label="Deck 1" track={deck1} active={!!deck1 && isPlaying} progress={progress} time={formatTime(position)} bars={BARS_A} color="oklch(0.9 0 0 / 0.6)" />
            <div className="w-px bg-foreground/5" />
            <DeckQuadrant label="Deck 2" track={deck2} active={!!deck2 && isCrossfading} progress={isCrossfading ? 0.5 : 0} time="" bars={BARS_B} color="oklch(0.7 0.17 240 / 0.6)" />
          </div>

          {/* Bottom row: Deck 3 | Deck 4 */}
          <div className="flex flex-1 min-h-0 border-b border-foreground/5">
            <DeckQuadrant label="Deck 3" track={deck3} active={false} progress={0} time="" bars={BARS_C} color="oklch(0.7 0.18 50 / 0.6)" />
            <div className="w-px bg-foreground/5" />
            <DeckQuadrant label="Deck 4" track={deck4} active={false} progress={0} time="" bars={BARS_D} color="oklch(0.9 0 0 / 0.4)" />
          </div>
        </>
      ) : (
        /* ══════ MASTER VIEW ══════ */
        <MasterView
          track={current}
          isPlaying={isPlaying}
          progress={progress}
          position={position}
          duration={duration}
          masterBpm={masterTempoBpm}
          style={activeStyle}
          isCrossfading={isCrossfading}
        />
      )}

      {/* ══════ CENTER HUB — always visible ══════ */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
        <div className="pointer-events-auto flex items-center gap-4">
          {/* Next */}
          {current && (
            <button
              type="button"
              onClick={handleNext}
              className="size-11 rounded-full border border-foreground/10 text-foreground/40 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all"
              aria-label="Next track"
            >
              <IconPlayerSkipForwardFilled className="size-4" />
            </button>
          )}

          {/* PLAY / PAUSE */}
          <button
            type="button"
            onClick={current ? () => audio.toggle() : handleStart}
            disabled={isLoading}
            className="size-20 rounded-full bg-foreground text-background flex items-center justify-center hover:bg-foreground/90 active:scale-95 transition-transform shadow-2xl ring-4 ring-black/50"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isLoading ? (
              <IconLoader2 className="size-8 animate-spin" />
            ) : isPlaying ? (
              <IconPlayerPauseFilled className="size-8" />
            ) : (
              <IconPlayerPlayFilled className="size-8 translate-x-[2px]" />
            )}
          </button>

          {/* VIEW TOGGLE — decks ↔ master */}
          <button
            type="button"
            onClick={() => setView(view === 'decks' ? 'master' : 'decks')}
            className="size-11 rounded-full border border-foreground/10 text-foreground/40 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all"
            aria-label={view === 'decks' ? 'Show master' : 'Show decks'}
          >
            {view === 'decks' ? <IconWaveSine className="size-4" /> : <IconLayoutGrid className="size-4" />}
          </button>
        </div>
      </div>

      {/* Idle overlay */}
      {!current && !isLoading && view === 'decks' && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
          <p className="display-heading text-5xl text-foreground/10 mt-16">Mix</p>
        </div>
      )}

      <TransitionVisualizer />
    </div>
  )
}
