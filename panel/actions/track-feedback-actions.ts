'use server'

import { callTool } from '@/lib/mcp-client'

/**
 * Record a "like" for a track.
 *
 * v1.0 mapping: `like_track` → `entity_create(entity="track_feedback",
 * data={track_id, kind: "like"})`.
 */
export async function likeTrack(trackId: number): Promise<boolean> {
  const result = await callTool('entity_create', {
    entity: 'track_feedback',
    data: { track_id: trackId, kind: 'like' },
  })
  return !result.is_error
}

/**
 * Record a "ban" for a track.
 *
 * v1.0 mapping: `ban_track` → `entity_create(entity="track_feedback",
 * data={track_id, kind: "ban"})`.
 */
export async function banTrack(trackId: number): Promise<boolean> {
  const result = await callTool('entity_create', {
    entity: 'track_feedback',
    data: { track_id: trackId, kind: 'ban' },
  })
  return !result.is_error
}

/**
 * Rate a track (1-5).
 *
 * v1.0 mapping: `rate_track` → `entity_create(entity="track_feedback",
 * data={track_id, kind: "rate", rating, notes?})`. Note: TrackFeedbackCreate
 * enforces rating 1..5 — out-of-range values will fail validation.
 */
export async function rateTrack(trackId: number, rating: number, notes?: string): Promise<boolean> {
  const result = await callTool('entity_create', {
    entity: 'track_feedback',
    data: {
      track_id: trackId,
      kind: 'rate',
      rating,
      notes: notes ?? null,
    },
  })
  return !result.is_error
}
