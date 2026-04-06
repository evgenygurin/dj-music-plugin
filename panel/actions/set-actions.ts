'use server'

import { revalidateTag } from 'next/cache'
import { mcpCall } from '@/lib/mcp-client'

export async function buildSet(
  playlistId: number,
  name: string,
  template?: string,
  algorithm: 'greedy' | 'ga' = 'ga'
) {
  const result = await mcpCall('build_set', {
    playlist_id: playlistId,
    name,
    template: template ?? undefined,
    algorithm,
  })
  revalidateTag('sets', 'default')
  return result
}

export async function rebuildSet(
  setId: number,
  options: {
    pin?: number[]
    unpin?: number[]
    exclude?: number[]
    algorithm?: 'greedy' | 'ga'
    version_label?: string
  } = {}
) {
  const result = await mcpCall('rebuild_set', { set_id: setId, ...options })
  revalidateTag('sets', 'default')
  return result
}

export async function deliverSet(
  setId: number,
  options: { version?: number; copy_files?: boolean; sync_to_ym?: boolean; dry_run?: boolean } = {}
) {
  const result = await mcpCall('deliver_set', { set_id: setId, ...options })
  revalidateTag('sets', 'default')
  return result
}

export async function scoreTransitions(setId: number) {
  const result = await mcpCall('score_transitions', { mode: 'set', set_id: setId })
  revalidateTag('sets', 'default')
  return result
}
