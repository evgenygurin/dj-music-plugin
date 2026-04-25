'use server'

import { callTool, type ToolCallResult } from '@/lib/mcp-client'
import { revalidateTag } from 'next/cache'

/**
 * Search Yandex Music catalog.
 *
 * v1.0 mapping: `ym_search` → `provider_search(provider="yandex", query, type, limit)`.
 *
 * The new tool returns `{provider, query, type, total, items}`. Consumers
 * (panel/app/discover/ym-search.tsx) expect either the old YM raw shape
 * (`structured_content.result.tracks.results`) or `structured_content.tracks`.
 * We rewrap to keep the consumer working without touching it.
 */
export async function ymSearch(query: string, type: string = 'tracks'): Promise<ToolCallResult> {
  const raw = await callTool('provider_search', {
    provider: 'yandex',
    query,
    type,
    limit: 20,
  })
  if (raw.is_error || !raw.structured_content) return raw
  const sc = raw.structured_content as { items?: unknown[] }
  const items = Array.isArray(sc.items) ? sc.items : []
  return {
    ...raw,
    structured_content: {
      ...raw.structured_content,
      tracks: items,
      result: { [type]: { results: items } },
    },
  }
}

/**
 * Import tracks from Yandex Music into the local DB.
 *
 * v1.0 mapping: `import_tracks` → `entity_create(entity="track",
 * data={source: "yandex", external_ids, playlist_id?})`. The track_import
 * handler resolves provider metadata + persists Track + YandexMetadata +
 * external id, idempotent by provider id.
 */
export async function importTracks(
  trackRefs: string[],
  playlistId?: number
): Promise<ToolCallResult> {
  const result = await callTool('entity_create', {
    entity: 'track',
    data: {
      source: 'yandex',
      external_ids: trackRefs,
      playlist_id: playlistId ?? null,
    },
  })
  revalidateTag('tracks', 'default')
  revalidateTag('library-stats', 'default')
  return result
}
