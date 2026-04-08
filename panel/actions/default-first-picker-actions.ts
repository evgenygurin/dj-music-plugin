'use server'

import { callTool } from '@/lib/mcp-client'
import type { ScoredCandidate } from '@/lib/set-narrative/types'

interface PickFirstTrackOptions {
  templateName?: string
  playlistId?: number
}

export async function pickDefaultFirstTrack(
  options: PickFirstTrackOptions,
): Promise<ScoredCandidate | null> {
  const { templateName, playlistId } = options

  // Get all candidates for the opening slot (no prior history, no transition scoring)
  // Use filter_tracks with mood + energy range suited to warm_up (default first slot)
  const response = await callTool('filter_tracks', {
    has_features: true,
    limit: 20,
    sort_by: 'energy_desc', // Start with moderate energy
  })

  if (response.is_error) {
    throw new Error(`MCP error: ${response.content?.[0]?.text ?? 'unknown error'}`)
  }

  const candidates = response.structured_content as any

  if (!candidates || candidates.length === 0) {
    return null
  }

  // Simple heuristic: pick the first track (usually good opener)
  const firstTrack = candidates[0]

  return {
    trackId: firstTrack.id,
    title: firstTrack.title,
    artists: firstTrack.artists?.join(', ') || 'Unknown',
    bpm: firstTrack.bpm,
    camelot: firstTrack.camelot,
    mood: firstTrack.mood,
    lufs: firstTrack.lufs,
    transitionScore: 0.5, // N/A for first track
    slotFit: 0.75, // Placeholder
    varietyPenalty: 1.0,
    combinedScore: 0.75,
    rationale: 'Opening track - energy-based selection',
  }
}
