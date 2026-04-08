'use client'

import { useState } from 'react'
import { Play, X } from 'lucide-react'

import { pickDefaultFirstTrack } from '@/actions/default-first-picker-actions'
import { Button } from '@/components/ui/button'
import type { PlayerTrackMeta } from '@/components/audio-player/audio-player-context'
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
 * Layer 0 — full-screen "Tap to start" hero. Shown when nothing is loaded
 * and the interaction level is 0. Pressing the centered Play button calls
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
      className="fixed inset-0 z-30 flex items-center justify-center bg-background/40 backdrop-blur-sm"
      role="dialog"
      aria-label="Start playback"
    >
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        className="absolute top-4 right-4 rounded-md p-2 text-muted-foreground hover:bg-muted/40 hover:text-foreground"
      >
        <X className="size-5" />
      </button>
      <div className="flex flex-col items-center gap-4">
        <Button
          size="icon"
          className="h-32 w-32 rounded-full shadow-xl"
          onClick={handleStart}
          disabled={loading}
          aria-label="Start playback"
        >
          <Play className="size-12 translate-x-1 fill-current" />
        </Button>
        <div className="text-sm text-muted-foreground">Tap to start</div>
      </div>
    </div>
  )
}
