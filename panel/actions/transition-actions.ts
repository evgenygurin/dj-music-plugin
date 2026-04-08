'use server'

import { callTool } from '@/lib/mcp-client'

export interface TransitionCandidate {
  to_track_id: number
  overall_quality: number
  bpm_distance: number
  energy_step: number
  groove_similarity: number
  key_distance_weighted: number
}

/**
 * Asks the backend's TransitionScorer for the best matching next tracks.
 * Returns null when scoring is unavailable (track lacks audio features) so
 * the caller can fall back to the lightweight client-side heuristic.
 */
export async function scoreTransitionCandidates(
  fromTrackId: number,
  topN: number = 20,
): Promise<TransitionCandidate[] | null> {
  try {
    const result = await callTool('score_transitions', {
      mode: 'track_candidates',
      track_id: fromTrackId,
      top_n: topN,
    })
    const sc = result?.structured_content as
      | { candidates?: TransitionCandidate[]; transitions?: TransitionCandidate[] }
      | undefined
    const list = sc?.candidates ?? sc?.transitions ?? null
    if (!list || !Array.isArray(list)) return null
    return list as TransitionCandidate[]
  } catch {
    return null
  }
}
