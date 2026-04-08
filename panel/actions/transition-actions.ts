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

/** 6 transition styles surfaced from the backend `recommend_style` decision. */
export type TransitionStyle =
  | 'cut'
  | 'bass_swap_short'
  | 'bass_swap_long'
  | 'long_blend'
  | 'echo_out'
  | 'filter_sweep'

/** Pair-score response with the recommended style + bars for the audio engine. */
export interface PairScoreResult {
  fromTrackId: number
  toTrackId: number
  overall: number | null
  hardReject: boolean
  rejectReason: string | null
  recommendedStyle: TransitionStyle | null
  recommendedBars: number | null
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

/**
 * Score a single (from, to) pair and return the recommended transition
 * style + bar count. Used by the audio engine to pick crossfade length
 * dynamically instead of relying on the fixed `crossfadeBars` slider.
 *
 * Returns null when scoring is unavailable (missing features, MCP
 * error). Callers should fall back to their default crossfade.
 */
export async function getTransitionStyle(
  fromTrackId: number,
  toTrackId: number,
): Promise<PairScoreResult | null> {
  try {
    const result = await callTool('score_transitions', {
      mode: 'pair',
      from_track_id: fromTrackId,
      to_track_id: toTrackId,
    })
    const sc = result?.structured_content as
      | {
          from_track_id?: number
          to_track_id?: number
          overall_quality?: number | null
          hard_reject?: boolean
          reject_reason?: string | null
          recommended_style?: string | null
          recommended_bars?: number | null
        }
      | undefined
    if (!sc || sc.overall_quality == null) return null
    return {
      fromTrackId: sc.from_track_id ?? fromTrackId,
      toTrackId: sc.to_track_id ?? toTrackId,
      overall: sc.overall_quality ?? null,
      hardReject: sc.hard_reject ?? false,
      rejectReason: sc.reject_reason ?? null,
      recommendedStyle: (sc.recommended_style ?? null) as TransitionStyle | null,
      recommendedBars: sc.recommended_bars ?? null,
    }
  } catch {
    return null
  }
}
