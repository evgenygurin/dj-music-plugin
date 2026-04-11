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

function fmt(s: number): string {
  if (!Number.isFinite(s) || s < 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/* ── Volume knob ── */
function VolKnob({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const sy = useRef(0); const sv = useRef(0)
  const angle = -135 + value * 270
  return (
    <div className="flex items-center gap-2 touch-none">
      <div ref={ref} className="size-10 rounded-full border border-foreground/8 bg-foreground/[0.02] relative cursor-ns-resize"
        onPointerDown={e => { sy.current = e.clientY; sv.current = value; ref.current?.setPointerCapture(e.pointerId) }}
        onPointerMove={e => { if (!ref.current?.hasPointerCapture(e.pointerId)) return; onChange(Math.max(0, Math.min(1, sv.current + (sy.current - e.clientY) / 80))) }}
        onPointerUp={e => ref.current?.releasePointerCapture(e.pointerId)}>
        <div className="absolute top-1 left-1/2 w-[1.5px] h-3 rounded-full bg-foreground/50 origin-bottom"
          style={{ transform: `translateX(-50%) rotate(${angle}deg)` }} />
      </div>
      <span className="dj-data text-[8px] text-muted-foreground/20">VOL</span>
    </div>
  )
}

/* ── Static waveform ── */
const BARS = [52,78,34,91,45,67,83,29,61,94,38,72,55,87,41,63,76,33,58,89,44,71,82,36,65,93,47,74,51,85,39,68]
function MiniWave({ active, progress }: { active: boolean; progress: number }) {
  return (
    <div className="flex items-end gap-[1px] h-full w-full">
      {BARS.map((h, i) => (
        <div key={i} className="flex-1 rounded-sm transition-colors duration-75"
          style={{ height: `${h}%`, backgroundColor: active && i / BARS.length < progress ? 'oklch(1 0 0 / 0.5)' : 'oklch(1 0 0 / 0.04)' }} />
      ))}
    </div>
  )
}

/* ── DECK A: Now Playing ── */
function DeckA({ track, isPlaying, position, duration, volume, onVol, onSeek }: {
  track: PlayerTrackMeta; isPlaying: boolean; position: number; duration: number
  volume: number; onVol: (v: number) => void; onSeek: (s: number) => void
}) {
  const progress = duration > 0 ? position / duration : 0
  return (
    <div className="flex-1 flex flex-col p-3 min-w-0 min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-1">
        <span className="dj-data text-[8px] tracking-[0.15em] text-foreground/40">A</span>
        <span className="dj-data text-[9px] text-muted-foreground/25">{fmt(position)} / {fmt(duration)}</span>
      </div>

      {/* Title — PRIMARY */}
      <h2 className="text-base font-medium truncate leading-tight">{track.title}</h2>
      <p className="text-[10px] text-muted-foreground/30 truncate mt-0.5">{track.artists || ''}</p>

      {/* BPM / Key / Mood */}
      <div className="flex items-center gap-2 mt-1.5">
        {track.bpm && <span className="dj-data text-sm text-foreground/70">{track.bpm.toFixed(0)}</span>}
        {track.camelot && <span className="dj-data text-xs text-muted-foreground/30">{track.camelot}</span>}
        {track.mood && <span className="text-[9px] text-muted-foreground/20">{track.mood.replace(/_/g, ' ')}</span>}
      </div>

      {/* Waveform */}
      <div className="flex-1 min-h-0 mt-2 relative">
        <div className="h-full max-h-10">
          <MiniWave active={isPlaying} progress={progress} />
        </div>
        <div className="absolute inset-0">
          <TrackWaveform trackId={track.id} position={position} duration={duration} onSeek={onSeek} height={40} className="w-full" />
        </div>
      </div>

      {/* Volume */}
      <div className="mt-2">
        <VolKnob value={volume} onChange={onVol} />
      </div>
    </div>
  )
}

/* ── DECK B: Transition Zone ── */
function DeckB({ outgoing, isCrossfading, style, bars }: {
  outgoing: PlayerTrackMeta | null; isCrossfading: boolean; style: string | null; bars: number
}) {
  return (
    <div className="flex-1 flex flex-col p-3 min-w-0 min-h-0 overflow-hidden">
      <span className="dj-data text-[8px] tracking-[0.15em] text-[oklch(0.6_0.14_240)] mb-2">B</span>

      {isCrossfading && outgoing ? (
        <>
          <p className="text-[9px] uppercase tracking-wider text-muted-foreground/20 mb-1">Outgoing</p>
          <p className="text-sm font-medium truncate">{outgoing.title}</p>
          <p className="text-[10px] text-muted-foreground/25 truncate">{outgoing.artists || ''}</p>
          {outgoing.bpm && <span className="dj-data text-xs text-[oklch(0.6_0.14_240)] mt-1">{outgoing.bpm.toFixed(0)}</span>}
          {style && (
            <div className="mt-3 rounded-lg border border-foreground/5 bg-foreground/[0.02] p-2">
              <p className="dj-data text-[8px] uppercase tracking-wider text-muted-foreground/20">Style</p>
              <p className="dj-data text-sm text-foreground/60 mt-0.5">{style.replace(/_/g, ' ')}</p>
            </div>
          )}
        </>
      ) : (
        <>
          <p className="text-[9px] uppercase tracking-wider text-muted-foreground/15 mb-2">Transition</p>
          <div className="space-y-2">
            <div>
              <p className="text-[8px] text-muted-foreground/15">Crossfade</p>
              <p className="dj-data text-lg text-foreground/40">{bars} <span className="text-[9px] text-muted-foreground/15">bars</span></p>
            </div>
            <div>
              <p className="text-[8px] text-muted-foreground/15">Mode</p>
              <p className="dj-data text-xs text-foreground/30">auto</p>
            </div>
          </div>
          <p className="text-[8px] text-muted-foreground/10 mt-auto">Waiting for next transition...</p>
        </>
      )}
    </div>
  )
}

/* ── DECK C: Next Up ── */
function DeckC({ current, next }: { current: PlayerTrackMeta | null; next: PlayerTrackMeta | null }) {
  if (!next) return (
    <div className="flex-1 flex flex-col p-3 min-w-0">
      <span className="dj-data text-[8px] tracking-[0.15em] text-[oklch(0.6_0.15_50)]">C</span>
      <p className="text-[9px] text-muted-foreground/10 mt-2">Queue empty</p>
    </div>
  )

  const bpmDelta = current?.bpm && next.bpm ? Math.abs(current.bpm - next.bpm) : null
  const bpmOk = bpmDelta !== null && bpmDelta <= 3

  return (
    <div className="flex-1 flex flex-col p-3 min-w-0 min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-1">
        <span className="dj-data text-[8px] tracking-[0.15em] text-[oklch(0.6_0.15_50)]">C</span>
        <span className="text-[8px] uppercase tracking-wider text-muted-foreground/15">Next</span>
      </div>

      <p className="text-sm font-medium truncate leading-tight">{next.title}</p>
      <p className="text-[10px] text-muted-foreground/25 truncate mt-0.5">{next.artists || ''}</p>

      <div className="flex items-center gap-2 mt-1.5">
        {next.bpm && <span className="dj-data text-xs text-[oklch(0.6_0.15_50)]">{next.bpm.toFixed(0)}</span>}
        {next.camelot && <span className="dj-data text-[10px] text-muted-foreground/25">{next.camelot}</span>}
        {next.mood && <span className="text-[8px] text-muted-foreground/15">{next.mood.replace(/_/g, ' ')}</span>}
      </div>

      {/* Compatibility */}
      <div className="mt-auto pt-2 space-y-1.5">
        {bpmDelta !== null && (
          <div className="flex items-center justify-between">
            <span className="text-[8px] text-muted-foreground/15">BPM Δ</span>
            <span className={`dj-data text-[10px] ${bpmOk ? 'text-foreground/40' : 'text-red-400/60'}`}>
              {bpmDelta < 0.1 ? '±0' : `±${bpmDelta.toFixed(1)}`}
            </span>
          </div>
        )}
        {current?.camelot && next.camelot && (
          <div className="flex items-center justify-between">
            <span className="text-[8px] text-muted-foreground/15">Key</span>
            <span className="dj-data text-[10px] text-foreground/30">
              {current.camelot} → {next.camelot}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── DECK D: Session ── */
function DeckD({ count, elapsed, history }: { count: number; elapsed: number; history: PlayerTrackMeta[] }) {
  return (
    <div className="flex-1 flex flex-col p-3 min-w-0 min-h-0 overflow-hidden">
      <span className="dj-data text-[8px] tracking-[0.15em] text-muted-foreground/20 mb-2">D</span>

      <div className="flex items-baseline gap-3 mb-3">
        <div>
          <p className="dj-data text-2xl text-foreground/50 leading-none">{count}</p>
          <p className="text-[7px] text-muted-foreground/10 mt-0.5">mixed</p>
        </div>
        <div>
          <p className="dj-data text-lg text-foreground/30 leading-none">{fmt(elapsed)}</p>
          <p className="text-[7px] text-muted-foreground/10 mt-0.5">elapsed</p>
        </div>
      </div>

      {/* History */}
      {history.length > 0 && (
        <div className="space-y-1 overflow-hidden">
          <p className="text-[7px] uppercase tracking-wider text-muted-foreground/10">History</p>
          {history.slice(0, 4).map((t, i) => (
            <p key={t.id} className="text-[9px] text-muted-foreground/15 truncate leading-tight">
              {t.title}
              {t.bpm ? ` · ${t.bpm.toFixed(0)}` : ''}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Master View ── */
function MasterView({ track, isPlaying, progress, position, duration, bpm, style, fading, onSeek }: {
  track: PlayerTrackMeta | null; isPlaying: boolean; progress: number; position: number; duration: number
  bpm: number | null; style: string | null; fading: boolean; onSeek: (s: number) => void
}) {
  return (
    <div className="flex-1 flex flex-col px-6 justify-center">
      {bpm && (
        <div className="flex items-baseline justify-center gap-2 mb-8">
          <span className="dj-data text-6xl text-foreground">{Math.round(bpm)}</span>
          <span className="dj-data text-sm text-muted-foreground/15">BPM</span>
        </div>
      )}
      {track && (
        <div className="text-center mb-8">
          <h1 className="display-heading text-3xl truncate">{track.title}</h1>
          <p className="text-sm text-muted-foreground/25 mt-1">{track.artists || ''}</p>
          <div className="flex items-center justify-center gap-4 mt-3">
            {track.bpm && <span className="dj-data text-foreground/40">{track.bpm.toFixed(1)}</span>}
            {track.camelot && <span className="dj-data text-muted-foreground/20">{track.camelot}</span>}
          </div>
        </div>
      )}
      <div className="relative h-20 rounded-lg border border-foreground/5 bg-foreground/[0.015] p-1.5 mb-4">
        <MiniWave active={isPlaying} progress={progress} />
        {track && <div className="absolute inset-0 p-1.5"><TrackWaveform trackId={track.id} position={position} duration={duration} onSeek={onSeek} height={72} /></div>}
      </div>
      <div className="flex items-center gap-3">
        <span className="dj-data text-[10px] text-muted-foreground/20 w-10 text-right">{fmt(position)}</span>
        <div className="flex-1 h-[2px] bg-foreground/5 rounded-full overflow-hidden">
          <div className="h-full bg-foreground/20" style={{ width: `${progress * 100}%` }} />
        </div>
        <span className="dj-data text-[10px] text-muted-foreground/20 w-10">{fmt(duration)}</span>
      </div>
      {fading && style && <p className="text-center mt-6 dj-data text-[9px] uppercase tracking-[0.3em] text-muted-foreground/15">{style.replace(/_/g, ' ')}</p>}
    </div>
  )
}

/* ── Idle ── */
function Idle({ onStart, loading }: { onStart: (bpm: number) => void; loading: boolean }) {
  const [bpm, setBpm] = useState(128)
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-10 gap-10">
      <div className="text-center">
        <p className="dj-data text-7xl text-foreground">{bpm}</p>
        <p className="dj-data text-xs text-muted-foreground/15 mt-1">BPM</p>
      </div>
      <div className="w-full max-w-xs">
        <Slider value={[bpm]} min={118} max={150} step={1} onValueChange={v => setBpm(v[0])} aria-label="BPM" />
        <div className="flex justify-between mt-1"><span className="dj-data text-[8px] text-muted-foreground/10">118</span><span className="dj-data text-[8px] text-muted-foreground/10">150</span></div>
      </div>
      <button type="button" onClick={() => onStart(bpm)} disabled={loading}
        className="size-24 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform shadow-2xl"
        aria-label="Play">
        {loading ? <IconLoader2 className="size-10 animate-spin" /> : <IconPlayerPlayFilled className="size-10 translate-x-[3px]" />}
      </button>
    </div>
  )
}

/* ══════ MAIN ══════ */
export default function PlayerPage() {
  const audio = useAudioPlayer()
  const [view, setView] = useState<'decks' | 'master'>('decks')
  const [count, setCount] = useState(0)
  const [start, setStart] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [history, setHistory] = useState<PlayerTrackMeta[]>([])
  const lastRef = useRef<number | null>(null)

  const { current, isPlaying, isLoading, position, duration, masterTempoBpm, nextUp, outgoing,
    isCrossfading, lastResolvedStyle, recommendedStyle, volume, crossfadeBars } = audio
  const progress = current && duration > 0 ? position / duration : 0

  // Track counter + history
  if (current && current.id !== lastRef.current) {
    if (lastRef.current !== null) {
      setCount(n => n + 1)
      if (outgoing) setHistory(h => [outgoing, ...h].slice(0, 10))
    }
    lastRef.current = current.id
  }

  // Timer
  useEffect(() => {
    if (!start) return
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(iv)
  }, [start])

  const handleStart = useCallback(async (bpm: number) => {
    const tracks = await loadDjQueue(bpm)
    if (tracks.length === 0) return
    const q: PlayerTrackMeta[] = tracks.map(t => ({ id: t.id, title: t.title, artists: t.artists, durationMs: t.duration_ms, bpm: t.bpm, camelot: t.camelot, mood: t.mood }))
    if (!audio.autoDj) audio.toggleAutoDj()
    if (!audio.mixEnabled) audio.toggleMixEnabled()
    audio.play(q[0], q)
    setStart(Date.now())
  }, [audio])

  if (!current && !isLoading) return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none bg-black">
      <Idle onStart={handleStart} loading={isLoading} />
    </div>
  )

  return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none bg-black">
      {view === 'decks' && current ? (
        <div className="flex flex-1 min-h-0">
          {/* Left column: Deck B (top) + Deck A (bottom) */}
          <div className="flex-1 flex flex-col min-w-0">
            <DeckB outgoing={isCrossfading ? outgoing : null} isCrossfading={isCrossfading}
              style={(lastResolvedStyle ?? recommendedStyle)} bars={crossfadeBars} />
            <div className="h-px bg-foreground/[0.03]" />
            <DeckA track={current} isPlaying={isPlaying} position={position} duration={duration}
              volume={volume} onVol={v => audio.setVolume(v)} onSeek={s => audio.seek(s)} />
          </div>

          {/* Vertical divider */}
          <div className="w-px bg-foreground/[0.03]" />

          {/* Right column: Deck D (top) + Deck C (bottom) */}
          <div className="flex-1 flex flex-col min-w-0">
            <DeckD count={count} elapsed={elapsed} history={history} />
            <div className="h-px bg-foreground/[0.03]" />
            <DeckC current={current} next={nextUp} />
          </div>
        </div>
      ) : (
        <MasterView track={current} isPlaying={isPlaying} progress={progress} position={position}
          duration={duration} bpm={masterTempoBpm} style={lastResolvedStyle ?? recommendedStyle}
          fading={isCrossfading} onSeek={s => audio.seek(s)} />
      )}

      {/* Hub */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
        <div className="pointer-events-auto flex items-center gap-3">
          {current && (
            <button type="button" onClick={() => void audio.playRecommendedNext()}
              className="size-10 rounded-full border border-foreground/8 text-foreground/25 flex items-center justify-center active:scale-95 transition-all backdrop-blur-sm"
              aria-label="Next"><IconPlayerSkipForwardFilled className="size-3.5" /></button>
          )}
          <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
            className="size-[68px] rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform shadow-2xl ring-2 ring-black/60"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isLoading ? <IconLoader2 className="size-7 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-7" />
              : <IconPlayerPlayFilled className="size-7 translate-x-[2px]" />}
          </button>
          <button type="button" onClick={() => setView(v => v === 'decks' ? 'master' : 'decks')}
            className="size-10 rounded-full border border-foreground/8 text-foreground/25 flex items-center justify-center active:scale-95 transition-all backdrop-blur-sm"
            aria-label="Toggle view">
            {view === 'decks' ? <IconWaveSine className="size-3.5" /> : <IconLayoutGrid className="size-3.5" />}
          </button>
        </div>
      </div>

      <TransitionVisualizer />
    </div>
  )
}
