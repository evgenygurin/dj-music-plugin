'use server'

import { revalidateTag } from 'next/cache'
import { callTool, type ToolCallResult } from '@/lib/mcp-client'

export async function classifyMood(trackIds: number[]): Promise<ToolCallResult> {
  const result = await callTool('classify_mood', { track_ids: trackIds })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}

export async function analyzeTrack(trackId: number): Promise<ToolCallResult> {
  const result = await callTool('analyze_track', { track_id: trackId })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}
