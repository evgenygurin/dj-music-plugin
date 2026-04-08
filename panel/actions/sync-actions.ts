'use server'

import { revalidateTag } from 'next/cache'
import { callTool, type ToolCallResult } from '@/lib/mcp-client'

export async function syncPlaylist(
  playlistId: number,
  direction?: 'push' | 'pull'
): Promise<ToolCallResult> {
  const result = await callTool('sync_playlist', { playlist_id: playlistId, direction })
  revalidateTag('playlists', 'default')
  return result
}

export async function distributeToSubgenres(
  sourcePlaylistId?: number,
  dryRun: boolean = false
): Promise<ToolCallResult> {
  const result = await callTool('distribute_to_subgenres', {
    source_playlist_id: sourcePlaylistId,
    dry_run: dryRun,
  })
  revalidateTag('playlists', 'default')
  revalidateTag('tracks', 'default')
  return result
}

export async function pushSetToYm(
  setId: number,
  playlistName?: string
): Promise<ToolCallResult> {
  const result = await callTool('push_set_to_ym', {
    set_id: setId,
    ym_playlist_name: playlistName,
  })
  revalidateTag('sets', 'default')
  return result
}
