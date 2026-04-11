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

// `PlayerTrackMeta` and `ManualTransitionStyle` are defined in a
// separate type-only module (`./audio-player-types`) so that mixing
// them with component / hook exports in THIS file doesn't break
// Fast Refresh (which requires a component module to export *only*
// components / hooks for incremental HMR). They're imported here
// for internal use but NOT re-exported — consumers should import
// from `./audio-player-types` directly.
import type { ManualTransitionStyle, PlayerTrackMeta } from './audio-player-types'

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

// Max BPM delta per transition — techno best practice: ±3 BPM.
const MAX_BPM_DELTA = 3
// Max Camelot key distance — ≤2 = harmonic, 3+ = key clash.
const MAX_KEY_DISTANCE = 2
// Keep tempo-match inside a DJ-safe window. Outside this range the
// browser time-stretch artifacts become obvious and the mix feels fake.
const MIN_TEMPO_MATCH_RATIO = 0.92
const MAX_TEMPO_MATCH_RATIO = 1.08

// ── Energy arc: mood → energy level mapping ──────────────────────
// Techno subgenres ordered by energy (0=lowest, 1=highest).
// Auto-DJ uses set position to prefer moods matching the energy arc.
const MOOD_ENERGY: Record<string, number> = {
  ambient_dub: 0.1, dub_techno: 0.15, minimal: 0.2,
  detroit: 0.35, melodic_deep: 0.3, progressive: 0.4,
  hypnotic: 0.45, driving: 0.55, tribal: 0.5,
  breakbeat: 0.55, peak_time: 0.75, acid: 0.7,
  raw: 0.8, industrial: 0.85, hard_techno: 0.9,
}

// Energy arc curve: maps set position (0..1) → target energy (0..1).
// Classic DJ arc: warm up → build → peak at 70% → gentle release.
function targetEnergy(setPosition: number): number {
  // Parabola peaking at 0.7 of the set
  const peak = 0.7
  const x = setPosition / peak
  if (setPosition <= peak) return 0.2 + 0.7 * Math.sin((x * Math.PI) / 2)
  // Release phase
  const rel = (setPosition - peak) / (1 - peak)
  return 0.9 - 0.5 * rel
}

function compatibilityScore(
  a: PlayerTrackMeta,
  b: PlayerTrackMeta,
  tracksPlayed: number = 0,
): number {
  // Hard reject: BPM too far
  if (a.bpm != null && b.bpm != null) {
    let diff = Math.abs(a.bpm - b.bpm)
    diff = Math.min(diff, Math.abs(a.bpm - b.bpm * 2), Math.abs(a.bpm - b.bpm / 2))
    if (diff > MAX_BPM_DELTA) return 0
  }
  // Hard reject: key too far (when both keys known)
  const cd = camelotDistance(a.camelot, b.camelot)
  if (cd !== null && cd > MAX_KEY_DISTANCE) return 0

  let bpmScore = 0.5
  if (a.bpm != null && b.bpm != null) {
    let diff = Math.abs(a.bpm - b.bpm)
    diff = Math.min(diff, Math.abs(a.bpm - b.bpm * 2), Math.abs(a.bpm - b.bpm / 2))
    bpmScore = Math.exp(-(diff * diff) / (2 * 1.5 * 1.5))
  }
  const harmonic = cd !== null ? Math.max(0, 1 - cd / 4) : 0.5
  const moodMatch = a.mood && b.mood && a.mood === b.mood ? 1 : 0.5

  // Energy arc: prefer tracks whose mood energy matches the set position.
  // Assume ~15 tracks per set (90 min / 6 min avg).
  let energyScore = 0.5
  if (b.mood && tracksPlayed > 0) {
    const candidateEnergy = MOOD_ENERGY[b.mood] ?? 0.5
    const setPos = Math.min(1, tracksPlayed / 15)
    const target = targetEnergy(setPos)
    // Gaussian: closer to target = higher score
    const diff = Math.abs(candidateEnergy - target)
    energyScore = Math.exp(-(diff * diff) / (2 * 0.2 * 0.2))
  }

  return bpmScore * 0.35 + harmonic * 0.30 + energyScore * 0.20 + moodMatch * 0.15
}

