import { SUBGENRE_ENERGY_ORDER, KEY_SLOT_MOODS, ALPHA_DEFAULT, ALPHA_KEY_SLOT, ALPHA_SLOT_ENDING, ALPHA_SLOT_ENDING_POSITION, VARIETY_RECENT_HISTORY_SIZE, VARIETY_MOOD_STREAK, VARIETY_PENALTY_SAME_ARTIST, VARIETY_PENALTY_MOOD_STREAK, VARIETY_PENALTY_RECENT } from './constants'
import type { CurrentSlot, SetTemplate, SlotDefinition, HistoryEntry, ScoredCandidate } from './types'

export function getCurrentSlot(
  template: SetTemplate,
  elapsedSec: number,
  totalDurationSec: number,
): CurrentSlot {
  const positionInSet = Math.max(0, Math.min(1, elapsedSec / totalDurationSec))

  for (let i = 0; i < template.slots.length; i++) {
    const slot = template.slots[i]
    const next = template.slots[i + 1]
    const slotStart = slot.position
    const slotEnd = next ? next.position : 1.0
    if (positionInSet >= slotStart && positionInSet < slotEnd) {
      const span = slotEnd - slotStart
      const positionInSlot = span > 0 ? (positionInSet - slotStart) / span : 0
      return { slot, index: i, positionInSlot, positionInSet }
    }
  }

  // Fall-through: beyond last slot
  const last = template.slots[template.slots.length - 1]
  return {
    slot: last,
    index: template.slots.length - 1,
    positionInSlot: 1,
    positionInSet: 1,
  }
}

interface CandidateFeatures {
  bpm: number | null
  lufs: number | null
  mood: string | null
}

function gaussianDecay(diff: number, sigma: number): number {
  return Math.exp(-(diff * diff) / (2 * sigma * sigma))
}

function areMoodsNeighbors(a: string, b: string): boolean {
  const ia = SUBGENRE_ENERGY_ORDER.indexOf(a)
  const ib = SUBGENRE_ENERGY_ORDER.indexOf(b)
  if (ia < 0 || ib < 0) return false
  return Math.abs(ia - ib) <= 2
}

export function slotFitScore(
  candidate: CandidateFeatures,
  slot: SlotDefinition,
): number {
  // BPM fit (weight 0.5)
  let bpmFit = 0.5
  if (candidate.bpm != null) {
    const center = (slot.bpmMin + slot.bpmMax) / 2
    const tolerance = Math.max(1, (slot.bpmMax - slot.bpmMin) / 2)
    const diff = Math.abs(candidate.bpm - center)
    if (diff <= tolerance) {
      // Inside range: gentle 0.3 linear penalty toward the edges
      bpmFit = 1 - (diff / tolerance) * 0.3
    } else {
      // Outside: gaussian fall-off with σ=4
      bpmFit = gaussianDecay(diff - tolerance, 4) * 0.7
    }
  }

  // LUFS fit (weight 0.3)
  let lufsFit = 0.5
  if (candidate.lufs != null) {
    const diff = Math.abs(candidate.lufs - slot.energyLufs)
    lufsFit = gaussianDecay(diff, 3)
  }

  // Mood fit (weight 0.2)
  let moodFit = 0.5
  if (candidate.mood && slot.targetMood) {
    if (candidate.mood === slot.targetMood) moodFit = 1.0
    else if (areMoodsNeighbors(candidate.mood, slot.targetMood)) moodFit = 0.85
  }

  return 0.5 * bpmFit + 0.3 * lufsFit + 0.2 * moodFit
}

export function getAlpha(slot: SlotDefinition, positionInSlot: number): number {
  const isKeySlot = KEY_SLOT_MOODS.has(slot.targetMood || '')
  const isSlotEnding = positionInSlot > ALPHA_SLOT_ENDING_POSITION

  if (isSlotEnding) {
    return ALPHA_SLOT_ENDING
  }

  if (isKeySlot) {
    return ALPHA_KEY_SLOT
  }

  return ALPHA_DEFAULT
}

interface VarietyCandidate {
  id?: number
  trackId?: number
  artistIds: number[]
  mood: string | null
}

export function varietyPenalty(
  candidate: VarietyCandidate,
  history: HistoryEntry[],
): number {
  const candidateId = candidate.id ?? candidate.trackId ?? 0
  const recentHistory = history.slice(-VARIETY_RECENT_HISTORY_SIZE)

  let penalty = 1.0

  // Penalize recently played track
  if (recentHistory.some(h => h.trackId === candidateId)) {
    penalty *= VARIETY_PENALTY_RECENT
  }

  // Penalize same artist as last few tracks
  if (recentHistory.length > 0) {
    const lastEntry = recentHistory[recentHistory.length - 1]
    if (candidate.artistIds.some(aid => lastEntry.artistIds.includes(aid))) {
      penalty *= VARIETY_PENALTY_SAME_ARTIST
    }
  }

  // Penalize mood streak (last N tracks same mood)
  if (candidate.mood) {
    const sameRecentMoods = recentHistory.filter(h => h.mood === candidate.mood).length
    if (sameRecentMoods >= VARIETY_MOOD_STREAK) {
      penalty *= VARIETY_PENALTY_MOOD_STREAK
    }
  }

  return penalty
}

export function weightedRandomPick(
  candidates: ScoredCandidate[],
  rng: () => number = Math.random,
): ScoredCandidate {
  if (candidates.length === 1) return candidates[0]

  const totalScore = candidates.reduce((sum, c) => sum + c.combinedScore, 0)
  if (totalScore <= 0) return candidates[0]

  let pick = rng() * totalScore
  for (const c of candidates) {
    pick -= c.combinedScore
    if (pick <= 0) return c
  }

  return candidates[candidates.length - 1]
}
