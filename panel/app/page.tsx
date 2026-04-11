'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  IconLoader2,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipForwardFilled,
  IconAdjustments,
  IconGridDots,
  IconBolt,
  IconArrowLeft,
  IconArrowRight,
  IconRepeat,
} from '@tabler/icons-react'

import { loadDjQueue } from '@/actions/library-actions'
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

type Panel = 'eq' | 'mix' | 'pads' | 'fx'

const CUE_COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#a855f7','#ec4899','#06b6d4']

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
          className="size-24 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform shadow-[0_0_80px_oklch(1_0_0/0.1)]">
          {loading ? <IconLoader2 className="size-10 animate-spin" /> : <IconPlayerPlayFilled className="size-10 translate-x-[2px]" />}
        </button>
      </div>
    </div>
  )
}

/* ── EQ Panel — vertical faders with fill bars ── */
function EqPanel() {
  const audio = useAudioPlayer()
  const [values, setValues] = useState({ low: 50, mid: 50, high: 50, filter: 100 })
  const pctToDb = (pct: number) => pct <= 50 ? -40 + (pct / 50) * 40 : ((pct - 50) / 50) * 6

  const apply = useCallback((band: 'low' | 'mid' | 'high', pct: number) => {
    audio.setDeckEq(band, pctToDb(pct))
    void setEq(1, band, pctToDb(pct))
  }, [audio])

  const bands = [
    { key: 'low' as const, label: 'LOW' },
    { key: 'mid' as const, label: 'MID' },
    { key: 'high' as const, label: 'HIGH' },
    { key: 'filter' as const, label: 'FILTER' },
  ]

  return (
    <div className="flex-1 flex items-stretch px-6 py-3 gap-5">
      {bands.map(({ key, label }) => {
        const v = values[key]
        return (
          <div key={key} className="flex-1 flex flex-col items-center gap-1.5">
            <span className="dj-data text-[7px] text-muted-foreground/20">{label}</span>
            {/* Visual fader track with fill */}
            <div className="flex-1 w-full relative rounded border border-foreground/[0.05] bg-foreground/[0.02] overflow-hidden"
              onClick={e => {
                const rect = e.currentTarget.getBoundingClientRect()
                const pct = Math.round((1 - (e.clientY - rect.top) / rect.height) * 100)
                const clamped = Math.max(0, Math.min(100, pct))
                setValues(prev => ({ ...prev, [key]: clamped }))
                if (key !== 'filter') apply(key, clamped)
                else void setFilter(1, 20 * Math.pow(1000, clamped / 100))
              }}>
              {/* Fill from bottom */}
              <div className="absolute bottom-0 left-0 right-0 bg-foreground/15 transition-[height] duration-75"
                style={{ height: `${v}%` }} />
              {/* Center line (0 dB) */}
              <div className="absolute left-0 right-0 top-1/2 h-px bg-foreground/[0.06]" />
              {/* Thumb */}
              <div className="absolute left-1 right-1 h-1.5 rounded-full bg-foreground/50 transition-[bottom] duration-75"
                style={{ bottom: `calc(${v}% - 3px)` }} />
            </div>
            <button type="button" onClick={() => {
              setValues(prev => ({ ...prev, [key]: key === 'filter' ? 100 : 50 }))
              if (key !== 'filter') apply(key, 50)
            }} className="dj-data text-[6px] text-muted-foreground/10 active:text-red-400/40 px-1.5 py-0.5 rounded border border-foreground/[0.04]">
              {key === 'filter' ? 'OPEN' : 'KILL'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

/* ── Neural Mix ── */
function NeuralMixPanel() {
  const [stems, setStems] = useState([100, 100, 100])
  const labels = ['DRUMS', 'HARMONIC', 'VOCALS']
  const icons = ['🥁', '🎹', '🎤']
  return (
    <div className="flex-1 flex flex-col px-4 py-2">
      <p className="dj-data text-[9px] uppercase tracking-[0.15em] text-center text-muted-foreground/20 mb-2">
        NEURAL<span className="text-foreground/30">MIX</span>
      </p>
      <div className="flex-1 flex gap-4">
        {labels.map((label, i) => (
          <div key={label} className="flex-1 flex flex-col items-center gap-1">
            <div className="flex items-center gap-1">
              <span className="text-sm">{icons[i]}</span>
              <button onClick={() => setStems(s => { const n = [...s]; n[i] = n[i] > 0 ? 0 : 100; return n })}
                className={`text-[9px] ${stems[i] === 0 ? 'text-red-400/60' : 'text-muted-foreground/15'}`}>
                {stems[i] === 0 ? '🔇' : '🔊'}
              </button>
            </div>
            <span className="dj-data text-[7px] text-muted-foreground/15">{label}</span>
            <div className="flex-1 w-full rounded border border-foreground/[0.04] bg-foreground/[0.02] relative overflow-hidden"
              onClick={e => {
                const rect = e.currentTarget.getBoundingClientRect()
                const pct = Math.round((1 - (e.clientY - rect.top) / rect.height) * 100)
                setStems(s => { const n = [...s]; n[i] = Math.max(0, Math.min(100, pct)); return n })
              }}>
              <div className="absolute bottom-0 left-0 right-0 bg-foreground/15" style={{ height: `${stems[i]}%` }} />
              <div className="absolute left-1 right-1 h-1 rounded-full bg-foreground/40" style={{ bottom: `calc(${stems[i]}% - 2px)` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="text-[7px] text-center text-muted-foreground/6 mt-1">Server-side Demucs required</p>
    </div>
  )
}

/* ── Cue Pads — set/jump ── */
function CuePadsPanel({ position, onSeek }: { position: number; onSeek: (s: number) => void }) {
  const [cues, setCues] = useState<(number | null)[]>(Array(8).fill(null))
  return (
    <div className="flex-1 flex flex-col px-3 py-2">
      <div className="flex items-center gap-3 mb-2">
        <span className="dj-data text-[9px] text-blue-400/70">Cue</span>
        <span className="dj-data text-[9px] text-muted-foreground/15">Pitch Cue</span>
        <span className="dj-data text-[9px] text-muted-foreground/15">Slice</span>
      </div>
      <div className="flex-1 grid grid-cols-4 grid-rows-2 gap-1.5">
        {cues.map((cue, i) => (
          <button key={i} type="button"
            onClick={() => {
              if (cue !== null) onSeek(cue)
              else setCues(c => { const n = [...c]; n[i] = position; return n })
            }}
            className="rounded-lg border flex flex-col items-center justify-center active:scale-95 transition-all"
            style={{
              borderColor: cue !== null ? CUE_COLORS[i] + '60' : 'oklch(1 0 0 / 0.04)',
              backgroundColor: cue !== null ? CUE_COLORS[i] + '10' : 'oklch(1 0 0 / 0.015)',
            }}>
            {cue !== null ? (
              <>
                <span className="dj-data text-[10px] font-medium" style={{ color: CUE_COLORS[i] }}>{i + 1}</span>
                <span className="dj-data text-[7px] text-muted-foreground/20">{fmt(cue)}</span>
              </>
            ) : (
              <span className="text-muted-foreground/12 text-lg">+</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── FX Panel ── */
function FxPanel() {
  const [fx, setFx] = useState([false, false, false])
  const effects = ['Reverb', 'Echo', 'Filter Sweep']
  const subs = ['', '1/16 BEAT', '']
  return (
    <div className="flex-1 flex flex-col px-3 py-2">
      <div className="flex items-center gap-3 mb-2">
        <span className="dj-data text-[9px] text-muted-foreground/15">Pad</span>
        <span className="dj-data text-[9px] text-muted-foreground/15">Instant</span>
        <span className="dj-data text-[9px] text-blue-400/60">Manual</span>
      </div>
      <div className="flex-1 flex flex-col gap-2">
        {effects.map((name, i) => (
          <div key={name} className={`flex items-center gap-2 rounded-lg border px-2 py-2 transition-colors ${fx[i] ? 'border-blue-500/30 bg-blue-500/[0.05]' : 'border-foreground/[0.04] bg-foreground/[0.015]'}`}>
            <button onClick={() => setFx(f => { const n = [...f]; n[i] = !n[i]; return n })}
              className={`dj-data text-[8px] px-2 py-0.5 rounded border font-medium transition-colors ${fx[i] ? 'border-blue-500/50 bg-blue-500/20 text-blue-400' : 'border-foreground/[0.06] text-muted-foreground/20'}`}>
              ON
            </button>
            <div className="flex-1">
              <p className={`dj-data text-[10px] ${fx[i] ? 'text-foreground/50' : 'text-foreground/25'}`}>{name}</p>
              {subs[i] && <p className="dj-data text-[7px] text-muted-foreground/10">{subs[i]}</p>}
            </div>
            <div className={`size-6 rounded-full border ${fx[i] ? 'border-blue-500/30 bg-blue-500/10' : 'border-foreground/[0.06] bg-foreground/[0.02]'}`} />
          </div>
        ))}
      </div>
    </div>
  )
}

/* ══════ PLAYING ══════ */
function PlayingScreen({ audio }: { audio: ReturnType<typeof useAudioPlayer> }) {
  const { current, isPlaying, isLoading, position, duration, masterTempoBpm, isCrossfading } = audio
  const progress = current && duration > 0 ? position / duration : 0
  const [panel, setPanel] = useState<Panel>('eq')
  const [activeDeck, setActiveDeck] = useState(1)
  const [loopBars, setLoopBars] = useState(4)

  if (!current) return null
  const bpm = masterTempoBpm ? (Math.round(masterTempoBpm * 10) / 10).toFixed(1) : current.bpm?.toFixed(1) ?? '—'

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-black">
      {/* ══ TOP ══ */}
      <div className="px-3 pt-1.5 pb-1 flex items-center gap-2.5">
        <div className="size-10 shrink-0 rounded-md bg-foreground/[0.04] border border-foreground/[0.06] grid place-items-center">
          <span className="text-foreground/12 text-sm">♪</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-medium truncate leading-tight">{current.title}</p>
          <p className="text-[10px] text-muted-foreground/25 truncate">{current.artists || ''}</p>
        </div>
        <p className="dj-data text-[12px] text-foreground/50 shrink-0">-{fmt(duration - position)}</p>
      </div>

      {/* Overview */}
      <div className="mx-3 h-2 rounded-sm overflow-hidden bg-foreground/[0.02] relative mb-0.5">
        <div className="absolute inset-y-0 left-0 bg-foreground/[0.05]" style={{ width: `${progress * 100}%` }} />
        <div className="absolute inset-y-0 bg-red-500/80" style={{ left: `${progress * 100}%`, width: '1.5px' }} />
      </div>

      {/* ══ LOOP CONTROLS ══ */}
      <div className="flex items-center justify-center gap-3 py-0.5 border-b border-foreground/[0.04]">
        <button className="text-muted-foreground/15 active:text-foreground/30"><IconArrowLeft className="size-3.5" /></button>
        <button onClick={() => setLoopBars(b => Math.max(1, b === 4 ? 8 : b === 8 ? 16 : 4))}
          className="flex items-center gap-1 text-muted-foreground/20 active:text-foreground/30">
          <IconRepeat className="size-3" />
          <span className="dj-data text-[9px]">{loopBars}</span>
        </button>
        <button className="text-muted-foreground/15 active:text-foreground/30"><IconArrowRight className="size-3.5" /></button>
      </div>

      {/* ══ WAVEFORM ══ */}
      <div className="flex-[2] min-h-0 border-b border-foreground/[0.04] relative">
        <TrackWaveform trackId={current.id} position={position} duration={duration}
          onSeek={s => audio.seek(s)} height={160} zoomable showTimeline className="w-full h-full" />
        <div className="absolute right-1 top-1/2 -translate-y-1/2 flex flex-col gap-1">
          <div className="size-5 rounded border border-foreground/[0.06] bg-black/80 grid place-items-center text-foreground/20 text-[10px]">+</div>
          <div className="size-5 rounded border border-foreground/[0.06] bg-black/80 grid place-items-center text-foreground/20 text-[10px]">−</div>
        </div>
        {/* Deck number */}
        <span className="absolute left-1 top-1 dj-data text-[9px] text-foreground/15">{activeDeck}</span>
      </div>

      {/* ══ PANEL SELECTOR ══ */}
      <div className="flex items-center border-b border-foreground/[0.04]">
        {([
          { id: 'mix' as const, label: <span className="dj-data text-[9px] font-bold">N</span> },
          { id: 'eq' as const, label: <IconAdjustments className="size-3.5" /> },
          { id: 'pads' as const, label: <IconGridDots className="size-3.5" /> },
          { id: 'fx' as const, label: <IconBolt className="size-3.5" /> },
        ]).map(tab => (
          <button key={tab.id} onClick={() => setPanel(tab.id)}
            className={`flex-1 flex items-center justify-center py-1.5 ${panel === tab.id ? 'text-blue-400/70' : 'text-muted-foreground/15'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ══ PANEL CONTENT ══ */}
      <div className="flex-[1.5] min-h-0 overflow-hidden">
        {panel === 'eq' && <EqPanel />}
        {panel === 'mix' && <NeuralMixPanel />}
        {panel === 'pads' && <CuePadsPanel position={position} onSeek={s => audio.seek(s)} />}
        {panel === 'fx' && <FxPanel />}
      </div>

      {/* ══ BOTTOM BAR ══ */}
      <div className="border-t border-foreground/[0.06] bg-[oklch(0.06_0_0)]">
        {/* Deck selector */}
        <div className="flex items-center px-1 py-0.5 border-b border-foreground/[0.04]">
          {[1, 2].map(d => (
            <button key={d} onClick={() => setActiveDeck(d)}
              className={`flex-1 dj-data text-[10px] text-center py-0.5 rounded ${activeDeck === d ? 'text-blue-400 bg-blue-500/10' : 'text-muted-foreground/15'}`}>
              {d}
            </button>
          ))}
        </div>

        {/* SYNC + BPM + crossfader */}
        <div className="flex items-center px-1.5 py-1 gap-1">
          <button className="dj-data text-[8px] px-1.5 py-0.5 rounded bg-blue-500 text-white font-medium active:bg-blue-400 shrink-0">SYNC</button>
          <div className="shrink-0">
            <span className="dj-data text-[11px] text-foreground/50">{bpm}</span>
            <span className="dj-data text-[7px] text-muted-foreground/15 ml-0.5">BPM</span>
          </div>
          <Slider value={[50]} min={0} max={100} step={1} className="flex-1 mx-1" aria-label="Crossfader" />
          <div className="shrink-0">
            <span className="dj-data text-[7px] text-muted-foreground/15 mr-0.5">BPM</span>
            <span className="dj-data text-[11px] text-foreground/50">{bpm}</span>
          </div>
          <button className="dj-data text-[8px] px-1.5 py-0.5 rounded bg-blue-500 text-white font-medium active:bg-blue-400 shrink-0">SYNC</button>
        </div>

        {/* CUE + skip */}
        <div className="flex items-center px-2 py-0.5">
          <button className="dj-data text-[8px] px-2 py-0.5 rounded border border-amber-500/40 text-amber-500/60 active:bg-amber-500/15">CUE</button>
          <div className="flex-1 flex justify-center">
            <button onClick={() => void audio.playRecommendedNext()} className="text-muted-foreground/15 active:text-foreground/30">
              <IconPlayerSkipForwardFilled className="size-3" />
            </button>
          </div>
          <button className="dj-data text-[8px] px-2 py-0.5 rounded border border-amber-500/40 text-amber-500/60 active:bg-amber-500/15">CUE</button>
        </div>

        {/* Play + crossfader visual */}
        <div className="flex items-center px-2 pb-1.5 gap-1.5">
          <button onClick={() => audio.toggle()} disabled={isLoading}
            className="size-11 rounded-full border-2 border-green-500/50 text-green-500/60 flex items-center justify-center active:scale-95 active:bg-green-500/10 shrink-0">
            {isLoading ? <IconLoader2 className="size-4 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-4" />
              : <IconPlayerPlayFilled className="size-4 translate-x-[0.5px]" />}
          </button>
          <div className="flex-1 flex items-center gap-1">
            <div className="h-7 w-1 rounded-full bg-blue-500/50" />
            <Slider value={[50]} min={0} max={100} step={1} className="flex-1" aria-label="Crossfader" />
          </div>
          <button onClick={() => audio.toggle()}
            className="size-11 rounded-full border-2 border-green-500/50 text-green-500/60 flex items-center justify-center active:scale-95 active:bg-green-500/10 shrink-0">
            <IconPlayerPlayFilled className="size-4 translate-x-[0.5px]" />
          </button>
        </div>
      </div>

      {isCrossfading && <div className="absolute top-0 left-0 right-0 h-0.5 bg-blue-500/30 animate-pulse" />}
      <TransitionVisualizer />
    </div>
  )
}

/* ══════ PAGE ══════ */
export default function PlayerPage() {
  const audio = useAudioPlayer()
  const [start, setStart] = useState<number | null>(null)
  const { current, isLoading } = audio

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
        <PlayingScreen audio={audio} />
      )}
    </div>
  )
}
