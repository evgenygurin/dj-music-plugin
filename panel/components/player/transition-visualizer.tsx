'use client'

import { useEffect, useRef, useState } from 'react'

import { useAudioPlayer } from '@/components/audio-player/audio-player-context'

import { TrackWaveform } from './track-waveform'

/**
 * Fixed overlay that materialises during a crossfade and renders a
 * "from → to" pair of waveforms with the equal-power gain envelopes,
 * the bass-swap automation, and a progress bar that walks across the
 * fade in real time.
 *
 * The audio engine itself owns the actual mixing — this is purely a
 * visualization layered on top of the existing AudioPlayer context.
 * Mounted permanently inside <Player>, but renders nothing unless
 * `isCrossfading` is true.
 */
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
  } = audio

  // Wall-clock progress 0..1 across the crossfade. Driven by rAF so it
  // updates smoothly without re-rendering on every audio sample.
  const [progress, setProgress] = useState(0)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    if (!isCrossfading || crossfadeStartedAt == null || !crossfadeDurationSeconds) {
      setProgress(0)
      return
    }
    const dur = crossfadeDurationSeconds * 1000
    // Anchor wall-clock to a sample taken right after the fade started
    // so we don't drift even if the AudioContext clock differs from
    // performance.now() by a few ms.
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
    // We intentionally only re-arm when the fade itself changes — `t0`
    // and `dur` are derived from the deps below.
  }, [isCrossfading, crossfadeStartedAt, crossfadeDurationSeconds])

  if (!isCrossfading || !outgoing || !current || outgoing.id === current.id) {
    return null
  }

  // Equal-power gain at the current progress (matches what the audio
  // engine is actually doing — see startCrossfade in audio-player-context).
  const gainOut = Math.cos((progress * Math.PI) / 2)
  const gainIn = Math.sin((progress * Math.PI) / 2)

  // Live per-deck playhead positions during the overlap. Each deck
  // started at a snapshot position and has been advancing at its own
  // playbackRate (incoming may be tempo-matched to outgoing). The
  // visualizer doesn't have raw access to <audio>.currentTime, so we
  // extrapolate from the snapshot + wall-clock progress to keep the
  // two waveform cursors driving in real time.
  const fadeDur = crossfadeDurationSeconds ?? 0
  const elapsed = progress * fadeDur
  const outRate = outgoingFadePlaybackRate ?? 1
  const inRate = incomingFadePlaybackRate ?? 1
  const outgoingPos =
    outgoingFadeStartPosition != null ? outgoingFadeStartPosition + elapsed * outRate : 0
  const incomingPos =
    incomingFadeStartPosition != null ? incomingFadeStartPosition + elapsed * inRate : 0

  // Bass swap is a short cross-ramp centered on the midpoint. The
  // audio engine ramps over 1..4 bars depending on cf; we don't have
  // cf in bars here, so we use a fixed 12.5 % window (matches the
  // engine's swapBars = cfBars / 8 rule). Outgoing bass drops from
  // 1 → 0 and incoming rises from 0 → 1 linearly over that window.
  const SWAP_WINDOW = 0.125 // 12.5 % of fade width
  const swapStart = 0.5 - SWAP_WINDOW / 2
  const swapEnd = 0.5 + SWAP_WINDOW / 2
  const swapProgress =
    progress <= swapStart
      ? 0
      : progress >= swapEnd
        ? 1
        : (progress - swapStart) / SWAP_WINDOW
  const bassOut = 1 - swapProgress
  const bassIn = swapProgress

  return (
    <div
      className="pointer-events-none fixed bottom-[88px] left-1/2 z-40 w-[min(960px,calc(100vw-2rem))] -translate-x-1/2"
      role="region"
      aria-label="Active transition"
    >
      <div className="pointer-events-auto rounded-xl border border-primary/40 bg-background/95 p-4 shadow-2xl backdrop-blur supports-[backdrop-filter]:bg-background/85">
        <div className="mb-2 flex items-center justify-between gap-3 text-[11px]">
          <span className="font-mono uppercase tracking-wider text-primary/80">
            Transition · {(progress * 100).toFixed(0)}%
          </span>
          {recommendedStyle && (
            <span
              className="rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-primary"
              title="Backend-recommended transition style"
            >
              {recommendedStyle.replace(/_/g, ' ')}
              {recommendedBars != null && recommendedBars > 0 ? ` · ${recommendedBars}b` : ''}
            </span>
          )}
          <span className="tabular-nums text-muted-foreground">
            {crossfadeDurationSeconds?.toFixed(1) ?? '?'}s
          </span>
        </div>

        {/* Outgoing deck (A) */}
        <div className="mb-1 flex items-center gap-2">
          <span
            className="w-12 shrink-0 text-right font-mono text-[10px] tabular-nums"
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
                <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
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

        {/* Equal-power crossfade indicator (single row, two-tone bar) */}
        <div className="my-2 flex h-1 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="bg-cyan-400/70 transition-[width] duration-75 ease-linear"
            style={{ width: `${gainOut * 100}%` }}
          />
          <div
            className="bg-fuchsia-500/80 transition-[width] duration-75 ease-linear"
            style={{ width: `${gainIn * 100}%` }}
          />
        </div>

        {/* Incoming deck (B) */}
        <div className="mt-1 flex items-center gap-2">
          <span
            className="w-12 shrink-0 text-right font-mono text-[10px] tabular-nums"
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
                <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
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
