'use client'

import { useEffect } from 'react'

import {
  AudioPlayerProvider,
  useAudioPlayer,
} from '@/components/audio-player/audio-player-context'
import { SetSessionProvider, useSetSession } from './set-session-context'
import {
  PlayerInteractionLevelProvider,
  usePlayerInteractionLevel,
  type PlayerLayer,
} from './interaction-level'

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  return (
    <AudioPlayerProvider>
      <SetSessionProvider>
        <PlayerInteractionLevelProvider>
          <>{children}</>
        </PlayerInteractionLevelProvider>
      </SetSessionProvider>
    </AudioPlayerProvider>
  )
}

export interface PlayerApi {
  audio: ReturnType<typeof useAudioPlayer>
  set: ReturnType<typeof useSetSession>
  layer: PlayerLayer
  promoteLayer: () => void
  collapseLayer: () => void
  jumpToLayer: (l: PlayerLayer) => void
}

export function usePlayer(): PlayerApi {
  const audio = useAudioPlayer()
  const set = useSetSession()
  const { level, promote, collapse, jumpTo } = usePlayerInteractionLevel()

  // Auto-promote: as soon as a track is loaded into the audio player,
  // make sure the bar layer is at least 1. Without this, clicking ▶ on
  // a library row sets `audio.current` but the Layer 1 mini bar's gate
  // (`if (layer !== 1) return null`) keeps it hidden.
  useEffect(() => {
    if (audio.current !== null && level === 0) {
      jumpTo(1)
    }
  }, [audio.current, level, jumpTo])

  return {
    audio,
    set,
    layer: level,
    promoteLayer: promote,
    collapseLayer: collapse,
    jumpToLayer: jumpTo,
  }
}
