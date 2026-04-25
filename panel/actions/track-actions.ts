'use server'

import { callTool } from '@/lib/mcp-client'
import { revalidatePath } from 'next/cache'

/**
 * Run audio analysis (L3 — scoring tier) on a single track.
 *
 * v1.0 mapping: `analyze_track` → `entity_create(entity="track_features",
 * data={track_ids: [trackId], level: 3})`.
 */
export async function analyzeTrack(trackId: number) {
  const result = await callTool('entity_create', {
    entity: 'track_features',
    data: { track_ids: [trackId], level: 3 },
  })
  revalidatePath(`/library/${trackId}`)
  return result
}

/**
 * Classify mood/subgenre for a single track (L2 — mood classifier).
 *
 * v1.0 mapping: `classify_mood` → `entity_create(entity="track_features",
 * data={track_ids: [trackId], level: 2})`.
 */
export async function classifyTrackMood(trackId: number) {
  const result = await callTool('entity_create', {
    entity: 'track_features',
    data: { track_ids: [trackId], level: 2 },
  })
  revalidatePath(`/library/${trackId}`)
  return result
}

/**
 * Archive a track (status = 1).
 *
 * v1.0 mapping: `manage_tracks(action="archive")` → `entity_update(
 * entity="track", id, data={status: 1})`. Track.status: 0 = active,
 * 1 = archived (per app/shared/constants.py).
 *
 * `entity_update` lives in the `crud:destructive` namespace which starts
 * locked — caller may need to first invoke `unlock_namespace(
 * namespace="crud:destructive", action="unlock")`.
 */
export async function archiveTrack(trackId: number) {
  const result = await callTool('entity_update', {
    entity: 'track',
    id: trackId,
    data: { status: 1 },
  })
  revalidatePath('/library')
  return result
}
