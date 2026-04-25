'use server'

import { revalidateTag } from 'next/cache'
import { callTool } from '@/lib/mcp-client'

/**
 * Audit playlist quality (techno criteria — BPM range, LUFS, energy, etc.).
 *
 * v1.0 mapping: `audit_playlist` → `read_resource(uri="local://playlists/
 * {id}/audit")`. The synthetic `read_resource` tool fetches the resource
 * and returns its JSON payload as `structured_content`.
 */
export async function auditPlaylist(playlistId: number) {
  return callTool('read_resource', {
    uri: `local://playlists/${playlistId}/audit`,
  })
}

/**
 * Pull a playlist from Yandex Music into the local DB.
 *
 * v1.0 mapping: `sync_playlist` → `playlist_sync(playlist_id, direction,
 * source, dry_run)`. `playlist_sync` lives in the `sync` namespace which
 * starts locked — the caller may need `unlock_namespace(namespace="sync",
 * action="unlock")` first.
 */
export async function syncPlaylist(playlistId: number) {
  const result = await callTool('playlist_sync', {
    playlist_id: playlistId,
    direction: 'pull',
    source: 'yandex',
    dry_run: false,
  })
  revalidateTag('playlists', 'default')
  return result
}
