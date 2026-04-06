'use server'

import { mcpCall } from '@/lib/mcp-client'
import { revalidateTag } from 'next/cache'

export async function ymSearch(query: string, type: string = 'tracks') {
  return await mcpCall('ym_search', { query, type, limit: 20 })
}

export async function importTracks(trackRefs: string[], playlistId?: number) {
  const result = await mcpCall('import_tracks', { track_refs: trackRefs, playlist_id: playlistId })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}
