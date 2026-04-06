'use server'

import { revalidateTag } from 'next/cache'
import { callTool } from '@/lib/mcp-client'

export async function auditPlaylist(playlistId: number) {
  return callTool('audit_playlist', { playlist_id: playlistId })
}

export async function syncPlaylist(playlistId: number) {
  const result = await callTool('sync_playlist', {
    playlist_id: playlistId,
    direction: 'pull',
    dry_run: false,
  })
  revalidateTag('playlists', 'default')
  return result
}
