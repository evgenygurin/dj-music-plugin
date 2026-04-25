'use server'

import { callTool } from '@/lib/mcp-client'

/**
 * Record positive/negative feedback for a track.
 *
 * v1.0 mapping: legacy direct write to `dj_set_feedback` (table DROPPED in
 * Phase 7 cutover, blueprint §13.2 — was 0 rows, feature unimplemented).
 *
 * Now persists to `track_feedback` via `entity_create(entity="track_feedback",
 * data={track_id, kind})`. The TrackFeedback model accepts kind ∈ {like, ban,
 * rate}. We map "like"→like, "ban"→ban; the rating column is not used here.
 */
export async function recordTrackFeedback(
  trackId: number,
  rating: 'like' | 'ban',
): Promise<{ success: boolean }> {
  const result = await callTool('entity_create', {
    entity: 'track_feedback',
    data: {
      track_id: trackId,
      kind: rating,
      notes: rating,
    },
  })
  return { success: !result.is_error }
}
