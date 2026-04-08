export interface SlotDefinition {
  position: number // 0..1 within set
  targetMood: string | null
  energyLufs: number
  bpmMin: number
  bpmMax: number
  durationMs: number
  flexibility: number
}

export interface SetTemplate {
  name: string
  durationMin: number
  description: string
  slots: SlotDefinition[]
}

export interface CurrentSlot {
  slot: SlotDefinition
  index: number
  positionInSlot: number // 0..1 within current slot
  positionInSet: number // 0..1 across entire set
}

export interface HistoryEntry {
  trackId: number
  artistIds: number[]
  mood: string | null
  lufs: number | null
  playedAtSec: number // elapsed at play time
}

export interface ScoredCandidate {
  trackId: number
  title: string
  artists: string
  bpm: number | null
  camelot: string | null
  mood: string | null
  lufs: number | null
  transitionScore: number // 0..1
  slotFit: number // 0..1
  varietyPenalty: number // multiplier, typically 0.5..1.0
  combinedScore: number // final
  rationale: string // short human-readable explanation
}

export interface SetSessionState {
  active: boolean
  template: SetTemplate | null
  startedAtSec: number // AudioContext currentTime when session started
  elapsedSec: number
  currentSlot: CurrentSlot | null
  history: HistoryEntry[]
  upcoming: ScoredCandidate[]
  varietyTier: 0 | 1 | 2 // 0 = strictest, 2 = open
  relaxationEvents: string[] // log messages when constraints relaxed
}
