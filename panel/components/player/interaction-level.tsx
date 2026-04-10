'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'

export type PlayerLayer = 0 | 1 | 2 | 3 | 4
const STORAGE_KEY = 'dj-player-level'

interface InteractionLevelApi {
  level: PlayerLayer
  promote: () => void
  collapse: () => void
  jumpTo: (target: PlayerLayer) => void
}

const Ctx = createContext<InteractionLevelApi | null>(null)

function readStoredPlayerLayer(): PlayerLayer | null {
  if (typeof window === 'undefined') return null
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (!stored) return null
  const parsed = Number.parseInt(stored, 10)
  return parsed >= 0 && parsed <= 4 ? (parsed as PlayerLayer) : null
}

function persistPlayerLayer(next: PlayerLayer) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, String(next))
}

export function PlayerInteractionLevelProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [level, setLevel] = useState<PlayerLayer>(0)

  useEffect(() => {
    const storedLevel = readStoredPlayerLayer()
    if (storedLevel === null) return
    const frame = window.requestAnimationFrame(() => {
      setLevel(storedLevel)
    })
    return () => window.cancelAnimationFrame(frame)
  }, [])

  const persist = useCallback((next: PlayerLayer) => {
    setLevel(next)
    persistPlayerLayer(next)
  }, [])

  const promote = useCallback(() => {
    setLevel((cur) => {
      const next = Math.min(4, cur + 1) as PlayerLayer
      persistPlayerLayer(next)
      return next
    })
  }, [])

  const collapse = useCallback(() => {
    setLevel((cur) => {
      const next = Math.max(0, cur - 1) as PlayerLayer
      persistPlayerLayer(next)
      return next
    })
  }, [])

  const jumpTo = useCallback(
    (target: PlayerLayer) => {
      persist(target)
    },
    [persist],
  )

  const api = useMemo<InteractionLevelApi>(
    () => ({ level, promote, collapse, jumpTo }),
    [level, promote, collapse, jumpTo],
  )

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>
}

export function usePlayerInteractionLevel(): InteractionLevelApi {
  const ctx = useContext(Ctx)
  if (!ctx) {
    throw new Error(
      'usePlayerInteractionLevel must be used inside PlayerInteractionLevelProvider',
    )
  }
  return ctx
}
