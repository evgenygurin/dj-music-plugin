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
import { TrackWaveform } from '@/components/player/track-waveform'
import { TransitionVisualizer } from '@/components/player/transition-visualizer'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/* ── Deterministic waveform bars (used when no real audio) ── */
const BARS = [
  [52,78,34,91,45,67,83,29,61,94,38,72,55,87,41,63,76,33,58,89,44,71,82,36,65,93,47,74,51,85,39,68,57,92,43,77],
  [71,43,88,55,92,37,66,81,48,74,33,85,62,41,79,53,90,35,68,83,46,72,39,87,58,44,76,31,93,64,49,82,57,91,38,70],
  [63,89,41,77,52,84,35,71,93,46,68,38,82,57,44,91,33,76,61,88,49,73,36,85,54,42,79,65,94,37,72,58,83,45,69,31],
  [81,37,74,56,92,43,67,88,34,79,51,85,62,39,77,48,93,41,72,55,83,36,69,94,45,78,33,86,59,44,71,53,91,38,65,82],
]

function StaticWaveform({ index, active, progress, color }: { index: number; active: boolean; progress: number; color: string }) {
  const bars = BARS[index] ?? BARS[0]
  return (
    <div className="flex items-end gap-[1px] h-full w-full">
      {bars.map((h, i) => (
        <div
          key={i}
          className="flex-1 rounded-sm transition-colors duration-100"
          style={{
            height: `${h}%`,
            backgroundColor: active && i / bars.length < progress ? color : active ? 'oklch(0.9 0 0 / 0.1)' : 'oklch(0.4 0 0 / 0.06)',
          }}
        />
      ))}
    </div>
  )
}

/* ── EQ Knob — draggable ── */
function EqKnob({ label, value, onChange, color }: { label: string; value: number; onChange?: (v: number) => void; color?: string }) {
  const knobRef = useRef<HTMLDivElement>(null)
  const startY = useRef(0)
  const startVal = useRef(0)

  const handlePointerDown = (e: React.PointerEvent) => {
    if (!onChange) return
    startY.current = e.clientY
    startVal.current = value
    const el = knobRef.current
    if (el) el.setPointerCapture(e.pointerId)
  }
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!onChange || !knobRef.current?.hasPointerCapture(e.pointerId)) return
    const delta = (startY.current - e.clientY) / 100
    onChange(Math.max(0, Math.min(1, startVal.current + delta)))
  }
  const handlePointerUp = (e: React.PointerEvent) => {
    knobRef.current?.releasePointerCapture(e.pointerId)
  }

  const angle = -135 + value * 270
  const indicatorColor = color ?? 'oklch(0.9 0 0 / 0.6)'

  return (
    <div className="flex flex-col items-center gap-0.5 touch-none">
      <div
        ref={knobRef}
        className="size-9 rounded-full border border-foreground/8 bg-foreground/[0.03] relative cursor-ns-resize"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <div
          className="absolute top-1 left-1/2 w-[1.5px] h-3 rounded-full origin-bottom"
          style={{ transform: `translateX(-50%) rotate(${angle}deg)`, backgroundColor: indicatorColor }}
        />
        {/* Arc track */}
        <svg className="absolute inset-0 size-full -rotate-90" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15" fill="none" stroke="oklch(1 0 0 / 0.04)" strokeWidth="1.5"
            strokeDasharray={`${0.75 * 94.2} ${0.25 * 94.2}`} strokeDashoffset="0" strokeLinecap="round" />
          <circle cx="18" cy="18" r="15" fill="none" stroke={indicatorColor} strokeWidth="1.5"
            strokeDasharray={`${value * 0.75 * 94.2} ${94.2}`} strokeDashoffset="0" strokeLinecap="round" opacity="0.5" />
        </svg>
      </div>
      <span className="dj-data text-[7px] uppercase tracking-wider text-muted-foreground/25">{label}</span>
    </div>
  )
}

