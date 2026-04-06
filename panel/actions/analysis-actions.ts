'use server'

import { revalidateTag } from 'next/cache'
import { mcpCall } from '@/lib/mcp-client'

export async function classifyMood(trackIds: number[]) {
  const result = await mcpCall('classify_mood', { track_ids: trackIds })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}

export async function analyzeTrack(trackId: number) {
  const result = await mcpCall('analyze_track', { track_id: trackId })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}
