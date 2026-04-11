'use client'

import { useCallback, useRef } from 'react'
import { IconLoader2, IconPlayerPauseFilled, IconPlayerPlayFilled, IconPlayerSkipForwardFilled } from '@tabler/icons-react'

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
    isCrossfading,
    lastResolvedStyle,
    recommendedStyle,
  } = audio

  const progressPct = current && duration > 0 ? (position / duration) * 100 : 0
  const activeStyle = lastResolvedStyle ?? recommendedStyle

  // First play — load queue at ~128 BPM and start
  const handleStart = useCallback(async () => {
    if (queueLoadedRef.current && current) {
      audio.toggle()
      return
    }
    const tracks = await loadDjQueue(128)
    if (tracks.length === 0) return
    const queue: PlayerTrackMeta[] = tracks.map((t) => ({
      id: t.id,
      title: t.title,
      artists: t.artists,
      durationMs: t.duration_ms,
      bpm: t.bpm,
      camelot: t.camelot,
      mood: t.mood,
    }))
    if (!audio.autoDj) audio.toggleAutoDj()
    if (!audio.mixEnabled) audio.toggleMixEnabled()
    audio.play(queue[0], queue)
    queueLoadedRef.current = true
  }, [audio, current])

  // Next — score transitions, pick best, crossfade
  const handleNext = useCallback(() => {
    void audio.playRecommendedNext()
  }, [audio])

  return (
    <div className="flex min-h-dvh flex-col safe-top safe-bottom">

      {/* Current track — center of screen */}
      <div className="flex-1 flex flex-col items-center justify-center px-6">
        {current ? (
          <div className="w-full max-w-md space-y-8">
            {/* Track info */}
            <div className="text-center">
              <h1 className="display-heading text-3xl leading-tight truncate">{current.title}</h1>
              <p className="text-sm text-muted-foreground/60 mt-1 truncate">{current.artists || ''}</p>
            </div>

            {/* BPM · Key · Mood */}
            <div className="flex items-center justify-center gap-4">
              {current.bpm && (
                <span className="dj-data text-sm text-foreground/70">{current.bpm.toFixed(1)}</span>
              )}
              {current.camelot && (
                <span className="dj-data text-sm text-muted-foreground/50">{current.camelot}</span>
              )}
              {current.mood && (
                <span className="text-xs text-muted-foreground/40">{current.mood.replace(/_/g, ' ')}</span>
              )}
            </div>

            {/* Waveform */}
            <TrackWaveform
              trackId={current.id}
              position={position}
              duration={duration}
              onSeek={(s) => audio.seek(s)}
              height={56}
            />

            {/* Time */}
            <div className="flex items-center justify-between">
              <span className="dj-data text-xs text-muted-foreground/40">{formatTime(position)}</span>
              <div className="flex-1 mx-4 h-px bg-foreground/5">
                <div className="h-full bg-foreground/20" style={{ width: `${progressPct}%` }} />
              </div>
              <span className="dj-data text-xs text-muted-foreground/40">{formatTime(duration)}</span>
            </div>

            {/* === TWO BUTTONS === */}
            <div className="flex items-center justify-center gap-8">
              {/* PLAY / PAUSE */}
              <button
                type="button"
                onClick={() => audio.toggle()}
                disabled={isLoading}
                className="size-20 rounded-full bg-foreground text-background flex items-center justify-center hover:bg-foreground/90 active:scale-95 transition-transform shadow-2xl"
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

              {/* NEXT — analyze & crossfade */}
              <button
                type="button"
                onClick={handleNext}
                disabled={!current}
                className="size-14 rounded-full border border-foreground/15 text-foreground/70 flex items-center justify-center hover:bg-foreground/5 active:scale-95 transition-all disabled:opacity-20"
                aria-label="Next track"
              >
                <IconPlayerSkipForwardFilled className="size-5" />
              </button>
            </div>

            {/* Transition style during crossfade */}
            {isCrossfading && activeStyle && (
              <p className="text-center dj-data text-[10px] uppercase tracking-[0.2em] text-muted-foreground/40">
                {activeStyle.replace(/_/g, ' ')}
              </p>
            )}
          </div>
        ) : (
          /* Nothing playing — big play button */
          <div className="text-center space-y-8">
            <h1 className="display-heading text-5xl">Mix</h1>
            <button
              type="button"
              onClick={handleStart}
              disabled={isLoading}
              className="size-24 rounded-full bg-foreground text-background flex items-center justify-center mx-auto hover:bg-foreground/90 active:scale-95 transition-transform shadow-2xl"
              aria-label="Start mixing"
            >
              {isLoading ? (
                <IconLoader2 className="size-10 animate-spin" />
              ) : (
                <IconPlayerPlayFilled className="size-10 translate-x-[3px]" />
              )}
            </button>
          </div>
        )}
      </div>

      {/* Bottom: master BPM + next up */}
      <div className="px-6 pb-4 space-y-2">
        {masterTempoBpm && (
          <div className="flex items-center justify-center gap-2">
            <span className="dj-data text-2xl text-foreground">{Math.round(masterTempoBpm)}</span>
            <span className="dj-data text-[10px] uppercase tracking-wider text-muted-foreground/30">BPM</span>
          </div>
        )}
        {nextUp && (
          <p className="text-center text-xs text-muted-foreground/30 truncate">
            next: {nextUp.title}
            {nextUp.bpm ? ` · ${nextUp.bpm.toFixed(0)}` : ''}
            {nextUp.camelot ? ` · ${nextUp.camelot}` : ''}
          </p>
        )}
      </div>

      <TransitionVisualizer />
    </div>
  )
}
