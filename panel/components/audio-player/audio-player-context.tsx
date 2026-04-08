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

import { fetchTrackMixMeta } from '@/actions/mix-meta-actions'
import {
  getTransitionStyle,
  scoreTransitionCandidates,
  type TransitionStyle,
} from '@/actions/transition-actions'
import type { TrackMixMeta } from '@/lib/queries/mix-meta'

export interface PlayerTrackMeta {
  id: number
  title: string
  artists?: string | null
  durationMs?: number | null
  bpm?: number | null
  camelot?: string | null
  mood?: string | null
}

// ── Auto-DJ scoring (client-side compatibility heuristic) ─────────

function parseCamelot(c?: string | null): { num: number; letter: 'A' | 'B' } | null {
  if (!c) return null
  const m = /^(\d{1,2})([AB])$/i.exec(c.trim())
  if (!m) return null
  const num = Number.parseInt(m[1], 10)
  if (!Number.isFinite(num) || num < 1 || num > 12) return null
  return { num, letter: m[2].toUpperCase() as 'A' | 'B' }
}

function camelotDistance(a?: string | null, b?: string | null): number | null {
  const pa = parseCamelot(a)
  const pb = parseCamelot(b)
  if (!pa || !pb) return null
  const numDiff = Math.min(Math.abs(pa.num - pb.num), 12 - Math.abs(pa.num - pb.num))
  const letterPenalty = pa.letter === pb.letter ? 0 : 0.5
  return numDiff + letterPenalty
}

function compatibilityScore(a: PlayerTrackMeta, b: PlayerTrackMeta): number {
  let bpmScore = 0.5
  if (a.bpm != null && b.bpm != null) {
    let diff = Math.abs(a.bpm - b.bpm)
    diff = Math.min(diff, Math.abs(a.bpm - b.bpm * 2), Math.abs(a.bpm - b.bpm / 2))
    bpmScore = Math.exp(-(diff * diff) / (2 * 4 * 4))
  }
  let harmonic = 0.5
  const cd = camelotDistance(a.camelot, b.camelot)
  if (cd !== null) harmonic = Math.max(0, 1 - cd / 4)
  const mood = a.mood && b.mood && a.mood === b.mood ? 1 : 0.5
  return bpmScore * 0.6 + harmonic * 0.3 + mood * 0.1
}

function pickAutoNext(
  current: PlayerTrackMeta,
  candidates: PlayerTrackMeta[],
  history: number[],
): PlayerTrackMeta | null {
  const recent = new Set(history.slice(-30))
  const scored = candidates
    .filter((t) => t.id !== current.id && !recent.has(t.id))
    .map((t) => ({ track: t, score: compatibilityScore(current, t) }))
    .filter((c) => c.score > 0.05)
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)

  if (scored.length === 0) return null
  const total = scored.reduce((acc, c) => acc + c.score, 0)
  let r = Math.random() * total
  for (const c of scored) {
    r -= c.score
    if (r <= 0) return c.track
  }
  return scored[0]?.track ?? null
}

interface AudioPlayerState {
  current: PlayerTrackMeta | null
  queue: PlayerTrackMeta[]
  queueIndex: number
  hasNext: boolean
  hasPrev: boolean
  isPlaying: boolean
  isLoading: boolean
  position: number // seconds
  duration: number // seconds
  volume: number // 0..1
  muted: boolean
  error: string | null
  autoDj: boolean
}

interface AudioPlayerApi extends AudioPlayerState {
  play: (track: PlayerTrackMeta, queue?: PlayerTrackMeta[]) => void
  toggle: (track?: PlayerTrackMeta, queue?: PlayerTrackMeta[]) => void
  pause: () => void
  stop: () => void
  next: () => void
  prev: () => void
  seek: (seconds: number) => void
  setVolume: (vol: number) => void
  toggleMute: () => void
  toggleAutoDj: () => void
  mixEnabled: boolean // master toggle for crossfade mixing — when false transitions snap
  toggleMixEnabled: () => void
  crossfadeBars: number // length of mix in BARS (DJ-native unit)
  setCrossfadeBars: (b: number) => void
  crossfadeSeconds: number // derived from bars + current BPM (read-only)
  isCrossfading: boolean
  // During an active crossfade these mirror the OUTGOING track + the
  // moment the fade was initiated (`AudioContext.currentTime` seconds).
  // Both clear back to null in the fadeTimeout finalizer. Used by the
  // <TransitionVisualizer> overlay to drive its progress bar and to
  // render the "from → to" pair of waveforms.
  outgoing: PlayerTrackMeta | null
  crossfadeStartedAt: number | null
  crossfadeDurationSeconds: number | null
  // Per-deck position snapshots taken at the moment the fade was
  // armed. Visualizer interpolates them with the wall-clock progress
  // and the matching playbackRate to show real playhead positions on
  // both tracks during the overlap. Both null outside an active fade.
  outgoingFadeStartPosition: number | null
  incomingFadeStartPosition: number | null
  outgoingFadePlaybackRate: number | null
  incomingFadePlaybackRate: number | null
  // Backend-recommended style for the active fade. Resolved
  // asynchronously after the crossfade starts (no audio blocking).
  // Visualizer reads these to surface "what the algorithm suggested".
  recommendedStyle: TransitionStyle | null
  recommendedBars: number | null
}

