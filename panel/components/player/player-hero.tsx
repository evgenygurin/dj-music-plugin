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

/**
 * Layer 0 — compact "start a mix" prompt. Shown when nothing is loaded
 * and the interaction level is 0. Pressing the CTA calls
 * `pickDefaultFirstTrack()` and starts the audio player, then promotes
 * the layer to 1 (mini bar).
 */
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
      className="fixed inset-x-4 bottom-24 z-30 sm:bottom-28 sm:left-auto sm:right-6 sm:max-w-sm"
      role="region"
      aria-label="Start playback"
    >
      <div className="relative overflow-hidden rounded-3xl border border-border/80 bg-background/90 p-5 shadow-2xl backdrop-blur-xl">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/90 via-fuchsia-400/45 to-transparent" />
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss"
          className="absolute right-4 top-4 rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
        >
          <X className="size-4" />
        </button>
        <div className="space-y-4">
          <div className="space-y-1 pr-10">
            <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
              Session Preview
            </p>
            <h2 className="text-xl font-semibold tracking-tight text-balance">
              Start a Mix Without Leaving the Dashboard
            </h2>
            <p className="text-sm text-muted-foreground">
              Pick a strong opening track from the analyzed library and drop into the player instantly.
            </p>
          </div>
          <Button
            className="w-full justify-center gap-2"
            onClick={handleStart}
            disabled={loading}
            aria-label="Start playback"
          >
            <Play className="size-4 fill-current" />
            {loading ? 'Finding a Starting Track…' : 'Start a Preview Mix'}
          </Button>
        </div>
      </div>
    </div>
  )
}
