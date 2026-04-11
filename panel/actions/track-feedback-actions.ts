'use server'

import { callTool } from '@/lib/mcp-client'

export async function likeTrack(trackId: number): Promise<boolean> {
  const result = await callTool('like_track', { track_id: trackId })
  return !result.is_error
}

export async function banTrack(trackId: number): Promise<boolean> {
  const result = await callTool('ban_track', { track_id: trackId })
  return !result.is_error
}

export async function rateTrack(trackId: number, rating: number, notes?: string): Promise<boolean> {
  const result = await callTool('rate_track', { track_id: trackId, rating, notes: notes ?? null })
  return !result.is_error
}
