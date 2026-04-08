'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import { fetchSetTemplates } from '@/actions/set-templates-actions'
import { pickNextSetTrack } from '@/actions/set-picker-actions'
import type {
  HistoryEntry,
  ScoredCandidate,
  SetSessionState,
  SetTemplate,
} from '@/lib/set-narrative/types'
import { getCurrentSlot } from '@/lib/set-narrative/scoring'

import { useAudioPlayer, type PlayerTrackMeta } from '@/components/audio-player/audio-player-context'

interface SetSessionApi extends SetSessionState {
  templates: SetTemplate[]
  startTemplate: (templateName: string) => void
  stopSet: () => void
  skipSlot: () => void
  rebuildRemainder: () => Promise<void>
  overridePick: (track: PlayerTrackMeta) => void
}

const Ctx = createContext<SetSessionApi | null>(null)

export function useSetSession(): SetSessionApi {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useSetSession must be used inside SetSessionProvider')
  return ctx
}

const SESSION_STORAGE_KEY = 'dj-set-session'

export function SetSessionProvider({ children }: { children: React.ReactNode }) {
  const player = useAudioPlayer()
  const [templates, setTemplates] = useState<SetTemplate[]>([])
  const [active, setActive] = useState(false)
  const [template, setTemplate] = useState<SetTemplate | null>(null)
  const [startedAtSec, setStartedAtSec] = useState(0)
  const [elapsedSec, setElapsedSec] = useState(0)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [upcoming, setUpcoming] = useState<ScoredCandidate[]>([])
  const [varietyTier] = useState<0 | 1 | 2>(0)
  const [relaxationEvents] = useState<string[]>([])
  const pickInFlight = useRef(false)

  // Fetch templates once on mount
  useEffect(() => {
    void fetchSetTemplates().then(setTemplates)
  }, [])

  // Restore session from sessionStorage on mount
  useEffect(() => {
    if (typeof window === 'undefined') return
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw)
      if (parsed && parsed.active && parsed.templateName) {
        // deferred: restored after templates load
      }
    } catch {
      // ignore
    }
  }, [])

  // Persist session on change
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!active) {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY)
      return
    }
    window.sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({
        active,
        templateName: template?.name,
        startedAtSec,
        history,
      }),
    )
  }, [active, template, startedAtSec, history])

  // Track elapsed time from AudioContext/clock
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => {
      setElapsedSec((s) => s + 1)
    }, 1000)
    return () => window.clearInterval(id)
  }, [active])

  // Compute currentSlot
  const currentSlot = useMemo(() => {
    if (!template) return null
    return getCurrentSlot(template, elapsedSec, template.durationMin * 60)
  }, [template, elapsedSec])

  // Record history when current track changes
  const lastCurrentId = useRef<number | null>(null)
  useEffect(() => {
    if (!active || !player.current) return
    if (lastCurrentId.current === player.current.id) return
    lastCurrentId.current = player.current.id
    setHistory((h) => [
      ...h,
      {
        trackId: player.current!.id,
        artistIds: [], // resolved by picker via Supabase
        mood: player.current!.mood ?? null,
        lufs: null,
        playedAtSec: elapsedSec,
      },
    ])
  }, [active, player.current, elapsedSec])

  // Refresh upcoming periodically (every 30s) when active
  useEffect(() => {
    if (!active || !template || !player.current) {
      setUpcoming([])
      return
    }
    let cancelled = false
    const doPick = async () => {
      if (pickInFlight.current) return
      pickInFlight.current = true
      try {
        const picks = await pickNextSetTrack({
          currentTrackId: player.current!.id,
          template,
          elapsedSec,
          totalDurationSec: template.durationMin * 60,
          history,
          varietyTier,
        })
        if (!cancelled) setUpcoming(picks)
      } finally {
        pickInFlight.current = false
      }
    }
    void doPick()
    const id = window.setInterval(() => void doPick(), 30_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [active, template, player.current, elapsedSec, history, varietyTier])

  const startTemplate = useCallback(
    (templateName: string) => {
      const tpl = templates.find((t) => t.name === templateName)
      if (!tpl) return
      setTemplate(tpl)
      setActive(true)
      setStartedAtSec(Math.floor(Date.now() / 1000))
      setElapsedSec(0)
      setHistory([])
    },
    [templates],
  )

  const stopSet = useCallback(() => {
    setActive(false)
    setTemplate(null)
    setElapsedSec(0)
    setHistory([])
    setUpcoming([])
  }, [])

  const skipSlot = useCallback(() => {
    // Advance elapsedSec to the start of the next slot.
    if (!template || !currentSlot) return
    const nextSlotIdx = currentSlot.index + 1
    const next = template.slots[nextSlotIdx]
    if (next) {
      setElapsedSec(Math.ceil(next.position * template.durationMin * 60))
    }
  }, [template, currentSlot])

  const rebuildRemainder = useCallback(async () => {
    if (!active || !template || !player.current) return
    const picks = await pickNextSetTrack({
      currentTrackId: player.current.id,
      template,
      elapsedSec,
      totalDurationSec: template.durationMin * 60,
      history,
      varietyTier,
    })
    setUpcoming(picks)
  }, [active, template, player.current, elapsedSec, history, varietyTier])

  const overridePick = useCallback(
    (track: PlayerTrackMeta) => {
      player.play(track)
    },
    [player],
  )

  const api = useMemo<SetSessionApi>(
    () => ({
      active,
      template,
      startedAtSec,
      elapsedSec,
      currentSlot,
      history,
      upcoming,
      varietyTier,
      relaxationEvents,
      templates,
      startTemplate,
      stopSet,
      skipSlot,
      rebuildRemainder,
      overridePick,
    }),
    [
      active,
      template,
      startedAtSec,
      elapsedSec,
      currentSlot,
      history,
      upcoming,
      varietyTier,
      relaxationEvents,
      templates,
      startTemplate,
      stopSet,
      skipSlot,
      rebuildRemainder,
      overridePick,
    ],
  )

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>
}
