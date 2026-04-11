'use client'

import { IconPlayerPauseFilled, IconPlayerPlayFilled, IconX } from '@tabler/icons-react'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import { TrackWaveform } from './track-waveform'

function fmt(s: number) {
  if (!Number.isFinite(s) || s < 0) return '0:00'
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

export function WaveformFullscreen({ onClose }: { onClose: () => void }) {
  const audio = useAudioPlayer()
  const { current, isPlaying, position, duration, masterTempoBpm } = audio

  if (!current) return null

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black safe-top safe-bottom">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{current.title}</p>
          <p className="truncate text-[11px] text-muted-foreground/30">{current.artists || ''}</p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {current.bpm && <span className="dj-data text-sm text-foreground/50">{current.bpm.toFixed(0)}</span>}
          {current.camelot && <span className="dj-data text-xs text-muted-foreground/25">{current.camelot}</span>}
          <button type="button" onClick={onClose}
            className="size-8 rounded-full border border-foreground/10 flex items-center justify-center text-foreground/30 hover:text-foreground/60"
            aria-label="Close">
            <IconX className="size-4" />
          </button>
        </div>
      </div>

      {/* Minimap + Main waveform + Timeline */}
      <div className="flex-1 flex flex-col justify-center px-2">
        <p className="dj-data text-[8px] uppercase tracking-[0.2em] text-muted-foreground/15 px-2 mb-1">
          Pinch to zoom · Tap to seek
        </p>
        <div className="rounded-xl border border-foreground/5 bg-foreground/[0.015] overflow-hidden">
          <TrackWaveform
            trackId={current.id}
            position={position}
            duration={duration}
            onSeek={s => audio.seek(s)}
            height={140}
            zoomable
            showMinimap
            showTimeline
          />
        </div>
      </div>

      {/* Controls */}
      <div className="px-4 pb-4 space-y-3">
        {/* Time */}
        <div className="flex items-center gap-3">
          <span className="dj-data text-xs text-muted-foreground/25 w-10 text-right">{fmt(position)}</span>
          <div className="flex-1 h-[2px] bg-foreground/5 rounded-full overflow-hidden">
            <div className="h-full bg-foreground/20" style={{ width: `${duration > 0 ? (position / duration) * 100 : 0}%` }} />
          </div>
          <span className="dj-data text-xs text-muted-foreground/25 w-10">{fmt(duration)}</span>
        </div>

        {/* Play/Pause */}
        <div className="flex items-center justify-center">
          <button type="button" onClick={() => audio.toggle()}
            className="size-14 rounded-full bg-foreground text-background flex items-center justify-center active:scale-95 transition-transform"
            aria-label={isPlaying ? 'Pause' : 'Play'}>
            {isPlaying
              ? <IconPlayerPauseFilled className="size-6" />
              : <IconPlayerPlayFilled className="size-6 translate-x-[1px]" />}
          </button>
        </div>

        {/* BPM */}
        {masterTempoBpm && (
          <p className="text-center dj-data text-xs text-muted-foreground/15">
            {Math.round(masterTempoBpm)} BPM
          </p>
        )}
      </div>
    </div>
  )
}
