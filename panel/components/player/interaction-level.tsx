'use client'

import { useCallback, useEffect, useState } from 'react'

export type PlayerLayer = 0 | 1 | 2 | 3 | 4
const STORAGE_KEY = 'dj-player-level'

export function usePlayerInteractionLevel() {
  const [level, setLevel] = useState<PlayerLayer>(0)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = Number.parseInt(stored, 10)
      if (parsed >= 0 && parsed <= 4) setLevel(parsed as PlayerLayer)
    }
  }, [])

  const persist = useCallback((next: PlayerLayer) => {
    setLevel(next)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, String(next))
    }
  }, [])

  const promote = useCallback(() => {
    persist(Math.min(4, level + 1) as PlayerLayer)
  }, [level, persist])

  const collapse = useCallback(() => {
    persist(Math.max(0, level - 1) as PlayerLayer)
  }, [level, persist])

  const jumpTo = useCallback(
    (target: PlayerLayer) => {
      persist(target)
    },
    [persist],
  )

  return { level, promote, collapse, jumpTo }
}