interface Deck {
  audio: HTMLAudioElement
  source: MediaElementAudioSourceNode
  // Signal chain: source → low (lowshelf) → mid (peaking) → high (highshelf) → gain → out
  low: BiquadFilterNode
  mid: BiquadFilterNode
  high: BiquadFilterNode
  gain: GainNode
}

const AudioPlayerContext = createContext<AudioPlayerApi | null>(null)

export function useAudioPlayer(): AudioPlayerApi {
  const ctx = useContext(AudioPlayerContext)
  if (!ctx) throw new Error('useAudioPlayer must be used inside AudioPlayerProvider')
  return ctx
}

export function AudioPlayerProvider({ children }: { children: React.ReactNode }) {
  const ctxRef = useRef<AudioContext | null>(null)
  const deckARef = useRef<Deck | null>(null)
  const deckBRef = useRef<Deck | null>(null)
  const activeDeckRef = useRef<'A' | 'B'>('A')
  const fadingRef = useRef(false)
  const fadeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [current, setCurrent] = useState<PlayerTrackMeta | null>(null)
  const [queue, setQueue] = useState<PlayerTrackMeta[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isCrossfading, setIsCrossfading] = useState(false)
  const [outgoing, setOutgoing] = useState<PlayerTrackMeta | null>(null)
  const [crossfadeStartedAt, setCrossfadeStartedAt] = useState<number | null>(null)
  const [crossfadeDurationSeconds, setCrossfadeDurationSeconds] = useState<number | null>(null)
  const [outgoingFadeStartPosition, setOutgoingFadeStartPosition] = useState<number | null>(
    null,
  )
  const [incomingFadeStartPosition, setIncomingFadeStartPosition] = useState<number | null>(
    null,
  )
  const [outgoingFadePlaybackRate, setOutgoingFadePlaybackRate] = useState<number | null>(
    null,
  )
  const [incomingFadePlaybackRate, setIncomingFadePlaybackRate] = useState<number | null>(
    null,
  )
  const [recommendedStyle, setRecommendedStyle] = useState<TransitionStyle | null>(null)
  const [recommendedBars, setRecommendedBars] = useState<number | null>(null)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(0.85)
  const [muted, setMuted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoDj, setAutoDj] = useState(false)
  // Master mix switch — default ON. When false, every transition snaps
  // instantly (useful for preview-style listening).
  const [mixEnabled, setMixEnabled] = useState(true)
  // Default 32 bars — long, smooth, professional DJ-style mix.
  // 32 bars at 124 BPM = 32*4/124*60 ≈ 62 seconds.
  const [crossfadeBars, setCrossfadeBars] = useState(32)
  const historyRef = useRef<number[]>([])

  // Compute crossfade duration in seconds from bars + active track BPM.
  // 1 bar = 4 beats; (bars * 4) beats / (bpm) bpm * 60 = seconds.
  const computeCrossfadeSeconds = useCallback(
    (bars: number, bpm: number | null | undefined): number => {
      const effectiveBpm = bpm && bpm > 60 ? bpm : 124
      return (bars * 4 * 60) / effectiveBpm
    },
    [],
  )

  // For UI display: derived from bars and the current track's BPM.
  const crossfadeSeconds = computeCrossfadeSeconds(
    crossfadeBars,
    current?.bpm,
  )

  // Refs for fresh values inside event listeners (which capture closures).
  const volumeRef = useRef(volume)
  useEffect(() => { volumeRef.current = volume }, [volume])

  const getActiveDeck = useCallback((): Deck | null => {
    return activeDeckRef.current === 'A' ? deckARef.current : deckBRef.current
  }, [])
  const getInactiveDeck = useCallback((): Deck | null => {
    return activeDeckRef.current === 'A' ? deckBRef.current : deckARef.current
  }, [])

  // Lazily build the AudioContext + two decks on first interaction.
  const ensureContext = useCallback((): { ctx: AudioContext; A: Deck; B: Deck } | null => {
    if (ctxRef.current && deckARef.current && deckBRef.current) {
      return { ctx: ctxRef.current, A: deckARef.current, B: deckBRef.current }
    }
    if (typeof window === 'undefined') return null
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!Ctx) return null
    const ctx = new Ctx()

    const buildDeck = (id: 'A' | 'B'): Deck => {
      const audio = new Audio()
      audio.preload = 'auto'
      audio.crossOrigin = 'anonymous'
      const source = ctx.createMediaElementSource(audio)

      // 3-band EQ chain (lowshelf @ 250 Hz, peaking @ 1 kHz, highshelf @ 4 kHz).
      const low = ctx.createBiquadFilter()
      low.type = 'lowshelf'
      low.frequency.value = 250
      low.gain.value = 0
      const mid = ctx.createBiquadFilter()
      mid.type = 'peaking'
      mid.frequency.value = 1000
      mid.Q.value = 1
      mid.gain.value = 0
      const high = ctx.createBiquadFilter()
      high.type = 'highshelf'
      high.frequency.value = 4000
      high.gain.value = 0

      const gain = ctx.createGain()
      gain.gain.value = 0
      source.connect(low).connect(mid).connect(high).connect(gain).connect(ctx.destination)

      audio.addEventListener('play', () => {
        if (activeDeckRef.current === id) setIsPlaying(true)
      })
      audio.addEventListener('pause', () => {
        if (activeDeckRef.current === id && !fadingRef.current) setIsPlaying(false)
      })
      audio.addEventListener('waiting', () => {
        if (activeDeckRef.current === id) setIsLoading(true)
      })
      audio.addEventListener('canplay', () => {
        if (activeDeckRef.current === id) setIsLoading(false)
      })
      audio.addEventListener('playing', () => {
        if (activeDeckRef.current === id) setIsLoading(false)
      })
      audio.addEventListener('loadedmetadata', () => {
        if (activeDeckRef.current === id) setDuration(audio.duration || 0)
      })
      audio.addEventListener('durationchange', () => {
        if (activeDeckRef.current === id) setDuration(audio.duration || 0)
      })
      audio.addEventListener('timeupdate', () => {
        if (activeDeckRef.current === id) setPosition(audio.currentTime || 0)
      })
      audio.addEventListener('ended', () => {
        if (activeDeckRef.current === id && !fadingRef.current) {
          setIsPlaying(false)
          setPosition(0)
          window.dispatchEvent(new CustomEvent('audio-player:ended'))
        }
      })
      audio.addEventListener('error', () => {
        if (activeDeckRef.current === id) {
          setError('Не удалось загрузить трек')
          setIsLoading(false)
          setIsPlaying(false)
        }
      })

      return { audio, source, low, mid, high, gain }
    }

    const A = buildDeck('A')
    const B = buildDeck('B')
    A.gain.gain.value = volume

    ctxRef.current = ctx
    deckARef.current = A
    deckBRef.current = B
    return { ctx, A, B }
  }, [volume])

  // Mix metadata cache: sections + bpm so we can plan transitions
  // around outro/intro and match tempos.
  const metaCacheRef = useRef<Map<number, TrackMixMeta>>(new Map())
  const currentMetaRef = useRef<TrackMixMeta | null>(null)
  // In-flight fetch dedup. Without this, two concurrent loadMixMeta
  // calls for the same track id (e.g. snap-load → immediately
  // crossfade) trigger two HTTP fetches because the cache is still
  // empty. The promise map collapses them into one.
  const metaInFlightRef = useRef<Map<number, Promise<TrackMixMeta | null>>>(new Map())

  const loadMixMeta = useCallback(async (id: number): Promise<TrackMixMeta | null> => {
    const cached = metaCacheRef.current.get(id)
    if (cached) return cached
    const inFlight = metaInFlightRef.current.get(id)
    if (inFlight) return inFlight
    const promise = fetchTrackMixMeta(id)
      .then((m) => {
        if (m) metaCacheRef.current.set(id, m)
        return m
      })
      .catch(() => null)
      .finally(() => {
        metaInFlightRef.current.delete(id)
      })
    metaInFlightRef.current.set(id, promise)
    return promise
  }, [])

  // ── DJ-style crossfade ─────────────────────────────────────────
  // Builds on:
  //  - Web Audio bass swap (lowshelf gain ramp on both decks)
  //  - playbackRate tempo match (≤ 8% delta to keep pitch sane)
  //  - Section anchoring: incoming track starts at its INTRO end so the
  //    "drop" of the new track lands when the outgoing track's outro is
  //    finishing. Without intro data we just play from 0.
  //  - linearRampToValueAtTime gain swap over `crossfadeSeconds`
  const startCrossfade = useCallback(
    (track: PlayerTrackMeta) => {
      const env = ensureContext()
      if (!env) return
      const { ctx } = env
      const active = getActiveDeck()
      const inactive = getInactiveDeck()
      if (!active || !inactive) return

      if (ctx.state === 'suspended') ctx.resume().catch(() => undefined)

      if (fadeTimeoutRef.current) clearTimeout(fadeTimeoutRef.current)
      fadingRef.current = true
      setIsCrossfading(true)
      // Snapshot the OUTGOING track BEFORE we mutate `current`. The
      // <TransitionVisualizer> needs both endpoints of the fade.
      setOutgoing(current)
      setRecommendedStyle(null)
      setRecommendedBars(null)
      setError(null)

      // Async style recommendation — runs in parallel with audio
      // loading. We later `await` it inside the play().then() block so
      // the recommended bar count actually drives the fade duration.
      // Tracked as a promise so the .then() chain can resolve it
      // exactly once without leaking pending fetches.
      const fromId = current?.id
      const stylePromise: Promise<Awaited<ReturnType<typeof getTransitionStyle>>> =
        fromId !== undefined ? getTransitionStyle(fromId, track.id) : Promise.resolve(null)
      void stylePromise.then((res) => {
        if (!res) return
        setRecommendedStyle(res.recommendedStyle)
        setRecommendedBars(res.recommendedBars)
      })

      const url = `/api/audio/${track.id}`
      inactive.audio.src = url
      inactive.audio.preservesPitch = false // we want true playback-rate behaviour
      // Reset any leftover playbackRate from a previous transition —
      // otherwise a chain of mixes compounds tempo-match ratios.
      try {
        inactive.audio.playbackRate = 1
      } catch {
        // ignore
      }
      inactive.gain.gain.cancelScheduledValues(ctx.currentTime)
      inactive.gain.gain.setValueAtTime(0, ctx.currentTime)

      setCurrent(track)
      historyRef.current = [...historyRef.current, track.id].slice(-50)
      setIsPlaying(true)

      // Kick off meta fetch in parallel with audio load. We consume it
      // inside the play().then() block below where we know the final
      // crossfade length and can align the seek correctly.
      const incomingMetaPromise = loadMixMeta(track.id)

      inactive.audio
        .play()
        .then(async () => {
          // Wait for the backend's style recommendation + incoming meta.
          // Worst case they arrived ~100-300ms ago and resolve instantly;
          // in the cold path we add up to ~300ms of pre-roll (silent —
          // `inactive` gain is at 0). The fade hasn't started yet, so
          // this is imperceptible.
          const [styleResult, incomingMeta] = await Promise.all([
            stylePromise,
            incomingMetaPromise,
          ])

          const t0 = ctx.currentTime
          // Use the OUTGOING track's BPM (already known from current.bpm /
          // currentMetaRef) to convert bars→seconds. This locks the mix
          // duration to musical time, not wall-clock time.
          const outgoingBpm =
            currentMetaRef.current?.bpm ?? current?.bpm ?? track.bpm ?? null

          // Pick the bar count: if the backend recommended a non-zero
          // value, use it; CUT (0 bars) collapses to a 2s minimum so
          // setValueCurveAtTime stays valid (proper snap-cut handling
          // is a separate PR — see TRANSITION_STYLE_PROFILES). Without
          // a recommendation we fall back to the user's slider.
          const recBars = styleResult?.recommendedBars
          const effectiveBars =
            typeof recBars === 'number' && recBars > 0 ? recBars : crossfadeBars

          let cf = Math.max(2, computeCrossfadeSeconds(effectiveBars, outgoingBpm))

          // ── DJ-correct mix-point alignment ─────────────────────
          // Classic 32-bar bass swap (Vande Veire & De Bie JASMP 2018,
          // Pioneer DJ DJ.Studio reference):
          //   t=0      outgoing enters OUTRO (drums only, melody gone)
          //            incoming plays INTRO (drums only, no bass/melody)
          //   t=mid    bass swap midpoint; equal-power crossfade at 50%
          //   t=cf     outgoing silent; incoming reaches its DROP exactly
          //
          // The previous implementation seeked the incoming to `introEnd`
          // (the drop) at t=0, which meant the drop hit way before the
          // crossfade finished. We instead start the incoming deep enough
          // into its intro that after `cf` seconds of playback it lands
          // exactly on the drop:
          //   seekTarget = max(introStart, introEnd - cf)
          // When the intro is SHORTER than the requested fade we shrink
          // the fade to match, so the drop still lands at fade end.
          // Outgoing-track guard: never schedule a fade longer than the
          // remaining audio on the active deck. Without this, calling
          // mixNow() near end-of-track means setValueCurveAtTime
          // outlives the actual sample data and the fade keeps running
          // over silence.
          if (active.audio.duration && active.audio.currentTime >= 0) {
            const outgoingRemaining = active.audio.duration - active.audio.currentTime
            if (outgoingRemaining > 1) {
              cf = Math.max(2, Math.min(cf, outgoingRemaining))
            }
          }

          if (
            incomingMeta?.introEndSec != null &&
            incomingMeta.introEndSec > 0 &&
            incomingMeta.introEndSec < 120
          ) {
            const introEnd = incomingMeta.introEndSec
            const introStart = Math.max(0, incomingMeta.introStartSec ?? 0)
            const introLen = Math.max(0, introEnd - introStart)
            if (introLen > 1) {
              cf = Math.max(2, Math.min(cf, introLen))
            }
            const seekTarget = Math.max(introStart, introEnd - cf)
            try {
              inactive.audio.currentTime = seekTarget
            } catch {
              // ignore — currentTime not yet writable
            }
          }

          // Tempo match against the active deck's track if BPMs are
          // within 8%. Applied AFTER the seek so it doesn't interfere
          // with currentTime.
          const activeMeta = currentMetaRef.current
          if (incomingMeta?.bpm && activeMeta?.bpm) {
            const ratio = activeMeta.bpm / incomingMeta.bpm
            if (ratio >= 0.92 && ratio <= 1.08) {
              try {
                inactive.audio.playbackRate = ratio
              } catch {
                // ignore
              }
            }
          }
          if (incomingMeta) currentMetaRef.current = incomingMeta
          const t1 = t0 + cf
          const tMid = t0 + cf / 2
          const vol = volumeRef.current

          // Publish fade timing for the visualizer overlay (AudioContext
          // currentTime, not wall clock — same units the engine uses).
          setCrossfadeStartedAt(t0)
          setCrossfadeDurationSeconds(cf)
          // Snapshot per-deck playhead positions and the playback rates
          // they're locked into. Visualizer extrapolates real positions
          // = startPos + progress*cf*rate, so it can drive both
          // waveforms with the actual sample positions instead of 0.
          setOutgoingFadeStartPosition(active.audio.currentTime || 0)
          setIncomingFadeStartPosition(inactive.audio.currentTime || 0)
          setOutgoingFadePlaybackRate(active.audio.playbackRate || 1)
          setIncomingFadePlaybackRate(inactive.audio.playbackRate || 1)

          // Equal-power crossfade — `cos(t·π/2)` for the outgoing deck and
          // `sin(t·π/2)` for the incoming deck. Linear ramps drop the
          // perceived loudness by ~3 dB at the midpoint; equal-power keeps
          // total power constant across the fade. We sample 64 points;
          // setValueCurveAtTime interpolates linearly between samples,
          // which is more than enough for a fade lasting seconds.
          const N = 64
          const fadeOut = new Float32Array(N)
          const fadeIn = new Float32Array(N)
          for (let i = 0; i < N; i++) {
            const x = i / (N - 1)
            fadeOut[i] = Math.cos((x * Math.PI) / 2) * vol
            fadeIn[i] = Math.sin((x * Math.PI) / 2) * vol
          }
          active.gain.gain.cancelScheduledValues(t0)
          active.gain.gain.setValueAtTime(active.gain.gain.value, t0)
          active.gain.gain.setValueCurveAtTime(fadeOut, t0, cf)
          inactive.gain.gain.cancelScheduledValues(t0)
          inactive.gain.gain.setValueAtTime(0, t0)
          inactive.gain.gain.setValueCurveAtTime(fadeIn, t0, cf)

          // Bass swap — keep low end clean during the overlap.
          // Active: 0 dB → -40 dB by midpoint, hold.
          // Inactive: starts at -40 dB, climbs to 0 dB by midpoint.
          active.low.gain.cancelScheduledValues(t0)
          active.low.gain.setValueAtTime(active.low.gain.value || 0, t0)
          active.low.gain.linearRampToValueAtTime(-40, tMid)

          inactive.low.gain.cancelScheduledValues(t0)
          inactive.low.gain.setValueAtTime(-40, t0)
          inactive.low.gain.linearRampToValueAtTime(0, tMid)

          fadeTimeoutRef.current = setTimeout(() => {
            // Reset filters on the freed deck so it's neutral next time.
            try {
              active.audio.pause()
              active.audio.removeAttribute('src')
              active.audio.load()
            } catch {
              // ignore
            }
            active.gain.gain.cancelScheduledValues(ctx.currentTime)
            active.gain.gain.setValueAtTime(0, ctx.currentTime)
            active.low.gain.cancelScheduledValues(ctx.currentTime)
            active.low.gain.setValueAtTime(0, ctx.currentTime)
            // Inactive becomes the new active.
            activeDeckRef.current = activeDeckRef.current === 'A' ? 'B' : 'A'
            fadingRef.current = false
            setIsCrossfading(false)
            setOutgoing(null)
            setCrossfadeStartedAt(null)
            setCrossfadeDurationSeconds(null)
            setOutgoingFadeStartPosition(null)
            setIncomingFadeStartPosition(null)
            setOutgoingFadePlaybackRate(null)
            setIncomingFadePlaybackRate(null)
            const newActive = getActiveDeck()
            if (newActive) {
              setPosition(newActive.audio.currentTime || 0)
              setDuration(newActive.audio.duration || 0)
              // Continuous-mix tempo bookkeeping: the just-faded-in deck
              // may be running at a non-1.0 playbackRate from the
              // previous transition's tempo match. Don't reset the
              // rate (would cause an audible speed bump), but patch
              // currentMetaRef.bpm to the *effective* BPM so the NEXT
              // crossfade computes its tempo-match ratio against
              // reality, not the file's tagged BPM. Without this,
              // chained mixes compound speed ratios.
              const settledRate = newActive.audio.playbackRate
              if (
                currentMetaRef.current?.bpm &&
                Math.abs(settledRate - 1) > 0.001
              ) {
                currentMetaRef.current = {
                  ...currentMetaRef.current,
                  bpm: currentMetaRef.current.bpm * settledRate,
                }
              }
            }
          }, cf * 1000 + 50)
        })
        .catch((err: DOMException) => {
          fadingRef.current = false
          setIsCrossfading(false)
          if (err?.name !== 'AbortError') {
            setError(err?.message ?? 'playback failed')
          }
        })
    },
    [
      ensureContext,
      getActiveDeck,
      getInactiveDeck,
      crossfadeBars,
      current,
      computeCrossfadeSeconds,
      loadMixMeta,
    ],
  )

  const play = useCallback(
    (track: PlayerTrackMeta, nextQueue?: PlayerTrackMeta[]) => {
      const env = ensureContext()
      if (!env) return
      const { ctx } = env

      if (nextQueue && nextQueue.length > 0) {
        setQueue(nextQueue)
      } else if (queue.length === 0) {
        setQueue([track])
      }

      const active = getActiveDeck()
      // Crossfade only if there's already a real track playing AND the
      // master mix toggle is on. Otherwise we snap to the new track.
      if (
        mixEnabled &&
        current &&
        active &&
        !active.audio.paused &&
        active.audio.currentTime > 0.1
      ) {
        startCrossfade(track)
        return
      }

      // Fresh start (or paused current) → snap-load on the active deck.
      if (!active) return
      if (fadeTimeoutRef.current) clearTimeout(fadeTimeoutRef.current)
      fadingRef.current = false
      setIsCrossfading(false)
      setOutgoing(null)
      setCrossfadeStartedAt(null)
      setCrossfadeDurationSeconds(null)
      setOutgoingFadeStartPosition(null)
      setIncomingFadeStartPosition(null)
      setOutgoingFadePlaybackRate(null)
      setIncomingFadePlaybackRate(null)
      setRecommendedStyle(null)
      setRecommendedBars(null)
      setError(null)
      setCurrent(track)
      historyRef.current = [...historyRef.current, track.id].slice(-50)
      const url = `/api/audio/${track.id}`
      if (!active.audio.src.endsWith(url)) {
        active.audio.src = url
      }
      active.audio.playbackRate = 1
      active.gain.gain.cancelScheduledValues(ctx.currentTime)
      active.gain.gain.setValueAtTime(volumeRef.current, ctx.currentTime)
      // Reset EQ filters to neutral.
      for (const f of [active.low, active.mid, active.high]) {
        f.gain.cancelScheduledValues(ctx.currentTime)
        f.gain.setValueAtTime(0, ctx.currentTime)
      }
      // Silence the inactive deck just in case.
      const inactive = getInactiveDeck()
      if (inactive) {
        inactive.gain.gain.cancelScheduledValues(ctx.currentTime)
        inactive.gain.gain.setValueAtTime(0, ctx.currentTime)
      }
      // Async load mix metadata for upcoming transitions.
      void loadMixMeta(track.id).then((m) => {
        currentMetaRef.current = m
      })
      setPosition(0)
      setDuration(0)
      if (ctx.state === 'suspended') ctx.resume().catch(() => undefined)
      active.audio.play().catch((err: DOMException) => {
        if (err?.name !== 'AbortError') {
          setError(err?.message ?? 'playback failed')
          setIsPlaying(false)
        }
      })
    },
    [
      ensureContext,
      getActiveDeck,
      getInactiveDeck,
      queue.length,
      current,
      startCrossfade,
      loadMixMeta,
      mixEnabled,
    ],
  )

  const pause = useCallback(() => {
    const a = getActiveDeck()
    if (!a) return
    a.audio.pause()
  }, [getActiveDeck])

  const stop = useCallback(() => {
    if (fadeTimeoutRef.current) clearTimeout(fadeTimeoutRef.current)
    fadingRef.current = false
    setIsCrossfading(false)
    for (const d of [deckARef.current, deckBRef.current]) {
      if (!d) continue
      try {
        d.audio.pause()
        d.audio.removeAttribute('src')
        d.audio.load()
      } catch {
        // ignore
      }
      if (ctxRef.current) {
        d.gain.gain.cancelScheduledValues(ctxRef.current.currentTime)
        d.gain.gain.setValueAtTime(0, ctxRef.current.currentTime)
      }
    }
    setCurrent(null)
    setPosition(0)
    setDuration(0)
    setIsPlaying(false)
  }, [])

  const toggle = useCallback(
    (track?: PlayerTrackMeta, nextQueue?: PlayerTrackMeta[]) => {
      if (track && (!current || current.id !== track.id)) {
        play(track, nextQueue)
        return
      }
      const a = getActiveDeck()
      if (!a || !current) return
      if (a.audio.paused) {
        if (ctxRef.current?.state === 'suspended') ctxRef.current.resume().catch(() => undefined)
        a.audio.play().catch(() => undefined)
      } else {
        a.audio.pause()
      }
    },
    [current, play, getActiveDeck],
  )

  const queueIndex = current ? queue.findIndex((t) => t.id === current.id) : -1
  const hasPrev = queueIndex > 0
  const hasNext = queueIndex >= 0 && queueIndex < queue.length - 1

  const next = useCallback(() => {
    if (!current) return
    const idx = queue.findIndex((t) => t.id === current.id)
    if (idx >= 0 && idx < queue.length - 1) {
      play(queue[idx + 1])
    }
  }, [current, queue, play])

  const prev = useCallback(() => {
    if (!current) return
    const a = getActiveDeck()
    if (a && a.audio.currentTime > 3) {
      a.audio.currentTime = 0
      setPosition(0)
      return
    }
    const idx = queue.findIndex((t) => t.id === current.id)
    if (idx > 0) {
      play(queue[idx - 1])
    }
  }, [current, queue, play, getActiveDeck])

  const seek = useCallback(
    (seconds: number) => {
      const a = getActiveDeck()
      if (!a) return
      a.audio.currentTime = Math.max(0, Math.min(seconds, a.audio.duration || seconds))
      setPosition(a.audio.currentTime)
    },
    [getActiveDeck],
  )

  const setVolume = useCallback((vol: number) => {
    const clamped = Math.max(0, Math.min(1, vol))
    setVolumeState(clamped)
    const ctx = ctxRef.current
    const a = activeDeckRef.current === 'A' ? deckARef.current : deckBRef.current
    if (ctx && a && !fadingRef.current) {
      a.gain.gain.cancelScheduledValues(ctx.currentTime)
      a.gain.gain.setValueAtTime(clamped, ctx.currentTime)
    }
    setMuted(false)
  }, [])

  const toggleMute = useCallback(() => {
    setMuted((m) => {
      const next = !m
      const ctx = ctxRef.current
      const a = activeDeckRef.current === 'A' ? deckARef.current : deckBRef.current
      if (ctx && a && !fadingRef.current) {
        a.gain.gain.cancelScheduledValues(ctx.currentTime)
        a.gain.gain.setValueAtTime(next ? 0 : volumeRef.current, ctx.currentTime)
      }
      return next
    })
  }, [])

  // Tear down on unmount
  useEffect(() => {
    return () => {
      if (fadeTimeoutRef.current) clearTimeout(fadeTimeoutRef.current)
      for (const d of [deckARef.current, deckBRef.current]) {
        if (!d) continue
        try {
          d.audio.pause()
          d.audio.removeAttribute('src')
          d.audio.load()
        } catch {
          // ignore
        }
      }
      ctxRef.current?.close().catch(() => undefined)
    }
  }, [])

  // Async picker that prefers the backend's TransitionScorer (real
  // 6-component scoring with hard rejects, MFCC similarity, chroma-
  // weighted Camelot) over the lightweight client heuristic.
  const pickNextTrackAsync = useCallback(
    async (
      currentTrack: PlayerTrackMeta,
      poolTracks: PlayerTrackMeta[],
      history: number[],
    ): Promise<PlayerTrackMeta | null> => {
      try {
        const scored = await scoreTransitionCandidates(currentTrack.id, 30)
        if (scored && scored.length > 0) {
          const poolIds = new Set(poolTracks.map((t) => t.id))
          const recent = new Set(history.slice(-30))
          const matches = scored
            .filter(
              (c) =>
                poolIds.has(c.to_track_id) &&
                !recent.has(c.to_track_id) &&
                c.overall_quality > 0,
            )
            .slice(0, 8)
          if (matches.length > 0) {
            const total = matches.reduce((acc, c) => acc + c.overall_quality, 0)
            let r = Math.random() * total
            for (const c of matches) {
              r -= c.overall_quality
              if (r <= 0) {
                return poolTracks.find((t) => t.id === c.to_track_id) ?? null
              }
            }
            return poolTracks.find((t) => t.id === matches[0].to_track_id) ?? null
          }
        }
      } catch {
        // network / scoring failure → fall through
      }
      // Fallback: client-side BPM/Camelot heuristic.
      return pickAutoNext(currentTrack, poolTracks, history)
    },
    [],
  )

  // Pre-emptive auto-DJ crossfade: prefer OUTRO section start as the
  // trigger so we mix during the outgoing track's designed mix-out zone.
  // Picker is async so we guard with a ref to avoid duplicate fires.
  const autoDjPickInFlight = useRef(false)
  useEffect(() => {
    if (!autoDj || fadingRef.current || autoDjPickInFlight.current || !current) return
    if (!duration) return
    const cfSec = computeCrossfadeSeconds(crossfadeBars, current.bpm)
    if (duration < cfSec * 1.5) return
    const meta = currentMetaRef.current
    // Latest we can safely start the fade so it finishes before the
    // outgoing track runs out of audio.
    const latestSafe = Math.max(0, duration - cfSec)
    const sectionTrigger =
      meta && meta.outroStartSec && meta.outroStartSec > 0
        ? Math.min(meta.outroStartSec, latestSafe)
        : latestSafe
    if (position >= sectionTrigger) {
      autoDjPickInFlight.current = true
      void pickNextTrackAsync(current, queue, historyRef.current)
        .then((nextTrack) => {
          if (nextTrack && !fadingRef.current) startCrossfade(nextTrack)
        })
        .finally(() => {
          // Release after a short delay so we don't refire mid-fade.
          setTimeout(() => {
            autoDjPickInFlight.current = false
          }, 2000)
        })
    }
  }, [
    position,
    duration,
    autoDj,
    current,
    queue,
    crossfadeBars,
    startCrossfade,
    pickNextTrackAsync,
    computeCrossfadeSeconds,
  ])

  // Auto-advance when current track finishes:
  // - autoDj on  → pick the most compatible (with weighted randomness)
  //                from the queue, avoiding recently played
  // - autoDj off → simply walk to the next item in the queue
  useEffect(() => {
    const handler = () => {
      if (autoDj && current) {
        const nextTrack = pickAutoNext(current, queue, historyRef.current)
        if (nextTrack) {
          play(nextTrack)
          return
        }
      }
      if (hasNext) next()
    }
    window.addEventListener('audio-player:ended', handler)
    return () => window.removeEventListener('audio-player:ended', handler)
  }, [autoDj, current, queue, hasNext, next, play])

  const toggleAutoDj = useCallback(() => setAutoDj((a) => !a), [])
  const toggleMixEnabled = useCallback(() => setMixEnabled((m) => !m), [])

  // ── Media Session API ────────────────────────────────────────────
  // Wires hardware media keys (Mac Touch Bar / F7-F9, headphone buttons,
  // bluetooth remotes, lockscreen controls, system Now Playing) to the
  // player so the OS can drive playback without focusing the browser.
  useEffect(() => {
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
    if (!current) {
      navigator.mediaSession.metadata = null
      navigator.mediaSession.playbackState = 'none'
      return
    }
    navigator.mediaSession.metadata = new MediaMetadata({
      title: current.title,
      artist: current.artists ?? '',
      album: current.mood ?? 'DJ Music Library',
    })
    navigator.mediaSession.playbackState = isPlaying ? 'playing' : 'paused'
  }, [current, isPlaying])

  useEffect(() => {
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
    const ms = navigator.mediaSession

    const safeSet = (
      action: MediaSessionAction,
      handler: MediaSessionActionHandler | null,
    ) => {
      try {
        ms.setActionHandler(action, handler)
      } catch {
        // Browser doesn't support this action — ignore.
      }
    }

    const getActive = () =>
      activeDeckRef.current === 'A' ? deckARef.current : deckBRef.current

    safeSet('play', () => {
      const d = getActive()
      if (d && d.audio.paused) d.audio.play().catch(() => undefined)
    })
    safeSet('pause', () => {
      const d = getActive()
      if (d && !d.audio.paused) d.audio.pause()
    })
    safeSet('previoustrack', () => prev())
    safeSet('nexttrack', () => next())
    safeSet('stop', () => stop())
    safeSet('seekto', (details) => {
      const dd = details as MediaSessionActionDetails & { seekTime?: number }
      if (typeof dd.seekTime === 'number') seek(dd.seekTime)
    })
    safeSet('seekbackward', (details) => {
      const d = getActive()
      if (!d) return
      const offset =
        (details as MediaSessionActionDetails & { seekOffset?: number }).seekOffset ?? 10
      seek(Math.max(0, d.audio.currentTime - offset))
    })
    safeSet('seekforward', (details) => {
      const d = getActive()
      if (!d) return
      const offset =
        (details as MediaSessionActionDetails & { seekOffset?: number }).seekOffset ?? 10
      seek(Math.min((d.audio.duration || d.audio.currentTime) + offset, d.audio.currentTime + offset))
    })

    return () => {
      safeSet('play', null)
      safeSet('pause', null)
      safeSet('previoustrack', null)
      safeSet('nexttrack', null)
      safeSet('stop', null)
      safeSet('seekto', null)
      safeSet('seekbackward', null)
      safeSet('seekforward', null)
    }
  }, [prev, next, stop, seek])

  // Keep the OS scrubber in sync with our playback position.
  useEffect(() => {
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
    if (!current || !duration) return
    try {
      navigator.mediaSession.setPositionState?.({
        duration,
        playbackRate: 1,
        position: Math.min(position, duration),
      })
    } catch {
      // Ignore — Safari sometimes throws on transient values.
    }
  }, [current, duration, position])

  const api = useMemo<AudioPlayerApi>(
    () => ({
      current,
      queue,
      queueIndex,
      hasPrev,
      hasNext,
      isPlaying,
      isLoading,
      position,
      duration,
      volume,
      muted,
      error,
      autoDj,
      mixEnabled,
      crossfadeBars,
      crossfadeSeconds,
      isCrossfading,
      outgoing,
      crossfadeStartedAt,
      crossfadeDurationSeconds,
      outgoingFadeStartPosition,
      incomingFadeStartPosition,
      outgoingFadePlaybackRate,
      incomingFadePlaybackRate,
      recommendedStyle,
      recommendedBars,
      play,
      toggle,
      pause,
      stop,
      next,
      prev,
      seek,
      setVolume,
      toggleMute,
      toggleAutoDj,
      toggleMixEnabled,
      setCrossfadeBars,
    }),
    [
      current,
      queue,
      queueIndex,
      hasPrev,
      hasNext,
      isPlaying,
      isLoading,
      position,
      duration,
      volume,
      muted,
      error,
      autoDj,
      mixEnabled,
      crossfadeBars,
      crossfadeSeconds,
      isCrossfading,
      outgoing,
      crossfadeStartedAt,
      crossfadeDurationSeconds,
      outgoingFadeStartPosition,
      incomingFadeStartPosition,
      outgoingFadePlaybackRate,
      incomingFadePlaybackRate,
      recommendedStyle,
      recommendedBars,
      play,
      toggle,
      pause,
      stop,
      next,
      prev,
      seek,
      setVolume,
      toggleMute,
      toggleAutoDj,
      toggleMixEnabled,
    ],
  )

  return <AudioPlayerContext.Provider value={api}>{children}</AudioPlayerContext.Provider>
}
