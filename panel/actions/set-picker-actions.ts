'use server'

import { callTool } from '@/lib/mcp-client'
import { slotFitScore, varietyPenalty, getAlpha, weightedRandomPick } from '@/lib/set-narrative/scoring'
import { PICKER_TOP_N, BACKEND_CANDIDATES_TOP_N } from '@/lib/set-narrative/constants'
import type { SetTemplate, ScoredCandidate, HistoryEntry, CurrentSlot } from '@/lib/set-narrative/types'

interface PickNextTrackOptions {
  currentSlot: CurrentSlot
  template: SetTemplate
  history: HistoryEntry[]
  varietyTier: 0 | 1 | 2
  playlistId?: number
}

export async function pickNextSetTrack(
  options: PickNextTrackOptions,
): Promise<ScoredCandidate | null> {
  const { currentSlot, template, history, varietyTier, playlistId } = options

  // Call backend tool to get candidates (top 30 by transition score + basic fit)
  const response = await callTool('score_transitions', {
    mode: 'track_candidates',
    track_id: history.length > 0 ? history[history.length - 1].trackId : null,
    top_n: BACKEND_CANDIDATES_TOP_N,
    playlist_id: playlistId,
  })

  if (response.is_error) {
    throw new Error(`MCP error: ${response.content?.[0]?.text ?? 'unknown error'}`)
  }

  const candidates = response.structured_content as any

  if (!candidates || !Array.isArray(candidates)) {
    return null
  }

  // Map backend response to typed ScoredCandidate with slot fit + variety penalty
  const scored: ScoredCandidate[] = candidates.map((c: any) => {
    const slotFit = slotFitScore(
      {
        bpm: c.bpm,
        lufs: c.lufs,
        mood: c.mood,
      },
      currentSlot.slot,
    )

    const variety = varietyPenalty({ trackId: c.id, artistIds: c.artist_ids || [], mood: c.mood }, history)

    // Alpha: blending weight between transition and slot fit
    const alpha = getAlpha(currentSlot.slot, currentSlot.positionInSlot)

    // Composite score: weighted average of transition (via alpha) and slot fit
    const combinedScore = alpha * (c.transition_score || 0.5) + (1 - alpha) * slotFit * variety

    return {
      trackId: c.id,
      title: c.title,
      artists: c.artists?.join(', ') || 'Unknown',
      bpm: c.bpm,
      camelot: c.camelot,
      mood: c.mood,
      lufs: c.lufs,
      transitionScore: c.transition_score || 0.5,
      slotFit,
      varietyPenalty: variety,
      combinedScore,
      rationale: `Transition ${(c.transition_score * 100).toFixed(0)}% + Slot fit ${(slotFit * 100).toFixed(0)}% = ${(combinedScore * 100).toFixed(0)}%`,
    }
  })

  // Sort by combined score and take top N
  const topN = scored.sort((a, b) => b.combinedScore - a.combinedScore).slice(0, PICKER_TOP_N)

  if (topN.length === 0) return null

  // Weighted random pick from top N
  return weightedRandomPick(topN)
}
