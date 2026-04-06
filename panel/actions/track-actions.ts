'use server'

import { callTool } from '@/lib/mcp-client'
import { revalidatePath } from 'next/cache'

export async function analyzeTrack(trackId: number) {
  const result = await callTool('analyze_track', { track_id: trackId, level: 3 })
  revalidatePath(`/library/${trackId}`)
  return result
}

export async function classifyTrackMood(trackId: number) {
  const result = await callTool('classify_mood', { track_ids: [trackId] })
  revalidatePath(`/library/${trackId}`)
  return result
}

export async function archiveTrack(trackId: number) {
  const result = await callTool('manage_tracks', { action: 'archive', data: { id: trackId } })
  revalidatePath('/library')
  return result
}
