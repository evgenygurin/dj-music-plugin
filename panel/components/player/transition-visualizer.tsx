'use client'

import { useEffect, useRef, useState } from 'react'

import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import { cn } from '@/lib/utils'

import { TrackWaveform } from './track-waveform'

export function TransitionVisualizer() {
  const audio = useAudioPlayer()
  const {
    isCrossfading,
    outgoing,
    current,
    crossfadeStartedAt,
    crossfadeDurationSeconds,
    outgoingFadeStartPosition,
    incomingFadeStartPosition,
    outgoingFadePlaybackRate,
    incomingFadePlaybackRate,
    recommendedStyle,
    recommendedBars,
    lastResolvedStyle,
    lastResolvedStyleWasManual,
  } = audio

  const [progress, setProgress] = useState(0)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    if (!isCrossfading || crossfadeStartedAt == null || !crossfadeDurationSeconds) {
      return
    }
    const dur = crossfadeDurationSeconds * 1000
    const wallStart = performance.now()
    const tick = () => {
      const elapsed = performance.now() - wallStart
      const p = Math.max(0, Math.min(1, elapsed / dur))
      setProgress(p)
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [isCrossfading, crossfadeStartedAt, crossfadeDurationSeconds])

  if (!isCrossfading || !outgoing || !current || outgoing.id === current.id) {
    return null
  }

  const displayProgress = Math.max(0, Math.min(1, progress))
  const gainOut = Math.cos((displayProgress * Math.PI) / 2)
  const gainIn = Math.sin((displayProgress * Math.PI) / 2)

  const fadeDur = crossfadeDurationSeconds ?? 0
  const elapsed = displayProgress * fadeDur
  const outRate = outgoingFadePlaybackRate ?? 1
  const inRate = incomingFadePlaybackRate ?? 1
  const outgoingPos =
    outgoingFadeStartPosition != null ? outgoingFadeStartPosition + elapsed * outRate : 0
  const incomingPos =
    incomingFadeStartPosition != null ? incomingFadeStartPosition + elapsed * inRate : 0

  const SWAP_WINDOW = 0.125
  const swapStart = 0.5 - SWAP_WINDOW / 2
  const swapEnd = 0.5 + SWAP_WINDOW / 2
  const swapProgress =
    displayProgress <= swapStart
      ? 0
      : displayProgress >= swapEnd
        ? 1
        : (displayProgress - swapStart) / SWAP_WINDOW
  const bassOut = 1 - swapProgress
  const bassIn = swapProgress

  return (
    <div
      className="pointer-events-none fixed bottom-[100px] left-1/2 z-40 w-[min(960px,calc(100vw-1.5rem))] -translate-x-1/2"
      role="region"
      aria-label="Active transition"
    >
      <div className="pointer-events-auto glass rounded-2xl p-4 shadow-2xl shadow-black/20">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="dj-data text-[10px] uppercase tracking-[0.2em] text-foreground/70">
            Transition · {(displayProgress * 100).toFixed(0)}%
          </span>
          {(lastResolvedStyle ?? recommendedStyle) && (
            <span
              className={cn(
                'rounded-full border px-2.5 py-0.5 dj-data text-[10px] uppercase tracking-wider',
                lastResolvedStyleWasManual
                  ? 'border-foreground/20 bg-foreground/5 text-foreground'
                  : 'border-muted-foreground/30 bg-muted/20 text-muted-foreground',
              )}
              title={
                lastResolvedStyleWasManual
                  ? 'Manual override'
                  : 'Backend recommendation'
              }
            >
              {(lastResolvedStyle ?? recommendedStyle ?? '').replace(/_/g, ' ')}
              {recommendedBars != null && recommendedBars > 0
                ? ` · ${recommendedBars}b`
                : ''}
              {lastResolvedStyleWasManual ? ' · manual' : ''}
            </span>
          )}
          <span className="dj-data text-[10px] text-muted-foreground/60">
            {crossfadeDurationSeconds?.toFixed(1) ?? '?'}s
          </span>
        </div>

        {/* Outgoing deck */}
        <div className="mb-1.5 flex items-center gap-2">
          <span
            className="w-10 shrink-0 text-right dj-data text-[10px]"
            style={{ opacity: 0.4 + gainOut * 0.6 }}
          >
            -{(40 * (1 - bassOut)).toFixed(0)}dB
          </span>
          <div className="min-w-0 flex-1">
            <div className="mb-0.5 flex items-baseline gap-2">
              <span className="truncate text-xs font-medium" style={{ opacity: 0.5 + gainOut * 0.5 }}>
                {outgoing.title}
              </span>
              {outgoing.bpm && (
                <span className="dj-data text-[10px] text-muted-foreground/60">
                  {outgoing.bpm.toFixed(1)}
                </span>
              )}
            </div>
            <div style={{ opacity: 0.3 + gainOut * 0.7 }}>
              <TrackWaveform
                trackId={outgoing.id}
                position={outgoingPos}
                duration={(outgoing.durationMs ?? 0) / 1000}
                onSeek={() => undefined}
                height={32}
              />
            </div>
          </div>
        </div>

        {/* Crossfade indicator — deck A (blue) → deck B (orange) */}
        <div className="my-2.5 flex h-1 w-full overflow-hidden rounded-full bg-muted/20">
          <div
            className="transition-[width] duration-75 ease-linear"
            style={{
              width: `${gainOut * 100}%`,
              background: 'oklch(0.70 0.17 240 / 0.7)',
            }}
          />
          <div
            className="transition-[width] duration-75 ease-linear"
            style={{
              width: `${gainIn * 100}%`,
              background: 'oklch(0.70 0.18 50 / 0.7)',
            }}
          />
        </div>

        {/* Incoming deck */}
        <div className="mt-1.5 flex items-center gap-2">
          <span
            className="w-10 shrink-0 text-right dj-data text-[10px]"
            style={{ opacity: 0.4 + gainIn * 0.6 }}
          >
            -{(40 * (1 - bassIn)).toFixed(0)}dB
          </span>
          <div className="min-w-0 flex-1">
            <div style={{ opacity: 0.3 + gainIn * 0.7 }}>
              <TrackWaveform
                trackId={current.id}
                position={incomingPos}
                duration={(current.durationMs ?? 0) / 1000}
                onSeek={() => undefined}
                height={32}
              />
            </div>
            <div className="mt-0.5 flex items-baseline gap-2">
              <span
                className="truncate text-xs font-medium"
                style={{ opacity: 0.5 + gainIn * 0.5 }}
              >
                {current.title}
              </span>
              {current.bpm && (
                <span className="dj-data text-[10px] text-muted-foreground/60">
                  {current.bpm.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
