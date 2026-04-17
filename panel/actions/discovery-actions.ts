'use server'

import { callTool, type ToolCallResult } from '@/lib/mcp-client'
import { revalidateTag } from 'next/cache'

export async function searchPlatform(query: string, type: string = 'tracks'): Promise<ToolCallResult> {
  return callTool('search_platform', { query, type, limit: 20 })
}

export async function importTracks(
  trackRefs: string[],
  playlistId?: number
): Promise<ToolCallResult> {
  const result = await callTool('import_tracks', {
    track_refs: trackRefs,
    playlist_id: playlistId,
  })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}
