'use server'

import { revalidateTag } from 'next/cache'
import { callTool, type ToolCallResult } from '@/lib/mcp-client'

/**
 * Sync a local playlist with its YM counterpart.
 *
 * v1.0 mapping: `sync_playlist` → `playlist_sync(playlist_id, direction,
 * source, dry_run)`. `playlist_sync` lives in the `sync` namespace which
 * starts locked — caller may need `unlock_namespace(namespace="sync")` first.
 */
export async function syncPlaylist(
  playlistId: number,
  direction?: 'push' | 'pull'
): Promise<ToolCallResult> {
  const result = await callTool('playlist_sync', {
    playlist_id: playlistId,
    direction: direction ?? 'diff',
    source: 'yandex',
    dry_run: false,
  })
  revalidateTag('playlists', 'default')
  return result
}

/**
 * Distribute tracks to subgenre playlists (15 subgenres).
 *
 * v1.0 status: NOT YET MIGRATED. The legacy `distribute_to_subgenres`
 * compound tool was removed; the v1 architecture expects this to be a
 * workflow recipe (compose `entity_aggregate` for mood histogram +
 * `provider_write(playlist, add_tracks)` per subgenre playlist) — see
 * blueprint §11. Until that workflow is wired, this action returns an
 * explicit error so consuming UI surfaces a clear message instead of
 * crashing.
 *
 * TODO(v1.0-actions-rewrite): build subgenre distribution workflow —
 * either as a server action that loops `entity_list(track_features,
 * filters={mood: <subgenre>})` + `playlist_sync(direction="push")`, or
 * resurrect the legacy bulk tool.
 */
export async function distributeToSubgenres(
  _sourcePlaylistId?: number,
  _dryRun: boolean = false
): Promise<ToolCallResult> {
  return {
    tool_name: 'distribute_to_subgenres',
    content: [
      {
        type: 'text',
        text:
          'distribute_to_subgenres is not available in v1.0 — see ' +
          'panel/actions/sync-actions.ts TODO(v1.0-actions-rewrite). ' +
          'Workflow needs to be composed from entity_list + playlist_sync.',
      },
    ],
    structured_content: null,
    is_error: true,
  }
}

/**
 * Push a DJ set as a YM playlist.
 *
 * v1.0 mapping: legacy `push_set_to_ym(set_id, ym_playlist_name)` is
 * decomposed into:
 *   1. `entity_get(entity="set", id)` — read the set, find its
 *      `linked_ym_playlist_id` (if persisted on the local Set).
 *   2. `playlist_sync(playlist_id=<linked playlist id>, direction="push")`.
 *
 * The DjSet model in v1 has `source_playlist_id` + `template_name` but
 * NOT a dedicated `linked_ym_playlist_id` column — the legacy field is
 * gone. Until the cutover wires `linked_ym_playlist_id` (or we adopt a
 * provider playlist resolver), this action surfaces an explicit error.
 *
 * TODO(v1.0-actions-rewrite): either persist the linked YM playlist id
 * back onto DjSet, or do `provider_write(provider="yandex", entity=
 * "playlist", operation="create", params={title})` followed by
 * `add_tracks` here.
 */
export async function pushSetToYm(
  _setId: number,
  _playlistName?: string
): Promise<ToolCallResult> {
  return {
    tool_name: 'push_set_to_ym',
    content: [
      {
        type: 'text',
        text:
          'push_set_to_ym is not yet wired in v1.0 — see ' +
          'panel/actions/sync-actions.ts TODO(v1.0-actions-rewrite). ' +
          'DjSet no longer carries linked_ym_playlist_id; needs ' +
          'provider_write(playlist, create) + (playlist_sync push) chain.',
      },
    ],
    structured_content: null,
    is_error: true,
  }
}
