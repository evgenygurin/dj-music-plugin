'use client'

import { useState } from 'react'
import { Play, X } from 'lucide-react'

import { pickDefaultFirstTrack } from '@/actions/default-first-picker-actions'
import { Button } from '@/components/ui/button'
import type { PlayerTrackMeta } from '@/components/audio-player/audio-player-types'
import type { TrackRow } from '@/lib/queries/tracks'

import { usePlayer } from './player-provider'

function toMeta(row: TrackRow): PlayerTrackMeta {
  return {
    id: row.id,
    title: row.title,
    artists: row.artists,
    durationMs: row.duration_ms,
    bpm: row.bpm,
    camelot: row.camelot,
    mood: row.mood,
  }
}

export function PlayerHero() {
  const player = usePlayer()
  const [dismissed, setDismissed] = useState(false)
  const [loading, setLoading] = useState(false)

  if (player.layer !== 0) return null
  if (player.audio.current !== null) return null
  if (dismissed) return null

  const handleStart = async () => {
    if (loading) return
    setLoading(true)
    try {
      const { first, queue } = await pickDefaultFirstTrack()
      if (!first) return
      const queueMeta = queue.map(toMeta)
      player.audio.play(toMeta(first), queueMeta)
      player.jumpToLayer(1)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-x-4 bottom-24 z-30 md:bottom-28 md:left-auto md:right-6 md:max-w-sm"
      role="region"
      aria-label="Start playback"
    >
      <div className="glass relative overflow-hidden rounded-2xl p-6 shadow-2xl">
        {/* Top accent line */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-foreground/20 via-foreground/5 to-transparent" />

        {/* Animated waveform decoration */}
        <div className="absolute inset-0 overflow-hidden opacity-[0.04] pointer-events-none">
          <svg viewBox="0 0 400 120" className="w-full h-full" preserveAspectRatio="none">
            <path
              d="M0,60 Q50,20 100,60 T200,60 T300,60 T400,60"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-primary"
            />
            <path
              d="M0,60 Q50,90 100,60 T200,60 T300,60 T400,60"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-primary/60"
            />
          </svg>
        </div>

        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss"
          className="absolute right-4 top-4 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
        >
          <X className="size-4" />
        </button>

        <div className="relative space-y-5">
          <div className="space-y-2 pr-10">
            <p className="dj-data text-[10px] uppercase tracking-[0.3em] text-foreground/40">
              Session
            </p>
            <h2 className="display-heading text-2xl text-foreground">
              Start a Mix
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Auto-select a strong opener from the analyzed library and drop straight into the player.
            </p>
          </div>

          <Button
            className="w-full justify-center gap-2.5 h-12 rounded-xl text-sm font-medium"
            onClick={handleStart}
            disabled={loading}
            aria-label="Start playback"
          >
            <Play className="size-4 fill-current" />
            {loading ? 'Finding a Track…' : 'Begin Session'}
          </Button>
        </div>
      </div>
    </div>
  )
}