/* ── Deck quadrant ── */
function DeckQuadrant({
  index,
  label,
  track,
  active,
  progress,
  time,
  color,
  useRealWaveform,
  position,
  duration,
  onSeek,
}: {
  index: number
  label: string
  track: PlayerTrackMeta | null
  active: boolean
  progress: number
  time: string
  color: string
  useRealWaveform?: boolean
  position?: number
  duration?: number
  onSeek?: (s: number) => void
}) {
  const [hi, setHi] = useState(0.5)
  const [mid, setMid] = useState(0.5)
  const [lo, setLo] = useState(0.5)
  const [vol, setVol] = useState(active ? 0.75 : 0.5)

  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0 relative overflow-hidden">
      {/* Subtle deck color accent line */}
      <div className="h-[2px] w-full" style={{ background: `linear-gradient(90deg, ${color}, transparent)` }} />

      <div className="flex-1 flex flex-col p-2">
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <span className="dj-data text-[8px] uppercase tracking-[0.15em]" style={{ color }}>{label}</span>
          {track && <span className="dj-data text-[9px] text-muted-foreground/25">{time}</span>}
        </div>

        {/* Waveform */}
        <div className="flex-1 min-h-0 flex items-center">
          {/* Always show static bars as instant fallback */}
          <div className="w-full h-full max-h-12 relative">
            <StaticWaveform index={index} active={active} progress={progress} color={color} />
            {/* Real waveform overlays on top once loaded */}
            {useRealWaveform && track && (
              <div className="absolute inset-0">
                <TrackWaveform
                  trackId={track.id}
                  position={position ?? 0}
                  duration={duration ?? 0}
                  onSeek={onSeek ?? (() => {})}
                  height={48}
                  className="w-full"
                />
              </div>
            )}
          </div>
        </div>

        {/* Track info */}
        <div className="mt-1">
          {track ? (
            <>
              <p className="text-[10px] font-medium truncate leading-tight">{track.title}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                {track.bpm && <span className="dj-data text-[9px]" style={{ color }}>{track.bpm.toFixed(0)}</span>}
                {track.camelot && <span className="dj-data text-[8px] text-muted-foreground/25">{track.camelot}</span>}
                {track.mood && <span className="text-[7px] text-muted-foreground/15">{track.mood.replace(/_/g, ' ')}</span>}
              </div>
            </>
          ) : (
            <p className="text-[8px] text-muted-foreground/10">—</p>
          )}
        </div>

        {/* EQ knobs row */}
        <div className="flex items-center justify-around mt-1.5 pt-1.5 border-t border-foreground/[0.03]">
          <EqKnob label="Hi" value={hi} onChange={setHi} color={color} />
          <EqKnob label="Mid" value={mid} onChange={setMid} color={color} />
          <EqKnob label="Lo" value={lo} onChange={setLo} color={color} />
          <EqKnob label="Vol" value={vol} onChange={setVol} color={color} />
        </div>
      </div>
    </div>
  )
}

/* ── Master view ── */
function MasterView({ track, isPlaying, progress, position, duration, masterBpm, style, isCrossfading, onSeek }: {
  track: PlayerTrackMeta | null; isPlaying: boolean; progress: number; position: number; duration: number
  masterBpm: number | null; style: string | null; isCrossfading: boolean; onSeek: (s: number) => void
}) {
  return (
    <div className="flex-1 flex flex-col px-5 justify-center">
      {/* BPM */}
      {masterBpm && (
        <div className="flex items-baseline justify-center gap-2 mb-6">
          <span className="dj-data text-5xl text-foreground">{Math.round(masterBpm)}</span>
          <span className="dj-data text-xs text-muted-foreground/15">BPM</span>
        </div>
      )}

      {/* Track */}
      {track ? (
        <div className="text-center mb-6">
          <h1 className="display-heading text-3xl truncate">{track.title}</h1>
          <p className="text-sm text-muted-foreground/30 mt-1 truncate">{track.artists || ''}</p>
          <div className="flex items-center justify-center gap-4 mt-3">
            {track.bpm && <span className="dj-data text-foreground/50">{track.bpm.toFixed(1)}</span>}
            {track.camelot && <span className="dj-data text-muted-foreground/25">{track.camelot}</span>}
            {track.mood && <span className="text-xs text-muted-foreground/15">{track.mood.replace(/_/g, ' ')}</span>}
          </div>
        </div>
      ) : null}

      {/* Waveform — static instant + real overlay */}
      <div className="rounded-lg border border-foreground/5 bg-foreground/[0.02] p-1.5 mb-4 relative h-20">
        <StaticWaveform index={0} active={isPlaying} progress={progress} color="oklch(0.9 0 0 / 0.5)" />
        {track && (
          <div className="absolute inset-0 p-1.5">
            <TrackWaveform trackId={track.id} position={position} duration={duration} onSeek={onSeek} height={72} />
          </div>
        )}
      </div>

      {/* Time */}
      <div className="flex items-center gap-3">
        <span className="dj-data text-[10px] text-muted-foreground/25 w-10 text-right">{formatTime(position)}</span>
        <div className="flex-1 h-[2px] bg-foreground/5 rounded-full overflow-hidden">
          <div className="h-full bg-foreground/25 transition-[width] duration-200" style={{ width: `${progress * 100}%` }} />
        </div>
        <span className="dj-data text-[10px] text-muted-foreground/25 w-10">{formatTime(duration)}</span>
      </div>

      {/* Transition */}
      {isCrossfading && style && (
        <p className="text-center mt-4 dj-data text-[9px] uppercase tracking-[0.3em] text-muted-foreground/15">
          {style.replace(/_/g, ' ')}
        </p>
      )}
    </div>
  )
}

/* ── Pioneer DDJ deck colors ── */
const DECK_COLORS = [
  'oklch(0.85 0 0)',       // Deck 1 — white (master/active)
  'oklch(0.65 0.15 240)',  // Deck 2 — Pioneer blue
  'oklch(0.65 0.16 50)',   // Deck 3 — Pioneer orange
  'oklch(0.50 0 0)',       // Deck 4 — dim gray (history)
]

