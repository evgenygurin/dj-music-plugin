import { describe, it, expect } from 'vitest'
import { getCurrentSlot, slotFitScore, getAlpha, varietyPenalty, weightedRandomPick } from './scoring'
import type { SetTemplate, SlotDefinition, HistoryEntry, ScoredCandidate } from './types'

const SAMPLE_TEMPLATE: SetTemplate = {
  name: 'test_60',
  durationMin: 60,
  description: 'test',
  slots: [
    { position: 0.0, targetMood: 'warm_up', energyLufs: -18, bpmMin: 120, bpmMax: 124, durationMs: 15 * 60_000, flexibility: 0.5 },
    { position: 0.25, targetMood: 'driving', energyLufs: -12, bpmMin: 124, bpmMax: 128, durationMs: 15 * 60_000, flexibility: 0.5 },
    { position: 0.5, targetMood: 'peak_time', energyLufs: -8, bpmMin: 128, bpmMax: 132, durationMs: 15 * 60_000, flexibility: 0.3 },
    { position: 0.75, targetMood: 'minimal', energyLufs: -14, bpmMin: 126, bpmMax: 130, durationMs: 15 * 60_000, flexibility: 0.5 },
  ],
}

const PEAK_SLOT: SlotDefinition = {
  position: 0.5,
  targetMood: 'peak_time',
  energyLufs: -8,
  bpmMin: 128,
  bpmMax: 132,
  durationMs: 900000,
  flexibility: 0.3,
}

describe('getCurrentSlot', () => {
  it('returns first slot at elapsed 0', () => {
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 0, 3600)
    expect(result.index).toBe(0)
    expect(result.slot.targetMood).toBe('warm_up')
    expect(result.positionInSlot).toBeCloseTo(0, 2)
    expect(result.positionInSet).toBeCloseTo(0, 2)
  })

  it('returns middle slot at half elapsed', () => {
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 1800, 3600)
    expect(result.index).toBe(2)
    expect(result.slot.targetMood).toBe('peak_time')
    expect(result.positionInSet).toBeCloseTo(0.5, 2)
  })

  it('clamps to last slot beyond duration', () => {
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 7200, 3600)
    expect(result.index).toBe(3)
    expect(result.positionInSet).toBeCloseTo(1, 2)
  })

  it('computes positionInSlot correctly inside first slot', () => {
    // half-way through slot 0 (0.0..0.25 of 3600 = 0..900s), elapsed 450
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 450, 3600)
    expect(result.index).toBe(0)
    expect(result.positionInSlot).toBeCloseTo(0.5, 2)
  })
})

describe('slotFitScore', () => {
  it('scores perfect match near 1.0', () => {
    const score = slotFitScore(
      { bpm: 130, lufs: -8, mood: 'peak_time' },
      PEAK_SLOT,
    )
    expect(score).toBeGreaterThan(0.9)
  })

  it('penalises wrong mood', () => {
    const scoreWrong = slotFitScore(
      { bpm: 130, lufs: -8, mood: 'ambient_dub' },
      PEAK_SLOT,
    )
    const scoreRight = slotFitScore(
      { bpm: 130, lufs: -8, mood: 'peak_time' },
      PEAK_SLOT,
    )
    expect(scoreWrong).toBeLessThan(scoreRight)
  })

  it('penalises off-range BPM', () => {
    const score = slotFitScore(
      { bpm: 140, lufs: -8, mood: 'peak_time' },
      PEAK_SLOT,
    )
    expect(score).toBeLessThan(0.75)
  })

  it('neighbour mood gets partial credit', () => {
    // acid is neighbour of peak_time (index ±1 in SUBGENRE_ENERGY_ORDER)
    const score = slotFitScore(
      { bpm: 130, lufs: -8, mood: 'acid' },
      PEAK_SLOT,
    )
    expect(score).toBeGreaterThan(0.85)
    expect(score).toBeLessThan(1.0)
  })

  it('returns neutral 0.5-ish when all features missing', () => {
    const score = slotFitScore({ bpm: null, lufs: null, mood: null }, PEAK_SLOT)
    expect(score).toBeGreaterThan(0.3)
    expect(score).toBeLessThan(0.7)
  })
})

