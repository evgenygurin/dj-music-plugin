'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  IconLoader2,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipForwardFilled,
  IconPlayerSkipBackFilled,
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

/* ══════ IDLE ══════ */
function IdleScreen({ onStart, loading }: { onStart: (bpm: number) => void; loading: boolean }) {
  const [bpm, setBpm] = useState(128)
  return (
    <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="size-[280px] rounded-full bg-foreground/[0.02] animate-pulse" style={{ animationDuration: '3s' }} />
      </div>
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="size-[160px] rounded-full bg-foreground/[0.03] animate-pulse" style={{ animationDuration: '2s', animationDelay: '0.5s' }} />
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

/* ══════ PLAYING — djay Pro style ══════ */
function PlayingScreen({ audio, count, elapsed }: {
  audio: ReturnType<typeof useAudioPlayer>; count: number; elapsed: number
}) {
  const { current, isPlaying, isLoading, position, duration, nextUp, outgoing, isCrossfading,
    lastResolvedStyle, recommendedStyle, volume, crossfadeBars, masterTempoBpm } = audio
  const progress = current && duration > 0 ? position / duration : 0
  const style = lastResolvedStyle ?? recommendedStyle

  if (!current) return null

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-black">

      {/* ── TOP: Track info + overview waveform ── */}
      <div className="px-3 pt-2 pb-1">
        <div className="flex items-center gap-3">
          {/* Album art placeholder */}
          <div className="size-12 shrink-0 rounded-lg bg-foreground/[0.04] border border-foreground/[0.06] grid place-items-center">
            <span className="text-foreground/15 text-lg">♪</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">{current.title}</p>
            <p className="text-[11px] text-muted-foreground/30 truncate">{current.artists || ''}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="dj-data text-sm text-foreground/60">-{fmt(duration - position)}</p>
            <p className="dj-data text-[10px] text-muted-foreground/20">{fmt(duration)}</p>
          </div>
        </div>
        {/* Overview waveform (thin strip) */}
        <div className="mt-1.5 h-3 rounded-sm overflow-hidden bg-foreground/[0.02] relative">
          <div className="absolute inset-y-0 left-0 bg-foreground/[0.06]" style={{ width: `${progress * 100}%` }} />
          <div className="absolute inset-y-0 bg-red-500/80" style={{ left: `${progress * 100}%`, width: '1px' }} />
        </div>
      </div>

      {/* ── MAIN: Zoomable waveform with sections ── */}
      <div className="flex-1 min-h-0 border-y border-foreground/[0.04]">
        <TrackWaveform
          trackId={current.id}
          position={position}
          duration={duration}
          onSeek={s => audio.seek(s)}
          height={200}
          zoomable
          showTimeline
          className="w-full h-full"
        />
      </div>

      {/* ── NEXT UP bar ── */}
      {nextUp && (
        <div className="px-3 py-1.5 border-b border-foreground/[0.03] flex items-center gap-2">
          <span className="text-[8px] uppercase tracking-wider text-muted-foreground/15">Next</span>
          <p className="text-[11px] text-muted-foreground/30 truncate flex-1">{nextUp.title}</p>
          {nextUp.bpm && <span className="dj-data text-[10px] text-muted-foreground/15">{nextUp.bpm.toFixed(0)}</span>}
          {nextUp.camelot && <span className="dj-data text-[9px] text-muted-foreground/10">{nextUp.camelot}</span>}
        </div>
      )}

      {/* ── SESSION INFO ── */}
      <div className="px-3 py-1 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {current.bpm && <span className="dj-data text-xs text-foreground/40">{current.bpm.toFixed(1)}</span>}
          {current.camelot && <span className="dj-data text-[11px] text-muted-foreground/20">{current.camelot}</span>}
          {current.mood && <span className="text-[9px] text-muted-foreground/12">{current.mood.replace(/_/g, ' ')}</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className="dj-data text-[9px] text-muted-foreground/10">{count} mixed</span>
          <span className="dj-data text-[9px] text-muted-foreground/10">{fmt(elapsed)}</span>
        </div>
      </div>

      {/* ── TRANSPORT BAR — djay style ── */}
      <div className="px-3 pb-1 pt-0.5">
        {/* Volume */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[8px] text-muted-foreground/10 w-6">VOL</span>
          <Slider value={[volume * 100]} min={0} max={100} step={1}
            onValueChange={v => audio.setVolume(v[0] / 100)} className="flex-1" aria-label="Volume" />
        </div>

        {/* Crossfade info */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <span className="dj-data text-[9px] text-muted-foreground/15">{style ? style.replace(/_/g, ' ') : 'auto'}</span>
            <span className="text-muted-foreground/8">·</span>
            <span className="dj-data text-[9px] text-muted-foreground/12">{crossfadeBars}b</span>
          </div>
          {masterTempoBpm && (
            <span className="dj-data text-sm text-foreground/50">{Math.round(masterTempoBpm)} <span className="text-[8px] text-muted-foreground/15">BPM</span></span>
          )}
        </div>

        {/* Transport buttons */}
        <div className="flex items-center justify-center gap-5 py-1">
          <button type="button" onClick={() => audio.prev?.()} disabled={!audio.hasPrev}
            className="size-10 rounded-full border border-foreground/6 text-foreground/20 flex items-center justify-center active:scale-95 disabled:opacity-10"
            aria-label="Previous">
            <IconPlayerSkipBackFilled className="size-3.5" />
          </button>

          <button type="button" onClick={() => void audio.playRecommendedNext()}
            className="size-10 rounded-full border border-foreground/8 text-foreground/25 flex items-center justify-center active:scale-95"
            aria-label="Smart next">
            <IconPlayerSkipForwardFilled className="size-3.5" />
          </button>

          <button type="button" onClick={() => audio.toggle()} disabled={isLoading}
            className="size-16 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 shadow-[0_0_30px_oklch(1_0_0/0.05)]"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isLoading ? <IconLoader2 className="size-6 animate-spin" />
              : isPlaying ? <IconPlayerPauseFilled className="size-6" />
              : <IconPlayerPlayFilled className="size-6 translate-x-[1px]" />}
          </button>

          <button type="button" onClick={() => audio.mixNow()}
            className="size-10 rounded-full border border-foreground/8 text-foreground/25 flex items-center justify-center active:scale-95"
            aria-label="Mix now">
            <span className="dj-data text-[8px]">MIX</span>
          </button>

          <button type="button"
            onClick={() => { if (!audio.autoDj) audio.toggleAutoDj(); if (!audio.mixEnabled) audio.toggleMixEnabled() }}
            className={`size-10 rounded-full border flex items-center justify-center active:scale-95 dj-data text-[8px] ${audio.autoDj && audio.mixEnabled ? 'border-foreground/20 text-foreground/50 bg-foreground/5' : 'border-foreground/6 text-foreground/15'}`}
            aria-label="Auto DJ">
            AUTO
          </button>
        </div>
      </div>

      {/* Crossfade pulse */}
      {isCrossfading && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-foreground/10 animate-pulse" />
      )}

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
  const lastRef = useRef<number | null>(null)
  const { current, isLoading, outgoing } = audio

  if (current && current.id !== lastRef.current) {
    if (lastRef.current !== null) setCount(n => n + 1)
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
      ) : (
        <PlayingScreen audio={audio} count={count} elapsed={elapsed} />
      )}
    </div>
  )
}
