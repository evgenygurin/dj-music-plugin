// panel/components/player/player-hero.tsx
'use client'

import { IconPlayerPlayFilled, IconX } from '@tabler/icons-react'
import { useState } from 'react'

import { pickDefaultFirstTrack } from '@/actions/default-first-picker-actions'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

export function PlayerHero() {
  const player = usePlayer()
  const [dismissed, setDismissed] = useState(false)
  const [loading, setLoading] = useState(false)

  if (player.layer > 0 || player.audio.current !== null) return null
  if (dismissed) return null

  const handlePlay = async () => {
    setLoading(true)
    try {
      const result = await pickDefaultFirstTrack()
      if (!result.first) return
      const queue = result.queue.map((t) => ({
        id: t.id,
        title: t.title,
        artists: t.artists,
        durationMs: t.duration_ms,
        bpm: t.bpm,
        camelot: t.camelot,
        mood: t.mood,
      }))
      const first = queue.find((q) => q.id === result.first!.id)!
      player.audio.play(first, queue)
      player.promoteLayer() // 0 → 1
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-label="Start playing"
      className={cn(
        'fixed inset-0 z-30 flex items-center justify-center',
        'bg-background/40 backdrop-blur-sm',
      )}
    >
      <div className="flex flex-col items-center gap-6">
        <Button
          size="icon"
          onClick={handlePlay}
          disabled={loading}
          className={cn(
            'h-32 w-32 rounded-full shadow-2xl',
            'bg-primary text-primary-foreground',
            'animate-pulse hover:animate-none hover:scale-105 transition-transform',
          )}
          aria-label="Start"
        >
          <IconPlayerPlayFilled className="size-12 translate-x-0.5" />
        </Button>
        <p className="text-sm text-muted-foreground">
          {loading ? 'Finding the right track…' : 'Tap to start'}
        </p>
      </div>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="absolute top-6 right-6 rounded-full p-2 hover:bg-muted/40"
        aria-label="Dismiss"
      >
        <IconX className="size-5" />
      </button>
    </div>
  )
}