describe('getAlpha', () => {
  it('defaults to 0.6 for non-key slots mid-slot', () => {
    const alpha = getAlpha({ targetMood: 'driving' } as SlotDefinition, 0.4)
    expect(alpha).toBeCloseTo(0.6, 2)
  })
  it('drops to 0.4 for key slots', () => {
    const alpha = getAlpha({ targetMood: 'peak_time' } as SlotDefinition, 0.4)
    expect(alpha).toBeCloseTo(0.4, 2)
  })
  it('drops to 0.3 near slot ending', () => {
    const alpha = getAlpha({ targetMood: 'driving' } as SlotDefinition, 0.9)
    expect(alpha).toBeCloseTo(0.3, 2)
  })
  it('key slot + ending = 0.3', () => {
    const alpha = getAlpha({ targetMood: 'peak_time' } as SlotDefinition, 0.9)
    expect(alpha).toBeCloseTo(0.3, 2)
  })
})

describe('varietyPenalty', () => {
  const history: HistoryEntry[] = [
    { trackId: 1, artistIds: [10], mood: 'driving', lufs: null, playedAtSec: 0 },
    { trackId: 2, artistIds: [20], mood: 'driving', lufs: null, playedAtSec: 300 },
    { trackId: 3, artistIds: [30], mood: 'driving', lufs: null, playedAtSec: 600 },
  ]

  it('no penalty for unrelated candidate', () => {
    const p = varietyPenalty(
      { trackId: 99, artistIds: [77], mood: 'peak_time' },
      history,
    )
    expect(p).toBeCloseTo(1.0, 2)
  })
  it('penalises same artist as previous', () => {
    const p = varietyPenalty(
      { trackId: 99, artistIds: [30], mood: 'peak_time' },
      history,
    )
    expect(p).toBeCloseTo(0.7, 2)
  })
  it('penalises mood streak', () => {
    const p = varietyPenalty(
      { trackId: 99, artistIds: [77], mood: 'driving' },
      history,
    )
    expect(p).toBeCloseTo(0.8, 2)
  })
  it('penalises recently played track', () => {
    const p = varietyPenalty(
      { trackId: 2, artistIds: [77], mood: 'peak_time' },
      history,
    )
    expect(p).toBeCloseTo(0.5, 2)
  })
  it('compounds multiple penalties', () => {
    const p = varietyPenalty(
      { trackId: 3, artistIds: [30], mood: 'driving' },
      history,
    )
    // recent (0.5) * same artist (0.7) * mood streak (0.8) = 0.28
    expect(p).toBeCloseTo(0.28, 2)
  })
})

describe('weightedRandomPick', () => {
  it('returns distribution proportional to combinedScore', () => {
    const candidates: ScoredCandidate[] = [
      { combinedScore: 0.9 } as ScoredCandidate,
      { combinedScore: 0.1 } as ScoredCandidate,
    ]
    let firstHits = 0
    const runs = 2000
    const rng = () => Math.random()
    for (let i = 0; i < runs; i++) {
      if (weightedRandomPick(candidates, rng) === candidates[0]) firstHits++
    }
    // Expect ~90% hits on the heavy candidate, allow 5% slack.
    expect(firstHits / runs).toBeGreaterThan(0.85)
    expect(firstHits / runs).toBeLessThan(0.95)
  })

  it('returns first when pool length is 1', () => {
    const candidates: ScoredCandidate[] = [{ combinedScore: 0.5 } as ScoredCandidate]
    expect(weightedRandomPick(candidates)).toBe(candidates[0])
  })
})
