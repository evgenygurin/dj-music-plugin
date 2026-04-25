'use server'

import { revalidateTag } from 'next/cache'
import { callTool, type ToolCallResult } from '@/lib/mcp-client'

/**
 * Classify mood/subgenre for the given tracks.
 *
 * v1.0 mapping: `classify_mood` → `entity_create(entity="track_features",
 * data={track_ids, level: 2})`. The track_features_analyze handler runs the
 * tiered audio pipeline at L2, which writes the mood classification.
 */
export async function classifyMood(trackIds: number[]): Promise<ToolCallResult> {
  const result = await callTool('entity_create', {
    entity: 'track_features',
    data: { track_ids: trackIds, level: 2 },
  })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}

/**
 * Run the full audio analysis pipeline for a single track at L3 (scoring tier).
 *
 * v1.0 mapping: `analyze_track` → `entity_create(entity="track_features",
 * data={track_ids: [trackId], level: 3})`.
 */
export async function analyzeTrack(trackId: number): Promise<ToolCallResult> {
  const result = await callTool('entity_create', {
    entity: 'track_features',
    data: { track_ids: [trackId], level: 3 },
  })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}
