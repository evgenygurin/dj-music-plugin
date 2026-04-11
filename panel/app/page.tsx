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
import { WaveformFullscreen } from '@/components/player/waveform-fullscreen'
import { Slider } from '@/components/ui/slider'

function fmt(s: number) {
  if (!Number.isFinite(s) || s < 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

/* ── Vertical waveform column (runs top-to-bottom like the sketch) ── */
const COL_BARS = [
  [78,52,91,34,67,83,45,94,61,38,55,87,72,41,76,63,33,89,58,44,82,71,36,93,65,47,85,74,51,39,92,68,57,43,88,77,54,31,79,64,35,95,69,42,81,73,56],
  [43,88,71,55,37,92,66,48,81,74,33,85,62,79,41,53,90,35,83,68,46,39,72,87,58,76,44,31,64,93,49,57,82,91,38,70,52,86,34,89,42,75,61,78,36,84,59],
]

function VerticalWave({ index, active, progress, color }: { index: number; active: boolean; progress: number; color: string }) {
  const bars = COL_BARS[index % 2]
  return (
    <div className="flex flex-col items-center gap-[1px] w-full h-full">
      {bars.map((w, i) => {
        const filled = active && i / bars.length < progress
        return (
          <div key={i} className="flex-1 w-full flex items-center justify-center">
            <div className="rounded-full transition-colors duration-100"
              style={{
                width: `${w}%`,
                height: '100%',
                maxHeight: '4px',
                backgroundColor: filled ? color : active ? 'oklch(1 0 0 / 0.07)' : 'oklch(1 0 0 / 0.025)',
              }} />
          </div>
        )
      })}
    </div>
  )
}

/* ── Track info block ── */
function TrackBlock({ track, label, color, sub }: {
  track: PlayerTrackMeta | null; label: string; color: string; sub?: string
}) {
  if (!track) return (
    <div className="p-3">
      <span className="dj-data text-[7px] tracking-[0.2em]" style={{ color }}>{label}</span>
      {sub && <p className="text-[8px] text-muted-foreground/10 mt-1">{sub}</p>}
    </div>
  )
  return (
    <div className="p-3">
      <span className="dj-data text-[7px] tracking-[0.2em]" style={{ color }}>{label}</span>
      <p className="text-sm font-medium truncate mt-1 leading-tight">{track.title}</p>
      <p className="text-[10px] text-muted-foreground/25 truncate">{track.artists || ''}</p>
      <div className="flex items-center gap-2 mt-1">
        {track.bpm && <span className="dj-data text-xs" style={{ color }}>{track.bpm.toFixed(0)}</span>}
        {track.camelot && <span className="dj-data text-[10px] text-muted-foreground/20">{track.camelot}</span>}
        {track.mood && <span className="text-[8px] text-muted-foreground/12">{track.mood.replace(/_/g, ' ')}</span>}
      </div>
    </div>
  )
}

/* ══════ IDLE SCREEN ══════ */
function IdleScreen({ onStart, loading }: { onStart: (bpm: number) => void; loading: boolean }) {
  const [bpm, setBpm] = useState(128)
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-10 gap-12">
      <div className="text-center">
        <p className="dj-data text-8xl text-foreground leading-none">{bpm}</p>
        <p className="dj-data text-xs text-muted-foreground/12 mt-2">BPM</p>
      </div>
      <div className="w-full max-w-[240px]">
        <Slider value={[bpm]} min={118} max={150} step={1} onValueChange={v => setBpm(v[0])} aria-label="BPM" />
        <div className="flex justify-between mt-1">
          <span className="dj-data text-[7px] text-muted-foreground/8">118</span>
          <span className="dj-data text-[7px] text-muted-foreground/8">150</span>
        </div>
      </div>
      <button type="button" onClick={() => onStart(bpm)} disabled={loading}
        className="size-28 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform shadow-[0_0_60px_oklch(1_0_0/0.08)]"
        aria-label="Play">
        {loading ? <IconLoader2 className="size-12 animate-spin" /> : <IconPlayerPlayFilled className="size-12 translate-x-[3px]" />}
      </button>
    </div>
  )
}

/* ══════ PLAYING SCREEN — vertical split layout from sketch ══════ */
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

      {/* ── LEFT COLUMN: vertical waveform + deck info ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Deck B — top left (transition/outgoing) */}
        <div className="flex-1 flex min-h-0">
          <div className="w-8 shrink-0 py-2 px-1">
            <VerticalWave index={0} active={!!outgoing && isCrossfading} progress={isCrossfading ? 0.5 : 0} color="oklch(0.6 0.14 240)" />
          </div>
          <div className="flex-1 flex flex-col justify-center">
            {isCrossfading && outgoing ? (
              <TrackBlock track={outgoing} label="B · OUT" color="oklch(0.6 0.14 240)" />
            ) : (
              <div className="p-3">
                <span className="dj-data text-[7px] tracking-[0.2em] text-[oklch(0.6_0.14_240)]">B</span>
                <div className="mt-2 space-y-1">
                  <div className="flex justify-between">
                    <span className="text-[8px] text-muted-foreground/12">Style</span>
                    <span className="dj-data text-[9px] text-foreground/25">{style ? style.replace(/_/g, ' ') : 'auto'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[8px] text-muted-foreground/12">Bars</span>
                    <span className="dj-data text-[9px] text-foreground/25">{crossfadeBars}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="h-px bg-foreground/[0.03]" />

        {/* Deck A — bottom left (NOW PLAYING + interactive waveform) */}
        <div className="flex-1 flex flex-col min-h-0 p-2 gap-1">
          <div className="flex items-center justify-between">
            <span className="dj-data text-[7px] tracking-[0.15em] text-foreground/40">A · NOW</span>
            <span className="dj-data text-[8px] text-muted-foreground/20">{fmt(position)} / {fmt(duration)}</span>
          </div>
          <p className="text-sm font-medium truncate leading-tight">{current.title}</p>
          <div className="flex items-center gap-2">
            {current.bpm && <span className="dj-data text-xs text-foreground/60">{current.bpm.toFixed(0)}</span>}
            {current.camelot && <span className="dj-data text-[10px] text-muted-foreground/25">{current.camelot}</span>}
            {current.mood && <span className="text-[8px] text-muted-foreground/12">{current.mood.replace(/_/g, ' ')}</span>}
          </div>
          {/* Interactive zoomable waveform — pinch to zoom, tap to seek */}
          <div className="flex-1 min-h-0 rounded-lg border border-foreground/5 bg-foreground/[0.01] overflow-hidden">
            <TrackWaveform
              trackId={current.id}
              position={position}
              duration={duration}
              onSeek={s => audio.seek(s)}
              height={100}
              zoomable
              showMinimap
              className="w-full"
            />
          </div>
          {/* Volume */}
          <div className="flex items-center gap-2">
            <IconVolume className="size-3 text-muted-foreground/15" />
            <Slider value={[volume * 100]} min={0} max={100} step={1}
              onValueChange={v => audio.setVolume(v[0] / 100)} className="flex-1" aria-label="Volume" />
          </div>
        </div>
      </div>

      {/* ── VERTICAL DIVIDER ── */}
      <div className="w-px bg-foreground/[0.04]" />

      {/* ── RIGHT COLUMN ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Deck D — top right (session stats) */}
        <div className="flex-1 flex min-h-0">
          <div className="flex-1 flex flex-col justify-center p-3">
            <span className="dj-data text-[7px] tracking-[0.2em] text-muted-foreground/15">D</span>
            <div className="mt-2">
              <p className="dj-data text-3xl text-foreground/40 leading-none">{count}</p>
              <p className="text-[7px] text-muted-foreground/8 mt-0.5">tracks mixed</p>
            </div>
            <div className="mt-2">
              <p className="dj-data text-lg text-foreground/25 leading-none">{fmt(elapsed)}</p>
            </div>
            {masterTempoBpm && (
              <div className="mt-2 flex items-baseline gap-1">
                <span className="dj-data text-sm text-foreground/30">{Math.round(masterTempoBpm)}</span>
                <span className="dj-data text-[7px] text-muted-foreground/10">BPM</span>
              </div>
            )}
            {/* Mini history */}
            {history.length > 0 && (
              <div className="mt-3 space-y-0.5">
                {history.slice(0, 3).map(t => (
                  <p key={t.id} className="text-[8px] text-muted-foreground/10 truncate">{t.title}</p>
                ))}
              </div>
            )}
          </div>
          <div className="w-8 shrink-0 py-2 px-1">
            <VerticalWave index={1} active={false} progress={0} color="oklch(0.3 0 0)" />
          </div>
        </div>

        <div className="h-px bg-foreground/[0.03]" />

        {/* Deck C — bottom right (NEXT UP) */}
        <div className="flex-1 flex min-h-0">
          <div className="flex-1 flex flex-col justify-between">
            <TrackBlock track={nextUp} label="C · NEXT" color="oklch(0.6 0.15 50)" sub="Analyzing..." />
            {/* Compatibility */}
            {current && nextUp && (
              <div className="p-3 pt-0 space-y-1">
                {current.bpm && nextUp.bpm && (
                  <div className="flex justify-between">
                    <span className="text-[8px] text-muted-foreground/10">BPM Δ</span>
                    <span className="dj-data text-[9px] text-foreground/25">
                      ±{Math.abs(current.bpm - nextUp.bpm).toFixed(1)}
                    </span>
                  </div>
                )}
                {current.camelot && nextUp.camelot && (
                  <div className="flex justify-between">
                    <span className="text-[8px] text-muted-foreground/10">Key</span>
                    <span className="dj-data text-[9px] text-foreground/20">
                      {current.camelot} → {nextUp.camelot}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="w-8 shrink-0 py-2 px-1">
            <VerticalWave index={1} active={false} progress={0} color="oklch(0.6 0.15 50)" />
          </div>
        </div>
      </div>

      {/* ── CENTER HUB (absolute overlay at intersection) ── */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
        <div className="pointer-events-auto flex items-center gap-2.5">
          <button type="button" onClick={() => void audio.playRecommendedNext()}
            className="size-9 rounded-full border border-foreground/8 text-foreground/20 flex items-center justify-center active:scale-95 transition-all bg-black/80 backdrop-blur-sm"
            aria-label="Next">
            <IconPlayerSkipForwardFilled className="size-3" />
          </button>
          <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
            className="size-16 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform shadow-[0_0_40px_oklch(1_0_0/0.06)] ring-2 ring-black/80"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isLoading ? <IconLoader2 className="size-6 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-6" />
              : <IconPlayerPlayFilled className="size-6 translate-x-[1px]" />}
          </button>
        </div>
      </div>

      {/* Crossfade flash */}
      {isCrossfading && (
        <div className="absolute inset-0 pointer-events-none z-10 animate-pulse">
          <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/10" />
        </div>
      )}
    </div>
  )
}

/* ══════ MASTER VIEW ══════ */
function MasterScreen({ audio }: { audio: ReturnType<typeof useAudioPlayer> }) {
  const { current, isPlaying, isLoading, position, duration, masterTempoBpm, isCrossfading, lastResolvedStyle, recommendedStyle } = audio
  const progress = current && duration > 0 ? position / duration : 0
  if (!current) return null
  return (
    <div className="flex-1 flex flex-col px-6 justify-center">
      {masterTempoBpm && (
        <p className="text-center mb-8">
          <span className="dj-data text-6xl text-foreground">{Math.round(masterTempoBpm)}</span>
          <span className="dj-data text-sm text-muted-foreground/12 ml-2">BPM</span>
        </p>
      )}
      <div className="text-center mb-8">
        <h1 className="display-heading text-3xl truncate">{current.title}</h1>
        <p className="text-sm text-muted-foreground/20 mt-1">{current.artists}</p>
      </div>
      <div className="relative h-24 rounded-xl border border-foreground/5 bg-foreground/[0.01] p-2 mb-4">
        <div className="h-full"><VerticalWave index={0} active={isPlaying} progress={progress} color="oklch(0.8 0 0 / 0.5)" /></div>
        <div className="absolute inset-0 p-2">
          <TrackWaveform trackId={current.id} position={position} duration={duration} onSeek={s => audio.seek(s)} height={80} zoomable showMinimap />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="dj-data text-[10px] text-muted-foreground/15 w-10 text-right">{fmt(position)}</span>
        <div className="flex-1 h-[2px] bg-foreground/5 rounded-full overflow-hidden">
          <div className="h-full bg-foreground/15" style={{ width: `${progress * 100}%` }} />
        </div>
        <span className="dj-data text-[10px] text-muted-foreground/15 w-10">{fmt(duration)}</span>
      </div>
      {/* Hub */}
      <div className="flex items-center justify-center gap-3 mt-8">
        <button type="button" onClick={() => void audio.playRecommendedNext()}
          className="size-10 rounded-full border border-foreground/8 text-foreground/20 flex items-center justify-center active:scale-95"
          aria-label="Next"><IconPlayerSkipForwardFilled className="size-3.5" /></button>
        <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
          className="size-16 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 shadow-2xl"
          aria-label={isPlaying ? 'Pause' : 'Play'}>
          {isLoading ? <IconLoader2 className="size-6 animate-spin" />
            : isPlaying ? <IconPlayerPauseFilled className="size-6" />
            : <IconPlayerPlayFilled className="size-6 translate-x-[1px]" />}
        </button>
      </div>
      {isCrossfading && (lastResolvedStyle ?? recommendedStyle) && (
        <p className="text-center mt-4 dj-data text-[9px] uppercase tracking-[0.3em] text-muted-foreground/10">
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

      {/* View toggle — bottom right */}
      {current && (
        <button type="button" onClick={() => setView(v => v === 'decks' ? 'master' : 'decks')}
          className="absolute bottom-4 right-4 size-9 rounded-full border border-foreground/6 text-foreground/15 flex items-center justify-center active:scale-95 z-30 bg-black/80 backdrop-blur-sm safe-bottom"
          aria-label="Toggle view">
          {view === 'decks' ? <IconWaveSine className="size-3.5" /> : <IconLayoutGrid className="size-3.5" />}
        </button>
      )}

      <TransitionVisualizer />
    </div>
  )
}
