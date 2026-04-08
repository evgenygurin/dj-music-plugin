'use client'

import {
  AudioPlayerProvider,
  useAudioPlayer,
} from '@/components/audio-player/audio-player-context'
import { SetSessionProvider, useSetSession } from './set-session-context'
import { usePlayerInteractionLevel, type PlayerLayer } from './interaction-level'

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  return (
    <AudioPlayerProvider>
      <SetSessionProvider>
        <>{children}</>
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
  return {
    audio,
    set,
    layer: level,
    promoteLayer: promote,
    collapseLayer: collapse,
    jumpToLayer: jumpTo,
  }
}
