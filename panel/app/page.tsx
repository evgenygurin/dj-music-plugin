'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
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
import { Slider } from '@/components/ui/slider'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/* ── Static waveform ── */
const BARS = [
  [52,78,34,91,45,67,83,29,61,94,38,72,55,87,41,63,76,33,58,89,44,71,82,36,65,93,47,74,51,85,39,68],
  [71,43,88,55,92,37,66,81,48,74,33,85,62,41,79,53,90,35,68,83,46,72,39,87,58,44,76,31,93,64,49,82],
  [63,89,41,77,52,84,35,71,93,46,68,38,82,57,44,91,33,76,61,88,49,73,36,85,54,42,79,65,94,37,72,58],
  [81,37,74,56,92,43,67,88,34,79,51,85,62,39,77,48,93,41,72,55,83,36,69,94,45,78,33,86,59,44,71,53],
]

function StaticWaveform({ index, active, progress, color }: { index: number; active: boolean; progress: number; color: string }) {
  const bars = BARS[index % 4]
  return (
    <div className="flex items-end gap-[1px] h-full w-full">
      {bars.map((h, i) => (
        <div key={i} className="flex-1 rounded-sm transition-colors duration-75"
          style={{ height: `${h}%`, backgroundColor: active && i / bars.length < progress ? color : active ? 'oklch(1 0 0 / 0.08)' : 'oklch(1 0 0 / 0.03)' }} />
      ))}
    </div>
  )
}

/* ── EQ Knob ── */
function Knob({ label, value, onChange, color }: { label: string; value: number; onChange?: (v: number) => void; color?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const startY = useRef(0)
  const startVal = useRef(0)
  const onDown = (e: React.PointerEvent) => { if (!onChange) return; startY.current = e.clientY; startVal.current = value; ref.current?.setPointerCapture(e.pointerId) }
  const onMove = (e: React.PointerEvent) => { if (!onChange || !ref.current?.hasPointerCapture(e.pointerId)) return; onChange(Math.max(0, Math.min(1, startVal.current + (startY.current - e.clientY) / 80))) }
  const onUp = (e: React.PointerEvent) => { ref.current?.releasePointerCapture(e.pointerId) }
  const angle = -135 + value * 270
  const c = color ?? 'oklch(0.7 0 0)'
  return (
    <div className="flex flex-col items-center gap-0.5 touch-none">
      <div ref={ref} className="size-8 rounded-full border border-foreground/6 bg-foreground/[0.02] relative cursor-ns-resize"
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}>
        <div className="absolute top-0.5 left-1/2 w-px h-2.5 rounded-full origin-bottom"
          style={{ transform: `translateX(-50%) rotate(${angle}deg)`, backgroundColor: c }} />
      </div>
      <span className="dj-data text-[6px] uppercase tracking-wider text-muted-foreground/20">{label}</span>
    </div>
  )
}

/* ── Deck quadrant ── */
const DECK_COLORS = ['oklch(0.85 0 0)', 'oklch(0.6 0.14 240)', 'oklch(0.6 0.15 50)', 'oklch(0.4 0 0)']
const DECK_LABELS = ['A', 'B', 'C', 'D']

function DeckQuad({ index, track, active, progress, time, useReal, pos, dur, onSeek, volume, onVolume }: {
  index: number; track: PlayerTrackMeta | null; active: boolean; progress: number; time: string
  useReal?: boolean; pos?: number; dur?: number; onSeek?: (s: number) => void
  volume?: number; onVolume?: (v: number) => void
}) {
  const color = DECK_COLORS[index]
  const [hi, setHi] = useState(0.5)
  const [mid, setMid] = useState(0.5)
  const [lo, setLo] = useState(0.5)

  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
      <div className="h-px w-full" style={{ background: color }} />
      <div className="flex-1 flex flex-col p-2 gap-1">
        {/* Label */}
        <div className="flex items-center justify-between">
          <span className="dj-data text-[8px] tracking-[0.15em]" style={{ color }}>{DECK_LABELS[index]}</span>
          {time && <span className="dj-data text-[8px] text-muted-foreground/20">{time}</span>}
        </div>

        {/* Track title — PRIMARY info */}
        {track ? (
          <div className="min-w-0">
            <p className="text-sm font-medium truncate leading-tight">{track.title}</p>
            <p className="text-[10px] text-muted-foreground/30 truncate">{track.artists || ''}</p>
          </div>
        ) : (
          <p className="text-[9px] text-muted-foreground/10">—</p>
        )}

        {/* BPM / Key / Mood — visible data */}
        {track && (
          <div className="flex items-center gap-2">
            {track.bpm && <span className="dj-data text-xs" style={{ color }}>{track.bpm.toFixed(0)}</span>}
            {track.camelot && <span className="dj-data text-[10px] text-muted-foreground/25">{track.camelot}</span>}
            {track.mood && <span className="text-[8px] text-muted-foreground/15">{track.mood.replace(/_/g, ' ')}</span>}
          </div>
        )}

        {/* Waveform — secondary */}
        <div className="flex-1 min-h-0 relative">
          <div className="h-full max-h-10">
            <StaticWaveform index={index} active={active} progress={progress} color={color} />
          </div>
          {useReal && track && (
            <div className="absolute inset-0">
              <TrackWaveform trackId={track.id} position={pos ?? 0} duration={dur ?? 0}
                onSeek={onSeek ?? (() => {})} height={40} className="w-full" />
            </div>
          )}
        </div>

        {/* EQ — compact row */}
        <div className="flex items-center justify-around pt-1 border-t border-foreground/[0.02]">
          <Knob label="Hi" value={hi} onChange={setHi} color={color} />
          <Knob label="Mid" value={mid} onChange={setMid} color={color} />
          <Knob label="Lo" value={lo} onChange={setLo} color={color} />
          <Knob label="Vol" value={volume ?? 0.75} onChange={onVolume} color={color} />
        </div>
      </div>
    </div>
  )
}

