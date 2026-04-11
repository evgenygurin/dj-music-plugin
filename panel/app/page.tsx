'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  IconLoader2,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipForwardFilled,
  IconLayoutGrid,
  IconWaveSine,
  IconVolume,
} from '@tabler/icons-react'

import { loadDjQueue } from '@/actions/library-actions'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import type { PlayerTrackMeta } from '@/components/audio-player/audio-player-types'
import { TrackWaveform } from '@/components/player/track-waveform'
import { TransitionVisualizer } from '@/components/player/transition-visualizer'
import { Slider } from '@/components/ui/slider'

function fmt(s: number) {
  if (!Number.isFinite(s) || s < 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/* ── Vertical waveform strip ── */
const VBARS = [
  [78,52,91,34,67,83,45,94,61,38,55,87,72,41,76,63,33,89,58,44,82,71,36,93,65,47,85,74,51,39,92,68,57,43,88,77],
  [43,88,71,55,37,92,66,48,81,74,33,85,62,79,41,53,90,35,83,68,46,39,72,87,58,76,44,31,64,93,49,57,82,91,38,70],
]
function VWave({ i, active, progress, color }: { i: number; active: boolean; progress: number; color: string }) {
  const bars = VBARS[i % 2]
  return (
    <div className="flex flex-col items-center gap-[1px] w-full h-full">
      {bars.map((w, j) => (
        <div key={j} className="flex-1 w-full flex items-center justify-center">
          <div className="rounded-full transition-colors duration-75"
            style={{ width: `${w}%`, height: '100%', maxHeight: '3px',
              backgroundColor: active && j / bars.length < progress ? color : active ? 'oklch(1 0 0 / 0.06)' : 'oklch(1 0 0 / 0.02)' }} />
        </div>
      ))}
    </div>
  )
}

/* ── Track info ── */
function TrackInfo({ track, label, color }: { track: PlayerTrackMeta | null; label: string; color: string }) {
  return (
    <div className="p-2.5">
      <span className="dj-data text-[7px] tracking-[0.2em]" style={{ color }}>{label}</span>
      {track ? (
        <>
          <p className="text-[13px] font-medium truncate mt-0.5 leading-tight">{track.title}</p>
          <p className="text-[10px] text-muted-foreground/20 truncate">{track.artists || ''}</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            {track.bpm && <span className="dj-data text-[11px]" style={{ color }}>{track.bpm.toFixed(0)}</span>}
            {track.camelot && <span className="dj-data text-[9px] text-muted-foreground/20">{track.camelot}</span>}
          </div>
        </>
      ) : (
        <p className="text-[8px] text-muted-foreground/8 mt-0.5">—</p>
      )}
    </div>
  )
}

/* ══════ IDLE ══════ */
function IdleScreen({ onStart, loading }: { onStart: (bpm: number) => void; loading: boolean }) {
  const [bpm, setBpm] = useState(128)
  return (
    <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
      {/* Radial pulse glow behind play button */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="size-[300px] rounded-full bg-foreground/[0.02] animate-pulse" style={{ animationDuration: '3s' }} />
      </div>
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="size-[180px] rounded-full bg-foreground/[0.03] animate-pulse" style={{ animationDuration: '2s', animationDelay: '0.5s' }} />
      </div>

      <div className="relative z-10 flex flex-col items-center gap-8">
        {/* BPM — the statement */}
        <div className="text-center">
          <p className="dj-data text-[96px] leading-none text-foreground tracking-tight">{bpm}</p>
        </div>

        {/* Slider */}
        <div className="w-[200px]">
          <Slider value={[bpm]} min={118} max={150} step={1} onValueChange={v => setBpm(v[0])} aria-label="BPM" />
          <div className="flex justify-between mt-1.5 px-0.5">
            <span className="dj-data text-[8px] text-muted-foreground/15">118</span>
            <span className="dj-data text-[8px] text-muted-foreground/10">BPM</span>
            <span className="dj-data text-[8px] text-muted-foreground/15">150</span>
          </div>
        </div>

        {/* Play */}
        <button type="button" onClick={() => onStart(bpm)} disabled={loading}
          className="size-24 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform shadow-[0_0_80px_oklch(1_0_0/0.1),0_0_20px_oklch(1_0_0/0.05)]"
          aria-label="Play">
          {loading ? <IconLoader2 className="size-10 animate-spin" /> : <IconPlayerPlayFilled className="size-10 translate-x-[2px]" />}
        </button>
      </div>
    </div>
  )
}

/* ══════ PLAYING — 4-deck vertical split ══════ */
function PlayingScreen({ audio, count, elapsed, history }: {
  audio: ReturnType<typeof useAudioPlayer>; count: number; elapsed: number; history: PlayerTrackMeta[]
}) {
  const { current, isPlaying, isLoading, position, duration, nextUp, outgoing, isCrossfading,
    lastResolvedStyle, recommendedStyle, volume, crossfadeBars, masterTempoBpm } = audio
  const progress = current && duration > 0 ? position / duration : 0
  const style = lastResolvedStyle ?? recommendedStyle

  if (!current) return null

  return (
    <div className="flex-1 flex min-h-0 relative">
      {/* LEFT COLUMN */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Deck B — transition zone */}
        <div className="flex-1 flex min-h-0">
          <div className="w-6 shrink-0 py-1.5 px-0.5">
            <VWave i={0} active={!!outgoing && isCrossfading} progress={0.5} color="oklch(0.5 0.12 240)" />
          </div>
          <div className="flex-1 flex flex-col justify-center">
            {isCrossfading && outgoing ? (
              <TrackInfo track={outgoing} label="B · OUT" color="oklch(0.5 0.12 240)" />
            ) : (
              <div className="p-2.5">
                <span className="dj-data text-[7px] tracking-[0.2em] text-[oklch(0.5_0.12_240)]">B</span>
                <div className="mt-1.5 space-y-0.5">
                  <p className="text-[8px] text-muted-foreground/10">{style ? style.replace(/_/g, ' ') : 'auto'} · {crossfadeBars}b</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="h-px bg-foreground/[0.03]" />

        {/* Deck A — NOW PLAYING with zoomable waveform */}
        <div className="flex-[1.5] flex flex-col min-h-0 p-2 gap-0.5">
          <div className="flex items-center justify-between">
            <span className="dj-data text-[7px] tracking-[0.15em] text-foreground/30">A</span>
            <span className="dj-data text-[8px] text-muted-foreground/15">{fmt(position)}<span className="text-muted-foreground/8"> / </span>{fmt(duration)}</span>
          </div>
          <p className="text-sm font-medium truncate leading-tight">{current.title}</p>
          <div className="flex items-center gap-1.5">
            {current.bpm && <span className="dj-data text-xs text-foreground/50">{current.bpm.toFixed(0)}</span>}
            {current.camelot && <span className="dj-data text-[10px] text-muted-foreground/20">{current.camelot}</span>}
            {current.mood && <span className="text-[8px] text-muted-foreground/10">{current.mood.replace(/_/g, ' ')}</span>}
          </div>
          {/* Waveform */}
          <div className="flex-1 min-h-0 rounded border border-foreground/[0.04] bg-foreground/[0.008] overflow-hidden mt-0.5">
            <TrackWaveform trackId={current.id} position={position} duration={duration}
              onSeek={s => audio.seek(s)} height={90} zoomable showMinimap className="w-full" />
          </div>
          {/* Volume */}
          <div className="flex items-center gap-1.5 mt-0.5">
            <IconVolume className="size-2.5 text-muted-foreground/10" />
            <Slider value={[volume * 100]} min={0} max={100} step={1}
              onValueChange={v => audio.setVolume(v[0] / 100)} className="flex-1" aria-label="Volume" />
          </div>
        </div>
      </div>

      {/* DIVIDER */}
      <div className="w-px bg-foreground/[0.04]" />

      {/* RIGHT COLUMN */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Deck D — session */}
        <div className="flex-1 flex flex-col justify-center p-2.5 min-h-0">
          <span className="dj-data text-[7px] tracking-[0.2em] text-muted-foreground/12">D</span>
          <p className="dj-data text-3xl text-foreground/30 leading-none mt-1">{count}</p>
          <p className="text-[7px] text-muted-foreground/6 mt-0.5">mixed</p>
          <p className="dj-data text-base text-foreground/15 leading-none mt-1.5">{fmt(elapsed)}</p>
          {masterTempoBpm && (
            <p className="dj-data text-[11px] text-foreground/20 mt-1.5">{Math.round(masterTempoBpm)} <span className="text-[7px] text-muted-foreground/8">BPM</span></p>
          )}
          {history.length > 0 && (
            <div className="mt-2 space-y-px">
              {history.slice(0, 3).map(t => (
                <p key={t.id} className="text-[7px] text-muted-foreground/8 truncate">{t.title}</p>
              ))}
            </div>
          )}
        </div>

        <div className="h-px bg-foreground/[0.03]" />

        {/* Deck C — next up */}
        <div className="flex-[1.5] flex flex-col justify-between min-h-0">
          <TrackInfo track={nextUp} label="C · NEXT" color="oklch(0.5 0.13 50)" />
          {current && nextUp && (
            <div className="px-2.5 pb-2 space-y-0.5">
              {current.bpm && nextUp.bpm && (
                <div className="flex justify-between">
                  <span className="text-[7px] text-muted-foreground/8">BPM Δ</span>
                  <span className="dj-data text-[9px] text-foreground/20">±{Math.abs(current.bpm - nextUp.bpm).toFixed(1)}</span>
                </div>
              )}
              {current.camelot && nextUp.camelot && (
                <div className="flex justify-between">
                  <span className="text-[7px] text-muted-foreground/8">Key</span>
                  <span className="dj-data text-[8px] text-foreground/12">{current.camelot} → {nextUp.camelot}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* CENTER HUB */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
        <div className="pointer-events-auto flex items-center gap-2">
          <button type="button" onClick={() => void audio.playRecommendedNext()}
            className="size-9 rounded-full border border-foreground/6 text-foreground/20 flex items-center justify-center active:scale-95 bg-black/90 backdrop-blur-sm"
            aria-label="Next"><IconPlayerSkipForwardFilled className="size-3" /></button>
          <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
            className="size-14 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 shadow-[0_0_30px_oklch(1_0_0/0.05)] ring-1 ring-black/80"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isLoading ? <IconLoader2 className="size-5 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-5" />
              : <IconPlayerPlayFilled className="size-5 translate-x-[1px]" />}
          </button>
        </div>
      </div>

      {isCrossfading && <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/8 pointer-events-none z-10 animate-pulse" style={{ animationDuration: '1.5s' }} />}
    </div>
  )
}

/* ══════ MASTER ══════ */
function MasterScreen({ audio }: { audio: ReturnType<typeof useAudioPlayer> }) {
  const { current, isPlaying, isLoading, position, duration, masterTempoBpm, isCrossfading, lastResolvedStyle, recommendedStyle } = audio
  const progress = current && duration > 0 ? position / duration : 0
  if (!current) return null
  return (
    <div className="flex-1 flex flex-col px-5 justify-center">
      {masterTempoBpm && (
        <p className="text-center mb-6">
          <span className="dj-data text-5xl text-foreground">{Math.round(masterTempoBpm)}</span>
          <span className="dj-data text-xs text-muted-foreground/10 ml-1.5">BPM</span>
        </p>
      )}
      <div className="text-center mb-6">
        <h1 className="display-heading text-2xl truncate">{current.title}</h1>
        <p className="text-sm text-muted-foreground/20 mt-0.5">{current.artists}</p>
      </div>
      <div className="relative rounded-lg border border-foreground/[0.04] bg-foreground/[0.01] overflow-hidden mb-4">
        <TrackWaveform trackId={current.id} position={position} duration={duration} onSeek={s => audio.seek(s)} height={100} zoomable showMinimap />
      </div>
      <div className="flex items-center gap-3">
        <span className="dj-data text-[10px] text-muted-foreground/15 w-10 text-right">{fmt(position)}</span>
        <div className="flex-1 h-[2px] bg-foreground/[0.04] rounded-full overflow-hidden">
          <div className="h-full bg-foreground/15" style={{ width: `${progress * 100}%` }} />
        </div>
        <span className="dj-data text-[10px] text-muted-foreground/15 w-10">{fmt(duration)}</span>
      </div>
      <div className="flex items-center justify-center gap-3 mt-6">
        <button type="button" onClick={() => void audio.playRecommendedNext()}
          className="size-10 rounded-full border border-foreground/6 text-foreground/15 flex items-center justify-center active:scale-95"
          aria-label="Next"><IconPlayerSkipForwardFilled className="size-3.5" /></button>
        <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
          className="size-14 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 shadow-2xl"
          aria-label={isPlaying ? 'Pause' : 'Play'}>
          {isLoading ? <IconLoader2 className="size-5 animate-spin" />
            : isPlaying ? <IconPlayerPauseFilled className="size-5" />
            : <IconPlayerPlayFilled className="size-5 translate-x-[1px]" />}
        </button>
      </div>
      {isCrossfading && (lastResolvedStyle ?? recommendedStyle) && (
        <p className="text-center mt-4 dj-data text-[8px] uppercase tracking-[0.3em] text-muted-foreground/8">
          {(lastResolvedStyle ?? recommendedStyle ?? '').replace(/_/g, ' ')}
        </p>
      )}
    </div>
  )
}

/* ══════ PAGE ══════ */
export default function PlayerPage() {
  const audio = useAudioPlayer()
  const [view, setView] = useState<'decks' | 'master'>('decks')
  const [count, setCount] = useState(0)
  const [start, setStart] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [history, setHistory] = useState<PlayerTrackMeta[]>([])
  const lastRef = useRef<number | null>(null)
  const { current, isLoading, outgoing } = audio

  if (current && current.id !== lastRef.current) {
    if (lastRef.current !== null) {
      setCount(n => n + 1)
      if (outgoing) setHistory(h => [outgoing, ...h].slice(0, 10))
    }
    lastRef.current = current.id
  }

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
      ) : view === 'decks' ? (
        <PlayingScreen audio={audio} count={count} elapsed={elapsed} history={history} />
      ) : (
        <MasterScreen audio={audio} />
      )}

      {current && (
        <button type="button" onClick={() => setView(v => v === 'decks' ? 'master' : 'decks')}
          className="absolute bottom-3 right-3 size-8 rounded-full border border-foreground/5 text-foreground/12 flex items-center justify-center active:scale-95 z-30 bg-black/90 safe-bottom"
          aria-label="Toggle view">
          {view === 'decks' ? <IconWaveSine className="size-3" /> : <IconLayoutGrid className="size-3" />}
        </button>
      )}

      <TransitionVisualizer />
    </div>
  )
}