/* ── Main ── */
export default function PlayerPage() {
  const audio = useAudioPlayer()
  const queueLoadedRef = useRef(false)
  const [view, setView] = useState<'decks' | 'master'>('decks')
  const [history, setHistory] = useState<PlayerTrackMeta[]>([])

  const { current, isPlaying, isLoading, position, duration, masterTempoBpm, nextUp, outgoing, isCrossfading, lastResolvedStyle, recommendedStyle } = audio
  const progress = current && duration > 0 ? position / duration : 0
  const activeStyle = lastResolvedStyle ?? recommendedStyle

  // Track history — remember last played
  const lastTrackRef = useRef<number | null>(null)
  if (current && current.id !== lastTrackRef.current) {
    if (lastTrackRef.current !== null) {
      const prev = history.find(t => t.id === lastTrackRef.current)
      if (!prev && outgoing) {
        setHistory(h => [outgoing, ...h].slice(0, 10))
      }
    }
    lastTrackRef.current = current.id
  }

  const handleStart = useCallback(async () => {
    if (queueLoadedRef.current && current) { audio.toggle(); return }
    const tracks = await loadDjQueue(128)
    if (tracks.length === 0) return
    const queue: PlayerTrackMeta[] = tracks.map(t => ({
      id: t.id, title: t.title, artists: t.artists, durationMs: t.duration_ms, bpm: t.bpm, camelot: t.camelot, mood: t.mood,
    }))
    if (!audio.autoDj) audio.toggleAutoDj()
    if (!audio.mixEnabled) audio.toggleMixEnabled()
    audio.play(queue[0], queue)
    queueLoadedRef.current = true
  }, [audio, current])

  const handleNext = useCallback(() => { void audio.playRecommendedNext() }, [audio])

  const lastPlayed = history[0] ?? null

  return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none bg-black">

      {view === 'decks' ? (
        <>
          {/* Top row */}
          <div className="flex flex-1 min-h-0">
            <DeckQuadrant index={0} label="A" track={current} active={!!current && isPlaying} progress={progress}
              time={formatTime(position)} color={DECK_COLORS[0]} useRealWaveform={!!current}
              position={position} duration={duration} onSeek={s => audio.seek(s)} />
            <div className="w-px bg-foreground/[0.03]" />
            <DeckQuadrant index={1} label="B" track={isCrossfading && outgoing ? outgoing : null}
              active={!!outgoing && isCrossfading} progress={isCrossfading ? 0.5 : 0} time="" color={DECK_COLORS[1]} />
          </div>

          <div className="h-px bg-foreground/[0.03]" />

          {/* Bottom row */}
          <div className="flex flex-1 min-h-0">
            <DeckQuadrant index={2} label="C" track={nextUp} active={false} progress={0} time="" color={DECK_COLORS[2]} />
            <div className="w-px bg-foreground/[0.03]" />
            <DeckQuadrant index={3} label="D" track={lastPlayed} active={false} progress={0} time="" color={DECK_COLORS[3]} />
          </div>
        </>
      ) : (
        <MasterView track={current} isPlaying={isPlaying} progress={progress} position={position}
          duration={duration} masterBpm={masterTempoBpm} style={activeStyle} isCrossfading={isCrossfading}
          onSeek={s => audio.seek(s)} />
      )}

      {/* ── Center hub ── */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
        <div className="pointer-events-auto flex items-center gap-3">
          {current && (
            <button type="button" onClick={handleNext}
              className="size-10 rounded-full border border-foreground/8 text-foreground/30 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all backdrop-blur-sm"
              aria-label="Next track">
              <IconPlayerSkipForwardFilled className="size-3.5" />
            </button>
          )}
          <button type="button" onClick={current ? () => audio.toggle() : handleStart} disabled={isLoading}
            className="size-[72px] rounded-full bg-foreground text-background flex items-center justify-center hover:bg-foreground/90 active:scale-95 transition-transform shadow-2xl ring-2 ring-black/60"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isLoading ? <IconLoader2 className="size-7 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-7" />
              : <IconPlayerPlayFilled className="size-7 translate-x-[2px]" />}
          </button>
          <button type="button" onClick={() => setView(v => v === 'decks' ? 'master' : 'decks')}
            className="size-10 rounded-full border border-foreground/8 text-foreground/30 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all backdrop-blur-sm"
            aria-label={view === 'decks' ? 'Master view' : 'Deck view'}>
            {view === 'decks' ? <IconWaveSine className="size-3.5" /> : <IconLayoutGrid className="size-3.5" />}
          </button>
        </div>
      </div>

      {!current && !isLoading && view === 'decks' && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
          <p className="display-heading text-6xl text-foreground/[0.04]">Mix</p>
        </div>
      )}

      <TransitionVisualizer />
    </div>
  )
}