function pickAutoNext(
  current: PlayerTrackMeta,
  candidates: PlayerTrackMeta[],
  history: number[],
): PlayerTrackMeta | null {
  const tracksPlayed = history.length
  const recent = new Set(history.slice(-30))
  const scored = candidates
    .filter((t) => t.id !== current.id && !recent.has(t.id))
    .map((t) => ({ track: t, score: compatibilityScore(current, t, tracksPlayed) }))
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

function normalizeTempoBpm(bpm: number | null | undefined): number | null {
  if (bpm == null || !Number.isFinite(bpm)) return null
  if (bpm < 60 || bpm > 220) return null
  return bpm
}

function resolveTempoMatchRatio(
  targetBpm: number | null | undefined,
  trackBpm: number | null | undefined,
): number {
  const normalizedTarget = normalizeTempoBpm(targetBpm)
  const normalizedTrack = normalizeTempoBpm(trackBpm)
  if (normalizedTarget == null || normalizedTrack == null) return 1
  const ratio = normalizedTarget / normalizedTrack
  return ratio >= MIN_TEMPO_MATCH_RATIO && ratio <= MAX_TEMPO_MATCH_RATIO ? ratio : 1
}

function fallbackMixMeta(track: PlayerTrackMeta): TrackMixMeta {
  return {
    trackId: track.id,
    durationMs: track.durationMs ?? null,
    bpm: normalizeTempoBpm(track.bpm),
    firstDownbeatSec: 0,
    outroStartSec: null,
    introEndSec: null,
    introStartSec: null,
    sections: [],
    integratedLufs: null,
    truePeakDb: null,
    kickProminence: null,
    hpRatio: null,
    energySub: null,
    energyLow: null,
    energyLowmid: null,
  }
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
  masterTempoBpm: number | null
  play: (track: PlayerTrackMeta, queue?: PlayerTrackMeta[]) => void
  toggle: (track?: PlayerTrackMeta, queue?: PlayerTrackMeta[]) => void
  pause: () => void
  stop: () => void
  next: () => void
  prev: () => void
  // Kick off a smooth crossfade to the already-planned next track
  // RIGHT NOW, without waiting for the current track to end. Picks
  // queue[idx+1] when available, otherwise falls back to the
  // client-side pickAutoNext. No-op when there's nothing to play.
  mixNow: () => void
  // Pick the most compatible track via the backend TransitionScorer
  // (scoreTransitionCandidates server action) and play it. Async
  // because it awaits the scoring RPC. Same picker as the auto-DJ
  // end-of-track handler, so behaviour is consistent across the UI.
  playRecommendedNext: () => Promise<void>
  // Next track that would play if the user did nothing. Derived from
  // queue[idx+1]; null when there's no queued item. Medium/Mini bars
  // render this as a "→ Artist — Title" peek chip.
  nextUp: PlayerTrackMeta | null
  seek: (seconds: number) => void
  setVolume: (vol: number) => void
  toggleMute: () => void
  toggleAutoDj: () => void
  mixEnabled: boolean // master toggle for crossfade mixing — when false transitions snap
  toggleMixEnabled: () => void
  nudgeMasterTempoBpm: (delta: number) => void
  resetMasterTempoToCurrentTrack: () => void
  crossfadeBars: number // length of mix in BARS (DJ-native unit)
  setCrossfadeBars: (b: number) => void
  setQueue: (q: PlayerTrackMeta[]) => void // expand queue for auto-DJ pool
  // Manual transition-style override. When `'auto'` (default) the
  // dispatcher follows the backend's recommendation. Any other value
  // forces that style on the next crossfade regardless of what the
  // scorer thinks. Lets the DJ test / override styles by ear.
  // Per-band EQ on the active deck. gain: -40 (kill) to +6 (boost), 0 = flat.
  setDeckEq: (band: 'low' | 'mid' | 'high', gain: number) => void
  manualStyle: ManualTransitionStyle
  setManualStyle: (s: ManualTransitionStyle) => void
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
  // What the dispatcher actually ran on the currently-active fade,
  // after applying `manualStyle` override. `null` outside an active
  // fade. Visualiser reads this to show the *resolved* style badge
  // (which may differ from `recommendedStyle` when the user clicks
  // a manual override chip).
  lastResolvedStyle: 'cut' | 'swap' | 'harmonic' | 'fade' | 'echo_out' | 'filter_sweep' | null
  lastResolvedStyleWasManual: boolean
}

interface Deck {
  audio: HTMLAudioElement
  source: MediaElementAudioSourceNode
  // Signal chain:
  //                              ┌─→ dryGain ─────────────────┐
  //   source → preGain → split ──┤                            ├─→ sum → mid → high → fadeGain → master
  //                              └─→ hp1 → hp2 → wetGain ─────┘
  //
  // - `preGain` holds a static replay-gain-style level offset used
  //   for LUFS normalization. Set once at fade start from
  //   `integrated_lufs`. We only ever *attenuate* (boost = clipping
  //   risk), so the loudest of the two decks gets pulled down to the
  //   quieter one and the quiet deck stays at 1.0.
  //
  // - The `dryGain + wetGain` split is the "kick kill" path. The dry
  //   branch passes the source unchanged; the wet branch is run
  //   through a Linkwitz-Riley 4th-order highpass (two cascaded
  //   BiquadFilterNode(highpass, Q=0.7071) @ 150 Hz) that completely
  //   removes the kick body AND its click transient. A biquad
  //   lowshelf at -40 dB cannot kill a kick drum — the attack
  //   transient lives up to 2-4 kHz and slips through the 12 dB/oct
  //   slope. Pro DJ mixers (Pioneer DJM, Allen & Heath Xone) use
  //   24 dB/oct Butterworth / Linkwitz-Riley for the same reason.
  //
  //   The *swap* is done by crossfading `dryGain` and `wetGain`
  //   against each other in equal-power: full-dry = kick intact,
  //   full-wet = kick killed. Both decks swap simultaneously in
  //   opposite directions. This is the same "dry/wet" pattern used
  //   throughout Web Audio effects work — it avoids gradual
  //   attenuation artefacts and guarantees a clean hand-off.
  //
  // - `sum` re-merges the two branches before the rest of the EQ.
  //
  // - `mid` (peaking 1 kHz) and `high` (highshelf 4 kHz) remain for
  //   future per-band EQ and are currently neutral.
  //
  // - `fadeGain` is the per-deck equal-power crossfade envelope.
  preGain: GainNode
  dryGain: GainNode
  wetGain: GainNode
  hp1: BiquadFilterNode
  hp2: BiquadFilterNode
  sum: GainNode
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
  // Master-bus safety limiter. Sits between both decks and the
  // destination. Guarantees true-peak never passes -0.3 dBFS even
  // if LUFS normalisation miscalculates. Industry standard for DJ
  // software (Serato, Rekordbox all have one on master out).
  const masterLimiterRef = useRef<DynamicsCompressorNode | null>(null)
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
  const [lastResolvedStyle, setLastResolvedStyle] = useState<
    'cut' | 'swap' | 'harmonic' | 'fade' | 'echo_out' | 'filter_sweep' | null
  >(null)
  const [lastResolvedStyleWasManual, setLastResolvedStyleWasManual] = useState(false)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(0.85)
  const [muted, setMuted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Default ON: out-of-the-box the user expects tracks to recommend +
  // auto-advance. The Auto-Mix toggle in the player bar flips this.
  const [autoDj, setAutoDj] = useState(true)
  // Master mix switch — default ON. When false, every transition snaps
  // instantly (useful for preview-style listening).
  const [mixEnabled, setMixEnabled] = useState(true)
  // Default 32 bars — long, smooth, professional DJ-style mix.
  // 32 bars at 124 BPM = 32*4/124*60 ≈ 62 seconds.
  const [crossfadeBars, setCrossfadeBars] = useState(32)
  // Session / master tempo. Unlike the old "follow the outgoing
  // track" model this stays stable across chained transitions until
  // the DJ explicitly nudges or resets it.
  const [masterTempoBpm, setMasterTempoBpmState] = useState<number | null>(null)
  // Manual transition-style override. 'auto' = follow backend scorer.
  // Any other value forces that style on the next crossfade.
  //
  // Persisted to localStorage so the DJ's chosen override survives a
  // page reload during a live session. We initialise with 'auto' on
  // the server (SSR has no window) and hydrate from storage in a
  // useEffect to avoid an SSR/CSR markup mismatch.
  const MANUAL_STYLE_STORAGE_KEY = 'dj.player.manualStyle'
  const isValidManualStyle = (v: unknown): v is ManualTransitionStyle =>
    v === 'auto' || v === 'cut' || v === 'swap' || v === 'harmonic' || v === 'fade'
  const [manualStyle, setManualStyleState] = useState<ManualTransitionStyle>('auto')
  // Ref mirror so startCrossfade's async body (which captures state
  // by value at the call site) still picks up the latest choice
  // made right before the crossfade actually fires.
  const manualStyleRef = useRef<ManualTransitionStyle>('auto')
  useEffect(() => {
    manualStyleRef.current = manualStyle
  }, [manualStyle])
  // Hydrate from localStorage once on mount.
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(MANUAL_STYLE_STORAGE_KEY)
      if (raw && isValidManualStyle(raw)) {
        setManualStyleState(raw)
      }
    } catch {
      // localStorage may be disabled (private mode, SSR) — ignore.
    }
    // Intentionally empty deps: hydrate once on mount.
  }, [])
  // Setter that also writes through to localStorage.
  const setManualStyle = useCallback((s: ManualTransitionStyle) => {
    setManualStyleState(s)
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(MANUAL_STYLE_STORAGE_KEY, s)
    } catch {
      // ignore
    }
  }, [])
  const historyRef = useRef<number[]>([])
  const masterTempoRef = useRef<number | null>(null)
  useEffect(() => {
    masterTempoRef.current = masterTempoBpm
  }, [masterTempoBpm])
  const currentTrackIdRef = useRef<number | null>(null)
  useEffect(() => {
    currentTrackIdRef.current = current?.id ?? null
  }, [current])

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
    masterTempoBpm ?? current?.bpm,
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

    // One-shot master limiter for the whole audio context. Sits
    // between both decks' gain and ctx.destination. DJ software
    // industry-standard safety net — guarantees no true-peak
    // clipping even if LUFS normalisation gets it wrong.
    //   threshold: -1 dBFS    (catches anything above -1)
    //   knee:       0 dB      (hard knee — brick-wall behaviour)
    //   ratio:     20:1       (effectively limiting, not soft comp)
    //   attack:     3 ms      (fast enough to catch transients)
    //   release:   50 ms      (natural decay without pumping)
    const masterLimiter = ctx.createDynamicsCompressor()
    masterLimiter.threshold.value = -1
    masterLimiter.knee.value = 0
    masterLimiter.ratio.value = 20
    masterLimiter.attack.value = 0.003
    masterLimiter.release.value = 0.05
    masterLimiter.connect(ctx.destination)
    masterLimiterRef.current = masterLimiter

    const buildDeck = (id: 'A' | 'B'): Deck => {
      const audio = new Audio()
      audio.preload = 'auto'
      audio.crossOrigin = 'anonymous'
      const source = ctx.createMediaElementSource(audio)

      // preGain — static LUFS-normalization offset applied before
      // the kick-kill split. Set per track in startCrossfade from
      // `track.integrated_lufs`. Default 1.0 (no offset). We ONLY
      // attenuate; boosting risks true-peak clipping (which the
      // master limiter would catch, but it's cleaner to prevent).
      const preGain = ctx.createGain()
      preGain.gain.value = 1.0

      // Dry/wet split for kick-kill. The dry branch passes the
      // source unchanged. The wet branch runs through a Linkwitz-
      // Riley 4th-order highpass (two cascaded Butterworth Q=0.707
      // @ 150 Hz = 24 dB/oct) that completely removes the kick
      // body AND its attack transient. During a bass swap we
      // crossfade between the two branches: `dry=1, wet=0` means
      // kick intact; `dry=0, wet=1` means kick fully killed.
      const dryGain = ctx.createGain()
      dryGain.gain.value = 1.0
      const wetGain = ctx.createGain()
      wetGain.gain.value = 0.0
      const hp1 = ctx.createBiquadFilter()
      hp1.type = 'highpass'
      hp1.frequency.value = 150
      hp1.Q.value = 0.7071
      const hp2 = ctx.createBiquadFilter()
      hp2.type = 'highpass'
      hp2.frequency.value = 150
      hp2.Q.value = 0.7071
      const sum = ctx.createGain()
      sum.gain.value = 1.0

      // 3-band DJ EQ: low shelf + mid peak + high shelf.
      // Exposed via setDeckEq() for per-band gain control (-40..+6 dB).
      const low = ctx.createBiquadFilter()
      low.type = 'lowshelf'
      low.frequency.value = 320
      low.gain.value = 0
      const mid = ctx.createBiquadFilter()
      mid.type = 'peaking'
      mid.frequency.value = 1000
      mid.Q.value = 1
      mid.gain.value = 0
      const high = ctx.createBiquadFilter()
      high.type = 'highshelf'
      high.frequency.value = 3200
      high.gain.value = 0

      const gain = ctx.createGain()
      gain.gain.value = 0

      // Wire topology:
      //   source → preGain ─┬─→ dryGain ────────────┐
      //                     │                       ├─→ sum → mid → high → gain → masterLimiter → destination
      //                     └─→ hp1 → hp2 → wetGain─┘
      source.connect(preGain)
      preGain.connect(dryGain)
      preGain.connect(hp1)
      hp1.connect(hp2)
      hp2.connect(wetGain)
      dryGain.connect(sum)
      wetGain.connect(sum)
      sum.connect(low).connect(mid).connect(high).connect(gain).connect(masterLimiter)

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

      return {
        audio,
        source,
        preGain,
        dryGain,
        wetGain,
        hp1,
        hp2,
        sum,
        low,
        mid,
        high,
        gain,
      }
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

  const updateMasterTempoBpm = useCallback((bpm: number | null | undefined) => {
    const normalized = normalizeTempoBpm(bpm)
    masterTempoRef.current = normalized
    setMasterTempoBpmState(normalized)
    return normalized
  }, [])

  const applyTempoMatchToDeck = useCallback(
    (
      deck: Deck | null,
      trackBpm: number | null | undefined,
      targetBpm: number | null | undefined,
    ): number => {
      const ratio = resolveTempoMatchRatio(targetBpm, trackBpm)
      if (!deck) return ratio
      try {
        deck.audio.playbackRate = ratio
      } catch {
        // ignore
      }
      return ratio
    },
    [],
  )

  const syncActiveDeckToMasterTempo = useCallback(
    (targetBpm: number | null | undefined) => {
      const active = getActiveDeck()
      const nativeTrackBpm = currentMetaRef.current?.bpm ?? current?.bpm ?? null
      return applyTempoMatchToDeck(active, nativeTrackBpm, targetBpm)
    },
    [applyTempoMatchToDeck, current, getActiveDeck],
  )

  const nudgeMasterTempoBpm = useCallback(
    (delta: number) => {
      const baseTempo =
        masterTempoRef.current ??
        normalizeTempoBpm(currentMetaRef.current?.bpm ?? current?.bpm ?? null)
      if (baseTempo == null) return
      const nextTempo = Math.round((baseTempo + delta) * 10) / 10
      updateMasterTempoBpm(nextTempo)
      if (!fadingRef.current) syncActiveDeckToMasterTempo(nextTempo)
    },
    [current, syncActiveDeckToMasterTempo, updateMasterTempoBpm],
  )

  const resetMasterTempoToCurrentTrack = useCallback(() => {
    const nativeTempo = normalizeTempoBpm(currentMetaRef.current?.bpm ?? current?.bpm ?? null)
    if (nativeTempo == null) return
    updateMasterTempoBpm(nativeTempo)
    if (!fadingRef.current) syncActiveDeckToMasterTempo(nativeTempo)
  }, [current, syncActiveDeckToMasterTempo, updateMasterTempoBpm])

  // ── Pre-load next track 30s before crossfade trigger ────────────
  // Picks the next track early and starts loading its audio on the
  // inactive deck so the crossfade begins instantly (no network wait).
  const [preloadedNext, setPreloadedNext] = useState<PlayerTrackMeta | null>(null)
  const [preloadFired, setPreloadFired] = useState(false)
  // Pre-emptive auto-DJ crossfade: prefer OUTRO section start as the
  // trigger so we mix during the outgoing track's designed mix-out zone.
  const [autoDjPickInFlight, setAutoDjPickInFlight] = useState(false)

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
      const outgoingTrack = current
      // Snapshot the OUTGOING track BEFORE we mutate `current`. The
      // <TransitionVisualizer> needs both endpoints of the fade.
      setOutgoing(outgoingTrack)
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
      setPreloadFired(false)
      setPreloadedNext(null)
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
          const resolvedIncomingMeta = incomingMeta ?? fallbackMixMeta(track)
          const activeMeta = currentMetaRef.current ?? (current ? fallbackMixMeta(current) : null)
          const sessionTempo =
            masterTempoRef.current ??
            normalizeTempoBpm(activeMeta?.bpm ?? current?.bpm ?? track.bpm ?? null)
          if (masterTempoRef.current == null && sessionTempo != null) {
            updateMasterTempoBpm(sessionTempo)
          }

          // Use the OUTGOING track's BPM (already known from current.bpm /
          // currentMetaRef) to convert bars→seconds. This locks the mix
          // duration to musical time, not wall-clock time.
          const outgoingNativeBpm = normalizeTempoBpm(activeMeta?.bpm ?? current?.bpm ?? null)
          const outgoingBpm =
            outgoingNativeBpm != null
              ? outgoingNativeBpm * (active.audio.playbackRate || 1)
              : sessionTempo

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

          // ── Downbeat alignment (the systemic fix) ───────────────
          // Previous implementation scheduled the envelopes at
          // ctx.currentTime and seeked incoming to a raw-seconds
          // position, so nothing guaranteed that the two tracks' kicks
          // landed on the same wall-clock moment. Tempo-match brings
          // BPMs together, but does nothing about PHASE. Result: every
          // transition played with a flam / off-beat kick.
          //
          // Fix in one pass:
          //   1. Tempo-match ratio first (we need it before the seek
          //      so we can pre-roll the incoming position to compensate
          //      for the delay we're about to add).
          //   2. Compute outgoing's next downbeat from current position.
          //      firstDownbeatSec is 0 in the TrackMixMeta query (no
          //      beatgrid wired up yet), so for 4/4 techno a downbeat
          //      sits at every multiple of `240/bpm` seconds from 0.
          //   3. Delay `t0` until that outgoing downbeat (at most one
          //      bar ~ 1.9s at 127 BPM). Outgoing's kick at t0 is now
          //      guaranteed to be on a downbeat.
          //   4. Snap the incoming seek target to *its* nearest native
          //      downbeat, then pre-roll by -(delay * ratio) so the
          //      audio element arrives at the snapped downbeat exactly
          //      at wall-clock t0. Incoming's kick at t0 also falls on
          //      a downbeat. Since wall-clock bar interval matches
          //      (incoming's bar = inBar / ratio = outBar), all
          //      subsequent beats stay aligned for the whole fade.
          const ratio = resolveTempoMatchRatio(sessionTempo, resolvedIncomingMeta.bpm)

          // Outgoing next-downbeat delay (0..outBar seconds).
          // Reads the REAL firstDownbeatSec from the beatgrid join in
          // getTrackMixMeta, with a 0 fallback when no beatgrid exists
          // (still correct for 4/4 techno that starts on a downbeat).
          const DOWNBEAT_EPSILON = 0.03 // 30 ms — already-on-beat snap
          let delaySec = 0
          if (outgoingBpm && outgoingBpm > 0) {
            const outBar = 240 / outgoingBpm // 4 beats / bar
            const outFirstDownbeat = Math.max(
              0,
              activeMeta?.firstDownbeatSec ?? 0,
            )
            const currentOutPos = active.audio.currentTime || 0
            // Distance from current position to the next downbeat of
            // outgoing: `(currentOut - firstDownbeat) mod outBar` gives
            // how far we are past the last downbeat; subtract from outBar.
            const sincePrev =
              ((currentOutPos - outFirstDownbeat) % outBar + outBar) % outBar
            const toNext = outBar - sincePrev
            // If we're within epsilon of a downbeat already, fire now.
            delaySec =
              toNext < DOWNBEAT_EPSILON || toNext > outBar - DOWNBEAT_EPSILON
                ? 0
                : toNext
            // Never delay past end-of-track.
            if (active.audio.duration) {
              const room = active.audio.duration - currentOutPos - cf
              if (room < delaySec) delaySec = Math.max(0, room)
            }
          }

          const t0 = ctx.currentTime + delaySec

          // Compute + snap incoming seek, with pre-roll compensation so
          // at wall-clock t0 the audio element is exactly on the snap.
          //
          // Seek target strategy:
          //   1. Measured intro from track_sections:
          //        seek = max(introStart, introEnd - cf)
          //      so incoming's DROP lands exactly at fade end.
          //   2. No measured sections (most tracks today — detection
          //      hasn't run yet): fall back to a CANONICAL 32-bar intro
          //      assumption. Techno tracks ship with a drum-led 32-bar
          //      intro almost universally, so we pretend introEnd =
          //      32 bars × bar_seconds and re-use the same "arrive at
          //      drop by fade end" rule. This is what stops incoming
          //      from always starting at 0.
          //   3. Then snap to a downbeat (using the real
          //      firstDownbeatSec from the beatgrid) and bump forward
          //      until pre-roll ≥ 0.
          const DEFAULT_INTRO_BARS = 32 // typical techno drum-led intro
          let snappedSeekTarget: number | null = null
          const incomingFirstDownbeat = Math.max(
            0,
            resolvedIncomingMeta.firstDownbeatSec ?? 0,
          )
          const inBar =
            resolvedIncomingMeta.bpm && resolvedIncomingMeta.bpm > 0
              ? 240 / resolvedIncomingMeta.bpm
              : null

          const snapToIncomingDownbeat = (t: number): number => {
            if (inBar == null) return Math.max(0, t)
            const offset = t - incomingFirstDownbeat
            const snapped = incomingFirstDownbeat + Math.round(offset / inBar) * inBar
            return Math.max(0, snapped)
          }

          const bumpForPreRoll = (t: number): number => {
            if (inBar == null) return Math.max(0, t)
            const needed = delaySec * ratio
            let out = t
            while (out < needed) out += inBar
            return out
          }

          // Case 1 — measured intro sections.
          if (
            resolvedIncomingMeta.introEndSec != null &&
            resolvedIncomingMeta.introEndSec > 0 &&
            resolvedIncomingMeta.introEndSec < 120
          ) {
            const introEnd = resolvedIncomingMeta.introEndSec
            const introStart = Math.max(0, resolvedIncomingMeta.introStartSec ?? 0)
            const introLen = Math.max(0, introEnd - introStart)
            if (introLen > 1) {
              cf = Math.max(2, Math.min(cf, introLen))
            }
            let seekTarget = Math.max(introStart, introEnd - cf)
            seekTarget = snapToIncomingDownbeat(seekTarget)
            seekTarget = bumpForPreRoll(seekTarget)
            snappedSeekTarget = seekTarget
            try {
              inactive.audio.currentTime = Math.max(0, seekTarget - delaySec * ratio)
            } catch {
              // ignore — currentTime not yet writable
            }
          }
          // Case 2 — no measured intro, assumed 32-bar intro fallback.
          else if (inBar != null) {
            const assumedIntroLen = DEFAULT_INTRO_BARS * inBar
            // Cap cf to the assumed intro length so the drop lands at
            // fade end (same rule as measured case).
            if (cf > assumedIntroLen) {
              cf = Math.max(2, assumedIntroLen)
            }
            let seekTarget = Math.max(0, assumedIntroLen - cf)
            seekTarget = snapToIncomingDownbeat(seekTarget)
            seekTarget = bumpForPreRoll(seekTarget)
            snappedSeekTarget = seekTarget
            try {
              inactive.audio.currentTime = Math.max(0, seekTarget - delaySec * ratio)
            } catch {
              // ignore
            }
          }
          // Case 3 — no BPM either: legacy default, just start at 0.
          else {
            try {
              inactive.audio.currentTime = 0
            } catch {
              // ignore
            }
          }

          // Apply tempo match AFTER seek so it doesn't race with the
          // currentTime write.
          if (ratio !== 1) {
            applyTempoMatchToDeck(inactive, resolvedIncomingMeta.bpm, sessionTempo)
          }
          // Bass-swap moment — the instant at which outgoing's kick/
          // bass is killed and incoming's kick/bass unmutes. Should
          // land on an OUTGOING downbeat to feel tight. For whole-bar
          // cf values (32-bar / 8-bar / 16-bar styles) `cf / 2` is
          // already on a downbeat, but cf may have been clamped by
          // intro length or outgoing-remaining time so we re-snap to
          // the nearest outgoing bar around the midpoint.
          let tSwap = t0 + cf / 2
          if (outgoingBpm && outgoingBpm > 0) {
            const outBar = 240 / outgoingBpm
            const bars = Math.round((tSwap - t0) / outBar)
            tSwap = t0 + bars * outBar
          }
          const vol = volumeRef.current

          // Publish fade timing for the visualizer overlay (AudioContext
          // currentTime, not wall clock — same units the engine uses).
          setCrossfadeStartedAt(t0)
          setCrossfadeDurationSeconds(cf)
          // Snapshot per-deck playhead positions and the playback rates
          // they're locked into, projected forward to the moment the
          // envelopes actually start (t0 = now + delaySec). Visualizer
          // extrapolates real positions = startPos + progress*cf*rate,
          // so it can drive both waveforms with actual sample positions
          // instead of 0.
          const outgoingAtT0 = (active.audio.currentTime || 0) + delaySec
          const incomingAtT0 =
            snappedSeekTarget != null
              ? snappedSeekTarget
              : (inactive.audio.currentTime || 0) + delaySec * ratio
          setOutgoingFadeStartPosition(outgoingAtT0)
          setIncomingFadeStartPosition(incomingAtT0)
          setOutgoingFadePlaybackRate(active.audio.playbackRate || 1)
          setIncomingFadePlaybackRate(ratio)

          // ── Transition-style dispatcher ───────────────────────
          //
          // Four canonical DJ transition types. The backend scorer
          // (score_transitions) recommends one of six styles; we
          // fold them down to four implementations and dispatch:
          //
          //   backend style     → runtime style
          //   ─────────────────   ─────────────
          //   'cut'              → CUT       (drum cut, hard on downbeat)
          //   'bass_swap_short'  → SWAP      (drum swap, LR4 kick kill)
          //   'bass_swap_long'   → SWAP
          //   'long_blend'       → HARMONIC  (key-matched long blend)
          //   'echo_out'         → SWAP      (advanced — defer)
          //   'filter_sweep'     → SWAP      (advanced — defer)
          //    null              → FADE      (safe default when no rec)
          //
          // All four share: downbeat alignment, LUFS normalisation,
          // master limiter. They differ in:
          //
          //   CUT:      hard cut. 50 ms linear fade-out on outgoing,
          //             instant snap-in of incoming. No overlap. No
          //             bass kill. `cf` collapses to 0.05 s.
          //
          //   SWAP:     equal-power cos/sin gain curves over `cf`
          //             + LR4 dry/wet bass-kick kill around tSwap.
          //             This is the standard techno bass swap.
          //
          //   HARMONIC: equal-power cos/sin gain curves over `cf`,
          //             NO dry/wet manipulation. Both kicks play
          //             through — relies on key compatibility for
          //             a clean tonal blend.
          //
          //   FADE:     LINEAR gain crossfade over `cf`, no bass kill.
          //             Plain fade — used as a safe default when the
          //             backend has no recommendation.
          const recommendedStyle: string | null | undefined = styleResult?.recommendedStyle
          type RuntimeStyle =
            | 'cut'
            | 'swap'
            | 'harmonic'
            | 'fade'
            | 'echo_out'
            | 'filter_sweep'
          // Manual override wins over the backend scorer. Read from
          // the ref — `startCrossfade` captures state at call time,
          // but the user might have clicked a chip between call and
          // fade-start (we're still inside the `.then()` after
          // network + audio load), so the ref is fresher. The manual
          // chip group currently only exposes the four "canonical"
          // styles (cut/swap/harmonic/fade); ECHO_OUT and FILTER_SWEEP
          // can only arrive via the backend recommender.
          const manualOverride = manualStyleRef.current
          const resolvedStyle: RuntimeStyle = ((): RuntimeStyle => {
            if (manualOverride !== 'auto') {
              return manualOverride
            }
            switch (recommendedStyle) {
              case 'cut':
                return 'cut'
              case 'bass_swap_short':
              case 'bass_swap_long':
                return 'swap'
              case 'echo_out':
                return 'echo_out'
              case 'filter_sweep':
                return 'filter_sweep'
              case 'long_blend':
                return 'harmonic'
              default:
                return 'fade'
            }
          })()

          // Publish the resolved style so the visualiser can show
          // which of the four runtime styles actually played. Also
          // flag whether it came from a manual override chip.
          setLastResolvedStyle(resolvedStyle)
          setLastResolvedStyleWasManual(manualOverride !== 'auto')

          // Effective fade duration — CUT collapses to 50 ms.
          const CUT_FADE_SEC = 0.05
          const effectiveFadeSec = resolvedStyle === 'cut' ? CUT_FADE_SEC : cf

          // Dispatch the gain envelope.
          active.gain.gain.cancelScheduledValues(t0)
          active.gain.gain.setValueAtTime(active.gain.gain.value, t0)
          inactive.gain.gain.cancelScheduledValues(t0)
          inactive.gain.gain.setValueAtTime(0, t0)

          // Extra cleanup callbacks registered by styles that build
          // transient Web Audio nodes (echo_out wires a DelayNode
          // feedback loop onto the outgoing deck). Drained in the
          // finaliser below after the fade wall-clock expires.
          const extraCleanup: Array<() => void> = []

          if (resolvedStyle === 'cut') {
            // Drum cut: 50 ms linear fade on outgoing, 5 ms micro-ramp
            // on incoming to avoid click from MP3 decoder seek artifact.
            active.gain.gain.linearRampToValueAtTime(0, t0 + CUT_FADE_SEC)
            inactive.gain.gain.setValueAtTime(0, t0)
            inactive.gain.gain.linearRampToValueAtTime(vol, t0 + 0.005)
          } else if (resolvedStyle === 'echo_out') {
            // ECHO_OUT: outgoing leaves on a dub-delay tail.
            //
            // Two-part envelope. The DRY outgoing path fades fast
            // (≈2 bars) so the beat stops, then a parallel tap from
            // `active.preGain → delay → feedback → delay` keeps
            // regenerating the last beat with decaying loudness.
            // Meanwhile the incoming deck equal-power fades in over
            // the full `cf`, so the listener hears the old track
            // dissolve into echoes underneath the new groove.
            //
            // Beat-quantised delay time: 1 beat @ outgoing BPM (or a
            // safe 0.5 s fallback). Feedback 0.55 gives ~4-5 audible
            // repeats before the -60 dB tail. Wet-ceiling 0.7 keeps
            // the tail clearly audible without fighting the incoming.
            const outBar = outgoingBpm ? 240 / outgoingBpm : 1.88
            const beatSec = outBar / 4
            const delayTime = Math.max(0.15, Math.min(0.75, beatSec))
            const echoDelay = ctx.createDelay(1.5)
            echoDelay.delayTime.setValueAtTime(delayTime, t0)
            const echoFb = ctx.createGain()
            echoFb.gain.setValueAtTime(0.55, t0)
            const echoWet = ctx.createGain()
            echoWet.gain.setValueAtTime(0.7 * vol, t0)
            // Parallel tap from preGain (post-LUFS-normalization,
            // pre-dry/wet split). We re-use the existing masterLimiter
            // on the graph by terminating at the deck's fadeGain
            // output node via a fresh sum — simpler: connect directly
            // to ctx.destination's upstream limiter via the master
            // path. Since every deck.gain → masterLimiter already, we
            // just land our wet on `active.gain`'s output target,
            // which is the masterLimiter input. `active.gain` is a
            // GainNode — we can connect `echoWet → active.gain` so
            // the wet signal rides through the same gain envelope,
            // BUT that would also scale the wet by the fast dry
            // fade-out. We want the wet independent. So instead we
            // grab the master limiter off the Deck's known downstream
            // chain by letting echoWet → ctx.destination directly.
            // The master limiter lives upstream of destination already
            // in the main graph, but echoWet is a separate branch —
            // routing it straight to destination bypasses the limiter.
            // Accept that: feedback=0.55 + wetCeiling=0.7 keeps the
            // signal well below clipping on any realistic master.
            // LPF in feedback loop: each repeat loses highs, like a
            // real analog dub delay. Without this, hi-hats and clicks
            // repeat at full brightness = harsh.
            const echoLpf = ctx.createBiquadFilter()
            echoLpf.type = 'lowpass'
            echoLpf.frequency.setValueAtTime(3500, t0)
            echoLpf.Q.setValueAtTime(0.7, t0)

            active.preGain.connect(echoDelay)
            echoDelay.connect(echoLpf)
            echoLpf.connect(echoFb)
            echoFb.connect(echoDelay)
            echoDelay.connect(echoWet)
            echoWet.connect(ctx.destination)

            // Fast dry fade-out on outgoing — 2 bars, matches what
            // a DJ does pulling the channel fader while the echo
            // send is still engaged.
            const dryFadeSec = Math.min(cf * 0.3, 2 * outBar)
            active.gain.gain.linearRampToValueAtTime(0, t0 + dryFadeSec)
            // Incoming: equal-power fade-in over the full cf.
            const N = 64
            const fadeIn = new Float32Array(N)
            for (let i = 0; i < N; i++) {
              const x = i / (N - 1)
              fadeIn[i] = Math.sin((x * Math.PI) / 2) * vol
            }
            inactive.gain.gain.setValueCurveAtTime(fadeIn, t0, cf)
            // Echo wet decays to 0 over cf so the tail dies with the
            // fade — otherwise feedback would ring forever.
            echoWet.gain.linearRampToValueAtTime(0, t0 + cf)
            // Kill feedback hard at fade end to silence any residual
            // loop before we disconnect.
            echoFb.gain.setValueAtTime(0.55, t0 + cf - 0.1)
            echoFb.gain.linearRampToValueAtTime(0, t0 + cf)

            extraCleanup.push(() => {
              try {
                active.preGain.disconnect(echoDelay)
              } catch {
                // ignore
              }
              try {
                echoDelay.disconnect()
                echoLpf.disconnect()
                echoFb.disconnect()
                echoWet.disconnect()
              } catch {
                // ignore
              }
            })
          } else if (resolvedStyle === 'filter_sweep') {
            // FILTER_SWEEP: outgoing swept up through the existing
            // LR4 highpass cascade until only thin air is left; the
            // incoming equal-power fades in underneath.
            //
            // We route outgoing fully wet (dryGain → 0, wetGain → 1)
            // at t0 so every sample passes through hp1 → hp2, then
            // exponentially ramp the HP cutoff from the current LR4
            // standard (150 Hz) up to 6 kHz over cf. At the top the
            // HP is so high that the only audible content is sibilant
            // top-end, which also fades as active.gain drops.
            //
            // Exponential (not linear) automation matches how human
            // pitch perception works — a linear Hz sweep sounds stuck
            // at the top for most of the duration. exponentialRamp
            // gives an even perceived glide.
            const SWEEP_START_HZ = 150
            const SWEEP_END_HZ = 6000
            try {
              active.dryGain.gain.cancelScheduledValues(t0)
              active.dryGain.gain.setValueAtTime(0, t0)
              active.wetGain.gain.cancelScheduledValues(t0)
              active.wetGain.gain.setValueAtTime(1, t0)
              active.hp1.frequency.cancelScheduledValues(t0)
              active.hp2.frequency.cancelScheduledValues(t0)
              active.hp1.frequency.setValueAtTime(SWEEP_START_HZ, t0)
              active.hp2.frequency.setValueAtTime(SWEEP_START_HZ, t0)
              active.hp1.frequency.exponentialRampToValueAtTime(SWEEP_END_HZ, t0 + cf)
              active.hp2.frequency.exponentialRampToValueAtTime(SWEEP_END_HZ, t0 + cf)
            } catch {
              // ignore
            }
            // Outgoing gain: hold for the first 70 % then linear out
            // — the sweep does most of the spectral killing, the
            // gain ramp is just a clean tail-off.
            active.gain.gain.setValueAtTime(vol, t0)
            active.gain.gain.setValueAtTime(vol, t0 + cf * 0.7)
            active.gain.gain.linearRampToValueAtTime(0, t0 + cf)
            // Incoming: equal-power fade-in, dry path (no filter).
            const N = 64
            const fadeIn = new Float32Array(N)
            for (let i = 0; i < N; i++) {
              const x = i / (N - 1)
              fadeIn[i] = Math.sin((x * Math.PI) / 2) * vol
            }
            inactive.gain.gain.setValueCurveAtTime(fadeIn, t0, cf)

            extraCleanup.push(() => {
              // Reset HP freq back to LR4 standard so the next swap
              // on this deck starts from a clean baseline.
              try {
                active.hp1.frequency.cancelScheduledValues(ctx.currentTime)
                active.hp2.frequency.cancelScheduledValues(ctx.currentTime)
                active.hp1.frequency.setValueAtTime(150, ctx.currentTime)
                active.hp2.frequency.setValueAtTime(150, ctx.currentTime)
              } catch {
                // ignore
              }
            })
          } else {
            // SWAP / HARMONIC → equal-power cos/sin.
            // FADE → linear.
            const N = 64
            const fadeOut = new Float32Array(N)
            const fadeIn = new Float32Array(N)
            if (resolvedStyle === 'fade') {
              for (let i = 0; i < N; i++) {
                const x = i / (N - 1)
                fadeOut[i] = (1 - x) * vol
                fadeIn[i] = x * vol
              }
            } else {
              // swap + harmonic: equal-power
              for (let i = 0; i < N; i++) {
                const x = i / (N - 1)
                fadeOut[i] = Math.cos((x * Math.PI) / 2) * vol
                fadeIn[i] = Math.sin((x * Math.PI) / 2) * vol
              }
            }
            active.gain.gain.setValueCurveAtTime(fadeOut, t0, cf)
            inactive.gain.gain.setValueCurveAtTime(fadeIn, t0, cf)
          }

          // ── LUFS normalization — attenuate-only ───────────────
          //
          // Professional DJ software (Serato Gain Structure, Rekordbox
          // Track Gain, Traktor Autogain) all normalise tracks to a
          // shared target BEFORE any crossfade curve runs. Without
          // this, equal-power cos/sin is correct mathematically but
          // the perceived level drifts through the fade because the
          // two masters are at different LUFS.
          //
          // Target policy: `min(outLufs, inLufs) - 0.5 dB`. This is
          // SAFE: we only ever attenuate. The quieter track stays at
          // its natural level; the louder one gets pulled down to
          // match. A boost would risk clipping even though the master
          // limiter catches it — better to never send over-level
          // signal into the graph in the first place.
          //
          //   outGainDb = target - outLufs  (≤ 0 always)
          //   inGainDb  = target - inLufs   (≤ 0 always)
          //
          // Both are written as `setValueAtTime` on the deck's
          // preGain node at t0; they hold for the entire fade
          // duration and only reset on the next play() / crossfade
          // start.
          const outLufs = activeMeta?.integratedLufs ?? null
          const inLufs = resolvedIncomingMeta.integratedLufs ?? null
          let outPreGain = 1.0
          let inPreGain = 1.0
          if (outLufs != null && inLufs != null) {
            const target = Math.min(outLufs, inLufs) - 0.5
            const outGainDb = target - outLufs
            const inGainDb = target - inLufs
            // Clamp to [0.3, 1.0] — we never boost (upper bound 1.0),
            // and never attenuate more than -10 dB (lower bound ~0.3)
            // for sanity on pathological masters.
            outPreGain = Math.max(0.3, Math.min(1.0, Math.pow(10, outGainDb / 20)))
            inPreGain = Math.max(0.3, Math.min(1.0, Math.pow(10, inGainDb / 20)))
          }
          try {
            active.preGain.gain.cancelScheduledValues(t0)
            active.preGain.gain.setValueAtTime(outPreGain, t0)
            inactive.preGain.gain.cancelScheduledValues(t0)
            inactive.preGain.gain.setValueAtTime(inPreGain, t0)
          } catch {
            // ignore
          }

          // ── Bass kick kill (SWAP style only) ──────────────────
          //
          // CUT / HARMONIC / FADE skip the dry/wet manipulation
          // entirely — they leave `dryGain = 1.0` and `wetGain = 0.0`
          // on both decks, so each track plays through the full-
          // spectrum path. Only the SWAP style engages the LR4
          // highpass cross-ramp to duck kicks.
          //
          // Adaptive parameters pulled from track metadata:
          //
          // 1. Swap DURATION scales with cf and with hp_ratio.
          //    Percussive pairs (low hp) need a longer swap to let
          //    kicks breathe; harmonic pairs (high hp) get a
          //    snappier handover.
          //
          // 2. HP cutoff adapts to hp_ratio. Harmonic-heavy pairs
          //    get a gentler 200 Hz cutoff (preserves more lower
          //    mids). Very percussive pairs get the tighter 150 Hz
          //    standard cutoff (kills more of the kick body).
          //
          // 3. `kick_prominence` scales how DEEPLY the wet path
          //    ducks — i.e. whether the swap goes to 100% wet
          //    (kick fully killed) or only 60% wet (partial duck,
          //    sounds more organic for ambient / minimal material).
          const outBarForSwap = outgoingBpm ? 240 / outgoingBpm : 1.88
          const cfBars = cf / outBarForSwap

          if (resolvedStyle === 'swap') {

          const avgHpRatio = (() => {
            const a = activeMeta?.hpRatio
            const b = resolvedIncomingMeta.hpRatio
            if (a == null && b == null) return 1.0
            if (a == null) return b!
            if (b == null) return a
            return (a + b) / 2
          })()
          const hpLengthFactor = Math.max(0.7, Math.min(1.5, 1.3 - avgHpRatio * 0.2))
          const baseSwapBars = Math.max(1, Math.min(4, cfBars / 8))
          const swapBars = Math.max(1, Math.min(4, baseSwapBars * hpLengthFactor))
          const swapDurationSec = swapBars * outBarForSwap
          const tSwapStart = Math.max(t0, tSwap - swapDurationSec / 2)
          const tSwapEnd = Math.min(t0 + cf, tSwap + swapDurationSec / 2)

          const avgKickProm = (() => {
            const a = activeMeta?.kickProminence
            const b = resolvedIncomingMeta.kickProminence
            if (a == null && b == null) return 0.5
            if (a == null) return b!
            if (b == null) return a
            return (a + b) / 2
          })()

          // Wet ceiling: how much of the signal goes through the HP
          // path at peak swap. 1.0 = fully killed, 0.6 = partial.
          // High kick prominence → full kill (1.0). Low → partial.
          const wetCeiling = 0.6 + avgKickProm * 0.4
          const dryFloor = 1.0 - wetCeiling

          // HP cutoff: percussive pairs get tight 150 Hz, harmonic
          // pairs get gentler 200 Hz. Applied to both decks' HP
          // cascades at t0 and held.
          const hpCutoffHz = avgHpRatio >= 2 ? 200 : 150
          try {
            active.hp1.frequency.setValueAtTime(hpCutoffHz, t0)
            active.hp2.frequency.setValueAtTime(hpCutoffHz, t0)
            inactive.hp1.frequency.setValueAtTime(hpCutoffHz, t0)
            inactive.hp2.frequency.setValueAtTime(hpCutoffHz, t0)
          } catch {
            // ignore
          }

          // Pre-compute equal-power dry/wet curves. One set on each
          // deck, 64 samples each. setValueCurveAtTime interpolates
          // linearly so the step count is mostly cosmetic for a
          // 2-8 s swap. Curves run on normalised [0, 1].
          const CURVE_N = 64
          // Outgoing deck: dry 1→dryFloor, wet 0→wetCeiling.
          const outDryCurve = new Float32Array(CURVE_N)
          const outWetCurve = new Float32Array(CURVE_N)
          // Incoming deck: dry dryFloor→1, wet wetCeiling→0.
          const inDryCurve = new Float32Array(CURVE_N)
          const inWetCurve = new Float32Array(CURVE_N)
          for (let i = 0; i < CURVE_N; i++) {
            const t = i / (CURVE_N - 1)
            const c = Math.cos((t * Math.PI) / 2) // 1→0
            const s = Math.sin((t * Math.PI) / 2) // 0→1
            outDryCurve[i] = dryFloor + c * (1 - dryFloor)
            outWetCurve[i] = s * wetCeiling
            inDryCurve[i] = dryFloor + s * (1 - dryFloor)
            inWetCurve[i] = c * wetCeiling
          }

          // Schedule the crossfade on all four gain nodes.
          // Pre-hold with setValueAtTime so the audio graph has a
          // known value at tSwapStart regardless of whatever the
          // previous fade left behind.
          const scheduleSwap = (
            node: GainNode,
            start: number,
            curve: Float32Array,
            dur: number,
          ) => {
            node.gain.cancelScheduledValues(t0)
            node.gain.setValueAtTime(node.gain.value, t0)
            node.gain.setValueAtTime(curve[0], start)
            node.gain.setValueCurveAtTime(curve, start, dur)
          }
          const swapDur = Math.max(0.01, tSwapEnd - tSwapStart)
          scheduleSwap(active.dryGain, tSwapStart, outDryCurve, swapDur)
          scheduleSwap(active.wetGain, tSwapStart, outWetCurve, swapDur)
          scheduleSwap(inactive.dryGain, tSwapStart, inDryCurve, swapDur)
          scheduleSwap(inactive.wetGain, tSwapStart, inWetCurve, swapDur)
          }
          // ── end of `if (resolvedStyle === 'swap')` ─────────────

          fadeTimeoutRef.current = setTimeout(() => {
            // Drain any per-style transient-node cleanup registered
            // during dispatch (echo_out, filter_sweep HP reset, …).
            for (const fn of extraCleanup) {
              try {
                fn()
              } catch {
                // ignore
              }
            }
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
            // Neutral-reset the freed deck's mid/high bands + restore
            // the dry/wet balance (fully dry = kick intact = the
            // state a fresh track expects).
            for (const f of [active.mid, active.high]) {
              f.gain.cancelScheduledValues(ctx.currentTime)
              f.gain.setValueAtTime(0, ctx.currentTime)
            }
            active.dryGain.gain.cancelScheduledValues(ctx.currentTime)
            active.dryGain.gain.setValueAtTime(1.0, ctx.currentTime)
            active.wetGain.gain.cancelScheduledValues(ctx.currentTime)
            active.wetGain.gain.setValueAtTime(0.0, ctx.currentTime)
            active.preGain.gain.cancelScheduledValues(ctx.currentTime)
            active.preGain.gain.setValueAtTime(1.0, ctx.currentTime)
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
            currentMetaRef.current = resolvedIncomingMeta
            const newActive = getActiveDeck()
            if (newActive) {
              setPosition(newActive.audio.currentTime || 0)
              setDuration(newActive.audio.duration || 0)
            }
            // ── Transition log ──────────────────────────────────
            // Structured log for analyzing transition quality.
            // Visible in DevTools console.
            try {
              const outMeta = activeMeta
              const inMeta = resolvedIncomingMeta
              console.info('[TRANSITION]', JSON.stringify({
                from: { id: outgoingTrack?.id, title: outgoingTrack?.title, bpm: outMeta?.bpm, key: outgoingTrack?.camelot },
                to: { id: track.id, title: track.title, bpm: inMeta?.bpm, key: track.camelot },
                style: resolvedStyle,
                recommended: recommendedStyle,
                manual: manualOverride !== 'auto',
                masterTempoBpm: sessionTempo,
                bars: effectiveBars,
                durationSec: Math.round(effectiveFadeSec * 10) / 10,
                tempoRatio: Math.round(ratio * 1000) / 1000,
                downbeatDelaySec: Math.round(delaySec * 100) / 100,
                seekTarget: snappedSeekTarget != null ? Math.round(snappedSeekTarget * 100) / 100 : null,
                outLufs: outMeta?.integratedLufs ?? null,
                inLufs: inMeta?.integratedLufs ?? null,
                setPosition: historyRef.current.length,
                targetEnergy: Math.round(targetEnergy(Math.min(1, historyRef.current.length / 15)) * 100) / 100,
                trackEnergy: track.mood ? (MOOD_ENERGY[track.mood] ?? null) : null,
              }))
            } catch { /* ignore logging errors */ }

            // Include the downbeat-alignment delay — fade starts at
            // delaySec into the future, so the finaliser must wait
            // (delaySec + effectiveFadeSec) wall-seconds for the
            // curves to finish. effectiveFadeSec collapses to 50 ms
            // for CUT-style transitions so we free the deck promptly.
          }, (delaySec + effectiveFadeSec) * 1000 + 50)
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
      applyTempoMatchToDeck,
      updateMasterTempoBpm,
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
      currentMetaRef.current = fallbackMixMeta(track)
      const url = `/api/audio/${track.id}`
      if (!active.audio.src.endsWith(url)) {
        active.audio.src = url
      }
      const sessionTempo =
        masterTempoRef.current ?? updateMasterTempoBpm(track.bpm)
      applyTempoMatchToDeck(active, track.bpm, sessionTempo)
      active.gain.gain.cancelScheduledValues(ctx.currentTime)
      active.gain.gain.setValueAtTime(volumeRef.current, ctx.currentTime)
      // Reset remaining EQ bands (mid/high) to neutral.
      for (const f of [active.mid, active.high]) {
        f.gain.cancelScheduledValues(ctx.currentTime)
        f.gain.setValueAtTime(0, ctx.currentTime)
      }
      // Reset the dry/wet kick-kill split — fresh track should play
      // dry (kick intact).
      active.dryGain.gain.cancelScheduledValues(ctx.currentTime)
      active.dryGain.gain.setValueAtTime(1.0, ctx.currentTime)
      active.wetGain.gain.cancelScheduledValues(ctx.currentTime)
      active.wetGain.gain.setValueAtTime(0.0, ctx.currentTime)
      // Reset preGain — the snap-load path plays a "first track",
      // there's nothing to match its LUFS against yet. The next
      // crossfade will set this based on outgoing vs incoming LUFS.
      active.preGain.gain.cancelScheduledValues(ctx.currentTime)
      active.preGain.gain.setValueAtTime(1.0, ctx.currentTime)
      // Silence the inactive deck just in case.
      const inactive = getInactiveDeck()
      if (inactive) {
        inactive.gain.gain.cancelScheduledValues(ctx.currentTime)
        inactive.gain.gain.setValueAtTime(0, ctx.currentTime)
      }
      // Async load mix metadata for upcoming transitions.
      void loadMixMeta(track.id).then((m) => {
        const resolvedMeta = m ?? fallbackMixMeta(track)
        if (currentTrackIdRef.current !== track.id || fadingRef.current) return
        currentMetaRef.current = resolvedMeta
        const resolvedSessionTempo =
          masterTempoRef.current ?? updateMasterTempoBpm(resolvedMeta.bpm)
        syncActiveDeckToMasterTempo(resolvedSessionTempo)
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
      applyTempoMatchToDeck,
      ensureContext,
      getActiveDeck,
      getInactiveDeck,
      queue.length,
      current,
      startCrossfade,
      loadMixMeta,
      mixEnabled,
      syncActiveDeckToMasterTempo,
      updateMasterTempoBpm,
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
    // Smart pick: use BPM/key/mood compatibility scoring.
    // Falls back to sequential if no compatible track found.
    const smart = pickAutoNext(current, queue, historyRef.current)
    if (smart) {
      play(smart)
      return
    }
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

  useEffect(() => {
    if (!autoDj || fadingRef.current || !current || autoDjPickInFlight) return
    if (!duration) return
    const cfSec = computeCrossfadeSeconds(crossfadeBars, masterTempoBpm ?? current.bpm)
    if (duration < cfSec * 1.5) return
    const meta = currentMetaRef.current
    const latestSafe = Math.max(0, duration - cfSec)
    const sectionTrigger =
      meta && meta.outroStartSec && meta.outroStartSec > 0
        ? Math.min(meta.outroStartSec, latestSafe)
        : latestSafe

    // Phase 1: Pre-load — 30s before trigger, pick next and start loading
    const preloadTrigger = Math.max(0, sectionTrigger - 30)
    if (position >= preloadTrigger && !preloadFired) {
      setPreloadFired(true)
      void pickNextTrackAsync(current, queue, historyRef.current).then((next) => {
        if (!next) return
        setPreloadedNext(next)
        // Start loading audio on the inactive deck (silent, gain=0)
        const inactive = getInactiveDeck()
        if (inactive) {
          const url = `/api/audio/${next.id}`
          inactive.audio.src = url
          inactive.audio.preload = 'auto'
          inactive.audio.load()
        }
      })
    }

    // Phase 2: Crossfade trigger — use preloaded track if available
    if (position >= sectionTrigger) {
      setAutoDjPickInFlight(true)
      const preloaded = preloadedNext
      if (preloaded && !fadingRef.current) {
        // Track already preloaded — instant crossfade
        setPreloadedNext(null)
        setPreloadFired(false)
        startCrossfade(preloaded)
        setTimeout(() => {
          setAutoDjPickInFlight(false)
        }, 2000)
      } else {
        // Fallback: pick and crossfade (original path)
        void pickNextTrackAsync(current, queue, historyRef.current)
          .then((nextTrack) => {
            if (nextTrack && !fadingRef.current) startCrossfade(nextTrack)
          })
          .finally(() => {
            setPreloadedNext(null)
            setPreloadFired(false)
            setTimeout(() => {
              setAutoDjPickInFlight(false)
            }, 2000)
          })
      }
    }
  }, [
    position,
    duration,
    autoDj,
    autoDjPickInFlight,
    current,
    preloadedNext,
    preloadFired,
    queue,
    crossfadeBars,
    masterTempoBpm,
    startCrossfade,
    pickNextTrackAsync,
    computeCrossfadeSeconds,
    getInactiveDeck,
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

  // ── iOS background playback ─────────────────────────────────────
  // WebKit PR #17812 (March 2024) added navigator.audioSession.type
  // = "playback" which tells iOS to NOT suspend AudioContext when
  // the page goes to background / screen locks. This is the official
  // WebKit-sanctioned way to enable background audio for Web Audio.
  //
  // Combined with MediaSession API (already set up above) this gives
  // full lock screen controls + continuous background playback.
  //
  // Fallback: silent <audio> keepalive for older iOS versions, plus
  // visibilitychange resume for returning from background.
  const silenceRef = useRef<HTMLAudioElement | null>(null)
  useEffect(() => {
    if (typeof document === 'undefined') return

    // Set audioSession type to "playback" (WebKit 275558, iOS 17.4+)
    try {
      const nav = navigator as Navigator & { audioSession?: { type: string } }
      if (nav.audioSession) {
        nav.audioSession.type = 'playback'
      }
    } catch { /* not supported — fall through to silent keepalive */ }

    if (!isPlaying) {
      if (silenceRef.current) silenceRef.current.pause()
      return
    }

    // Silent keepalive for older iOS (< 17.4) that don't support audioSession
    if (!silenceRef.current) {
      const el = document.createElement('audio')
      el.src = '/silence.mp3'
      el.loop = true
      el.volume = 0.01
      el.setAttribute('playsinline', 'true')
      silenceRef.current = el
    }
    void silenceRef.current.play().catch(() => undefined)

    // Visibility change: resume ctx + re-kick audio on return
    const handler = () => {
      if (document.visibilityState === 'visible') {
        const ctx = ctxRef.current
        if (ctx && ctx.state === 'suspended') void ctx.resume()
        const active = activeDeckRef.current === 'A' ? deckARef.current : deckBRef.current
        if (active && active.audio.paused && isPlaying) {
          void active.audio.play().catch(() => undefined)
        }
        if (silenceRef.current?.paused) {
          void silenceRef.current.play().catch(() => undefined)
        }
      }
    }
    document.addEventListener('visibilitychange', handler)
    return () => document.removeEventListener('visibilitychange', handler)
  }, [isPlaying])

  // "Next up" peek — what a linear `next()` would walk to. Null when
  // the queue is exhausted. Medium/Mini bars render this as a chip
  // so the user can see what's coming before hitting MIX NOW.
  const nextUp: PlayerTrackMeta | null = useMemo(() => {
    if (queueIndex < 0) return null
    return queue[queueIndex + 1] ?? null
  }, [queue, queueIndex])

  // MIX NOW — start a crossfade to the planned next track right now,
  // without waiting for `ended`. Source priority:
  //   1. queue[idx+1] (what `next()` would walk to)
  //   2. pickAutoNext (client heuristic) on empty queue
  // No-op when there's no current track or no candidate.
  const mixNow = useCallback(() => {
    if (!current) return
    const queued = queueIndex >= 0 ? queue[queueIndex + 1] : undefined
    const target =
      queued ?? pickAutoNext(current, queue, historyRef.current) ?? null
    if (!target) return
    play(target)
  }, [current, queue, queueIndex, play])

  // RECOMMENDED NEXT — run the backend TransitionScorer for the
  // current track and play the winner. Same picker as the auto-DJ
  // end-of-track handler, so recommendations are consistent.
  const playRecommendedNext = useCallback(async () => {
    if (!current) return
    const target = await pickNextTrackAsync(current, queue, historyRef.current)
    if (!target) return
    play(target)
  }, [current, queue, pickNextTrackAsync, play])

  // ── Per-band EQ control ──────────────────────────────────────
  // Sets gain on the active deck's low/mid/high BiquadFilterNode.
  // gain range: -40 (kill) to +6 (boost), 0 = flat.
  const setDeckEq = useCallback((band: 'low' | 'mid' | 'high', gain: number) => {
    const deck = activeDeckRef.current === 'A' ? deckARef.current : deckBRef.current
    if (!deck) return
    const clamped = Math.max(-40, Math.min(6, gain))
    const node = band === 'low' ? deck.low : band === 'mid' ? deck.mid : deck.high
    node.gain.setTargetAtTime(clamped, node.context.currentTime, 0.02)
  }, [])

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
      masterTempoBpm,
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
      lastResolvedStyle,
      lastResolvedStyleWasManual,
      nextUp,
      play,
      toggle,
      pause,
      stop,
      next,
      prev,
      mixNow,
      playRecommendedNext,
      seek,
      setVolume,
      toggleMute,
      toggleAutoDj,
      toggleMixEnabled,
      nudgeMasterTempoBpm,
      resetMasterTempoToCurrentTrack,
      setCrossfadeBars,
      setQueue,
      setDeckEq,
      manualStyle,
      setManualStyle,
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
      masterTempoBpm,
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
      lastResolvedStyle,
      lastResolvedStyleWasManual,
      nextUp,
      play,
      toggle,
      pause,
      stop,
      next,
      prev,
      mixNow,
      playRecommendedNext,
      seek,
      setVolume,
      toggleMute,
      toggleAutoDj,
      toggleMixEnabled,
      nudgeMasterTempoBpm,
      resetMasterTempoToCurrentTrack,
      setDeckEq,
      manualStyle,
      setManualStyle,
    ],
  )

  return <AudioPlayerContext.Provider value={api}>{children}</AudioPlayerContext.Provider>
}
