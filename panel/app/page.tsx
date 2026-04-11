'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  IconLoader2,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipForwardFilled,
  IconAdjustments,
  IconWaveSine,
  IconGridDots,
  IconMusic,
  IconBolt,
} from '@tabler/icons-react'

import { loadDjQueue } from '@/actions/library-actions'
import { recordTrackFeedback } from '@/actions/feedback-actions'
import { setEq, resetEq, setFilter } from '@/actions/mixer-actions'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import type { PlayerTrackMeta } from '@/components/audio-player/audio-player-types'
import { TrackWaveform } from '@/components/player/track-waveform'
import { TransitionVisualizer } from '@/components/player/transition-visualizer'
import { Slider } from '@/components/ui/slider'

function fmt(s: number) {
  if (!Number.isFinite(s) || s < 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

type MiddlePanel = 'eq' | 'mix' | 'pads' | 'fx'

/* ══════ IDLE ══════ */
function IdleScreen({ onStart, loading }: { onStart: (bpm: number) => void; loading: boolean }) {
  const [bpm, setBpm] = useState(128)
  return (
    <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="size-[280px] rounded-full bg-foreground/[0.02] animate-pulse" style={{ animationDuration: '3s' }} />
      </div>
      <div className="relative z-10 flex flex-col items-center gap-8">
        <p className="dj-data text-[96px] leading-none text-foreground tracking-tight">{bpm}</p>
        <div className="w-[200px]">
          <Slider value={[bpm]} min={118} max={150} step={1} onValueChange={v => setBpm(v[0])} />
          <div className="flex justify-between mt-1.5 px-0.5">
            <span className="dj-data text-[8px] text-muted-foreground/15">118</span>
            <span className="dj-data text-[8px] text-muted-foreground/10">BPM</span>
            <span className="dj-data text-[8px] text-muted-foreground/15">150</span>
          </div>
        </div>
        <button type="button" onClick={() => onStart(bpm)} disabled={loading}
          className="size-24 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform shadow-[0_0_80px_oklch(1_0_0/0.1)]"
          aria-label="Play">
          {loading ? <IconLoader2 className="size-10 animate-spin" /> : <IconPlayerPlayFilled className="size-10 translate-x-[2px]" />}
        </button>
      </div>
    </div>
  )
}

/* ── EQ Panel (like djay EQ view) ── */
function EqPanel() {
  const audio = useAudioPlayer()
  const [lo, setLo] = useState(50)
  const [mid, setMid] = useState(50)
  const [hi, setHi] = useState(50)
  const [fil, setFil] = useState(100)

  const pctToDb = (pct: number) => pct <= 50 ? -40 + (pct / 50) * 40 : ((pct - 50) / 50) * 6
  const applyEq = useCallback((band: 'low' | 'mid' | 'high', pct: number) => {
    audio.setDeckEq(band, pctToDb(pct))
    void setEq(1, band, pctToDb(pct))
  }, [audio])

  return (
    <div className="flex-1 flex flex-col px-4 py-2 gap-3">
      <div className="flex items-center justify-between">
        <span className="dj-data text-[9px] uppercase tracking-wider text-muted-foreground/20">EQ</span>
        <button type="button" onClick={() => {
          setLo(50); setMid(50); setHi(50); setFil(100)
          audio.setDeckEq('low', 0); audio.setDeckEq('mid', 0); audio.setDeckEq('high', 0)
          void resetEq(1)
        }} className="dj-data text-[8px] text-muted-foreground/15 active:text-foreground/40">RESET</button>
      </div>
      {/* Vertical faders like djay EQ view */}
      <div className="flex-1 flex items-stretch gap-4 justify-center">
        {[
          { label: 'LOW', value: lo, set: setLo, band: 'low' as const },
          { label: 'MID', value: mid, set: setMid, band: 'mid' as const },
          { label: 'HIGH', value: hi, set: setHi, band: 'high' as const },
          { label: 'FILTER', value: fil, set: setFil, band: null },
        ].map(({ label, value, set, band }) => (
          <div key={label} className="flex flex-col items-center gap-1 flex-1">
            <span className="dj-data text-[7px] text-muted-foreground/15">{label}</span>
            <div className="flex-1 flex items-center justify-center">
              <Slider value={[value]} min={0} max={100} step={1}
                onValueChange={v => {
                  set(v[0])
                  if (band) applyEq(band, v[0])
                  else void setFilter(1, 20 * Math.pow(1000, v[0] / 100))
                }} className="h-full" aria-label={label} />
            </div>
            <button type="button" onClick={() => { set(0); if (band) applyEq(band, 0) }}
              className="dj-data text-[7px] text-muted-foreground/8 active:text-red-400/50 px-2 py-0.5 rounded border border-foreground/[0.04]">
              KILL
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Neural Mix Panel (DRUMS / HARMONIC / VOCALS faders) ── */
function NeuralMixPanel() {
  const stems = [
    { label: 'DRUMS', icon: '🥁', value: 100 },
    { label: 'HARMONIC', icon: '🎹', value: 100 },
    { label: 'VOCALS', icon: '🎤', value: 100 },
  ]
  return (
    <div className="flex-1 flex flex-col px-4 py-2">
      <span className="dj-data text-[9px] uppercase tracking-[0.15em] text-center text-muted-foreground/20 mb-2">
        NEURAL<span className="text-foreground/30">MIX</span>
      </span>
      <div className="flex-1 flex gap-3">
        {stems.map(s => (
          <div key={s.label} className="flex-1 flex flex-col items-center gap-1">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">{s.icon}</span>
              <button className="text-muted-foreground/15 active:text-foreground/30 text-[10px]">🔇</button>
            </div>
            <span className="dj-data text-[7px] text-muted-foreground/15">{s.label}</span>
            <div className="flex-1 w-full flex items-center justify-center">
              <div className="w-full h-full rounded border border-foreground/[0.04] bg-foreground/[0.02] flex items-end justify-center p-1">
                <div className="w-full bg-foreground/20 rounded-sm" style={{ height: `${s.value}%` }} />
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[8px] text-center text-muted-foreground/8 mt-1">Stems require server-side Demucs processing</p>
    </div>
  )
}

/* ── Cue Pads Panel (4x2 grid) ── */
function CuePadsPanel({ trackId }: { trackId: number }) {
  const pads = Array.from({ length: 8 }, (_, i) => i + 1)
  return (
    <div className="flex-1 flex flex-col px-3 py-2">
      <div className="flex items-center gap-3 mb-2">
        <span className="dj-data text-[9px] text-foreground/30">Cue</span>
        <span className="dj-data text-[9px] text-muted-foreground/15">Pitch Cue</span>
        <span className="dj-data text-[9px] text-muted-foreground/15">Slice</span>
      </div>
      <div className="flex-1 grid grid-cols-4 grid-rows-2 gap-1.5">
        {pads.map(i => (
          <button key={i} type="button"
            className="rounded-lg border border-foreground/[0.06] bg-foreground/[0.02] flex items-center justify-center active:bg-foreground/10 transition-colors">
            <span className="text-muted-foreground/15 text-lg">+</span>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── FX Panel (Reverb / Echo / Alarm) ── */
function FxPanel() {
  const effects = [
    { name: 'Reverb', on: false },
    { name: 'Echo', on: false, sub: '1/16 BEAT' },
    { name: 'Filter Sweep', on: false },
  ]
  return (
    <div className="flex-1 flex flex-col px-3 py-2">
      <div className="flex items-center gap-3 mb-2">
        <span className="dj-data text-[9px] text-muted-foreground/15">Pad</span>
        <span className="dj-data text-[9px] text-muted-foreground/15">Instant</span>
        <span className="dj-data text-[9px] text-foreground/30">Manual</span>
      </div>
      <div className="flex-1 flex flex-col gap-2">
        {effects.map(fx => (
          <div key={fx.name} className="flex items-center gap-2 rounded-lg border border-foreground/[0.04] bg-foreground/[0.015] px-2 py-1.5">
            <button className="dj-data text-[8px] px-2 py-0.5 rounded border border-foreground/[0.06] text-muted-foreground/20 active:text-foreground/50 active:border-foreground/20">
              ON
            </button>
            <div className="flex-1">
              <p className="dj-data text-[10px] text-foreground/30">{fx.name}</p>
              {fx.sub && <p className="dj-data text-[7px] text-muted-foreground/10">{fx.sub}</p>}
            </div>
            <span className="dj-data text-[7px] text-muted-foreground/10">D/W</span>
            <div className="size-6 rounded-full border border-foreground/[0.06] bg-foreground/[0.02]" />
          </div>
        ))}
      </div>
    </div>
  )
}

/* ══════ PLAYING — djay Pro layout ══════ */
function PlayingScreen({ audio, count, elapsed, history }: {
  audio: ReturnType<typeof useAudioPlayer>; count: number; elapsed: number; history: PlayerTrackMeta[]
}) {
  const { current, isPlaying, isLoading, position, duration, nextUp, isCrossfading,
    lastResolvedStyle, recommendedStyle, volume, crossfadeBars, masterTempoBpm } = audio
  const progress = current && duration > 0 ? position / duration : 0
  const [panel, setPanel] = useState<MiddlePanel>('eq')

  if (!current) return null

  const bpm = masterTempoBpm ? Math.round(masterTempoBpm * 10) / 10 : current.bpm?.toFixed(1) ?? '—'

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-black">

      {/* ══ TOP: Track info + overview ══ */}
      <div className="px-3 pt-1.5 pb-1 flex items-center gap-2.5">
        <div className="size-11 shrink-0 rounded-md bg-foreground/[0.04] border border-foreground/[0.06] grid place-items-center">
          <span className="text-foreground/12 text-base">♪</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium truncate leading-tight">{current.title}</p>
          <p className="text-[10px] text-muted-foreground/25 truncate">{current.artists || ''}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="dj-data text-[13px] text-foreground/50">-{fmt(duration - position)}</p>
        </div>
      </div>

      {/* Overview strip */}
      <div className="mx-3 h-2.5 rounded-sm overflow-hidden bg-foreground/[0.02] relative mb-0.5">
        <div className="absolute inset-y-0 left-0 bg-foreground/[0.05]" style={{ width: `${progress * 100}%` }} />
        <div className="absolute inset-y-0 bg-red-500/80" style={{ left: `${progress * 100}%`, width: '1.5px' }} />
      </div>

      {/* ══ WAVEFORM ══ */}
      <div className="flex-[2] min-h-0 border-y border-foreground/[0.04] relative">
        <TrackWaveform trackId={current.id} position={position} duration={duration}
          onSeek={s => audio.seek(s)} height={180} zoomable showTimeline className="w-full h-full" />
        {/* Zoom buttons overlay */}
        <div className="absolute right-1 top-1/2 -translate-y-1/2 flex flex-col gap-1">
          <div className="size-6 rounded border border-foreground/[0.06] bg-black/80 grid place-items-center text-foreground/20 text-xs">+</div>
          <div className="size-6 rounded border border-foreground/[0.06] bg-black/80 grid place-items-center text-foreground/20 text-xs">−</div>
        </div>
      </div>

      {/* ══ MIDDLE PANEL (tabbed) ══ */}
      <div className="flex-[1.5] min-h-0 flex flex-col">
        {/* Panel selector tabs — djay style [N] [EQ] [≈] [⊞] [FX] */}
        <div className="flex items-center border-b border-foreground/[0.04] px-1">
          {([
            { id: 'mix' as const, icon: <span className="dj-data text-[9px] font-bold">N</span>, label: 'Neural Mix' },
            { id: 'eq' as const, icon: <IconAdjustments className="size-3.5" />, label: 'EQ' },
            { id: 'pads' as const, icon: <IconGridDots className="size-3.5" />, label: 'Pads' },
            { id: 'fx' as const, icon: <IconBolt className="size-3.5" />, label: 'FX' },
          ]).map(tab => (
            <button key={tab.id} type="button" onClick={() => setPanel(tab.id)}
              className={`flex-1 flex items-center justify-center py-2 transition-colors ${panel === tab.id ? 'text-foreground/60' : 'text-muted-foreground/15'}`}
              aria-label={tab.label}>
              {tab.icon}
            </button>
          ))}
        </div>

        {/* Panel content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {panel === 'eq' && <EqPanel />}
          {panel === 'mix' && <NeuralMixPanel />}
          {panel === 'pads' && <CuePadsPanel trackId={current.id} />}
          {panel === 'fx' && <FxPanel />}
        </div>
      </div>

      {/* ══ BOTTOM BAR — always visible, djay Pro style ══ */}
      <div className="border-t border-foreground/[0.06] bg-black">
        {/* SYNC / BPM row */}
        <div className="flex items-center px-2 py-1">
          <button className="dj-data text-[9px] px-2 py-0.5 rounded bg-blue-500/80 text-white font-medium active:bg-blue-400">
            SYNC
          </button>
          <span className="dj-data text-[13px] text-foreground/50 ml-1.5">{bpm}</span>
          <span className="dj-data text-[8px] text-muted-foreground/15 ml-0.5">BPM</span>

          {/* Crossfader center */}
          <div className="flex-1 flex items-center justify-center px-2">
            <Slider value={[50]} min={0} max={100} step={1} className="w-full" aria-label="Crossfader" />
          </div>

          <span className="dj-data text-[8px] text-muted-foreground/15 mr-0.5">BPM</span>
          <span className="dj-data text-[13px] text-foreground/50 mr-1.5">{bpm}</span>
          <button className="dj-data text-[9px] px-2 py-0.5 rounded bg-blue-500/80 text-white font-medium active:bg-blue-400">
            SYNC
          </button>
        </div>

        {/* CUE row */}
        <div className="flex items-center px-2 pb-0.5">
          <button className="dj-data text-[9px] px-2.5 py-0.5 rounded border border-amber-500/50 text-amber-500/70 active:bg-amber-500/20">
            CUE
          </button>
          <div className="flex-1" />
          <button className="text-muted-foreground/15 active:text-foreground/30" onClick={() => void audio.playRecommendedNext()}>
            <IconPlayerSkipForwardFilled className="size-3" />
          </button>
          <div className="flex-1" />
          <button className="dj-data text-[9px] px-2.5 py-0.5 rounded border border-amber-500/50 text-amber-500/70 active:bg-amber-500/20">
            CUE
          </button>
        </div>

        {/* Play + crossfader slider row */}
        <div className="flex items-center px-2 pb-1.5 gap-2">
          <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
            className="size-12 rounded-full border-2 border-green-500/60 text-green-500/70 flex items-center justify-center active:scale-95 active:bg-green-500/10"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isLoading ? <IconLoader2 className="size-5 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-5" />
              : <IconPlayerPlayFilled className="size-5 translate-x-[1px]" />}
          </button>

          <div className="flex-1 flex items-center gap-1">
            <div className="h-8 w-1.5 rounded-full bg-blue-500/60" />
            <Slider value={[50]} min={0} max={100} step={1} className="flex-1" aria-label="Crossfader" />
          </div>

          <button type="button" onClick={() => audio.toggle()}
            className="size-12 rounded-full border-2 border-green-500/60 text-green-500/70 flex items-center justify-center active:scale-95 active:bg-green-500/10"
            aria-label="Play Deck 2">
            <IconPlayerPlayFilled className="size-5 translate-x-[1px]" />
          </button>
        </div>
      </div>

      <TransitionVisualizer />
    </div>
  )
}

/* ══════ PAGE ══════ */
export default function PlayerPage() {
  const audio = useAudioPlayer()
  const [count, setCount] = useState(0)
  const [start, setStart] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [history, setHistory] = useState<PlayerTrackMeta[]>([])
  const lastRef = useRef<number | null>(null)
  const { current, isLoading, outgoing } = audio

  useEffect(() => {
    if (!current) return
    if (current.id !== lastRef.current) {
      if (lastRef.current !== null) {
        setCount(n => n + 1)
        if (outgoing) setHistory(h => [outgoing, ...h].slice(0, 20))
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect
      lastRef.current = current.id
    }
  }, [current, outgoing])

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

  return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom select-none bg-black">
      {!current && !isLoading ? (
        <IdleScreen onStart={handleStart} loading={isLoading} />
      ) : (
        <PlayingScreen audio={audio} count={count} elapsed={elapsed} history={history} />
      )}
    </div>
  )
}