/* ── Session stats for Deck D ── */
function SessionStats({ tracksPlayed, elapsed, color }: { tracksPlayed: number; elapsed: number; color: string }) {
  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
      <div className="h-px w-full" style={{ background: color }} />
      <div className="flex-1 flex flex-col p-2 gap-2 justify-center">
        <span className="dj-data text-[8px] tracking-[0.15em]" style={{ color }}>D</span>
        <div>
          <p className="dj-data text-[9px] uppercase tracking-wider text-muted-foreground/20">Session</p>
          <p className="dj-data text-2xl text-foreground/60 leading-none mt-1">{tracksPlayed}</p>
          <p className="text-[8px] text-muted-foreground/15 mt-0.5">tracks mixed</p>
        </div>
        <div>
          <p className="dj-data text-lg text-foreground/40 leading-none">{formatTime(elapsed)}</p>
          <p className="text-[8px] text-muted-foreground/15 mt-0.5">elapsed</p>
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
      {masterBpm && (
        <div className="flex items-baseline justify-center gap-2 mb-8">
          <span className="dj-data text-6xl text-foreground">{Math.round(masterBpm)}</span>
          <span className="dj-data text-sm text-muted-foreground/15">BPM</span>
        </div>
      )}
      {track && (
        <div className="text-center mb-8">
          <h1 className="display-heading text-3xl truncate">{track.title}</h1>
          <p className="text-sm text-muted-foreground/30 mt-1">{track.artists || ''}</p>
          <div className="flex items-center justify-center gap-4 mt-3">
            {track.bpm && <span className="dj-data text-foreground/40">{track.bpm.toFixed(1)}</span>}
            {track.camelot && <span className="dj-data text-muted-foreground/20">{track.camelot}</span>}
          </div>
        </div>
      )}
      <div className="relative h-20 rounded-lg border border-foreground/5 bg-foreground/[0.015] p-1.5 mb-4">
        <StaticWaveform index={0} active={isPlaying} progress={progress} color="oklch(0.9 0 0 / 0.4)" />
        {track && (
          <div className="absolute inset-0 p-1.5">
            <TrackWaveform trackId={track.id} position={position} duration={duration} onSeek={onSeek} height={72} />
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        <span className="dj-data text-[10px] text-muted-foreground/20 w-10 text-right">{formatTime(position)}</span>
        <div className="flex-1 h-[2px] bg-foreground/5 rounded-full overflow-hidden">
          <div className="h-full bg-foreground/20" style={{ width: `${progress * 100}%` }} />
        </div>
        <span className="dj-data text-[10px] text-muted-foreground/20 w-10">{formatTime(duration)}</span>
      </div>
      {isCrossfading && style && (
        <p className="text-center mt-6 dj-data text-[9px] uppercase tracking-[0.3em] text-muted-foreground/15">{style.replace(/_/g, ' ')}</p>
      )}
    </div>
  )
}

/* ── Idle screen with BPM selector ── */
function IdleScreen({ onStart, isLoading }: { onStart: (bpm: number) => void; isLoading: boolean }) {
  const [bpm, setBpm] = useState(128)
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-8 gap-10">
      <div className="text-center">
        <p className="dj-data text-7xl text-foreground">{bpm}</p>
        <p className="dj-data text-xs text-muted-foreground/20 mt-1">BPM</p>
      </div>
      <div className="w-full max-w-xs">
        <Slider value={[bpm]} min={118} max={150} step={1}
          onValueChange={v => setBpm(v[0])} aria-label="Master BPM" />
        <div className="flex justify-between mt-1.5">
          <span className="dj-data text-[8px] text-muted-foreground/15">118</span>
          <span className="dj-data text-[8px] text-muted-foreground/15">150</span>
        </div>
      </div>
      <button type="button" onClick={() => onStart(bpm)} disabled={isLoading}
        className="size-24 rounded-full bg-foreground text-background flex items-center justify-center hover:bg-foreground/90 active:scale-95 transition-transform shadow-2xl"
        aria-label="Start mixing">
        {isLoading ? <IconLoader2 className="size-10 animate-spin" /> : <IconPlayerPlayFilled className="size-10 translate-x-[3px]" />}
      </button>
    </div>
  )
}

