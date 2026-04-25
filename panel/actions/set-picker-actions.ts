'use server'

import { createClient } from '@/lib/supabase/server'
import {
  BACKEND_CANDIDATES_TOP_N,
  PICKER_TOP_N,
} from '@/lib/set-narrative/constants'
import {
  getAlpha,
  getCurrentSlot,
  slotFitScore,
  varietyPenalty,
} from '@/lib/set-narrative/scoring'
import type {
  HistoryEntry,
  ScoredCandidate,
  SetTemplate,
} from '@/lib/set-narrative/types'
import { scoreTransitionCandidates } from '@/actions/transition-actions'

export interface PickerInput {
  currentTrackId: number
  template: SetTemplate
  elapsedSec: number
  totalDurationSec: number
  history: HistoryEntry[]
  varietyTier: 0 | 1 | 2
}

interface CandidateFeatures {
  title: string
  bpm: number | null
  lufs: number | null
  mood: string | null
  camelot: string | null
  artistIds: number[]
}

export async function pickNextSetTrack(
  input: PickerInput,
): Promise<ScoredCandidate[]> {
  // 1. Resolve current slot + dynamic alpha from template + elapsed
  const current = getCurrentSlot(
    input.template,
    input.elapsedSec,
    input.totalDurationSec,
  )
  const alpha = getAlpha(current.slot, current.positionInSlot)

  // 2. Ask backend TransitionScorer for top-N candidates from current track.
  //
  // v1.0 mapping: legacy `score_transitions(mode="track_candidates")` was
  // a server-side helper. We now compose the same thing client-side via
  // `scoreTransitionCandidates` (transition-actions.ts), which prunes by
  // BPM and runs `transition_score_pool`.
  const rawList = await scoreTransitionCandidates(
    input.currentTrackId,
    BACKEND_CANDIDATES_TOP_N,
  )
  if (!rawList || rawList.length === 0) return []

  // 3. Fetch features + artist ids for candidate tracks in one query
  const trackIds = rawList.map((c) => c.to_track_id)
  const supabase = await createClient()
  const { data: featureRows } = await supabase
    .from('tracks')
    .select(
      `
      id,
      title,
      track_audio_features_computed!inner(bpm, mood, integrated_lufs, key_code),
      track_artists(artist_id)
    `,
    )
    .in('id', trackIds)

  const featureMap = new Map<number, CandidateFeatures>()
  for (const row of featureRows ?? []) {
    const f = Array.isArray(row.track_audio_features_computed)
      ? row.track_audio_features_computed[0]
      : row.track_audio_features_computed
    const artistRefs = Array.isArray(row.track_artists) ? row.track_artists : []
    featureMap.set(row.id, {
      title: row.title,
      bpm: f?.bpm ?? null,
      lufs: f?.integrated_lufs ?? null,
      mood: f?.mood ?? null,
      camelot: null, // resolved at UI layer via camelotNotation if needed
      artistIds: artistRefs.map((a: { artist_id: number }) => a.artist_id),
    })
  }

  // 4. Apply hard rejects per variety tier
  const recentIds = new Set(input.history.slice(-50).map((h) => h.trackId))
  const previous = input.history[input.history.length - 1]
  const filtered = rawList.filter((c) => {
    if (!featureMap.has(c.to_track_id)) return false
    if (c.overall_quality <= 0) return false
    if (recentIds.has(c.to_track_id)) return false
    if (input.varietyTier === 0 && previous) {
      const cand = featureMap.get(c.to_track_id)!
      if (cand.artistIds.some((a) => previous.artistIds.includes(a))) return false
    }
    return true
  })

  // 5. Score each candidate: combined = α·transition + (1-α)·slotFit, × variety
  const scoredCandidates: ScoredCandidate[] = filtered.map((c) => {
    const feat = featureMap.get(c.to_track_id)!
    const slotFit = slotFitScore(
      { bpm: feat.bpm, lufs: feat.lufs, mood: feat.mood },
      current.slot,
    )
    const variety = varietyPenalty(
      { id: c.to_track_id, artistIds: feat.artistIds, mood: feat.mood },
      input.history,
    )
    const combinedScore =
      (alpha * c.overall_quality + (1 - alpha) * slotFit) * variety

    return {
      trackId: c.to_track_id,
      title: feat.title,
      artists: '',
      bpm: feat.bpm,
      camelot: feat.camelot,
      mood: feat.mood,
      lufs: feat.lufs,
      transitionScore: c.overall_quality,
      slotFit,
      varietyPenalty: variety,
      combinedScore,
      rationale: `slot ${slotFit.toFixed(2)} · transition ${c.overall_quality.toFixed(2)} · variety ×${variety.toFixed(2)}`,
    }
  })

  scoredCandidates.sort((a, b) => b.combinedScore - a.combinedScore)
  return scoredCandidates.slice(0, PICKER_TOP_N)
}