/* ══════ MAIN ══════ */
export default function PlayerPage() {
  const audio = useAudioPlayer()
  const [view, setView] = useState<'decks' | 'master'>('decks')
  const [tracksPlayed, setTracksPlayed] = useState(0)
  const [sessionStart, setSessionStart] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const lastIdRef = useRef<number | null>(null)

  const { current, isPlaying, isLoading, position, duration, masterTempoBpm, nextUp, outgoing, isCrossfading, lastResolvedStyle, recommendedStyle, volume } = audio
  const progress = current && duration > 0 ? position / duration : 0
  const activeStyle = lastResolvedStyle ?? recommendedStyle

  // Track counter
  if (current && current.id !== lastIdRef.current) {
    if (lastIdRef.current !== null) setTracksPlayed(n => n + 1)
    lastIdRef.current = current.id
  }

  // Session timer
  useEffect(() => {
    if (!sessionStart) return
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - sessionStart) / 1000)), 1000)
    return () => clearInterval(iv)
  }, [sessionStart])

  const handleStart = useCallback(async (bpm: number) => {
    const tracks = await loadDjQueue(bpm)
    if (tracks.length === 0) return
    const queue: PlayerTrackMeta[] = tracks.map(t => ({
      id: t.id, title: t.title, artists: t.artists, durationMs: t.duration_ms, bpm: t.bpm, camelot: t.camelot, mood: t.mood,
    }))
    if (!audio.autoDj) audio.toggleAutoDj()
    if (!audio.mixEnabled) audio.toggleMixEnabled()
    audio.play(queue[0], queue)
    setSessionStart(Date.now())
  }, [audio])

  const handleNext = useCallback(() => { void audio.playRecommendedNext() }, [audio])
  const handleVol = useCallback((v: number) => { audio.setVolume(v) }, [audio])

  // Idle — no track loaded
  if (!current && !isLoading) {
    return (
      <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none bg-black">
        <IdleScreen onStart={handleStart} isLoading={isLoading} />
      </div>
    )
  }

  return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none bg-black">
      {view === 'decks' ? (
        <>
          <div className="flex flex-1 min-h-0">
            <DeckQuad index={0} track={current} active={!!current && isPlaying} progress={progress}
              time={formatTime(position)} useReal={!!current} pos={position} dur={duration}
              onSeek={s => audio.seek(s)} volume={volume} onVolume={handleVol} />
            <div className="w-px bg-foreground/[0.03]" />
            <DeckQuad index={1} track={isCrossfading && outgoing ? outgoing : null}
              active={!!outgoing && isCrossfading} progress={isCrossfading ? 0.5 : 0} time="" />
          </div>
          <div className="h-px bg-foreground/[0.03]" />
          <div className="flex flex-1 min-h-0">
            <DeckQuad index={2} track={nextUp} active={false} progress={0} time="" />
            <div className="w-px bg-foreground/[0.03]" />
            <SessionStats tracksPlayed={tracksPlayed} elapsed={elapsed} color={DECK_COLORS[3]} />
          </div>
        </>
      ) : (
        <MasterView track={current} isPlaying={isPlaying} progress={progress} position={position}
          duration={duration} masterBpm={masterTempoBpm} style={activeStyle} isCrossfading={isCrossfading}
          onSeek={s => audio.seek(s)} />
      )}

      {/* Center hub */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
        <div className="pointer-events-auto flex items-center gap-3">
          {current && (
            <button type="button" onClick={handleNext}
              className="size-10 rounded-full border border-foreground/8 text-foreground/30 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all backdrop-blur-sm"
              aria-label="Next track">
              <IconPlayerSkipForwardFilled className="size-3.5" />
            </button>
          )}
          <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
            className="size-[68px] rounded-full bg-foreground text-background flex items-center justify-center hover:bg-foreground/90 active:scale-95 transition-transform shadow-2xl ring-2 ring-black/60"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isLoading ? <IconLoader2 className="size-7 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-7" />
              : <IconPlayerPlayFilled className="size-7 translate-x-[2px]" />}
          </button>
          <button type="button" onClick={() => setView(v => v === 'decks' ? 'master' : 'decks')}
            className="size-10 rounded-full border border-foreground/8 text-foreground/30 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all backdrop-blur-sm"
            aria-label={view === 'decks' ? 'Master' : 'Decks'}>
            {view === 'decks' ? <IconWaveSine className="size-3.5" /> : <IconLayoutGrid className="size-3.5" />}
          </button>
        </div>
      </div>

      <TransitionVisualizer />
    </div>
  )
}
